"""Application Default Credentials (ADC): on a MIG VM the client libraries get tokens for the ATTACHED service account
from the metadata server. No key files exist anywhere. Locally ADC falls back to `gcloud auth application-default login`."""
import google.auth
from google.auth.transport.requests import Request


def identity():
    try:
        creds, project = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        creds.refresh(Request())
        return {"ok": True, "principal": getattr(creds, "service_account_email", "user ADC"), "project": project}   # never return the token
    except Exception as e:  # noqa
        return {"ok": False, "error": str(e)[:300]}
