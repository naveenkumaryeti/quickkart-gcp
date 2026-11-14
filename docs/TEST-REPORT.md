# Testing report
| Run | Environment | Result |
|---|---|---|
| `python3 scripts/e2e_test.py --local` | Flask app + **in-memory fakes** for Firestore / Cloud Storage / Pub/Sub | **34 / 34 PASS** (below) |
| `python3 scripts/e2e_test.py --url http://<LB_IP>` | **Real GCP deployment** | **Not run by the author** - run after `deploy.sh` (add `--poison` to include the ~1.5 min dead-letter test) |
| `./scripts/test-infra.sh` | Real GCP (tests 27-30: IAM, firewall, autoscaling, logging/monitoring) | **Not run by the author** |
Honest scope: the offline run validates business logic only (auth/roles, publish rules, server-side pricing, idempotency, stock, outbox, consumer retries and dead-lettering, delivery rules, COD stays Pending, version conflicts, GCS sync). It does **not** prove IAM, networking, Pub/Sub or Firestore behaviour. Python syntax was exercised; Terraform files were parsed (HCL syntax) but **not** `terraform validate`d or applied - run `./scripts/deploy.sh plan` first and fix any provider-version message it reports.
## Offline output
```
== QuickKart GCP acceptance tests
  PASS  TEST    1 - Seller login
  PASS  TEST    2 - Add iPhone 8 (Draft created)
  PASS  TEST    3 - Colour = Burgundy (Monochrome)
  PASS  TEST    4 - Stock = 10 units
  PASS  TEST    5 - Image uploaded to GCS product-images/
  PASS  TEST    6 - Product JSON object in GCS products/
  PASS  TEST    7 - Firestore product document exists (seller list)
  PASS  TEST    8 - Publish -> appears on homepage API (hidden while Draft)
  PASS  TEST  8.1 - Publish without price rejected
  PASS  TEST    9 - Customer login
  PASS  TEST   10 - Product details: name, colour, price, stock
  PASS  TEST   11 - Add to cart
  PASS  TEST   12 - COD available
  PASS  TEST   13 - Order confirmed, unique Order ID (browser price ignored)
  PASS  TEST   14 - Stock 10 -> 9
  PASS  TEST   15 - Order stored in Firestore (readable by owner)
  PASS  TEST   16 - Order event published to Pub/Sub (outbox PUBLISHED)
  PASS  TEST   18 - TableQueue record (Queued)
  PASS  TEST   19 - TableService record
  PASS  TEST   17 - Subscription: consumer receives + processes the message
  PASS  TEST   20 - TableQueue Processed + TableService Processing
  PASS  TEST   21 - Delivery -> Delivered (skipping steps rejected); customer sees it
  PASS  TEST   22 - GCS order archive updated (Delivered + deliveredAt)
  PASS  TEST   23 - Delivery audit event in GCS audit-logs/
  PASS  TEST   24 - COD payment still Pending after delivery
  PASS  TEST 24.1 - Cash collection confirmed -> Paid
  PASS  TEST   25 - Duplicate submission: same order, stock not decremented twice
  PASS  TEST   26 - Insufficient stock / invalid product rejected
  PASS  TEST   X1 - Customer cannot call admin APIs (403); anonymous 401
  PASS  TEST   X2 - Stale version (ETag) update rejected with 409
  PASS  TEST   X3 - Admin dashboard has real counts
  PASS  TEST   X4 - Service-account self-test (upload/read/delete object)
  PASS  TEST   X5 - Retries -> dead-letter topic -> TableQueue Failed
  PASS  TEST   X6 - Reconcile endpoint runs
== PASSED 34/34
```
