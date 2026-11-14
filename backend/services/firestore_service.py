"""Firestore Native mode access. Operational source of truth. Thin wrapper so the rest of the code is storage-agnostic."""
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

import config

_db = None


def db():
    global _db
    if _db is None:
        _db = firestore.Client(project=config.PROJECT, database=config.FIRESTORE_DB)
    return _db


def get(col, i):
    s = db().collection(col).document(i).get()
    return s.to_dict() if s.exists else None


def set_(col, i, data):
    db().collection(col).document(i).set(data)


def create(col, i, data):            # raises google.api_core.exceptions.AlreadyExists
    db().collection(col).document(i).create(data)


def update(col, i, fields):
    db().collection(col).document(i).update(fields)


def delete(col, i):
    db().collection(col).document(i).delete()


def all_(col):
    return [d.to_dict() for d in db().collection(col).stream()]


def query(col, **eq):
    q = db().collection(col)
    for k, v in eq.items():
        q = q.where(filter=FieldFilter(k, "==", v))
    return [d.to_dict() for d in q.stream()]


class Tx:
    def __init__(self, tx): self.tx = tx
    def get(self, col, i):
        s = db().collection(col).document(i).get(transaction=self.tx)
        return s.to_dict() if s.exists else None
    def set(self, col, i, data): self.tx.set(db().collection(col).document(i), data)
    def update(self, col, i, fields): self.tx.update(db().collection(col).document(i), fields)


def transaction(fn):
    """fn(tx) must do all reads before writes and have no external side effects (Firestore may retry it)."""
    @firestore.transactional
    def run(tx):
        return fn(Tx(tx))
    return run(db().transaction())
