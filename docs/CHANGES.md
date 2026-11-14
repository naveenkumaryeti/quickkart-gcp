# Files: what / why / how / test
| File | What | Why | How it works | Test |
|---|---|---|---|---|
| `backend/config.py` | env-only config (project, bucket, topic, subscriptions, secrets) | no hard-coding | read from `/etc/quickkart.env` | boot |
| `services/identity_service.py` | ADC identity probe | prove attached SA, no tokens exposed | `google.auth.default()` | `/api/health?deep=1` |
| `services/firestore_service.py` | Firestore wrapper + transactions | source of truth | `get/set/create/query/transaction` | e2e |
| `services/storage_service.py` | GCS wrapper, generation preconditions, signed URL | safe concurrent object writes | `if_generation_match` retry | e2e 5,6,22 |
| `services/pubsub_service.py` | publish / pull / ack / nack | async orders | unary pull, ack after success | e2e 16,17 |
| `services/audit_service.py` | audit to Firestore + GCS + Cloud Logging | req. 18 | best-effort sinks | e2e 23 |
| `services/auth_service.py` | users in Firestore, PBKDF2, signed tokens, roles | auth | `require(role)` | e2e 1,9,X1 |
| `services/product_service.py` | product CRUD + GCS JSON sync + version ETag | req. 4,5 | `gcsSyncPending` + reconcile | e2e 2-8,X2 |
| `services/order_service.py` | order transaction, outbox, delivery, cash, reconcile, dashboard | req. 9-12 | one Firestore transaction; outbox retry | e2e 13-26 |
| `services/queue_worker.py`, `worker.py` | consumer, NACK retry, DLQ drain | req. 10 | idempotent transaction, ack last | e2e 17,20,X5 |
| `routes/*`, `app.py` | REST API (same contract as Azure version), error mapping to IAM/auth/network | req. 11,17 | blueprints | e2e |
| `infrastructure/terraform/*` | everything in GCP | req. 19 | see README | `deploy.sh plan` |
| `scripts/*` | setup, deploy, IAM demo, tests, load, cleanup | req. 22 | gcloud/terraform | run |
| `frontend/*` | reused UI; field names/labels; admin statistics | req. 17 | calls `/api` | manual |
Script mapping to the brief's list: `setup-gcp.sh`=enable-apis+verify; `deploy.sh`=create-network/service-account/iam/storage/firestore/pubsub/deploy-* (all via Terraform); `test-storage.sh`, `test-pubsub.sh`, `cleanup.sh` as named.
