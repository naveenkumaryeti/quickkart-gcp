"""In-memory stand-ins for Firestore / Cloud Storage / Pub/Sub used ONLY by `e2e_test.py --local` (offline logic check). Real tests use GCP."""
import copy
import json
from datetime import datetime, timezone

from google.api_core.exceptions import AlreadyExists, NotFound


def patch():
    import config
    from services import audit_service as au, firestore_service as fs, identity_service as idn, pubsub_service as ps, storage_service as st
    DB = {}

    def get(c, i): d = DB.get(c, {}).get(i); return copy.deepcopy(d) if d is not None else None
    def set_(c, i, d): DB.setdefault(c, {})[i] = copy.deepcopy(d)
    def create(c, i, d):
        if i in DB.get(c, {}): raise AlreadyExists("exists")
        set_(c, i, d)
    def update(c, i, f):
        if i not in DB.get(c, {}): raise NotFound("nf")
        DB[c][i].update(copy.deepcopy(f))
    def all_(c): return [copy.deepcopy(v) for v in DB.get(c, {}).values()]
    def query(c, **eq): return [copy.deepcopy(v) for v in DB.get(c, {}).values() if all(v.get(k) == x for k, x in eq.items())]

    class Tx:
        def __init__(s): s.w = []
        def get(s, c, i): return get(c, i)
        def set(s, c, i, d): s.w.append(("set", c, i, copy.deepcopy(d)))
        def update(s, c, i, f): s.w.append(("upd", c, i, f))

    def transaction(fn):
        tx = Tx(); r = fn(tx)                      # exception in fn => nothing applied (rollback)
        for op, c, i, d in tx.w: set_(c, i, d) if op == "set" else update(c, i, d)
        return r
    fs.get, fs.set_, fs.create, fs.update, fs.all_, fs.query, fs.transaction = get, set_, create, update, all_, query, transaction
    fs.delete = lambda c, i: DB.get(c, {}).pop(i, None)

    OBJ, gen = {}, [0]
    def put(name, data, ctype, metadata=None): gen[0] += 1; OBJ[name] = {"data": data, "ctype": ctype, "gen": gen[0], "lm": datetime.now(timezone.utc).isoformat()}; return gen[0]
    def sget(name):
        if name not in OBJ: raise NotFound("nf")
        return OBJ[name]["data"], OBJ[name]["ctype"]
    st.put = put
    st.put_json = lambda n, o, m=None: put(n, json.dumps(o).encode(), "application/json")
    st.get, st.get_json = sget, lambda n: json.loads(sget(n)[0])
    st.delete = lambda n: OBJ.pop(n) if n in OBJ else (_ for _ in ()).throw(NotFound("nf"))
    st.list_ = lambda p: [{"name": n, "size": len(v["data"]), "content_type": v["ctype"], "last_modified": v["lm"], "etag": str(v["gen"])} for n, v in sorted(OBJ.items()) if n.startswith(p)]
    st.signed_url = lambda n, m=10: "https://storage.googleapis.com/fake-signed-url"

    main, dlq, n = [], [], [0]
    def publish(obj): n[0] += 1; main.append({"id": str(n[0]), "data": obj, "attempt": 0, "ack": f"a{n[0]}"}); return n[0]
    def pull(sub, k=10):
        src = main if sub == config.SUBSCRIPTION else dlq
        out = []
        for m in src[:k]:
            m["attempt"] += 1; out.append({"ack_id": m["ack"], "id": m["id"], "data": copy.deepcopy(m["data"]), "attempt": m["attempt"]})
        return out
    def ack(sub, ids):
        src = main if sub == config.SUBSCRIPTION else dlq
        src[:] = [m for m in src if m["ack"] not in ids]
    def nack(sub, ids):                            # Pub/Sub dead-letters after max_delivery_attempts failed deliveries
        for m in list(main):
            if m["ack"] in ids and m["attempt"] >= config.MAX_DELIVERY_ATTEMPTS: main.remove(m); dlq.append({**m, "attempt": 0})
    ps.publish, ps.pull, ps.ack, ps.nack = publish, pull, ack, nack
    au._cloud = lambda rec: None
    idn.identity = lambda: {"ok": True, "principal": "fake-backend-sa@local", "project": "local"}
