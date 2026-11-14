#!/usr/bin/env python3
"""End-to-end acceptance tests for QuickKart on GCP (tests 1-26 + extras; tests 27-30 are infrastructure checks in test-infra.sh).
  GCP:     python3 e2e_test.py --url http://<load-balancer-ip> [--poison]   (credentials: scripts/.state/credentials.env or QK_* env vars)
  Offline: python3 e2e_test.py --local                                      (in-memory fakes; validates business logic only)"""
import argparse, io, json, os, sys, time, urllib.error, urllib.request, uuid

PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360f8cfc000000301010018dd8db00000000049454e44ae426082")


class Remote:
    def __init__(s, url): s.url = url.rstrip("/")
    def call(s, method, path, body=None, token=None, headers=None, form=None, files=None):
        h, data = dict(headers or {}), None
        if token: h["Authorization"] = "Bearer " + token
        if form is not None or files:
            b = uuid.uuid4().hex; parts = []
            for k, v in (form or {}).items(): parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
            for k, (fn, c, ct) in (files or {}).items(): parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"; filename="{fn}"\r\nContent-Type: {ct}\r\n\r\n'.encode() + c + b"\r\n")
            data = b"".join(parts) + f"--{b}--\r\n".encode(); h["Content-Type"] = "multipart/form-data; boundary=" + b
        elif body is not None: data = json.dumps(body).encode(); h["Content-Type"] = "application/json"
        req = urllib.request.Request(s.url + path, data=data, headers=h, method=method)
        try: r = urllib.request.urlopen(req, timeout=120); code, raw = r.status, r.read()
        except urllib.error.HTTPError as e: code, raw = e.code, e.read()
        try: return code, json.loads(raw)
        except Exception: return code, raw


class Local:
    def __init__(s):
        os.environ.update(GCS_BUCKET_NAME="local", SESSION_SECRET="x" * 32, SEED_SELLER_PASSWORD="SellerPass#1", SEED_ADMIN_PASSWORD="AdminPass#1", SEED_CUSTOMER_PASSWORD="CustPass#1")
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
        sys.path.insert(0, os.path.join(base, "backend")); sys.path.insert(0, os.path.join(base, "tests"))
        import fake_gcp; fake_gcp.patch(); import app; s.c = app.app.test_client()
    def call(s, method, path, body=None, token=None, headers=None, form=None, files=None):
        h = dict(headers or {}); kw = {}
        if token: h["Authorization"] = "Bearer " + token
        if form is not None or files:
            d = dict(form or {}); d.update({k: (io.BytesIO(c), fn, ct) for k, (fn, c, ct) in (files or {}).items()}); kw["data"] = d
        elif body is not None: kw["json"] = body
        r = s.c.open(path, method=method, headers=h, **kw)
        return r.status_code, (r.get_json(silent=True) if r.is_json else r.data)


