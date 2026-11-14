# API (JSON; `Authorization: Bearer <token>` from `/api/auth/login`)
| Method | Endpoint | Role |
|---|---|---|
| POST | `/api/auth/login`, `/api/auth/register` (customer) | public |
| GET | `/api/products[?q=]`, `/api/products/{id}` | public (Published only) |
| GET/POST | `/api/seller/products` (multipart: product_name colour product_status available_quantity price category description image) | seller, admin |
| PUT/DELETE | `/api/seller/products/{id}` (PUT honours `If-Match: <etag>` = product version, 409 on mismatch) | owner, admin |
| POST | `/api/seller/products/{id}/publish`, `/unpublish`, `/image` | owner, admin |
| GET/POST | `/api/cart`; PUT/DELETE `/api/cart/{product_id}` | customer |
| GET | `/api/payment-methods` | public |
| POST | `/api/orders` (`Idempotency-Key` header; price/total/seller from Firestore) | customer |
| GET | `/api/orders/{id}`, `/api/customer/orders` | owner / customer |
| POST | `/api/orders/{id}/process` | admin |
| GET | `/api/admin/orders` | admin, seller (own) |
| GET | `/api/admin/dashboard`, `/api/admin/queue`, `/api/admin/table-queue`, `/api/admin/table-service` | admin |
| POST | `/api/admin/queue/run[?fail=1]`, `/api/admin/reconcile` | admin |
| PUT | `/api/admin/orders/{id}/delivery-status` `{"status":"Processing\|Out for Delivery\|Delivered"}` | admin |
| POST | `/api/admin/orders/{id}/confirm-cash` | admin |
| GET | `/api/admin/storage/products\|orders\|containers\|selftest\|signed-url?object=` | admin |
| GET/POST/DELETE | `/api/storage/*` (explorer) | admin |
| GET | `/api/images/{name}`, `/api/health[?deep=1]` | public |
Errors: `{"error": CODE, "message": text}`; 401 login, 403 role/IAM, 409 stock/conflict/transition, 503 identity/network.
