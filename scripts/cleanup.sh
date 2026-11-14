#!/usr/bin/env bash
# Destroy everything created by Terraform (stops billing). Asks for confirmation. Never run automatically.
set -euo pipefail; source "$(dirname "$0")/env.sh"
read -rp "Destroy ALL QuickKart resources in project $GCP_PROJECT_ID? (type yes) " a
[ "$a" = yes ] && terraform -chdir="$TF" destroy -input=false && echo "Destroyed. Check: gcloud compute instances list; gcloud storage buckets list"
echo "Note: the Firestore (default) database is deleted by Terraform; if destroy reports a protected resource, delete it in Console > Firestore."
