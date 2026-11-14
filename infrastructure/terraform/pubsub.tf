resource "google_pubsub_topic" "orders" {
  name       = "${var.name_prefix}-order-topic"
  depends_on = [google_project_service.api]
}
resource "google_pubsub_topic" "dlq" {
  name = "${var.name_prefix}-order-dead-letter-topic"
}
resource "google_pubsub_subscription" "orders" {
  name                       = "${var.name_prefix}-order-subscription"
  topic                      = google_pubsub_topic.orders.id
  ack_deadline_seconds       = 30
  message_retention_duration = "604800s"
  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "60s"
  }
  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dlq.id
    max_delivery_attempts = 5 # must match MAX_DELIVERY_ATTEMPTS in backend/config.py (minimum allowed by Pub/Sub is 5)
  }
}
resource "google_pubsub_subscription" "dlq" {
  name                 = "${var.name_prefix}-order-dlq-subscription"
  topic                = google_pubsub_topic.dlq.id
  ack_deadline_seconds = 30
}
# The Pub/Sub service agent forwards dead letters: needs publish on the DLQ topic and subscribe on the source subscription
resource "google_project_service_identity" "pubsub" {
  provider = google-beta
  service  = "pubsub.googleapis.com"
}
resource "google_pubsub_topic_iam_member" "dlq_publisher" {
  topic  = google_pubsub_topic.dlq.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_project_service_identity.pubsub.email}"
}
resource "google_pubsub_subscription_iam_member" "dlq_subscriber" {
  subscription = google_pubsub_subscription.orders.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_project_service_identity.pubsub.email}"
}
