# Deployment
## 1. Verify
```bash
gcloud auth list                       # active account
gcloud config get-value project        # active project
gcloud billing projects describe $(gcloud config get-value project) --format="value(billingEnabled)"   # True
./scripts/setup-gcp.sh                 # enables the 11 APIs and lists them
```
## 2. Deploy
```bash
./scripts/deploy.sh                    # = terraform init, validate, plan, apply  (+ waits for the site, prints credentials)
./scripts/deploy.sh plan               # plan only
terraform -chdir=infrastructure/terraform output
```
Expected: `Apply complete`, `url = http://<IP>`, 3 seller/admin/customer passwords printed. VMs need 4-8 min after apply (packages + pip).
Verify resources:
```bash
gcloud storage buckets describe gs://$(gcloud config get-value project)-quickkart-storage --format="value(uniform_bucket_level_access,public_access_prevention)"   # True enforced
gcloud firestore databases list ; gcloud pubsub topics list ; gcloud pubsub subscriptions list
gcloud compute instance-groups managed list ; gcloud compute forwarding-rules list
gcloud iam service-accounts list --filter=quickkart
```
## 3. Environment variables (backend, written to /etc/quickkart.env by the startup script)
| Variable | Purpose |
|---|---|
| `GCP_PROJECT_ID` `GCP_REGION` | project/region (project optional: ADC default) |
| `GCS_BUCKET_NAME` | data bucket |
| `FIRESTORE_DATABASE` | database id (`(default)`) |
| `PUBSUB_TOPIC` `PUBSUB_SUBSCRIPTION` `PUBSUB_DLQ_SUBSCRIPTION` | messaging |
| `BACKEND_SERVICE_ACCOUNT` | informational |
| `SESSION_SECRET` | signs login tokens (from Secret Manager; same on all instances) |
| `SEED_SELLER_PASSWORD` `SEED_ADMIN_PASSWORD` `SEED_CUSTOMER_PASSWORD` (+`SEED_*_EMAIL`) | demo users (Secret Manager) |
Terraform variables: `project_id region zone bucket_name domain alert_email retention_days force_destroy_bucket machine_type` (see `terraform.tfvars.example`). `GCP_NETWORK`, `GCP_FRONTEND_SUBNET`, `GCP_BACKEND_SUBNET` are created and referenced by Terraform (`quickkart-vpc`, `quickkart-frontend-subnet`, `quickkart-backend-subnet`).
## 4. HTTPS
Set `domain = "shop.example.com"`, apply, create a DNS A record to `load_balancer_ip`; the Google-managed certificate becomes ACTIVE in 10-60 min. For the class demo use the HTTP URL (always `http://`, not `https://`).
## 5. Remote state (shared environments)
Create a private versioned bucket, uncomment `backend "gcs" {}` in `providers.tf`, then `terraform init -backend-config="bucket=<bucket>" -backend-config="prefix=quickkart"` (state locking is built in). Terraform state contains the generated secrets: restrict access to it.
## 6. Update code / rollback
`./scripts/update-app.sh` re-packages code -> new instance templates -> MIG rolling replace. Rollback: `git checkout <previous>` then `update-app.sh`; data: Cloud Storage versioning (`gcloud storage ls -a gs://BUCKET/products/`), Firestore PITR/export if enabled. Nothing outside the project is touched.
## 7. Migration from the Azure version
Different cloud, new data store: no schema migration. Re-create products in the Seller Portal (or script POSTs to `/api/seller/products`). `image_blob_name` became `image_object_name` in API JSON.
## 8. Cleanup
`./scripts/cleanup.sh` (asks to confirm) -> `terraform destroy`. Verify: `gcloud compute instances list; gcloud storage buckets list; gcloud pubsub topics list`. Disable billing alerts/ budgets if you created any.
