"""Orders. Firestore transaction = order + stock decrement + tableService + tableQueue + outbox event (all-or-nothing INSIDE Firestore).
Pub/Sub and Cloud Storage are separate systems, so: outbox + retry for Pub/Sub, sync flag + reconcile for Cloud Storage, idempotent consumer."""
import hashlib
import logging

import config
from models import order as om
from models.product import now
from services import audit_service as audit
from services import firestore_service as fs
from services import pubsub_service as ps
from services import storage_service as st
from services.errors import AppError

log = logging.getLogger(__name__)
FLOW = ["Confirmed", "Processing", "Out for Delivery", "Delivered"]
DELIVERY = {"Confirmed": "Pending", "Processing": "Processing", "Out for Delivery": "Out for Delivery", "Delivered": "Delivered"}


def order_id_for(customer_id, key):
    return "ORD-" + hashlib.sha256(f"{customer_id}:{key}".encode()).hexdigest()[:10].upper()


def order_json(o):
    from models.product import snake
    return snake({k: v for k, v in o.items() if k not in ("gcsSyncPending",)})


def create_order(customer, data, key):
    pid, address = str(data.get("product_id", "")), str(data.get("delivery_address", "")).strip()
    try:
        qty = int(data.get("quantity"))
    except (TypeError, ValueError):
        raise AppError("quantity must be a whole number")
    if data.get("payment_method", "COD") != "COD":
        raise AppError("only Cash on Delivery (COD) is supported")
    if len(address) < 10:
        raise AppError("a delivery address (at least 10 characters) is required")
    if qty < 1:
        raise AppError("quantity must be at least 1")
    oid = order_id_for(customer["uid"], key)

    def t(tx):
        ex = tx.get("orders", oid)                       # idempotency: same key -> same order, nothing else changes
        if ex:
            return ex, False
        p = tx.get("products", pid) if pid else None
        if not p:
            raise AppError("invalid product id")
        if p["publicationStatus"] != "Published":
            raise AppError("this product is not available for purchase", 409, "NOT_AVAILABLE")
        if qty > p["availableQuantity"]:
            raise AppError(f"Only {p['availableQuantity']} unit(s) in stock", 409, "INSUFFICIENT_STOCK")
        o = om.build(oid, customer, p, qty, address)     # price / total / seller from Firestore, never from the browser
        p["availableQuantity"] -= qty
        if p["availableQuantity"] == 0:
            p["publicationStatus"] = "Out of Stock"
        p.update(version=p["version"] + 1, updatedAt=now(), gcsSyncPending=True)
        tx.set("products", pid, p)
        tx.set("orders", oid, o)
        tx.set("tableService", oid, om.service_row(o))
        tx.set("tableQueue", oid, om.queue_row(o))
        tx.set("outbox", o["eventId"], {"eventId": o["eventId"], "orderId": oid, "status": "PENDING", "attempts": 0, "payload": om.event(o), "createdAt": now(), "publishedAt": ""})
        return o, True
    order, created = fs.transaction(t)
    if created:
        audit.log_event("cod_order_confirmed", oid, customer["uid"], details={"product_id": pid, "quantity": qty})
        try_publish(order["eventId"])
        try_sync_order(oid)
        try_sync_product(pid)
    return order, created


def try_publish(eid):
    ob = fs.get("outbox", eid)
    if not ob or ob["status"] == "PUBLISHED":
        return
    try:
        mid = ps.publish(ob["payload"])
        fs.update("outbox", eid, {"status": "PUBLISHED", "publishedAt": now(), "messageId": str(mid)})
        audit.log_event("pubsub_message_published", ob["orderId"], "backend", details={"event_id": eid})
    except Exception as e:  # stays PENDING -> reconcile()/worker retries; the order is already safe in Firestore
        log.error("publish failed for %s: %s", eid, e)
        fs.update("outbox", eid, {"attempts": ob["attempts"] + 1})
        audit.log_event("pubsub_publish_failed", ob["orderId"], "backend", "failure", {"error": str(e)[:200]})


def sync_order(oid):
    o = fs.get("orders", oid)
    if not o:
        return
    st.put_json(f"orders/{oid}.json", order_json(o), {"orderId": oid, "orderStatus": o["orderStatus"], "updatedAt": o["updatedAt"]})

    def t(tx):
        cur = tx.get("orders", oid)
        if cur and cur["version"] == o["version"]:
            cur["gcsSyncPending"] = False
            tx.set("orders", oid, cur)
    fs.transaction(t)


def try_sync_order(oid):
    try:
        sync_order(oid)
    except Exception as e:
        log.warning("GCS order archive pending for %s: %s", oid, e)


def try_sync_product(pid):
    from services import product_service
    product_service.try_sync(pid)


