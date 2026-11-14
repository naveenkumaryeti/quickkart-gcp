# Dedicated identities. No default Compute Engine service account. NO service account keys are created anywhere.
resource "google_service_account" "backend" {
  account_id   = "${var.name_prefix}-backend-sa"
  display_name = "QuickKart backend (attached to backend MIG)"
  depends_on   = [google_project_service.api]
}
resource "google_service_account" "frontend" {
  account_id   = "${var.name_prefix}-frontend-sa"
  display_name = "QuickKart frontend (no data access)"
  depends_on   = [google_project_service.api]
}
locals {
  be = "serviceAccount:${google_service_account.backend.email}"
  fe = "serviceAccount:${google_service_account.frontend.email}"
}
# --- backend: least privilege, scoped to the specific resources ---
resource "google_storage_bucket_iam_member" "be_data" {
  bucket = google_storage_bucket.data.name
  role   = "roles/storage.objectAdmin"
  member = local.be
}
resource "google_project_iam_member" "be_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = local.be
}
resource "google_pubsub_topic_iam_member" "be_pub" {
  topic  = google_pubsub_topic.orders.name
  role   = "roles/pubsub.publisher"
  member = local.be
}
resource "google_pubsub_subscription_iam_member" "be_sub" {
  subscription = google_pubsub_subscription.orders.name
  role         = "roles/pubsub.subscriber"
  member       = local.be
}
resource "google_pubsub_subscription_iam_member" "be_dlq_sub" {
  subscription = google_pubsub_subscription.dlq.name
  role         = "roles/pubsub.subscriber"
  member       = local.be
}
resource "google_project_iam_member" "be_logs" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = local.be
}
resource "google_project_iam_member" "be_metrics" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = local.be
}
resource "google_secret_manager_secret_iam_member" "be_secrets" {
  for_each  = google_secret_manager_secret.s
  secret_id = each.value.id
  role      = "roles/secretmanager.secretAccessor"
  member    = local.be
}
resource "google_storage_bucket_iam_member" "be_artifacts" {
  bucket = google_storage_bucket.artifacts.name
  role   = "roles/storage.objectViewer"
  member = local.be
}
# signed URLs: the SA may sign blobs as itself (IAM signBlob)
resource "google_service_account_iam_member" "be_self_sign" {
  service_account_id = google_service_account.backend.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = local.be
}
# --- frontend: logs/metrics + download its own code only. No Firestore / data bucket / Pub/Sub / secrets. ---
resource "google_project_iam_member" "fe_logs" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = local.fe
}
resource "google_project_iam_member" "fe_metrics" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = local.fe
}
resource "google_storage_bucket_iam_member" "fe_artifacts" {
  bucket = google_storage_bucket.artifacts.name
  role   = "roles/storage.objectViewer"
  member = local.fe
}
