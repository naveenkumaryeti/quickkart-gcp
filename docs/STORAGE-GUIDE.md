# Storage, Firestore and Pub/Sub guide
## Cloud Storage
Private bucket `<project>-quickkart-storage`: uniform bucket-level access, public access prevention **enforced**, versioning on (backup demo), lifecycle: delete noncurrent versions beyond 5, `backups/` to Nearline after 30 days, optional retention (`retention_days`). Folders: `products/ product-images/ orders/ audit-logs/<event>/ backups/`. Object metadata: Content-Type, productId, sellerId/uploadedBy, updatedAt. Images are served by the backend (`/api/images/<name>`); `/api/admin/storage/signed-url?object=...` returns a 10-minute V4 signed URL.
```bash
gcloud storage ls -r gs://BUCKET/                                  # folders and objects
gcloud storage objects describe gs://BUCKET/products/PROD-XXXX.json # metadata, generation
gcloud storage cat gs://BUCKET/products/PROD-XXXX.json
gcloud storage ls -a gs://BUCKET/products/                         # all versions
```
Console: Cloud Storage -> Buckets -> bucket -> Objects. Concepts: bucket (container) / object (file + metadata) / storage class (cost tier) / versioning / lifecycle rules / signed URL (temporary access without IAM) / IAM (permanent access by identity).
## Firestore (Native, `(default)`)
Collections: `products customers sellers carts orders tableQueue tableService auditLogs outbox`. Console: Firestore -> Data. CLI: `gcloud firestore databases list`; data via Console or client libraries. Timestamps are ISO-8601 strings. Queries use equality filters only (no composite index needed).
## Pub/Sub
```bash
./scripts/test-pubsub.sh        # topic, subscription config (ack 30 s, retry 10-60 s, dead-letter after 5), peek messages, DLQ
```
Flow demo: place an order -> Admin dashboard shows the event Queued -> **Run Pub/Sub consumer** -> Processed. Retry demo: **simulate failure** 5 times (NACK -> redelivery with backoff) -> message dead-lettered -> `Failed` -> `quickkart_dead_letters` log metric/alert fires. Console: Pub/Sub -> Topics/Subscriptions -> Metrics.
