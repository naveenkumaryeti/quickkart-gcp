data "google_project" "this" {}

locals {
  bucket      = var.bucket_name != "" ? var.bucket_name : "${var.project_id}-${var.name_prefix}-storage"
  artifacts   = "${var.project_id}-${var.name_prefix}-artifacts"
  apis        = ["compute", "storage", "firestore", "pubsub", "iam", "iamcredentials", "cloudresourcemanager", "logging", "monitoring", "secretmanager", "cloudbuild"]
  fe_tag      = "${var.name_prefix}-frontend"
  be_tag      = "${var.name_prefix}-backend"
  hc_ranges   = ["130.211.0.0/22", "35.191.0.0/16"] # Google health-check + load balancer proxy ranges
  secret_ids  = ["session-secret", "seller-password", "admin-password", "customer-password"]
}

resource "google_project_service" "api" {
  for_each           = toset(local.apis)
  service            = "${each.key}.googleapis.com"
  disable_on_destroy = false
}

# ---- Secrets (Secret Manager). Values are generated here; they live in Terraform STATE - protect the state bucket. ----
resource "random_password" "secret" {
  for_each = toset(local.secret_ids)
  length   = 20
  special  = false
}
resource "google_secret_manager_secret" "s" {
  for_each  = toset(local.secret_ids)
  secret_id = "${var.name_prefix}-${each.key}"
  replication {
    auto {}
  }
  depends_on = [google_project_service.api]
}
resource "google_secret_manager_secret_version" "v" {
  for_each    = toset(local.secret_ids)
  secret      = google_secret_manager_secret.s[each.key].id
  secret_data = random_password.secret[each.key].result
}

# ---- Application artifacts (code tarballs) in a separate private bucket; VMs download with their own service account ----
resource "google_storage_bucket" "artifacts" {
  name                        = local.artifacts
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = true
  depends_on                  = [google_project_service.api]
}
data "archive_file" "backend" {
  type        = "tar.gz"
  source_dir  = "${path.module}/../../backend"
  output_path = "${path.module}/.build/backend.tar.gz"
  excludes    = ["__pycache__"]
}
data "archive_file" "frontend" {
  type        = "tar.gz"
  source_dir  = "${path.module}/../../frontend"
  output_path = "${path.module}/.build/frontend.tar.gz"
}
resource "google_storage_bucket_object" "backend" {
  name   = "backend-${data.archive_file.backend.output_md5}.tar.gz"
  bucket = google_storage_bucket.artifacts.name
  source = data.archive_file.backend.output_path
}
resource "google_storage_bucket_object" "frontend" {
  name   = "frontend-${data.archive_file.frontend.output_md5}.tar.gz"
  bucket = google_storage_bucket.artifacts.name
  source = data.archive_file.frontend.output_path
}
