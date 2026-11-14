#!/bin/bash
# Backend VM bootstrap. Runs as root on every boot. No credentials are embedded: gcloud/ADC use the ATTACHED service account.
set -eu
export DEBIAN_FRONTEND=noninteractive
apt-get update -y && apt-get install -y python3-venv python3-pip stress-ng
mkdir -p /opt/quickkart/app
gcloud storage cp "gs://${artifacts_bucket}/${object}" /tmp/backend.tgz
tar xzf /tmp/backend.tgz -C /opt/quickkart/app
python3 -m venv /opt/quickkart/venv
/opt/quickkart/venv/bin/pip install -q -r /opt/quickkart/app/requirements.txt
sec() { for i in $(seq 1 20); do gcloud secrets versions access latest --secret="${prefix}-$1" && return 0; sleep 15; done; return 1; }
umask 077
cat > /etc/quickkart.env <<ENV
GCP_PROJECT_ID=${project_id}
GCP_REGION=${region}
GCS_BUCKET_NAME=${bucket}
FIRESTORE_DATABASE=(default)
PUBSUB_TOPIC=${topic}
PUBSUB_SUBSCRIPTION=${subscription}
PUBSUB_DLQ_SUBSCRIPTION=${dlq_subscription}
BACKEND_SERVICE_ACCOUNT=${sa_email}
SESSION_SECRET=$(sec session-secret)
SEED_SELLER_PASSWORD=$(sec seller-password)
SEED_ADMIN_PASSWORD=$(sec admin-password)
SEED_CUSTOMER_PASSWORD=$(sec customer-password)
ENV
cat > /etc/systemd/system/quickkart.service <<UNIT
[Unit]
Description=QuickKart Flask API
After=network-online.target
[Service]
DynamicUser=yes
WorkingDirectory=/opt/quickkart/app
EnvironmentFile=/etc/quickkart.env
ExecStart=/opt/quickkart/venv/bin/gunicorn -w 2 --threads 4 -b 0.0.0.0:5000 app:app
Restart=always
[Install]
WantedBy=multi-user.target
UNIT
cat > /etc/systemd/system/quickkart-worker.service <<UNIT
[Unit]
Description=QuickKart Pub/Sub consumer (disabled by default; enable: systemctl enable --now quickkart-worker)
After=network-online.target
[Service]
DynamicUser=yes
WorkingDirectory=/opt/quickkart/app
EnvironmentFile=/etc/quickkart.env
ExecStart=/opt/quickkart/venv/bin/python worker.py
Restart=always
UNIT
systemctl daemon-reload
systemctl enable quickkart
systemctl restart quickkart
