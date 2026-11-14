"""Users live in Firestore: customers (role customer) and sellers (role seller/admin). Passwords: salted PBKDF2. Tokens: signed, expiring."""
import hashlib
import logging
import re
import uuid
from functools import wraps

from flask import g, request
from google.api_core.exceptions import AlreadyExists
from itsdangerous import BadSignature, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

import config
from models.product import now
from services import audit_service as audit
from services import firestore_service as fs
from services.errors import AppError, AuthError

log = logging.getLogger(__name__)
_ser = URLSafeTimedSerializer(config.SESSION_SECRET, salt="quickkart-auth")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PREFIX = {"customer": "CUST", "seller": "SELLER", "admin": "ADMIN"}


def _id(email):
    return hashlib.sha256(email.strip().lower().encode()).hexdigest()[:32]


def _find(email):
    for col in ("customers", "sellers"):
        u = fs.get(col, _id(email))
        if u:
            return u
    return None


def create_user(email, name, password, role, uid=None):
    email = (email or "").strip().lower()
    if not EMAIL.match(email):
        raise AppError("a valid email is required")
    if len(password or "") < 8:
        raise AppError("password must be at least 8 characters")
    if not (name or "").strip():
        raise AppError("name is required")
    if _find(email):
        raise AppError("email already registered", 409, "CONFLICT")
    col = "customers" if role == "customer" else "sellers"
    rec = {"userId": uid or f"{PREFIX[role]}-{uuid.uuid4().hex[:6].upper()}", "email": email, "name": name.strip(), "role": role,
           "passwordHash": generate_password_hash(password, method="pbkdf2:sha256"), "createdAt": now()}
    try:
        fs.create(col, _id(email), rec)
    except AlreadyExists:
        raise AppError("email already registered", 409, "CONFLICT")
    return rec


def public(u):
    return {"user_id": u["userId"], "email": u["email"], "name": u["name"], "role": u["role"]}


def login(email, password):
    u = _find(email or "")
    if not u or not check_password_hash(u["passwordHash"], password or ""):
        audit.log_event("login_failed", actor_id="anonymous", result="failure")
        raise AuthError("Invalid email or password", 401, "UNAUTHORIZED")
    token = _ser.dumps({"uid": u["userId"], "role": u["role"], "name": u["name"]})
    audit.log_event(f"{u['role']}_logged_in", u["userId"], u["userId"])
    return token, public(u)


def ensure_seed():
    for role, email, pw, uid, name in config.SEEDS:
        if pw:
            try:
                create_user(email, name, pw, role, uid)
            except AppError as e:
                if e.status != 409:
                    raise


def _current():
    h = request.headers.get("Authorization", "")
    if not h.startswith("Bearer "):
        return None
    try:
        return _ser.loads(h[7:], max_age=config.TOKEN_MAX_AGE)
    except BadSignature:
        return None


def require(*roles):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **k):
            u = _current()
            if not u:
                raise AuthError("login required", 401, "UNAUTHORIZED")
            if roles and u["role"] not in roles:
                raise AuthError("your role may not perform this action", 403, "FORBIDDEN")
            g.user = u
            return fn(*a, **k)
        return wrapper
    return deco
