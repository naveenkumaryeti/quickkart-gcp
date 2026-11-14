resource "google_monitoring_notification_channel" "email" {
  count        = var.alert_email != "" ? 1 : 0
  display_name = "QuickKart alerts"
  type         = "email"
  labels       = { email_address = var.alert_email }
  depends_on   = [google_project_service.api]
}
locals {
  channels = [for c in google_monitoring_notification_channel.email : c.id]
}

resource "google_monitoring_alert_policy" "cpu" {
  display_name          = "QuickKart: high VM CPU"
  combiner              = "OR"
  notification_channels = local.channels
  conditions {
    display_name = "CPU > 80% for 5 min"
    condition_threshold {
      filter          = "metric.type=\"compute.googleapis.com/instance/cpu/utilization\" AND resource.type=\"gce_instance\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0.8
      duration        = "300s"
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }
}
resource "google_monitoring_alert_policy" "backlog" {
  display_name          = "QuickKart: Pub/Sub backlog"
  combiner              = "OR"
  notification_channels = local.channels
  conditions {
    display_name = "undelivered messages > 20 for 5 min"
    condition_threshold {
      filter          = "metric.type=\"pubsub.googleapis.com/subscription/num_undelivered_messages\" AND resource.type=\"pubsub_subscription\" AND resource.label.subscription_id=\"${google_pubsub_subscription.orders.name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 20
      duration        = "300s"
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }
}
resource "google_monitoring_uptime_check_config" "app" {
  display_name = "QuickKart /api/health"
  timeout      = "10s"
  period       = "60s"
  http_check {
    path         = "/api/health"
    port         = 80
    use_ssl      = false
    validate_ssl = false
  }
  monitored_resource {
    type   = "uptime_url"
    labels = { project_id = var.project_id, host = google_compute_global_address.lb.address }
  }
}
resource "google_monitoring_alert_policy" "uptime" {
  display_name          = "QuickKart: application health check failing"
  combiner              = "OR"
  notification_channels = local.channels
  conditions {
    display_name = "uptime check failed"
    condition_threshold {
      filter          = "metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\" AND metric.label.check_id=\"${google_monitoring_uptime_check_config.app.uptime_check_id}\" AND resource.type=\"uptime_url\""
      comparison      = "COMPARISON_GT"
      threshold_value = 1
      duration        = "300s"
      aggregations {
        alignment_period     = "1200s"
        per_series_aligner   = "ALIGN_NEXT_OLDER"
        cross_series_reducer = "REDUCE_COUNT_FALSE"
        group_by_fields      = ["resource.label.*"]
      }
    }
  }
}
# Log-based metric: dead-lettered / repeatedly failing order events
resource "google_logging_metric" "dead_letters" {
  name   = "quickkart_dead_letters"
  filter = "logName:\"quickkart-audit\" AND jsonPayload.eventType=\"queue_message_dead_lettered\""
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}
resource "google_monitoring_alert_policy" "dead_letters" {
  display_name          = "QuickKart: order events dead-lettered (repeated processing failure)"
  combiner              = "OR"
  notification_channels = local.channels
  conditions {
    display_name = "any dead letter"
    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.dead_letters.name}\" AND resource.type=\"global\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }
}
resource "google_monitoring_dashboard" "main" {
  dashboard_json = jsonencode({
    displayName = "QuickKart"
    gridLayout = {
      widgets = [
        { title = "VM CPU utilization", xyChart = { dataSets = [{ timeSeriesQuery = { timeSeriesFilter = { filter = "metric.type=\"compute.googleapis.com/instance/cpu/utilization\" resource.type=\"gce_instance\"", aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_MEAN" } } } }] } },
        { title = "Pub/Sub undelivered messages", xyChart = { dataSets = [{ timeSeriesQuery = { timeSeriesFilter = { filter = "metric.type=\"pubsub.googleapis.com/subscription/num_undelivered_messages\" resource.type=\"pubsub_subscription\"", aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_MEAN" } } } }] } },
        { title = "Load balancer requests", xyChart = { dataSets = [{ timeSeriesQuery = { timeSeriesFilter = { filter = "metric.type=\"loadbalancing.googleapis.com/https/request_count\" resource.type=\"https_lb_rule\"", aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_RATE" } } } }] } },
        { title = "Dead letters (log metric)", xyChart = { dataSets = [{ timeSeriesQuery = { timeSeriesFilter = { filter = "metric.type=\"logging.googleapis.com/user/quickkart_dead_letters\"", aggregation = { alignmentPeriod = "60s", perSeriesAligner = "ALIGN_SUM" } } } }] } }
      ]
    }
  })
}
