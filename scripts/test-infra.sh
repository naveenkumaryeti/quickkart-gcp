#!/usr/bin/env bash
# Infrastructure acceptance checks (tests 27-30).  ./test-infra.sh
set -uo pipefail; source "$(dirname "$0")/env.sh"; P=0; F=0
chk() { if eval "$2" >/dev/null 2>&1; then echo "  PASS  $1"; P=$((P+1)); else echo "  FAIL  $1"; F=$((F+1)); fi; }
IP=$(lb_ip)
chk "27 backend SA holds objectAdmin on the data bucket only (no keys exist)" "gcloud storage buckets get-iam-policy gs://$BUCKET --format=json | grep -q $BACKEND_SA && [ -z \"\$(gcloud iam service-accounts keys list --iam-account=$BACKEND_SA --managed-by=user --format='value(name)')\" ]"
chk "27 app reaches GCS/Firestore/Pub/Sub with the attached SA (deep health)" "curl -fsS http://$IP/api/health?deep=1 | grep -q '\"ok\": *true'"
chk "28 firewall: deny-all ingress + SA-based frontend->backend rule exist" "gcloud compute firewall-rules list --filter='name~$PREFIX' --format='value(name)' | grep -q deny-all && gcloud compute firewall-rules describe $PREFIX-allow-frontend-backend --format='value(sourceServiceAccounts)' | grep -q frontend-sa"
chk "28 backend ILB $(terraform -chdir=$TF output -raw backend_ilb_ip) is NOT reachable from the internet (private IP)" "! curl -s -m 5 http://$(terraform -chdir=$TF output -raw backend_ilb_ip):5000/api/health"
chk "29 autoscalers: min 1 / max 4, CPU target 0.7" "gcloud compute region-autoscalers describe $PREFIX-backend-as --region $GCP_REGION --format='value(autoscalingPolicy.maxNumReplicas,autoscalingPolicy.cpuUtilization.utilizationTarget)' | grep -q '4.*0.7'"
chk "30 audit log entries visible in Cloud Logging" "[ -n \"\$(gcloud logging read 'logName:quickkart-audit' --limit=1 --format='value(timestamp)')\" ]"
chk "30 dashboard + alert policies exist" "gcloud alpha monitoring policies list --format='value(displayName)' | grep -q QuickKart"
echo "== PASS=$P FAIL=$F"; [ $F -eq 0 ]
