#!/usr/bin/env bash
# IAM demonstration (requirement 7).  ./iam-demo.sh show|identity|remove|restore|selftest
#   show      list the backend service account's roles          identity  prove the attached identity from the VM (no token printed)
#   remove    remove Storage Object Admin (bucket scope)        restore   add it back
#   selftest  call the app's service-account self-test (upload/read/delete object) - fails with 403 while the role is removed
set -euo pipefail; source "$(dirname "$0")/env.sh"
ROLE="roles/storage.objectAdmin"
case "${1:-show}" in
  show) echo "== bucket policy"; gcloud storage buckets get-iam-policy "gs://$BUCKET" --format="table(bindings.role,bindings.members)"
        echo "== project roles of $BACKEND_SA"; gcloud projects get-iam-policy "$GCP_PROJECT_ID" --flatten="bindings[].members" --filter="bindings.members:$BACKEND_SA" --format="value(bindings.role)"
        echo "== service account keys (must be empty = no keys):"; gcloud iam service-accounts keys list --iam-account="$BACKEND_SA" --managed-by=user ;;
  identity) VM=$(gcloud compute instances list --filter="name~$PREFIX-be" --format="value(name,zone)" | head -1); N=${VM%%[[:space:]]*}; Z=${VM##*[[:space:]]}
        gcloud compute ssh "$N" --zone "$Z" --tunnel-through-iap --command 'curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/email"; echo; gcloud auth list' ;;
  remove) gcloud storage buckets remove-iam-policy-binding "gs://$BUCKET" --member="serviceAccount:$BACKEND_SA" --role="$ROLE"; echo "Removed. Wait ~60 s, then run: $0 selftest   (expect 403 AUTHORIZATION_FAILED)" ;;
  restore) gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" --member="serviceAccount:$BACKEND_SA" --role="$ROLE" >/dev/null; echo "Restored. Wait ~60 s, then: $0 selftest   (expect upload/read/delete true)" ;;
  selftest) . "$ROOT/scripts/.state/credentials.env"; IP=$(lb_ip)
        T=$(curl -s -X POST "http://$IP/api/auth/login" -H 'Content-Type: application/json' -d "{\"email\":\"$QK_ADMIN_EMAIL\",\"password\":\"$QK_ADMIN_PASSWORD\"}" | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")
        curl -s -w "\nHTTP %{http_code}\n" -H "Authorization: Bearer $T" "http://$IP/api/admin/storage/selftest" ;;
  *) echo "usage: $0 show|identity|remove|restore|selftest"; exit 1 ;;
esac
