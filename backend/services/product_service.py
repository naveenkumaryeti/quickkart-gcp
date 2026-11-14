"""Products: Firestore is the source of truth; the JSON copy in Cloud Storage is synchronised (flag + retry + reconcile)."""
import logging

import config
from models import product as pm
from services import audit_service as audit
from services import firestore_service as fs
from services import storage_service as st
from services.errors import AppError

log = logging.getLogger(__name__)


def json_doc(p):
    return pm.snake({k: v for k, v in p.items() if k != "gcsSyncPending"})


def store_image(pid, f, actor):
    ctype = f.mimetype
    if ctype not in config.ALLOWED_IMAGE_TYPES:
        raise AppError("only JPG, PNG and WebP images are allowed")
    data = f.read(config.MAX_IMAGE_BYTES + 1)
    if len(data) > config.MAX_IMAGE_BYTES:
        raise AppError("image larger than 5 MB")
    ok = ((ctype == "image/jpeg" and data[:3] == b"\xff\xd8\xff") or (ctype == "image/png" and data[:4] == b"\x89PNG") or
          (ctype == "image/webp" and data[:4] == b"RIFF" and data[8:12] == b"WEBP"))
    if not ok:
        raise AppError("file content does not match its image type")
    name = f"{pid}.{config.ALLOWED_IMAGE_TYPES[ctype]}"
    st.put(f"product-images/{name}", data, ctype, {"productId": pid, "uploadedBy": actor})
    audit.log_event("product_image_uploaded", pid, actor, details={"object": name})
    return name


def sync_json(pid):
    """Upload products/<id>.json then clear the pending flag ONLY if the product was not changed meanwhile."""
    p = fs.get("products", pid)
    if not p:
        return
    st.put_json(f"products/{pid}.json", json_doc(p), {"productId": pid, "sellerId": p["sellerId"], "updatedAt": p["updatedAt"]})

    def t(tx):
        cur = tx.get("products", pid)
        if cur and cur["version"] == p["version"]:
            cur["gcsSyncPending"] = False
            tx.set("products", pid, cur)
    fs.transaction(t)


def try_sync(pid):
    try:
        sync_json(pid)
    except Exception as e:  # stays pending -> reconcile() retries
        log.warning("GCS JSON sync pending for %s: %s", pid, e)


def mutate(pid, fn, if_match=None):
    """Transactional read-modify-write with optimistic concurrency (version == ETag shown to the browser)."""
    def t(tx):
        p = tx.get("products", pid)
        if not p:
            raise AppError("product not found", 404, "NOT_FOUND")
        if if_match not in (None, "") and str(p["version"]) != str(if_match):
            raise AppError("Product was modified by someone else - reload and retry (version mismatch)", 409, "CONFLICT")
        fn(p)
        p["version"] = p["version"] + 1
        p["updatedAt"] = pm.now()
        p["gcsSyncPending"] = True
        tx.set("products", pid, p)
        return p
    return fs.transaction(t)


def own(p, user):
    if user["role"] != "admin" and p["sellerId"] != user["uid"]:
        raise AppError("this product belongs to another seller", 403, "FORBIDDEN")


def create(data, user, image):
    p = pm.build(data, user["uid"])
    if image:
        p["imageObjectName"] = store_image(p["productId"], image, user["uid"])
    p.update(version=1, gcsSyncPending=True)
    fs.create("products", p["productId"], p)
    audit.log_event("product_created", p["productId"], user["uid"])
    try_sync(p["productId"])
    return fs.get("products", p["productId"])


def update(pid, data, user, image, if_match):
    img = store_image(pid, image, user["uid"]) if image else None

    def fn(p):
        own(p, user)
        p.update({k: v for k, v in pm.build(data, p["sellerId"], p).items()})
        if img:
            p["imageObjectName"] = img
        if p["publicationStatus"] == "Published" and pm.publish_errors(p):
            raise AppError("cannot keep published: " + "; ".join(pm.publish_errors(p)))
    p = mutate(pid, fn, if_match)
    audit.log_event("product_updated", pid, user["uid"])
    try_sync(pid)
    return fs.get("products", pid)


def set_status(pid, status, user):
    def fn(p):
        own(p, user)
        if status == "Published" and pm.publish_errors(p):
            raise AppError("cannot publish: " + "; ".join(pm.publish_errors(p)))
        p["publicationStatus"] = status
    mutate(pid, fn)
    audit.log_event(f"product_{status.lower()}", pid, user["uid"])
    try_sync(pid)
    return fs.get("products", pid)


def delete(pid, user):
    p = fs.get("products", pid)
    if not p:
        raise AppError("product not found", 404, "NOT_FOUND")
    own(p, user)
    fs.delete("products", pid)
    for obj in (f"products/{pid}.json", f"product-images/{p.get('imageObjectName')}" if p.get("imageObjectName") else None):
        if obj:
            try:
                st.delete(obj)
            except Exception:  # noqa
                pass
    audit.log_event("product_deleted", pid, user["uid"])
