#!/usr/bin/env bash
# Pub/Sub inspection.  ./test-pubsub.sh
set -euo pipefail; source "$(dirname "$0")/env.sh"
echo "== topic";        gcloud pubsub topics describe "$PREFIX-order-topic"
echo "== subscription (ack deadline, retry, dead-letter policy)"; gcloud pubsub subscriptions describe "$PREFIX-order-subscription" --format="yaml(ackDeadlineSeconds,retryPolicy,deadLetterPolicy,messageRetentionDuration)"
echo "== peek 5 messages WITHOUT acknowledging (they stay in the backlog)"; gcloud pubsub subscriptions pull "$PREFIX-order-subscription" --limit=5 --format=json || true
echo "== dead-letter subscription"; gcloud pubsub subscriptions pull "$PREFIX-order-dlq-subscription" --limit=5 --format=json || true
echo "== backlog metric (Cloud Console: Monitoring > Metrics Explorer > pubsub.googleapis.com/subscription/num_undelivered_messages)"
