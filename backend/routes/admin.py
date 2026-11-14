import uuid

from flask import Blueprint, g, jsonify, request

import config
from models import order as om
from services import auth_service as auth
from services import firestore_service as fs
from services import order_service as osv
from services import queue_worker
from services import storage_service as st

bp = Blueprint("admin", __name__)


@bp.get("/api/admin/orders")
@auth.require("admin", "seller")
def orders():
    return jsonify(osv.overview(g.user["uid"] if g.user["role"] == "seller" else None))


@bp.get("/api/admin/dashboard")
@auth.require("admin")
def dashboard():
    return jsonify(osv.dashboard())


@bp.get("/api/admin/queue")
@auth.require("admin")
def queue():
    return jsonify(osv.queue_overview())


@bp.post("/api/admin/queue/run")
@auth.require("admin")
def run_consumer():
    return jsonify({"results": queue_worker.process_batch(fail=request.args.get("fail") == "1")})


@bp.post("/api/admin/reconcile")
@auth.require("admin")
def reconcile():
    return jsonify({"fixed": osv.reconcile()})


@bp.put("/api/admin/orders/<oid>/delivery-status")
@auth.require("admin")
def delivery(oid):
    o = osv.update_delivery(oid, (request.get_json(silent=True) or {}).get("status", ""), g.user["uid"])
    return jsonify(osv.order_json(o))


@bp.post("/api/admin/orders/<oid>/confirm-cash")
@auth.require("admin")
def cash(oid):
    return jsonify(osv.order_json(osv.confirm_cash(oid, g.user["uid"])))


@bp.get("/api/admin/table-queue")
@auth.require("admin")
def table_queue():
    return jsonify([om.queue_api(r) for r in sorted(fs.all_("tableQueue"), key=lambda r: r["createdAt"], reverse=True)])


@bp.get("/api/admin/table-service")
@auth.require("admin")
def table_service():
    return jsonify([om.service_api(r) for r in sorted(fs.all_("tableService"), key=lambda r: r["createdAt"], reverse=True)])


def _rel(prefix):
    return [{**b, "name": b["name"][len(prefix) + 1:]} for b in st.list_(prefix + "/") if b["name"] != prefix + "/"]


@bp.get("/api/admin/storage/containers")
@auth.require("admin")
def containers():
    return jsonify(config.PREFIXES)


@bp.get("/api/admin/storage/products")
@auth.require("admin")
def st_products():
    return jsonify({"products": _rel("products"), "product-images": _rel("product-images")})


@bp.get("/api/admin/storage/orders")
@auth.require("admin")
def st_orders():
    return jsonify({"orders": _rel("orders"), "audit-logs": _rel("audit-logs")})


@bp.get("/api/admin/storage/selftest")
@auth.require("admin")
def selftest():
    """IAM demo: upload -> read -> delete a test object with the attached service account. Fails with 403 when the role is removed."""
    name = f"backups/test-selftest-{uuid.uuid4().hex[:8]}.json"
    st.put_json(name, {"test": "iam"})
    ok = st.get_json(name) == {"test": "iam"}
    st.delete(name)
    return jsonify({"object": name, "upload": True, "read": ok, "delete": True})


@bp.get("/api/admin/storage/signed-url")
@auth.require("admin")
def signed():
    return jsonify({"url": st.signed_url(request.args["object"], 10), "expires_minutes": 10})