def mutate_order(oid, fn):
    """Transaction: order + tableService updated together."""
    def t(tx):
        o = tx.get("orders", oid)
        if not o:
            raise AppError("order not found", 404, "NOT_FOUND")
        fn(o)
        o.update(updatedAt=now(), version=o["version"] + 1, gcsSyncPending=True)
        tx.set("orders", oid, o)
        tx.set("tableService", oid, om.service_row(o))
        return o
    return fs.transaction(t)


def update_delivery(oid, new, actor):
    if new not in FLOW[1:]:
        raise AppError("status must be Processing, Out for Delivery or Delivered")

    def f(o):
        cur = o["orderStatus"]
        if FLOW.index(new) != FLOW.index(cur) + 1:
            raise AppError(f"cannot move order from {cur} to {new}", 409, "INVALID_TRANSITION")
        o["orderStatus"], o["deliveryStatus"] = new, DELIVERY[new]
        if new == "Delivered":
            o["deliveredAt"] = now()
        o["history"].append({"status": new, "at": now(), "by": actor})
    o = mutate_order(oid, f)
    audit.log_event("delivery_completed" if new == "Delivered" else "delivery_status_updated", oid, actor, details={"status": new})
    try_sync_order(oid)
    return fs.get("orders", oid)


def confirm_cash(oid, actor):
    def f(o):
        if o["orderStatus"] not in ("Out for Delivery", "Delivered"):
            raise AppError("cash can only be confirmed once the order is out for delivery or delivered", 409, "INVALID_TRANSITION")
        o["paymentStatus"], o["paidAt"] = "Paid", now()
    mutate_order(oid, f)
    audit.log_event("cod_payment_collected", oid, actor)
    try_sync_order(oid)
    return fs.get("orders", oid)


def reconcile():
    fixed = []
    for ob in fs.query("outbox", status="PENDING"):
        try_publish(ob["eventId"]); fixed.append(f"{ob['orderId']}: event republished")
    for p in fs.query("products", gcsSyncPending=True):
        try_sync_product(p["productId"]); fixed.append(f"{p['productId']}: JSON synced to Cloud Storage")
    for o in fs.query("orders", gcsSyncPending=True):
        try_sync_order(o["orderId"]); fixed.append(f"{o['orderId']}: archive synced to Cloud Storage")
    return fixed


def overview(seller_id=None):
    rows = fs.all_("tableService")
    if seller_id:
        rows = [r for r in rows if r.get("sellerId") == seller_id]
    c = lambda s: sum(1 for r in rows if r["orderStatus"] == s)
    return {"total": len(rows), "confirmed": c("Confirmed"), "processing": c("Processing"), "out_for_delivery": c("Out for Delivery"), "delivered": c("Delivered"),
            "pending_cod_payments": sum(1 for r in rows if r["paymentMethod"] == "COD" and r["paymentStatus"] == "Pending"),
            "orders": [om.service_api(r) for r in sorted(rows, key=lambda r: r["createdAt"], reverse=True)]}


def queue_overview():
    rows = fs.all_("tableQueue")
    s = lambda k: sum(1 for r in rows if r["queueStatus"] == k)
    waiting = [r for r in rows if r["queueStatus"] == "Queued"]
    return {"queue": config.SUBSCRIPTION, "approximate_messages": len(waiting), "poison_messages": s("Failed"),
            "published_events": sum(1 for o in fs.all_("outbox") if o["status"] == "PUBLISHED"),
            "stats": {"total": len(rows), "pending": s("Queued"), "processed": s("Processed"), "failed": s("Failed"), "retries": sum(max(int(r.get("deliveryAttempts", 0)) - 1, 0) for r in rows)},
            "messages": [{"id": r["orderId"], "dequeue_count": r.get("deliveryAttempts", 0), "inserted_on": r["createdAt"],
                          "content": {"order_id": r["orderId"], "product_id": r["productId"], "customer_id": r["customerId"], "quantity": r["quantity"]}} for r in waiting[:20]]}


def dashboard():
    prods, orders = fs.all_("products"), fs.all_("tableService")
    pc = lambda s: sum(1 for p in prods if p["publicationStatus"] == s)
    q = queue_overview()
    objs = {p: st.list_(p + "/") for p in config.PREFIXES}
    last = max([o["last_modified"] for v in objs.values() for o in v], default=None)
    return {"products": {"total": len(prods), "published": pc("Published"), "draft": pc("Draft"), "out_of_stock": pc("Out of Stock"), "unpublished": pc("Unpublished")},
            "orders": {k: v for k, v in overview().items() if k != "orders"},
            "queue": {"published_events": q["published_events"], **q["stats"]},
            "storage": {"bucket": config.BUCKET, "product_images": len(objs["product-images"]), "product_json": len(objs["products"]), "order_archives": len(objs["orders"]), "audit_objects": len(objs["audit-logs"]), "last_upload": last},
            "firestore": {c: len(fs.all_(c)) for c in ("products", "orders", "tableQueue", "tableService", "customers", "sellers", "carts", "outbox", "auditLogs")}}
