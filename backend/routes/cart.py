"""Server-side cart: Firestore carts/<customerId>"""
from flask import Blueprint, g, jsonify, request

from models.product import now
from services import audit_service as audit
from services import auth_service as auth
from services import firestore_service as fs
from services.errors import AppError

bp = Blueprint("cart", __name__)


def modify(uid, fn):
    def t(tx):
        c = tx.get("carts", uid) or {"customerId": uid, "items": []}
        fn(c)
        c["updatedAt"] = now()
        tx.set("carts", uid, c)
        return c
    return fs.transaction(t)


def remove_line(uid, pid):
    modify(uid, lambda c: c.update(items=[i for i in c["items"] if i["productId"] != pid]))


def _published(pid):
    p = fs.get("products", pid) if pid else None
    if not p:
        raise AppError("invalid product id")
    if p["publicationStatus"] != "Published":
        raise AppError("product is not available", 409, "NOT_AVAILABLE")
    return p


def view(cart):
    lines, total = [], 0.0
    for i in cart["items"]:
        p = fs.get("products", i["productId"])
        if not p:
            continue
        ok = p["publicationStatus"] == "Published"
        sub = round((p.get("price") or 0) * i["quantity"], 2)
        total += sub if ok else 0
        lines.append({"product_id": p["productId"], "product_name": p["productName"], "colour": p.get("colour", ""), "price": p.get("price"),
                      "image_object_name": p.get("imageObjectName", ""), "quantity": i["quantity"], "available_quantity": p["availableQuantity"], "available": ok, "subtotal": sub})
    return {"items": lines, "total": round(total, 2)}


def _cart(uid):
    return fs.get("carts", uid) or {"customerId": uid, "items": []}


@bp.get("/api/cart")
@auth.require("customer")
def get_cart():
    return jsonify(view(_cart(g.user["uid"])))


@bp.post("/api/cart")
@auth.require("customer")
def add():
    d = request.get_json(silent=True) or {}
    pid = str(d.get("product_id", ""))
    try:
        qty = int(d.get("quantity", 1))
    except (TypeError, ValueError):
        raise AppError("quantity must be a number")
    p = _published(pid)

    def f(c):
        line = next((i for i in c["items"] if i["productId"] == pid), None)
        new = (line["quantity"] if line else 0) + qty
        if qty < 1 or new > p["availableQuantity"]:
            raise AppError(f"Only {p['availableQuantity']} unit(s) in stock", 409, "INSUFFICIENT_STOCK")
        if line:
            line["quantity"] = new
        else:
            c["items"].append({"productId": pid, "quantity": qty})
    cart = modify(g.user["uid"], f)
    audit.log_event("product_added_to_cart", pid, g.user["uid"], details={"quantity": qty})
    return jsonify(view(cart)), 201


@bp.put("/api/cart/<pid>")
@auth.require("customer")
def set_qty(pid):
    try:
        qty = int((request.get_json(silent=True) or {}).get("quantity"))
    except (TypeError, ValueError):
        raise AppError("quantity must be a number")
    p = _published(pid)
    if qty > p["availableQuantity"]:
        raise AppError(f"Only {p['availableQuantity']} unit(s) in stock", 409, "INSUFFICIENT_STOCK")

    def f(c):
        c["items"] = [i for i in c["items"] if i["productId"] != pid]
        if qty > 0:
            c["items"].append({"productId": pid, "quantity": qty})
    return jsonify(view(modify(g.user["uid"], f)))


@bp.delete("/api/cart/<pid>")
@auth.require("customer")
def remove(pid):
    remove_line(g.user["uid"], pid)
    return jsonify(view(_cart(g.user["uid"])))
