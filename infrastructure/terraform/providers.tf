terraform {
  required_version = ">= 1.5"
  required_providers {
    google      = { source = "hashicorp/google", version = "~> 5.40" }
    google-beta = { source = "hashicorp/google-beta", version = "~> 5.40" }
    random      = { source = "hashicorp/random", version = "~> 3.6" }
    archive     = { source = "hashicorp/archive", version = "~> 2.4" }
  }
  # Shared environments: store state in a protected GCS bucket (supports state locking). Create the bucket once, then:
  #   terraform init -backend-config="bucket=<state-bucket>" -backend-config="prefix=quickkart"
  # Remove this block for a local-state classroom run.
  # backend "gcs" {}
}

provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}
provider "google-beta" {
  project = var.project_id
  region  = var.region
}