def creds(local):
    if local: return {"seller": ("seller@quickkart.demo", "SellerPass#1"), "admin": ("admin@quickkart.demo", "AdminPass#1"), "customer": ("customer@quickkart.demo", "CustPass#1")}
    f = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".state", "credentials.env"); kv = dict(os.environ)
    if os.path.exists(f): kv.update(dict(l.strip().split("=", 1) for l in open(f) if "=" in l))
    return {r: (kv.get(f"QK_{r.upper()}_EMAIL", f"{r}@quickkart.demo"), kv[f"QK_{r.upper()}_PASSWORD"]) for r in ("seller", "admin", "customer")}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--url"); ap.add_argument("--local", action="store_true"); ap.add_argument("--price", default="1000"); ap.add_argument("--poison", action="store_true")
    a = ap.parse_args(); c = Local() if a.local else Remote(a.url); cr = creds(a.local); res = []; wait = 0 if a.local else 3

    def t(n, name, cond, info=""):
        res.append(bool(cond)); print(f"  {'PASS' if cond else 'FAIL'}  TEST {n:>4} - {name}" + (f"  [{info}]" if info and not cond else ""))

    def login(role):
        code, d = c.call("POST", "/api/auth/login", {"email": cr[role][0], "password": cr[role][1]}); return code, d.get("token") if isinstance(d, dict) else None

    def run_consumer(token, tries=6):
        for _ in range(tries):
            code, r = c.call("POST", "/api/admin/queue/run", token=token)
            if code == 200 and any("processed" in str(x.get("result")) for x in r["results"]): return code, r
            time.sleep(wait)
        return code, r
    print("== QuickKart GCP acceptance tests")
    code, S = login("seller"); t(1, "Seller login", code == 200 and S, code)
    _, A = login("admin")
    code, d = c.call("POST", "/api/seller/products", token=S, form={"product_name": "iPhone 8", "colour": "Burgundy (Monochrome)", "product_status": "Recently Launched", "available_quantity": "10", "price": a.price, "category": "Smartphones", "description": "Acceptance test product"}, files={"image": ("iphone8.png", PNG, "image/png")})
    pid = d.get("product_id") if isinstance(d, dict) else None
    t(2, "Add iPhone 8 (Draft created)", code == 201 and pid and d["publication_status"] == "Draft", d)
    t(3, "Colour = Burgundy (Monochrome)", d.get("colour") == "Burgundy (Monochrome)")
    t(4, "Stock = 10 units", d.get("available_quantity") == 10)
    _, st = c.call("GET", "/api/admin/storage/products", token=A)
    t(5, "Image uploaded to GCS product-images/", any(b["name"] == d.get("image_object_name") for b in st["product-images"]), d.get("image_object_name"))
    t(6, "Product JSON object in GCS products/", any(b["name"] == f"{pid}.json" for b in st["products"]))
    _, mine = c.call("GET", "/api/seller/products", token=S); t(7, "Firestore product document exists (seller list)", any(p["product_id"] == pid for p in mine))
    _, pub0 = c.call("GET", "/api/products"); hidden = pid not in [p["product_id"] for p in pub0]
    code, d = c.call("POST", f"/api/seller/products/{pid}/publish", token=S); _, pub = c.call("GET", "/api/products")
    t(8, "Publish -> appears on homepage API (hidden while Draft)", code == 200 and hidden and pid in [p["product_id"] for p in pub], d)
    _, nd = c.call("POST", "/api/seller/products", token=S, form={"product_name": "NoPrice", "available_quantity": "1"}, files={"image": ("x.png", PNG, "image/png")})
    pc, _ = c.call("POST", f"/api/seller/products/{nd.get('product_id')}/publish", token=S); t("8.1", "Publish without price rejected", pc == 400, pc)
    code, C = login("customer"); t(9, "Customer login", code == 200 and C)
    code, d = c.call("GET", f"/api/products/{pid}"); t(10, "Product details: name, colour, price, stock", code == 200 and d["product_name"] == "iPhone 8" and d["price"] == float(a.price) and d["available_quantity"] == 10)
    code, d = c.call("POST", "/api/cart", {"product_id": pid, "quantity": 1}, token=C); t(11, "Add to cart", code == 201 and d["items"][0]["product_id"] == pid, d)
    _, pm = c.call("GET", "/api/payment-methods"); t(12, "COD available", pm and pm[0]["code"] == "COD")
    key = uuid.uuid4().hex; addr = "12 MG Road, Hyderabad, Telangana"
    code, o = c.call("POST", "/api/orders", {"product_id": pid, "quantity": 1, "delivery_address": addr, "payment_method": "COD", "price": 1, "total_amount": 1}, token=C, headers={"Idempotency-Key": key})
    oid = o.get("order_id") if isinstance(o, dict) else None
    t(13, "Order confirmed, unique Order ID (browser price ignored)", code == 201 and oid and o["total_amount"] == float(a.price) and o["order_status"] == "Confirmed" and o["payment_status"] == "Pending", o)
    _, p = c.call("GET", f"/api/products/{pid}"); t(14, "Stock 10 -> 9", p["available_quantity"] == 9, p.get("available_quantity"))
    _, ob = c.call("GET", f"/api/orders/{oid}", token=C); t(15, "Order stored in Firestore (readable by owner)", ob.get("order_id") == oid)
    _, q = c.call("GET", "/api/admin/queue", token=A); t(16, "Order event published to Pub/Sub (outbox PUBLISHED)", o.get("queue_status") == "Queued" and q["published_events"] >= 1, o.get("queue_status"))
    _, tq = c.call("GET", "/api/admin/table-queue", token=A); t(18, "TableQueue record (Queued)", any(r["OrderID"] == oid and r["QueueStatus"] == "Queued" for r in tq))
    _, tsr = c.call("GET", "/api/admin/table-service", token=A); t(19, "TableService record", any(r["OrderID"] == oid for r in tsr))
    code, r = run_consumer(A); t(17, "Subscription: consumer receives + processes the message", code == 200 and any(x.get("order_id") == oid for x in r["results"]), r)
    _, tq = c.call("GET", "/api/admin/table-queue", token=A); _, tsr = c.call("GET", "/api/admin/table-service", token=A)
    t(20, "TableQueue Processed + TableService Processing", any(r["OrderID"] == oid and r["QueueStatus"] == "Processed" for r in tq) and any(r["OrderID"] == oid and r["OrderStatus"] == "Processing" for r in tsr))
    c1, _ = c.call("PUT", f"/api/admin/orders/{oid}/delivery-status", {"status": "Delivered"}, token=A)
    c.call("PUT", f"/api/admin/orders/{oid}/delivery-status", {"status": "Out for Delivery"}, token=A)
    c2, d = c.call("PUT", f"/api/admin/orders/{oid}/delivery-status", {"status": "Delivered"}, token=A); _, mine = c.call("GET", "/api/customer/orders", token=C)
    t(21, "Delivery -> Delivered (skipping steps rejected); customer sees it", c1 == 409 and c2 == 200 and any(r["OrderID"] == oid and r["OrderStatus"] == "Delivered" and r["DeliveryStatus"] == "Delivered" for r in mine), (c1, c2))
    _, arch = c.call("GET", f"/api/storage/blob/orders/{oid}.json", token=A)
    t(22, "GCS order archive updated (Delivered + deliveredAt)", isinstance(arch, dict) and arch.get("order_status") == "Delivered" and arch.get("delivered_at"), arch)
    _, ao = c.call("GET", "/api/admin/storage/orders", token=A); t(23, "Delivery audit event in GCS audit-logs/", any("delivery_completed" in b["name"] for b in ao["audit-logs"]))
    t(24, "COD payment still Pending after delivery", arch.get("payment_status") == "Pending")
    cp, d = c.call("POST", f"/api/admin/orders/{oid}/confirm-cash", token=A); t("24.1", "Cash collection confirmed -> Paid", cp == 200 and d["payment_status"] == "Paid")
    code, o2 = c.call("POST", "/api/orders", {"product_id": pid, "quantity": 1, "delivery_address": addr}, token=C, headers={"Idempotency-Key": key}); _, p = c.call("GET", f"/api/products/{pid}")
    t(25, "Duplicate submission: same order, stock not decremented twice", code == 200 and o2["order_id"] == oid and o2["duplicate"] and p["available_quantity"] == 9, (code, p.get("available_quantity")))
    code, e = c.call("POST", "/api/orders", {"product_id": pid, "quantity": 50, "delivery_address": addr}, token=C); code2, _ = c.call("POST", "/api/orders", {"product_id": "PROD-NOPE0000", "quantity": 1, "delivery_address": addr}, token=C)
    t(26, "Insufficient stock / invalid product rejected", code == 409 and code2 == 400, (code, code2))
    t("X1", "Customer cannot call admin APIs (403); anonymous 401", c.call("GET", "/api/admin/queue", token=C)[0] == 403 and c.call("GET", "/api/admin/queue")[0] == 401)
    code, d = c.call("PUT", f"/api/seller/products/{pid}", token=S, form={"product_name": "iPhone 8", "available_quantity": "9", "price": a.price}, headers={"If-Match": "0"}); t("X2", "Stale version (ETag) update rejected with 409", code == 409, code)
    _, dash = c.call("GET", "/api/admin/dashboard", token=A); t("X3", "Admin dashboard has real counts", dash["products"]["total"] >= 2 and dash["storage"]["product_images"] >= 1 and dash["firestore"]["orders"] >= 1, dash)
    code, st_ = c.call("GET", "/api/admin/storage/selftest", token=A); t("X4", "Service-account self-test (upload/read/delete object)", code == 200 and st_["read"], st_)
    if a.local or a.poison:
        _, o3 = c.call("POST", "/api/orders", {"product_id": pid, "quantity": 1, "delivery_address": addr}, token=C, headers={"Idempotency-Key": uuid.uuid4().hex})
        for _ in range(6): c.call("POST", "/api/admin/queue/run?fail=1", token=A); time.sleep(12 if not a.local else 0)
        c.call("POST", "/api/admin/queue/run", token=A); _, tq = c.call("GET", "/api/admin/table-queue", token=A)
        t("X5", "Retries -> dead-letter topic -> TableQueue Failed", any(r["OrderID"] == o3.get("order_id") and r["QueueStatus"] == "Failed" for r in tq), [r for r in tq if r["OrderID"] == o3.get("order_id")])
    _, rc = c.call("POST", "/api/admin/reconcile", token=A); t("X6", "Reconcile endpoint runs", isinstance(rc, dict) and "fixed" in rc, rc)
    ok = sum(res); print(f"== PASSED {ok}/{len(res)}"); sys.exit(0 if ok == len(res) else 1)


main()
