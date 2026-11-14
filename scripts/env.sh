#!/usr/bin/env bash
# Shared parameters (override by exporting before running). Nothing is hard-coded: the active gcloud project is used.
export MSYS_NO_PATHCONV=1
export GCP_PROJECT_ID="${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
export GCP_REGION="${GCP_REGION:-asia-south1}"
export GCP_ZONE="${GCP_ZONE:-asia-south1-a}"
export ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PREFIX="${PREFIX:-quickkart}"
export BACKEND_SA="$PREFIX-backend-sa@$GCP_PROJECT_ID.iam.gserviceaccount.com"
export BUCKET="${GCS_BUCKET_NAME:-$GCP_PROJECT_ID-$PREFIX-storage}"
lb_ip() { terraform -chdir="$TF" output -raw load_balancer_ip; }
W() { if command -v cygpath >/dev/null 2>&1; then cygpath -m "$1"; else echo "$1"; fi; }
export TF="$(W "$ROOT/infrastructure/terraform")"   # native Windows path (C:/...) so terraform.exe can open it