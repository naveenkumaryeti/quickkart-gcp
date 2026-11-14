#!/usr/bin/env bash
# Phase 0: verify the environment and enable APIs.  ./setup-gcp.sh
set -euo pipefail; source "$(dirname "$0")/env.sh"
command -v gcloud >/dev/null || { echo "gcloud not found. Use Cloud Shell or install the Google Cloud CLI."; exit 1; }
echo "== account";  gcloud auth list --filter=status:ACTIVE --format="value(account)"
echo "== project";  echo "$GCP_PROJECT_ID"; [ -n "$GCP_PROJECT_ID" ] || { echo "No project: gcloud config set project <id>"; exit 1; }
echo "== billing";  gcloud billing projects describe "$GCP_PROJECT_ID" --format="value(billingEnabled)"
echo "== enabling APIs (1-2 min)"
gcloud services enable compute.googleapis.com storage.googleapis.com firestore.googleapis.com pubsub.googleapis.com iam.googleapis.com iamcredentials.googleapis.com \
  cloudresourcemanager.googleapis.com logging.googleapis.com monitoring.googleapis.com secretmanager.googleapis.com cloudbuild.googleapis.com
echo "== enabled APIs"; gcloud services list --enabled --format="value(config.name)" | grep -E "compute|storage|firestore|pubsub|iam|logging|monitoring|secretmanager" | sort
echo "== Application Default Credentials (needed by Terraform on this machine)"
if ! gcloud auth application-default print-access-token >/dev/null 2>&1; then
  echo "No ADC found: opening the browser login (one time)..."; gcloud auth application-default login
fi
gcloud auth application-default set-quota-project "$GCP_PROJECT_ID" >/dev/null 2>&1 || true
echo "ADC OK"