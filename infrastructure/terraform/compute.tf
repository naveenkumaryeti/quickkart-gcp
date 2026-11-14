data "google_compute_image" "debian" {
  family  = "debian-12" # includes gcloud and the guest environment
  project = "debian-cloud"
}

resource "google_compute_instance_template" "backend" {
  name_prefix  = "${var.name_prefix}-backend-"
  machine_type = var.machine_type
  tags         = [local.be_tag]
  disk {
    source_image = data.google_compute_image.debian.self_link
    boot         = true
    disk_size_gb = 20
  }
  network_interface {
    subnetwork = google_compute_subnetwork.backend.id # no access_config => no external IP
  }
  service_account {
    email  = google_service_account.backend.email # ATTACHED identity -> ADC in the application
    scopes = ["cloud-platform"]                   # scopes open the door; IAM roles decide what is allowed
  }
  shielded_instance_config {
    enable_secure_boot = true
  }
  metadata = {
    enable-oslogin = "TRUE"
    startup-script = templatefile("${path.module}/startup-backend.sh.tpl", {
      artifacts_bucket = google_storage_bucket.artifacts.name, object = google_storage_bucket_object.backend.name, project_id = var.project_id, region = var.region,
      bucket = google_storage_bucket.data.name, topic = google_pubsub_topic.orders.name, subscription = google_pubsub_subscription.orders.name,
      dlq_subscription = google_pubsub_subscription.dlq.name, sa_email = google_service_account.backend.email, prefix = var.name_prefix })
  }
  lifecycle {
    create_before_destroy = true
  }
  depends_on = [google_secret_manager_secret_iam_member.be_secrets, google_secret_manager_secret_version.v]
}
resource "google_compute_instance_template" "frontend" {
  name_prefix  = "${var.name_prefix}-frontend-"
  machine_type = var.machine_type
  tags         = [local.fe_tag]
  disk {
    source_image = data.google_compute_image.debian.self_link
    boot         = true
    disk_size_gb = 20
  }
  network_interface {
    subnetwork = google_compute_subnetwork.frontend.id
  }
  service_account {
    email  = google_service_account.frontend.email
    scopes = ["cloud-platform"]
  }
  shielded_instance_config {
    enable_secure_boot = true
  }
  metadata = {
    enable-oslogin = "TRUE"
    startup-script = templatefile("${path.module}/startup-frontend.sh.tpl", {
      artifacts_bucket = google_storage_bucket.artifacts.name, object = google_storage_bucket_object.frontend.name, backend_ip = var.backend_ilb_ip })
  }
  lifecycle {
    create_before_destroy = true
  }
}

resource "google_compute_health_check" "backend" {
  name = "${var.name_prefix}-backend-hc"
  http_health_check {
    port         = 5000
    request_path = "/api/health"
  }
  check_interval_sec  = 10
  timeout_sec         = 5
  healthy_threshold   = 2
  unhealthy_threshold = 3
}
resource "google_compute_health_check" "frontend" {
  name = "${var.name_prefix}-frontend-hc"
  http_health_check {
    port         = 80
    request_path = "/"
  }
  check_interval_sec  = 10
  timeout_sec         = 5
  healthy_threshold   = 2
  unhealthy_threshold = 3
}

resource "google_compute_region_instance_group_manager" "backend" {
  name               = "${var.name_prefix}-backend-mig"
  base_instance_name = "${var.name_prefix}-be"
  region             = var.region
  target_size        = 2 # starts with 2; the autoscaler (min 1, max 4) then takes over
  version {
    instance_template = google_compute_instance_template.backend.id
  }
  named_port {
    name = "api"
    port = 5000
  }
  auto_healing_policies {
    health_check      = google_compute_health_check.backend.id
    initial_delay_sec = 400
  }
  update_policy { # rolling update when the template changes (new code)
    type                  = "PROACTIVE"
    minimal_action        = "REPLACE"
    max_surge_fixed       = 3
    max_unavailable_fixed = 3
  }
  lifecycle {
    ignore_changes = [target_size]
  }
}
resource "google_compute_region_instance_group_manager" "frontend" {
  name               = "${var.name_prefix}-frontend-mig"
  base_instance_name = "${var.name_prefix}-fe"
  region             = var.region
  target_size        = 2
  version {
    instance_template = google_compute_instance_template.frontend.id
  }
  named_port {
    name = "http"
    port = 80
  }
  auto_healing_policies {
    health_check      = google_compute_health_check.frontend.id
    initial_delay_sec = 300
  }
  update_policy {
    type                  = "PROACTIVE"
    minimal_action        = "REPLACE"
    max_surge_fixed       = 3
    max_unavailable_fixed = 3
  }
  lifecycle {
    ignore_changes = [target_size]
  }
}
resource "google_compute_region_autoscaler" "backend" {
  name   = "${var.name_prefix}-backend-as"
  region = var.region
  target = google_compute_region_instance_group_manager.backend.id
  autoscaling_policy {
    min_replicas    = 1
    max_replicas    = 4
    cooldown_period = 120
    cpu_utilization {
      target = 0.7 # above 70% average CPU -> scale out; scale-in follows the stabilisation period
    }
  }
}
resource "google_compute_region_autoscaler" "frontend" {
  name   = "${var.name_prefix}-frontend-as"
  region = var.region
  target = google_compute_region_instance_group_manager.frontend.id
  autoscaling_policy {
    min_replicas    = 1
    max_replicas    = 4
    cooldown_period = 120
    cpu_utilization {
      target = 0.7
    }
  }
}
