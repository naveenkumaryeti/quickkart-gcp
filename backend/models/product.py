import re
import uuid
from datetime import datetime, timezone


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def snake(d):
    return {re.sub(r"([A-Z])", lambda m: "_" + m.group(1).lower(), k): v for k, v in d.items()}


def build(data, seller_id, existing=None):
    """Validate seller input -> Firestore product document (camelCase, per the brief). Price may stay empty while Draft."""
    name = str(data.get("product_name", "")).strip()
    if not name:
        raise ValueError("product_name is required")
    try:
        qty = int(data.get("available_quantity"))
    except (TypeError, ValueError):
        raise ValueError("available_quantity must be a whole number")
    if qty < 0:
        raise ValueError("available_quantity must be >= 0")
    raw, price = data.get("price"), None
    if raw not in (None, ""):
        try:
            price = round(float(raw), 2)
        except (TypeError, ValueError):
            raise ValueError("price must be a number")
        if price <= 0:
            raise ValueError("price must be greater than 0")
    p = dict(existing or {})
    pid = p.get("productId") or "PROD-" + uuid.uuid4().hex[:8].upper()
    p.update(productId=pid, productName=name, colour=str(data.get("colour", "")).strip(), productStatus=str(data.get("product_status", "")).strip(),
             category=str(data.get("category") or "General").strip(), description=str(data.get("description", "")).strip()[:1000],
             availableQuantity=qty, price=price, sellerId=p.get("sellerId") or seller_id, imageObjectName=p.get("imageObjectName", ""),
             publicationStatus=p.get("publicationStatus", "Draft"), gcsJsonObject=f"products/{pid}.json")
    if qty == 0 and p["publicationStatus"] == "Published":
        p["publicationStatus"] = "Out of Stock"
    elif qty > 0 and p["publicationStatus"] == "Out of Stock":
        p["publicationStatus"] = "Published"
    p.setdefault("createdAt", now())
    p["updatedAt"] = now()
    return p


def publish_errors(p):
    e = []
    if not p.get("price") or p["price"] <= 0:
        e.append("a valid selling price is required")
    if p["availableQuantity"] < 1:
        e.append("stock must be at least 1")
    if not p.get("imageObjectName"):
        e.append("upload a product image first")
    return e


def api(p):
    d = snake({k: v for k, v in p.items() if k not in ("gcsSyncPending", "version")})
    d["etag"] = str(p.get("version", 1))
    return d
