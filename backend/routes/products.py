import re

from flask import Blueprint, g, jsonify, request

from models import product as pm
from services import auth_service as auth
from services import firestore_service as fs
from services import product_service as svc
from services.errors import AppError

bp = Blueprint("products", __name__)
ID_RE = re.compile(r"^[A-Za-z0-9-]{3,40}$")


def _pid(pid):
    if not ID_RE.match(pid):
        raise AppError("invalid product id")
    return pid


def _input():
    return request.form.to_dict() if request.form else (request.get_json(silent=True) or {})


# ---- public / customer: Published only ----
@bp.get("/api/products")
def list_published():
    q = request.args.get("q", "").lower()
    items = [p for p in fs.query("products", publicationStatus="Published") if q in (p["productName"] + p["colour"] + p["category"]).lower()]
    return jsonify([pm.api(p) for p in sorted(items, key=lambda p: p["createdAt"], reverse=True)])


@bp.get("/api/products/<pid>")
def get_published(pid):
    p = fs.get("products", _pid(pid))
    if not p or p["publicationStatus"] != "Published":
        raise AppError("product not found", 404, "NOT_FOUND")
    return jsonify(pm.api(p))


# ---- seller ----
@bp.get("/api/seller/products")
@auth.require("seller", "admin")
def seller_list():
    items = [p for p in fs.all_("products") if g.user["role"] == "admin" or p["sellerId"] == g.user["uid"]]
    return jsonify([pm.api(p) for p in sorted(items, key=lambda p: p["createdAt"], reverse=True)])


@bp.post("/api/seller/products")
@auth.require("seller", "admin")
def seller_create():
    return jsonify(pm.api(svc.create(_input(), g.user, request.files.get("image")))), 201


@bp.put("/api/seller/products/<pid>")
@auth.require("seller", "admin")
def seller_update(pid):
    return jsonify(pm.api(svc.update(_pid(pid), _input(), g.user, request.files.get("image"), request.headers.get("If-Match"))))


@bp.post("/api/seller/products/<pid>/publish")
@auth.require("seller", "admin")
def seller_publish(pid):
    return jsonify(pm.api(svc.set_status(_pid(pid), "Published", g.user)))


@bp.post("/api/seller/products/<pid>/unpublish")
@auth.require("seller", "admin")
def seller_unpublish(pid):
    return jsonify(pm.api(svc.set_status(_pid(pid), "Unpublished", g.user)))


@bp.post("/api/seller/products/<pid>/image")
@auth.require("seller", "admin")
def seller_image(pid):
    f = request.files.get("image")
    if not f:
        raise AppError("image file is required (form field 'image')")
    img = svc.store_image(_pid(pid), f, g.user["uid"])

    def fn(p):
        svc.own(p, g.user)
        p["imageObjectName"] = img
    svc.mutate(pid, fn)
    svc.try_sync(pid)
    return jsonify(pm.api(fs.get("products", pid)))


@bp.delete("/api/seller/products/<pid>")
@auth.require("seller", "admin")
def seller_delete(pid):
    svc.delete(_pid(pid), g.user)
    return jsonify({"deleted": pid})
