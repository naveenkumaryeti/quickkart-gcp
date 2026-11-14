# 60-minute GCP classroom demo
Setup: `cd scripts && source env.sh && IP=$(lb_ip) && cat .state/credentials.env`. Browser: `http://$IP`. Keep the background consumer off (default).
| Min | Topic | Theory (say) | Console | Commands / expected | Use case |
|---|---|---|---|---|---|
| 5 | Architecture | 3 tiers, LB, MIG, Firestore/GCS/Pub/Sub | Compute Engine -> Instance groups; Network services -> Load balancing | `gcloud compute instance-groups managed list` -> 2 MIGs, `gcloud compute forwarding-rules list` | retail platform |
| 8 | Cloud Storage | bucket/object/IAM/versioning/signed URL, private bucket | Cloud Storage -> bucket -> Configuration | `gcloud storage buckets describe gs://BUCKET --format="value(uniform_bucket_level_access,public_access_prevention)"` -> `True enforced`; `gcloud storage ls -r gs://BUCKET/` | product media |
| 8 | Service account + IAM | identity, ADC, least privilege, no keys | IAM & Admin -> IAM; Service Accounts -> Keys | `./iam-demo.sh show` (keys list empty); `./iam-demo.sh identity`; `./iam-demo.sh remove` -> `selftest` 403 -> `restore` -> 200 | microservice access control |
| 8 | Seller publishing | draft vs published, price rule | Firestore -> Data -> products; Storage -> products/ | Seller login -> Add New Product (button "Fill iPhone 8 demo values": Burgundy (Monochrome), 10) -> enter YOUR price -> image -> Save (Draft) -> Publish -> home page shows it; JSON + image in bucket | marketplace |
| 8 | Customer COD order | server-side price, idempotency, stock | Firestore -> orders, tableService, tableQueue | Customer: View Product -> Add to Cart -> Checkout -> COD -> Confirm -> "Your order has been successfully placed!" + Order ID; stock 10 -> 9 | checkout |
| 8 | Pub/Sub + Firestore | async, ack, at-least-once, DLQ | Pub/Sub -> Subscriptions; Firestore | Admin dashboard: event Queued -> **Run Pub/Sub consumer** -> Processed/Processing; `./test-pubsub.sh`; optional **simulate failure** x5 -> Failed | order pipelines |
| 5 | Delivery | lifecycle, COD stays Pending | Storage -> orders/ORD-*.json; audit-logs/ | Admin: -> Out for Delivery -> Delivered; payment still Pending; **Cash collected** -> Paid | logistics |
| 5 | VPC firewall | rules, priority, tags vs SA | VPC network -> Firewall | commands in `NETWORKING-GUIDE.md` (list rules; block demo rule -> 502/504 -> delete) | zero trust |
| 3 | MIG autoscale + monitoring | autoscaler, autohealing, alerts | Compute -> MIG -> Monitoring; Monitoring -> Dashboards "QuickKart"; Logging -> `logName:quickkart-audit` | `./load-test.sh start`; `./load-test.sh status` (2 -> 3 -> 4 in ~5-10 min); `./test-infra.sh` | peak sale |
Troubleshooting: see `TROUBLESHOOTING.md`. Finish with `./test-infra.sh`, `python3 e2e_test.py --url http://$IP`, then `./cleanup.sh`.
