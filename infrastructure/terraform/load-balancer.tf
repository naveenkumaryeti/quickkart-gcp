# ---- Internal passthrough load balancer in front of the backend MIG (private IP only) ----
resource "google_compute_region_health_check" "backend_ilb" {
  name   = "${var.name_prefix}-backend-ilb-hc"
  region = var.region
  http_health_check {
    port         = 5000
    request_path = "/api/health"
  }
}
resource "google_compute_region_backend_service" "backend" {
  name                  = "${var.name_prefix}-backend-ilb"
  region                = var.region
  protocol              = "TCP"
  load_balancing_scheme = "INTERNAL"
  network               = google_compute_network.vpc.id
  health_checks         = [google_compute_region_health_check.backend_ilb.id]
  backend {
    group          = google_compute_region_instance_group_manager.backend.instance_group
    balancing_mode = "CONNECTION"
  }
}
resource "google_compute_forwarding_rule" "backend_ilb" {
  name                  = "${var.name_prefix}-backend-ilb-fr"
  region                = var.region
  load_balancing_scheme = "INTERNAL"
  backend_service       = google_compute_region_backend_service.backend.id
  network               = google_compute_network.vpc.id
  subnetwork            = google_compute_subnetwork.backend.id
  ip_address            = var.backend_ilb_ip
  ip_protocol           = "TCP"
  ports                 = ["5000"]
}
# ---- External Application Load Balancer (global) in front of the frontend MIG ----
resource "google_compute_global_address" "lb" {
  name = "${var.name_prefix}-lb-ip"
}
resource "google_compute_backend_service" "frontend" {
  name                  = "${var.name_prefix}-frontend-bs"
  protocol              = "HTTP"
  port_name             = "http"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  timeout_sec           = 60
  health_checks         = [google_compute_health_check.frontend.id]
  backend {
    group           = google_compute_region_instance_group_manager.frontend.instance_group
    balancing_mode  = "UTILIZATION"
    max_utilization = 0.8
  }
  log_config {
    enable = true
  }
}
resource "google_compute_url_map" "lb" {
  name            = "${var.name_prefix}-url-map"
  default_service = google_compute_backend_service.frontend.id
}
resource "google_compute_target_http_proxy" "http" {
  name    = "${var.name_prefix}-http-proxy"
  url_map = google_compute_url_map.lb.id
}
resource "google_compute_global_forwarding_rule" "http" {
  name                  = "${var.name_prefix}-http-fr"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  target                = google_compute_target_http_proxy.http.id
  port_range            = "80"
  ip_address            = google_compute_global_address.lb.id
}
# HTTPS with a Google-managed certificate (only when var.domain is set; DNS A record must point to the LB IP)
resource "google_compute_managed_ssl_certificate" "cert" {
  count = var.domain != "" ? 1 : 0
  name  = "${var.name_prefix}-cert"
  managed {
    domains = [var.domain]
  }
}
resource "google_compute_target_https_proxy" "https" {
  count            = var.domain != "" ? 1 : 0
  name             = "${var.name_prefix}-https-proxy"
  url_map          = google_compute_url_map.lb.id
  ssl_certificates = [google_compute_managed_ssl_certificate.cert[0].id]
}
resource "google_compute_global_forwarding_rule" "https" {
  count                 = var.domain != "" ? 1 : 0
  name                  = "${var.name_prefix}-https-fr"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  target                = google_compute_target_https_proxy.https[0].id
  port_range            = "443"
  ip_address            = google_compute_global_address.lb.id
}
