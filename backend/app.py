"""QuickKart Flask REST API (Tier 2). gunicorn :5000 behind the internal load balancer. Auth to Google Cloud = ADC / attached service account."""
import logging
import socket
import threading
import time

from flask import Flask, jsonify, request
from google.api_core import exceptions as gex
from google.auth.exceptions import DefaultCredentialsError, RefreshError, TransportError
from werkzeug.exceptions import HTTPException

from routes import admin, auth, cart, orders, products, storage
from services import audit_service as audit
from services import auth_service
from services import identity_service
from services import storage_service as st
from services.errors import AppError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
try:  # structured logs -> Cloud Logging (needs roles/logging.logWriter on the attached service account)
    import google.cloud.logging as gcl
    gcl.Client().setup_logging()
except Exception as _e:  # noqa
    logging.info("Cloud Logging handler not attached: %s", _e)
log = logging.getLogger("app")
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 6 * 1024 * 1024
for m in (auth, products, cart, orders, admin, storage):
    app.register_blueprint(m.bp)
_ready, _last, _lock = False, 0.0, threading.Lock()


def ensure_ready():
    """Seed demo users once per process; retried every 30 s while Firestore/IAM are not ready yet."""
    global _ready, _last
    if _ready or time.time() - _last < 30:
        return
    with _lock:
        if _ready:
            return
        _last = time.time()
        try:
            auth_service.ensure_seed()
            _ready = True
        except Exception as e:  # noqa
            log.warning("bootstrap not complete yet: %s", e)


@app.before_request
def _boot():
    if request.path != "/api/health":
        ensure_ready()


@app.get("/api/health")
def health():
    """Shallow by default (LB / MIG health checks must not depend on Google APIs). ?deep=1 checks ADC identity + bucket access."""
    body = {"status": "ok", "instance": socket.gethostname()}
    if request.args.get("deep"):
        body["identity"] = identity_service.identity()
        try:
            body["objects_visible"] = len(st.list_("products/"))
        except Exception as e:  # noqa
            body.update(status="degraded", storage_error=str(e)[:300])
    return jsonify(body)


def _fail(code, error, msg):
    return jsonify({"error": error, "message": msg}), code


@app.errorhandler(Exception)
def handle(e):
    if isinstance(e, AppError):
        return _fail(e.status, e.error, str(e))
    if isinstance(e, HTTPException):
        return _fail(e.code, e.name.upper().replace(" ", "_"), e.description)
    if isinstance(e, ValueError):
        return _fail(400, "BAD_REQUEST", str(e))
    if isinstance(e, (gex.PermissionDenied, gex.Forbidden)):
        log.error("IAM AUTHORIZATION FAILED: %s", e)
        audit.log_event("iam_authorization_failure", actor_id="backend", result="failure", details={"error": str(e)[:200]})
        return _fail(403, "AUTHORIZATION_FAILED", "Google Cloud rejected the request: the backend service account is missing an IAM role (e.g. Storage Object Admin, Cloud Datastore User, Pub/Sub Publisher/Subscriber)")
    if isinstance(e, (DefaultCredentialsError, RefreshError, TransportError, gex.Unauthenticated)):
        return _fail(503, "AUTHENTICATION_FAILED", "No usable Application Default Credentials: is a service account attached to this VM?")
    if isinstance(e, gex.NotFound):
        return _fail(404, "NOT_FOUND", "Record or object not found")
    if isinstance(e, gex.AlreadyExists):
        return _fail(409, "ALREADY_EXISTS", "Record already exists")
    if isinstance(e, (gex.PreconditionFailed, gex.Aborted)):
        return _fail(409, "CONFLICT", "Concurrent modification - reload and retry")
    if isinstance(e, (gex.ServiceUnavailable, gex.DeadlineExceeded, gex.RetryError)):
        return _fail(503, "SERVICE_UNAVAILABLE", "Google Cloud service temporarily unreachable (check Private Google Access / NAT / firewall egress)")
    log.exception("unhandled")
    return _fail(500, "INTERNAL_ERROR", "Unexpected server error")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
