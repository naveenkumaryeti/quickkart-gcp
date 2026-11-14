# One (default) Firestore database per project. If it already exists: terraform import google_firestore_database.db "projects/<id>/databases/(default)"
resource "google_firestore_database" "db" {
  name                = "(default)"
  location_id         = var.firestore_location
  type                = "FIRESTORE_NATIVE"
  deletion_policy     = "DELETE"
  depends_on          = [google_project_service.api]
}
# All application queries use single-field or equality-only filters (automatic indexes). No composite index is required.
