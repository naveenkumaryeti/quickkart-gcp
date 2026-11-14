# Implementation Gap Analysis (done before coding)
The existing project was the **Azure Phase-2 QuickKart** (Flask + Bootstrap, Bicep, Blob/Queue/Table, Managed Identity). No GCP code existed.

| Feature | Status in repository | Action for GCP |
|---|---|---|
| Frontend (login, home, details, cart, checkout, orders, seller, admin, explorer) | Completed (Azure-backed API) | **Reused**; field names (`image_blob_name`->`image_object_name`), labels, admin statistics panel changed |
| REST API contract | Completed | Preserved (same endpoints/JSON) so the UI keeps working |
| Seller/customer authentication + roles | Completed (users in Blob) | Requires modification: users moved to Firestore `customers` / `sellers` |
| Product management + publish rules | Completed (Blob) | Requires modification: Firestore doc + GCS JSON sync + version-based ETag |
| Image upload | Completed (Blob) | Requires modification: Cloud Storage `product-images/` |
| Orders: idempotency, stock safety, COD | Partially (ETag ledger across Blob) | Rewritten with **Firestore transaction** |
| Queue + consumer + poison queue | Completed (Azure Queue) | Not implemented for GCP -> **Pub/Sub** + DLQ + outbox worker |
| TableQueue / TableService | Completed (Azure Tables) | Not implemented for GCP -> Firestore collections |
| Delivery lifecycle, COD cash confirmation | Completed | Ported (Firestore transaction + GCS archive) |
| Dashboards | Completed (Azure) | Ported + product/storage/Firestore statistics endpoint |
| Audit logging | Completed (Blob) | Firestore `auditLogs` + GCS objects + Cloud Logging |
| Identity/IAM | Managed Identity | Not implemented -> service accounts, ADC, roles |
| Networking/firewall/MIG/LB/autoscale | Bicep | Not implemented -> Terraform |
| Monitoring/alerts | Basic | Not implemented -> dashboards, alert policies, log-based metric |
| Terraform | none | Created |
Not working: nothing broken found. **Files modified:** frontend `js/*.js`, `admin.html`, `storage-dashboard.html`, `index.html`. **New:** everything under `backend/`, `infrastructure/terraform/`, `scripts/`, `tests/`, `docs/`.
Dependencies: auth -> all routes; product service -> cart/orders/home; order service -> Firestore + Pub/Sub + GCS; Terraform (APIs, IAM, Pub/Sub, secrets) -> backend startup.
Limits: one product per order (cart can hold several lines); HTTP demo endpoint (HTTPS needs a real domain: `var.domain`); passwords/secrets live in Secret Manager but also in Terraform state - protect the state bucket.
