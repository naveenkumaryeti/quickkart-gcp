"""Audit trail: Firestore auditLogs (queryable) + Cloud Storage audit-logs/<event>/ (archive) + Cloud Logging (structured). Never log secrets."""
import logging
import socket
import uuid
from datetime import datetime, timezone

from services import firestore_service as fs
from services import storage_service as st

log = logging.getLogger(__name__)
_lg = None


def _cloud(rec):
    global _lg
    from google.cloud import logging as gcl
    _lg = _lg or gcl.Client().logger("quickkart-audit")
    _lg.log_struct(rec, severity="WARNING" if rec["result"] != "success" else "INFO")


def log_event(event_type, entity_id="", actor_id="system", result="success", details=None):
    ts = datetime.now(timezone.utc); eid = uuid.uuid4().hex
    rec = {"eventId": eid, "eventType": event_type, "entityId": entity_id, "actorId": actor_id, "timestamp": ts.isoformat(),
           "result": result, "instance": socket.gethostname(), "details": details or {}}
    for fn in (lambda: fs.set_("auditLogs", eid, rec),
               lambda: st.put_json(f"audit-logs/{event_type}/{ts:%Y%m%dT%H%M%S%f}-{eid[:8]}.json", rec),
               lambda: _cloud(rec)):
        try:
            fn()
        except Exception as e:  # auditing must never break the business operation
            log.warning("audit sink failed (%s): %s", event_type, e)
