"""Cloud Storage access (private bucket, uniform bucket-level access, IAM only). Objects: products/, product-images/, orders/, audit-logs/, backups/"""
import json
from datetime import timedelta

import google.auth
from google.api_core.exceptions import NotFound, PreconditionFailed
from google.auth.transport.requests import Request
from google.cloud import storage

import config

_c = None


def client():
    global _c
    if _c is None:
        _c = storage.Client(project=config.PROJECT)
    return _c


def bucket():
    return client().bucket(config.BUCKET)


def put(name, data, content_type, metadata=None):
    b = bucket().blob(name)
    b.metadata = metadata or {}
    b.upload_from_string(data, content_type=content_type)
    return b.generation


def put_json(name, obj, metadata=None):
    """Overwrite with an object-generation precondition (safe against concurrent writers; retried on conflict)."""
    data = json.dumps(obj, indent=2).encode()
    for _ in range(4):
        try:
            cur = bucket().blob(name); cur.reload(); gen = cur.generation
        except NotFound:
            gen = 0
        try:
            b = bucket().blob(name); b.metadata = metadata or {}
            b.upload_from_string(data, content_type="application/json", if_generation_match=gen)
            return b.generation
        except PreconditionFailed:
            continue
    raise PreconditionFailed("object changed concurrently")


def get(name):
    b = bucket().blob(name)
    data = b.download_as_bytes()
    return data, b.content_type or "application/octet-stream"


def get_json(name):
    return json.loads(get(name)[0])


def delete(name):
    bucket().blob(name).delete()


def list_(prefix):
    return [{"name": b.name, "size": b.size, "content_type": b.content_type, "last_modified": b.updated.isoformat(), "etag": str(b.generation)}
            for b in client().list_blobs(config.BUCKET, prefix=prefix)]


def signed_url(name, minutes=10):
    """V4 signed URL via IAM signBlob (needs roles/iam.serviceAccountTokenCreator on the SA itself - granted by Terraform)."""
    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"]); creds.refresh(Request())
    return bucket().blob(name).generate_signed_url(version="v4", expiration=timedelta(minutes=minutes), method="GET",
                                                    service_account_email=creds.service_account_email, access_token=creds.token)
