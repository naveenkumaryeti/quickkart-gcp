"""Configuration - environment variables only. No project ids, bucket names, keys or passwords in code (docs/DEPLOYMENT.md)."""
import logging
import os
import secrets

PROJECT = os.environ.get("GCP_PROJECT_ID") or None          # None -> project of the attached service account (ADC)
REGION = os.environ.get("GCP_REGION", "asia-south1")
BUCKET = os.environ.get("GCS_BUCKET_NAME", "")
FIRESTORE_DB = os.environ.get("FIRESTORE_DATABASE", "(default)")
TOPIC = os.environ.get("PUBSUB_TOPIC", "quickkart-order-topic")
SUBSCRIPTION = os.environ.get("PUBSUB_SUBSCRIPTION", "quickkart-order-subscription")
DLQ_SUBSCRIPTION = os.environ.get("PUBSUB_DLQ_SUBSCRIPTION", "quickkart-order-dlq-subscription")
BACKEND_SERVICE_ACCOUNT = os.environ.get("BACKEND_SERVICE_ACCOUNT", "")   # informational only
MAX_DELIVERY_ATTEMPTS = 5                                    # must match terraform dead_letter_policy

PREFIXES = ["products", "product-images", "orders", "audit-logs", "backups"]   # logical folders in the bucket
MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}

SESSION_SECRET = os.environ.get("SESSION_SECRET", "")
if not SESSION_SECRET:
    SESSION_SECRET = secrets.token_hex(32)
    logging.warning("SESSION_SECRET not set: random per-process key (tokens will not work across instances)")
TOKEN_MAX_AGE = 8 * 3600
SEEDS = [("seller", os.environ.get("SEED_SELLER_EMAIL", "seller@quickkart.demo"), os.environ.get("SEED_SELLER_PASSWORD", ""), "SELLER001", "Demo Seller"),
         ("admin", os.environ.get("SEED_ADMIN_EMAIL", "admin@quickkart.demo"), os.environ.get("SEED_ADMIN_PASSWORD", ""), "ADMIN001", "Delivery Admin"),
         ("customer", os.environ.get("SEED_CUSTOMER_EMAIL", "customer@quickkart.demo"), os.environ.get("SEED_CUSTOMER_PASSWORD", ""), "CUST001", "Demo Customer")]
