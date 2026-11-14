#!/usr/bin/env bash
# Full deployment with Terraform. ./deploy.sh [plan]       (cost: ~ $5-8/day, see docs/DEPLOYMENT.md - run cleanup.sh afterwards)
set -euo pipefail; source "$(dirname "$0")/env.sh"
"$ROOT/scripts/setup-gcp.sh"
cd "$TF"
[ -f terraform.tfvars ] || printf 'project_id = "%s"\nregion = "%s"\nzone = "%s"\n' "$GCP_PROJECT_ID" "$GCP_REGION" "$GCP_ZONE" > terraform.tfvars
terraform init -input=false
terraform validate
terraform plan -input=false -out=tfplan
[ "${1:-}" = "plan" ] && exit 0
terraform apply -input=false tfplan
mkdir -p "$ROOT/scripts/.state"; ST="$ROOT/scripts/.state/credentials.env"
{ for r in seller admin customer; do
    echo "QK_${r^^}_EMAIL=$r@quickkart.demo"; echo "QK_${r^^}_PASSWORD=$(gcloud secrets versions access latest --secret=$PREFIX-$r-password)"; done; } > "$ST"; chmod 600 "$ST"
IP=$(lb_ip); echo "== waiting for the site (VMs install packages, 4-8 min): http://$IP"
for i in $(seq 1 60); do curl -fsS "http://$IP/api/health" >/dev/null 2>&1 && break; sleep 15; done
echo "Open:  http://$IP        (HTTP demo; set var domain for HTTPS)"
echo "Credentials (scripts/.state/credentials.env):"; sed 's/^/   /' "$ST"
echo "Test:  python3 $(W "$ROOT/scripts/e2e_test.py") --url http://$IP"
