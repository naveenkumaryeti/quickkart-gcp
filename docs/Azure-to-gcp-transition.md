# QuickKart: Transition from Azure to Google Cloud (GCP)

The business workflow, REST API and web UI are the same on both clouds. What changed is the cloud services underneath and how the code talks to them.

## 1. Service mapping
| Purpose | Azure | GCP |
|---|---|---|
| Virtual machines | VM Scale Set (VMSS) | Instance template + regional Managed Instance Group (MIG) |
| Autoscaling | Azure Monitor autoscale rules | MIG autoscaler (CPU target 70%, min 1 / max 4) |
| Public load balancer | Standard Public LB | External Application Load Balancer (global) |
| Internal load balancer | Standard Internal LB | Internal passthrough Load Balancer |
| Virtual network | VNet + subnets | VPC (global) + regional subnets |
| Traffic rules | NSG + ASG | VPC firewall rules + network tags / service-account targeting |
| Outbound internet | NAT Gateway | Cloud Router + Cloud NAT |
| Private access to storage | Private Endpoint + Private DNS | Private Google Access (Private Service Connect optional) |
| Files and images | Blob Storage | Cloud Storage (private bucket with folders) |
| Order queue | Queue Storage | Pub/Sub topic + subscription + dead-letter topic |
| TableQueue / TableService | Table Storage | Firestore collections `tableQueue`, `tableService` |
| Main database | (Blob JSON files) | Firestore (Native mode), now the source of truth |
| Identity for the app | Managed Identity | Attached service account + Application Default Credentials (ADC) |
| Permissions | RBAC roles | IAM roles |
| Secrets | cloud-init values | Secret Manager |
| Monitoring and logs | Azure Monitor + Log Analytics | Cloud Logging + Cloud Monitoring + alert policies |
| Infrastructure as code | Bicep | Terraform |
| CLI | `az` | `gcloud` |

## 2. Concept differences to explain in class
| Topic | Azure | GCP |
|---|---|---|
| App identity | System-assigned identity is created with the VMSS and tied to it | You create a service account, grant it roles, and attach it to the instance template |
| App login in code | `DefaultAzureCredential` | `google.auth.default()` (ADC); client libraries do this automatically |
| Roles | Storage Blob / Queue / Table Data Contributor | Storage Object Admin, Datastore User, Pub/Sub Publisher + Subscriber, Logs Writer |
| Role scope | Storage account | Specific bucket, topic and subscription (narrower) |
| Firewall targets | ASG name tag inside NSG rules | Network tag, or the service account of the VM (stronger, cannot be spoofed) |
| Network scope | VNet is regional | VPC is global; subnets are regional |
| Concurrency control | Blob ETag (If-Match) | Firestore transactions + object generation preconditions + version number |
| Queue retries | Dequeue count, poison queue you manage | NACK + backoff, Pub/Sub dead-letter policy (minimum 5 attempts) |
| Queue visibility | Peek messages | No peek; the TableQueue rows show status and attempts |

Tags are not an exact ASG replacement. An ASG is a separate Azure resource used inside rules; GCP has no such object.

## 3. What changed in the code
| Area | Azure version | GCP version |
|---|---|---|
| Source of truth | Blob JSON files | Firestore documents |
| Blob / object copies | Primary store | Secondary copy (`products/<id>.json`, `orders/<id>.json`) kept in sync, with a repair job |
| Order creation | ETag ledger + outbox flag | One Firestore transaction: order, stock, tableService, tableQueue, outbox |
| Queue consumer | Receive, delete message after success | Pull, ack after success, NACK on failure |
| Users | `users/` blobs | Firestore `customers` and `sellers` collections |
| Field names | `image_blob_name` | `image_object_name` (Firestore uses camelCase, API uses snake_case) |
| Product ETag | Blob ETag | Product `version` number |
| Audit | Blob events | Firestore `auditLogs` + Cloud Storage `audit-logs/` + Cloud Logging |
| Secrets | In cloud-init | Secret Manager, read by the VM at startup |

**Unchanged:** the REST endpoints, JSON shapes, UI pages, roles (seller, customer, admin), COD flow, delivery steps, and the rule that COD stays Pending until cash is confirmed.

## 4. Files that changed
| Folder | Change |
|---|---|
| `backend/services/` | Blob, queue and table services replaced by `storage_service`, `pubsub_service`, `firestore_service`; order, product, auth and worker logic rewritten for Firestore |
| `backend/routes/` | Same endpoints; new `/api/admin/dashboard`, `/storage/selftest`, `/storage/signed-url` |
| `frontend/` | Reused; field rename, labels, and a platform statistics panel |
| `infrastructure/` | Bicep replaced by `terraform/` (network, firewall, storage, firestore, pubsub, iam, compute, load-balancer, monitoring) |
| `scripts/` | `az` scripts replaced by `gcloud` and `terraform` scripts |

## 5. Command equivalents
| Task | Azure | GCP |
|---|---|---|
| Login | `az login` | `gcloud auth login` + `gcloud auth application-default login` (for Terraform) |
| Deploy | `./deploy.sh` (Bicep) | `./deploy.sh` (Terraform) |
| List app VMs | `az vmss list-instances` | `gcloud compute instance-groups managed list-instances` |
| Check roles | `./configure-rbac.sh show` | `./iam-demo.sh show` |
| Remove / restore permission | `./configure-rbac.sh remove / add` | `./iam-demo.sh remove / restore` |
| Run consumer | Admin dashboard button | Admin dashboard button (pulls from Pub/Sub) |
| View storage | Portal, `az storage blob list` | Console, `gcloud storage ls -r gs://BUCKET/` |
| Load test | `configure-vmss.sh load` | `load-test.sh start` |
| Cleanup | delete resource group | `./cleanup.sh` (`terraform destroy`) |

## 6. Demo mapping (60 minutes)
| Azure topic | GCP topic |
|---|---|
| Blob Storage | Cloud Storage buckets and objects |
| Managed Identity + RBAC | Service account + IAM + ADC |
| ASG and NSG | VPC firewall rules, tags, service-account targeting |
| Private Endpoint | Private Google Access |
| Storage Queue + Tables | Pub/Sub + Firestore |
| VMSS autoscaling | MIG autoscaling |
| Azure Monitor | Cloud Logging and Monitoring |

## 7. Migration steps
1. Keep the Azure project as is. Nothing is moved automatically; the two clouds have separate data.
2. Run `./scripts/setup-gcp.sh`, then `./scripts/deploy.sh`.
3. Log in with the printed demo accounts and re-create products in the Seller Portal.
4. Run `python3 scripts/e2e_test.py --url http://<LB_IP>` and `./scripts/test-infra.sh`.
5. Run `./cleanup.sh` for each cloud after class to stop billing.

## 8. Practical differences you will notice
- Terraform needs Application Default Credentials (`gcloud auth application-default login`); Cloud Shell has them already.
- SSH to VMs goes through Identity-Aware Proxy (`--tunnel-through-iap`); there are no public IPs.
- Use `http://` for the demo load-balancer address; HTTPS needs a real domain.
- Pub/Sub has no message peek; use the admin dashboard and `./test-pubsub.sh`.
- Firestore allows one `(default)` database per project.
- Terraform state holds the generated passwords; protect the state file.