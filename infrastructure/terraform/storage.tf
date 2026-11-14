resource "google_storage_bucket" "data" {
  name                        = local.bucket
  location                    = var.region
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced" # bucket can never be made public
  force_destroy               = var.force_destroy_bucket
  versioning {
    enabled = true # backup demo: restore overwritten/deleted objects
  }
  lifecycle_rule {
    condition {
      num_newer_versions = 5
      with_state         = "ARCHIVED"
    }
    action {
      type = "Delete"
    }
  }
  lifecycle_rule {
    condition {
      age            = 30
      matches_prefix = ["backups/"]
    }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }
  dynamic "retention_policy" {
    for_each = var.retention_days > 0 ? [1] : []
    content {
      retention_period = var.retention_days * 86400
    }
  }
  depends_on = [google_project_service.api]
}
