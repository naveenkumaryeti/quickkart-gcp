# Troubleshooting
| Symptom | Cause | Fix |
|---|---|---|
| Site not up after apply | startup script still running | wait 8 min; serial console: `gcloud compute instances get-serial-port-output <vm> --zone <z> \| tail -50` |
| LB returns 502 | frontend health check failing / backend ILB unreachable | `gcloud compute backend-services get-health quickkart-frontend-bs --global`; check firewall list |
| `/api/*` 504 but UI loads | firewall rule or backend unhealthy | `./test-infra.sh`; `gcloud compute backend-services get-health quickkart-backend-ilb --region asia-south1` |
| 403 AUTHORIZATION_FAILED | missing IAM role (restored with `iam-demo.sh restore`) or role not yet propagated | `./iam-demo.sh show`; wait 60 s |
| 503 AUTHENTICATION_FAILED | no service account attached / metadata blocked | `./iam-demo.sh identity` |
| 503 SERVICE_UNAVAILABLE | no Private Google Access / NAT / egress rule | `gcloud compute networks subnets describe ... --format="value(privateIpGoogleAccess)"` |
| Firestore `Database already exists` on apply | `(default)` exists | `terraform import google_firestore_database.db "projects/<id>/databases/(default)"` |
| Order shows `queue_status: Retrying` | Pub/Sub publish failed | fix cause, then Admin -> Reconcile |
| Message not dead-lettered | Pub/Sub service agent roles missing | re-apply (`pubsub.tf`), check `gcloud pubsub subscriptions describe ... deadLetterPolicy` |
| 401 on every call | token expired or `SESSION_SECRET` differs between instances | login again; `update-app.sh` |
| Cannot SSH | only IAP allowed | `gcloud compute ssh VM --zone Z --tunnel-through-iap` (needs IAP-secured Tunnel User role) |
| Terraform auth error on PC | no ADC | `gcloud auth application-default login` (or use Cloud Shell) |
