"""Dashboard + Cloud Storage explorer. Browser never sees credentials. 'containers' = top-level folders (prefixes) of the private bucket."""
import json
import os
import socket

from flask import Blueprint, Response, g, jsonify, request
from werkzeug.utils import secure_filename

import config
from services import audit_service as audit
from services import auth_service as auth
from services import firestore_service as fs
from services import identity_service as idn
from services import storage_service as st
from services.errors import AppError

bp = Blueprint("storage", __name__)
EXT_TYPES = {".json": "application/json", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


def _folder(c):
    if c not in config.PREFIXES:
        raise AppError("unknown folder")
    return c


@bp.get("/api/storage/info")
@auth.require("admin")
def info():
    n = lambda p: len([o for o in st.list_(p + "/")])
    objs = {p: st.list_(p + "/") for p in config.PREFIXES}
    last = max([o["last_modified"] for v in objs.values() for o in v], default=None)
    ident = idn.identity()
    return jsonify({"account": config.BUCKET, "endpoint": f"gs://{config.BUCKET}", "containers": config.PREFIXES,
                    "total_products": len(fs.all_("products")), "total_images": len(objs["product-images"]), "total_orders": len(fs.all_("orders")),
                    "total_audit_events": len(objs["audit-logs"]), "last_upload": last, "last_success_op": "list objects", "upload_status": "success",
                    "auth": f"Attached service account (ADC): {ident.get('principal', 'unavailable')}", "token": ident, "served_by": socket.gethostname()})


@bp.get("/api/storage/containers")
@auth.require("admin")
def containers():
    return jsonify(config.PREFIXES)


@bp.get("/api/storage/containers/<c>/blobs")
@auth.require("admin")
def blobs(c):
    p = _folder(c)
    return jsonify([{**b, "name": b["name"][len(p) + 1:]} for b in st.list_(p + "/")])


@bp.get("/api/storage/blob/<c>/<path:name>")
@auth.require("admin")
def blob(c, name):
    data, ctype = st.get(f"{_folder(c)}/{name}")
    headers = {"X-Content-Type-Options": "nosniff"}
    if request.args.get("download"):
        headers["Content-Disposition"] = f'attachment; filename="{os.path.basename(name)}"'
    return Response(data, mimetype=ctype, headers=headers)


@bp.get("/api/images/<path:name>")
def image(name):
    """Private bucket: images are streamed by the backend (public product pages only ever see this URL, not the bucket)."""
    data, ctype = st.get(f"product-images/{name}")
    return Response(data, mimetype=ctype, headers={"Cache-Control": "public, max-age=300", "X-Content-Type-Options": "nosniff"})


@bp.post("/api/storage/upload")
@auth.require("admin")
def upload():
    c = _folder(request.form.get("container", ""))
    f = request.files.get("file")
    if not f:
        raise AppError("file is required")
    name = secure_filename(f.filename or "")
    ctype = EXT_TYPES.get(os.path.splitext(name)[1].lower())
    if not name or not ctype:
        raise AppError("allowed: .json .jpg .png .webp")
    data = f.read(config.MAX_IMAGE_BYTES + 1)
    if len(data) > config.MAX_IMAGE_BYTES:
        raise AppError("file larger than 5 MB")
    if ctype == "application/json":
        json.loads(data)
    st.put(f"{c}/{name}", data, ctype, {"uploadedBy": g.user["uid"]})
    audit.log_event("explorer_upload", f"{c}/{name}", g.user["uid"])
    return jsonify({"uploaded": f"{c}/{name}"}), 201


@bp.delete("/api/storage/blob/<c>/<path:name>")
@auth.require("admin")
def delete_blob(c, name):
    c = _folder(c)
    if not (name.startswith("test-") or c == "backups"):
        raise AppError("Explorer may only delete 'test-*' objects or objects in backups/")
    st.delete(f"{c}/{name}")
    audit.log_event("explorer_delete", f"{c}/{name}", g.user["uid"])
    return jsonify({"deleted": f"{c}/{name}"})
