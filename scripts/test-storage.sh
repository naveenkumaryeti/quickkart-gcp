#!/usr/bin/env bash
# Cloud Storage + ADC proof FROM a backend VM (uses the attached service account; no keys).  ./test-storage.sh
set -euo pipefail; source "$(dirname "$0")/env.sh"
VM=$(gcloud compute instances list --filter="name~$PREFIX-be" --format="value(name,zone)" | head -1); N=${VM%%[[:space:]]*}; Z=${VM##*[[:space:]]}
gcloud compute ssh "$N" --zone "$Z" --tunnel-through-iap --command "
set -e; echo '{\"test\":\"hello from backend VM\"}' > /tmp/t.json
echo '== identity:'; curl -s -H 'Metadata-Flavor: Google' http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/email; echo
gcloud storage cp /tmp/t.json gs://$BUCKET/backups/test-vm.json && echo UPLOAD-OK
gcloud storage cat gs://$BUCKET/backups/test-vm.json && echo READ-OK
gcloud storage rm gs://$BUCKET/backups/test-vm.json && echo DELETE-OK"
echo "== from your own machine the bucket is also private (public access prevention):"
curl -s -o /dev/null -w "HTTP %{http_code} (expect 401/403)\n" "https://storage.googleapis.com/$BUCKET/products/x.json"
