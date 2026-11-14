import uuid

from flask import Blueprint, g, jsonify, request

from models import order as om
from models.product import snake
from routes.cart import remove_line
from services import auth_service as auth
from services import firestore_service as fs
from services import order_service as osv
from services import queue_worker
from services.errors import AppError

bp = Blueprint("orders", __name__)


def _api(o):
    d = osv.order_json(o)
    ob = fs.get("outbox", o["eventId"]) if o.get("eventId") else None
    d["queue_status"] = "Queued" if ob and ob["status"] == "PUBLISHED" else "Retrying"
    return d


@bp.get("/api/payment-methods")
def payment_methods():
    return jsonify([{"code": "COD", "label": "Cash on Delivery", "offline": True}])


@bp.post("/api/orders")
@auth.require("customer")
def create():
    key = request.headers.get("Idempotency-Key") or uuid.uuid4().hex     # frontend sends one key per checkout attempt
    order, created = osv.create_order(g.user, request.get_json(silent=True) or {}, key)
    if created:
        remove_line(g.user["uid"], order["productId"])
    return jsonify({**_api(order), "message": "Your order has been successfully placed!", "duplicate": not created}), 201 if created else 200


@bp.get("/api/orders/<oid>")
@auth.require("customer", "seller", "admin")
def get_order(oid):
    o, u = fs.get("orders", oid), g.user
    if not o:
        raise AppError("order not found", 404, "NOT_FOUND")
    if (u["role"] == "customer" and o["customerId"] != u["uid"]) or (u["role"] == "seller" and o["sellerId"] != u["uid"]):
        raise AppError("not your order", 403, "FORBIDDEN")
    return jsonify(_api(o))


@bp.get("/api/customer/orders")
@auth.require("customer")
def my_orders():
    rows = fs.query("tableService", customerId=g.user["uid"])
    return jsonify([om.service_api(r) for r in sorted(rows, key=lambda r: r["createdAt"], reverse=True)])


@bp.post("/api/orders/<oid>/process")
@auth.require("admin")
def process_one(oid):
    o = fs.get("orders", oid)
    if not o:
        raise AppError("order not found", 404, "NOT_FOUND")
    return jsonify({"order_id": oid, "result": queue_worker.process_event(om.event(o))})
