# IAM guide (service account demo)
| Principal | Roles | Scope |
|---|---|---|
| `quickkart-backend-sa` | Storage Object Admin | data bucket only |
| | Cloud Datastore User | project (Firestore) |
| | Pub/Sub Publisher | topic `quickkart-order-topic` |
| | Pub/Sub Subscriber | subscriptions `...order-subscription`, `...order-dlq-subscription` |
| | Logs Writer, Monitoring Metric Writer | project |
| | Secret Manager Secret Accessor | the 4 app secrets only |
| | Storage Object Viewer | artifacts bucket (to download code) |
| | Service Account Token Creator | itself (signed URLs) |
| `quickkart-frontend-sa` | Logs Writer, Metric Writer, Object Viewer on artifacts | no Firestore / data bucket / Pub/Sub / secrets |
| Pub/Sub service agent | Publisher on DLQ topic, Subscriber on main subscription | dead-lettering |
Demonstration (`scripts/iam-demo.sh`):
```bash
./iam-demo.sh show        # bucket policy, roles, and: service account keys list (must be EMPTY)
./iam-demo.sh identity    # IAP SSH to a backend VM: metadata server email + gcloud auth list (no token printed)
./test-storage.sh         # on the VM: upload / read / delete a test object with the attached SA
./iam-demo.sh selftest    # app endpoint: upload+read+delete -> {"upload":true,"read":true,"delete":true}
./iam-demo.sh remove      # remove Storage Object Admin on the bucket; wait ~60 s
./iam-demo.sh selftest    # -> HTTP 403 AUTHORIZATION_FAILED  (Console: Logging shows "iam_authorization_failure")
./iam-demo.sh restore     # add it back; selftest works again
```
Console: IAM & Admin -> IAM (filter the SA), Service Accounts -> quickkart-backend-sa -> *Keys* (none), Cloud Storage -> bucket -> Permissions, Compute Engine -> instance -> *Service account* section. Real-world use: a payments or inventory service that may only touch its own bucket/topic.
Never create keys: `gcloud iam service-accounts keys create` is not used anywhere; consider org policy `iam.disableServiceAccountKeyCreation`.
