#!/bin/bash
# Frontend VM bootstrap: nginx serves the static site and proxies /api to the internal load balancer of the backend tier.
set -eu
export DEBIAN_FRONTEND=noninteractive
apt-get update -y && apt-get install -y nginx
gcloud storage cp "gs://${artifacts_bucket}/${object}" /tmp/frontend.tgz
rm -rf /var/www/html/* && tar xzf /tmp/frontend.tgz -C /var/www/html
rm -f /etc/nginx/sites-enabled/default
cat > /etc/nginx/conf.d/quickkart.conf <<NGINX
server {
  listen 80 default_server;
  root /var/www/html;
  index index.html;
  client_max_body_size 6m;
  location /api/ { proxy_pass http://${backend_ip}:5000; proxy_read_timeout 60s; }
}
NGINX
systemctl restart nginx
