#!/usr/bin/env bash
# Roll out new application code: Terraform re-packages the code, creates new instance templates and the MIGs rolling-replace the VMs.
set -euo pipefail; source "$(dirname "$0")/env.sh"
terraform -chdir="$TF" apply -auto-approve -input=false
echo "Rolling update started: gcloud compute instance-groups managed describe $PREFIX-backend-mig --region $GCP_REGION --format='value(status.versionTarget.isReached)'"
