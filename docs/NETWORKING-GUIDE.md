# Networking guide
VPC `quickkart-vpc` (custom mode): `quickkart-frontend-subnet 10.20.1.0/24`, `quickkart-backend-subnet 10.20.2.0/24`, both with Private Google Access; Cloud Router + Cloud NAT (outbound for apt/pip). VMs have **no external IPs**.
| Rule | Dir | Prio | Source -> target | Ports |
|---|---|---|---|---|
| allow-lb-frontend | in | 900 | Google LB/health ranges 130.211.0.0/22, 35.191.0.0/16 -> tag `quickkart-frontend` | tcp 80 |
| allow-frontend-backend | in | 900 | **source SA frontend-sa -> target SA backend-sa** | tcp 5000 |
| allow-health-backend | in | 900 | health ranges -> tag `quickkart-backend` | tcp 5000 |
| allow-iap-ssh | in | 1000 | 35.235.240.0/20 (IAP) -> both tags | tcp 22 |
| allow-egress-web | out | 1000 | tags -> 0.0.0.0/0 | tcp 80,443 (Google APIs via PGA, packages via NAT) |
| deny-all-ingress | in | 65000 | 0.0.0.0/0 | all |
Lower priority number wins; rules are stateful (replies allowed). Public traffic: Internet -> external Application LB -> frontend MIG. Backend API is reachable only through the internal passthrough LB `10.20.2.10:5000` from VMs running as `frontend-sa`.
Demo commands:
```bash
gcloud compute firewall-rules list --filter="name~quickkart" --format="table(name,direction,priority,sourceRanges.list(),sourceServiceAccounts.list(),targetTags.list(),targetServiceAccounts.list(),allowed[].map().firewall_rule().list(),denied[].map().firewall_rule().list())"
gcloud compute networks subnets describe quickkart-backend-subnet --region asia-south1 --format="value(ipCidrRange,privateIpGoogleAccess)"
# allow/deny test: from the internet the backend ILB (private IP) is unreachable:   curl -m 5 http://10.20.2.10:5000/api/health   -> timeout
# block frontend->backend: add a higher-priority deny, watch /api/* fail with 502/504, then delete it
gcloud compute firewall-rules create qk-block-demo --network quickkart-vpc --direction INGRESS --priority 500 --action DENY --rules tcp:5000 --source-service-accounts quickkart-frontend-sa@$(gcloud config get-value project).iam.gserviceaccount.com --target-service-accounts quickkart-backend-sa@$(gcloud config get-value project).iam.gserviceaccount.com
gcloud compute firewall-rules delete qk-block-demo --quiet
```
Tags vs service accounts: tags are plain labels (anyone who can edit the instance can change them); service-account targeting follows identity and cannot be spoofed by the VM. Neither equals an Azure ASG object. Private Service Connect for Google APIs is an optional hardening step (not needed: Private Google Access is enabled).
