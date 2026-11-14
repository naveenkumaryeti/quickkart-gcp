#!/usr/bin/env bash
# Generate CPU load on all backend instances to demonstrate autoscaling.  ./load-test.sh start|status|stop
set -euo pipefail; source "$(dirname "$0")/env.sh"
inst() { gcloud compute instance-groups managed list-instances "$PREFIX-backend-mig" --region "$GCP_REGION" --format="value(name,instance.scope().segment(0))" ; }
case "${1:-status}" in
  start) gcloud compute instance-groups managed list-instances "$PREFIX-backend-mig" --region "$GCP_REGION" --format="value(instance)" | while read -r u; do N=${u##*/}; Z=$(echo "$u" | sed 's#.*/zones/\([^/]*\)/.*#\1#')
           gcloud compute ssh "$N" --zone "$Z" --tunnel-through-iap --command "nohup stress-ng --cpu 0 --timeout 900s >/dev/null 2>&1 &" ; done; echo "Load started (15 min). Watch: $0 status" ;;
  stop)  gcloud compute instance-groups managed list-instances "$PREFIX-backend-mig" --region "$GCP_REGION" --format="value(instance)" | while read -r u; do N=${u##*/}; Z=$(echo "$u" | sed 's#.*/zones/\([^/]*\)/.*#\1#')
           gcloud compute ssh "$N" --zone "$Z" --tunnel-through-iap --command "pkill stress-ng || true"; done ;;
  status) gcloud compute instance-groups managed list-instances "$PREFIX-backend-mig" --region "$GCP_REGION"; gcloud compute region-autoscalers describe "$PREFIX-backend-as" --region "$GCP_REGION" --format="yaml(status,recommendedSize,autoscalingPolicy)" ;;
esac
