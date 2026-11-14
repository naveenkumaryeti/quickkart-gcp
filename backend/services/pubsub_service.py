"""Pub/Sub publisher + pull subscriber (backend authenticates with its attached service account)."""
import json

import google.auth
from google.api_core.exceptions import DeadlineExceeded
from google.cloud import pubsub_v1

import config

_pub = _sub = None


def _project():
    return config.PROJECT or google.auth.default()[1]


def _p():
    global _pub
    _pub = _pub or pubsub_v1.PublisherClient()
    return _pub


def _s():
    global _sub
    _sub = _sub or pubsub_v1.SubscriberClient()
    return _sub


def publish(obj):
    path = _p().topic_path(_project(), config.TOPIC)
    return _p().publish(path, json.dumps(obj).encode(), event_id=obj["event_id"], order_id=obj["order_id"]).result(timeout=15)


def pull(sub, n=10):
    path = _s().subscription_path(_project(), sub)
    try:
        r = _s().pull(request={"subscription": path, "max_messages": n}, timeout=10)
    except DeadlineExceeded:
        return []
    out = []
    for m in r.received_messages:
        try: data = json.loads(m.message.data)
        except ValueError: data = {"_invalid": True}
        out.append({"ack_id": m.ack_id, "id": m.message.message_id, "data": data, "attempt": m.delivery_attempt or 1})
    return out


def ack(sub, ids):
    _s().acknowledge(request={"subscription": _s().subscription_path(_project(), sub), "ack_ids": ids})


def nack(sub, ids):
    _s().modify_ack_deadline(request={"subscription": _s().subscription_path(_project(), sub), "ack_ids": ids, "ack_deadline_seconds": 0})
