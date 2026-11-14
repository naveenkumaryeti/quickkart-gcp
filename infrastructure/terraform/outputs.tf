output "load_balancer_ip" { value = google_compute_global_address.lb.address }
output "url" { value = "http://${google_compute_global_address.lb.address}" }
output "data_bucket" { value = google_storage_bucket.data.name }
output "artifacts_bucket" { value = google_storage_bucket.artifacts.name }
output "backend_service_account" { value = google_service_account.backend.email }
output "frontend_service_account" { value = google_service_account.frontend.email }
output "pubsub_topic" { value = google_pubsub_topic.orders.name }
output "pubsub_subscription" { value = google_pubsub_subscription.orders.name }
output "backend_ilb_ip" { value = var.backend_ilb_ip }
output "secret_names" { value = [for s in google_secret_manager_secret.s : s.secret_id] }
output "credential_commands" {
  value = "gcloud secrets versions access latest --secret=${var.name_prefix}-seller-password   (also -admin-password, -customer-password)"
}
