# GCP firewall rules are VPC-level, stateful, with priority (lower number wins). Targets: network tags and/or service accounts.
resource "google_compute_firewall" "lb_to_frontend" {
  name          = "${var.name_prefix}-allow-lb-frontend"
  network       = google_compute_network.vpc.name
  direction     = "INGRESS"
  priority      = 900
  source_ranges = local.hc_ranges
  target_tags   = [local.fe_tag]
  allow {
    protocol = "tcp"
    ports    = ["80"]
  }
}
# Frontend -> backend: matched by SERVICE ACCOUNT identity (stronger than tags: a VM cannot spoof it)
resource "google_compute_firewall" "frontend_to_backend" {
  name                    = "${var.name_prefix}-allow-frontend-backend"
  network                 = google_compute_network.vpc.name
  direction               = "INGRESS"
  priority                = 900
  source_service_accounts = [google_service_account.frontend.email]
  target_service_accounts = [google_service_account.backend.email]
  allow {
    protocol = "tcp"
    ports    = ["5000"]
  }
}
resource "google_compute_firewall" "health_backend" {
  name          = "${var.name_prefix}-allow-health-backend"
  network       = google_compute_network.vpc.name
  direction     = "INGRESS"
  priority      = 900
  source_ranges = local.hc_ranges
  target_tags   = [local.be_tag]
  allow {
    protocol = "tcp"
    ports    = ["5000"]
  }
}
# Administrative SSH only through Identity-Aware Proxy (no public SSH)
resource "google_compute_firewall" "iap_ssh" {
  name          = "${var.name_prefix}-allow-iap-ssh"
  network       = google_compute_network.vpc.name
  direction     = "INGRESS"
  priority      = 1000
  source_ranges = ["35.235.240.0/20"]
  target_tags   = [local.fe_tag, local.be_tag]
  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
}
resource "google_compute_firewall" "deny_all_ingress" {
  name          = "${var.name_prefix}-deny-all-ingress"
  network       = google_compute_network.vpc.name
  direction     = "INGRESS"
  priority      = 65000
  source_ranges = ["0.0.0.0/0"]
  deny {
    protocol = "all"
  }
}
# Egress: HTTPS/HTTP for Google APIs (Private Google Access) and package mirrors (Cloud NAT)
resource "google_compute_firewall" "egress_web" {
  name               = "${var.name_prefix}-allow-egress-web"
  network            = google_compute_network.vpc.name
  direction          = "EGRESS"
  priority           = 1000
  destination_ranges = ["0.0.0.0/0"]
  target_tags        = [local.fe_tag, local.be_tag]
  allow {
    protocol = "tcp"
    ports    = ["80", "443"]
  }
}
