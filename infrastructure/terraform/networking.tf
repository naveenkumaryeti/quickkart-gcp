resource "google_compute_network" "vpc" {
  name                    = "${var.name_prefix}-vpc"
  auto_create_subnetworks = false
  depends_on              = [google_project_service.api]
}
resource "google_compute_subnetwork" "frontend" {
  name                     = "${var.name_prefix}-frontend-subnet"
  region                   = var.region
  network                  = google_compute_network.vpc.id
  ip_cidr_range            = var.vpc_cidr_frontend
  private_ip_google_access = true # VMs without external IPs reach Google APIs (GCS, Firestore, Pub/Sub, Secret Manager)
}
resource "google_compute_subnetwork" "backend" {
  name                     = "${var.name_prefix}-backend-subnet"
  region                   = var.region
  network                  = google_compute_network.vpc.id
  ip_cidr_range            = var.vpc_cidr_backend
  private_ip_google_access = true
}
# Cloud NAT: outbound internet ONLY for apt/pip at boot (VMs have no external IPs)
resource "google_compute_router" "r" {
  name    = "${var.name_prefix}-router"
  region  = var.region
  network = google_compute_network.vpc.id
}
resource "google_compute_router_nat" "nat" {
  name                               = "${var.name_prefix}-nat"
  router                             = google_compute_router.r.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"
}
