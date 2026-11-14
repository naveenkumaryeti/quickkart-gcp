"""Pub/Sub consumer: validate -> idempotent Firestore transaction -> ACK only after success. Failures are NACKed (retry with backoff);
after max_delivery_attempts Pub/Sub moves the message to the dead-letter topic, and drain_dead_letters() marks the TableQueue row Failed."""
import logging

import config
from models import order as om
from models.product import now
from services import audit_service as audit
from services import firestore_service as fs
from services import order_service as osv
from services import pubsub_service as ps
from services.errors import AppError

log = logging.getLogger(__name__)


def process_event(body):
    for k in ("event_id", "order_id", "product_id", "customer_id", "quantity"):
        if k not in body:
            raise AppError(f"invalid event: missing {k}")
    oid = body["order_id"]

    def t(tx):
        q, o = tx.get("tableQueue", oid), tx.get("orders", oid)
        if not o or not q:
            raise AppError("order not found for event")
        if q["queueStatus"] == "Processed":
            return "duplicate (already processed)"
        if o["customerId"] != body["customer_id"] or o["productId"] != body["product_id"]:
            raise AppError("event does not match the stored order")
        if o["orderStatus"] == "Confirmed":
            o.update(orderStatus="Processing", deliveryStatus="Processing", updatedAt=now(), version=o["version"] + 1, gcsSyncPending=True)
            o["history"].append({"status": "Processing", "at": now(), "by": "pubsub-consumer"})
            tx.set("orders", oid, o)
            tx.set("tableService", oid, om.service_row(o))
        q.update(queueStatus="Processed", processedAt=now(), lastError="", lastEventId=body["event_id"])
        tx.set("tableQueue", oid, q)
        return "processed"
    res = fs.transaction(t)
    if res == "processed":
        audit.log_event("queue_message_processed", oid, "pubsub-consumer")
        osv.try_sync_order(oid)
    return res


def drain_dead_letters(n=10):
    out = []
    for m in ps.pull(config.DLQ_SUBSCRIPTION, n):
        oid = m["data"].get("order_id")
        if oid and fs.get("tableQueue", oid):
            fs.update("tableQueue", oid, {"queueStatus": "Failed", "lastError": f"dead-lettered after {config.MAX_DELIVERY_ATTEMPTS} delivery attempts"})
        audit.log_event("queue_message_dead_lettered", oid or "", "pubsub-consumer", "failure")
        ps.ack(config.DLQ_SUBSCRIPTION, [m["ack_id"]])
        out.append({"order_id": oid, "result": "moved to dead-letter topic -> TableQueue Failed"})
    return out


def process_batch(max_messages=10, fail=False):
    """fail=True is a TEACHING switch (simulated failure) so students can watch retries and the dead-letter flow."""
    out = []
    for m in ps.pull(config.SUBSCRIPTION, max_messages):
        body = m["data"]
        try:
            if fail:
                raise RuntimeError("simulated failure (teaching demo)")
            res = process_event(body)
            ps.ack(config.SUBSCRIPTION, [m["ack_id"]])
            out.append({"order_id": body["order_id"], "delivery_attempt": m["attempt"], "result": res})
        except Exception as e:
            log.warning("processing %s failed (attempt %s): %s", body.get("order_id"), m["attempt"], e)
            oid = body.get("order_id")
            try:
                if oid and fs.get("tableQueue", oid):
                    fs.update("tableQueue", oid, {"deliveryAttempts": m["attempt"], "lastError": str(e)[:200]})
            except Exception:  # noqa
                pass
            ps.nack(config.SUBSCRIPTION, [m["ack_id"]])
            out.append({"order_id": oid, "delivery_attempt": m["attempt"], "result": f"failed (NACK, Pub/Sub will redeliver): {e}"})
    out += drain_dead_letters(max_messages)
    return out
