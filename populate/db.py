"""DB layer for the populate phase.

Creates tables from discovery/schema.json (all TEXT affinity; values stored
as the extractor emitted them, except booleans, which are canonicalized to
'1'/'0' at apply time) plus harness-owned system tables (catchall,
ingest_log). Applies envelope ops with the locked semantics: normalized
canonical-key lookup decides create-vs-update; per-field merge; unknown
fields dropped and logged; explicit "clear" list nulls stated-gone fields
(never canonical keys; nulls in "set" still mean unknown and are dropped);
provenance (source_email_id, updated_at) stamped on every write.

Backends: local SQLite (default; populate runs locally first) and Turso over
plain HTTP (same interface) selected by APS_DB=turso.
"""
import hashlib
import json
import os
import re
import sqlite3
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCHEMA_PATH = HERE.parent / "discovery" / "schema.json"


def load_schema():
    return json.loads(SCHEMA_PATH.read_text())


def norm_key(value):
    """Canonical-key normalization: casefold, strip non-alphanumerics."""
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


class LocalDB:
    def __init__(self, path, readonly=False):
        if readonly:
            self.conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        else:
            self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row

    def execute(self, sql, args=()):
        cur = self.conn.execute(sql, args)
        self.conn.commit()
        return [dict(r) for r in cur.fetchall()]


class TursoDB:
    def __init__(self):
        url = os.environ["TURSO_DATABASE_URL"].replace("libsql://", "https://").rstrip("/")
        self.endpoint = url + "/v2/pipeline"
        self.token = os.environ["TURSO_AUTH_TOKEN"]

    def execute(self, sql, args=()):
        stmt = {"sql": sql,
                "args": [{"type": "text", "value": str(a)} if a is not None
                         else {"type": "null"} for a in args]}
        body = {"requests": [{"type": "execute", "stmt": stmt}, {"type": "close"}]}
        req = urllib.request.Request(
            self.endpoint, data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {self.token}",
                     "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            out = json.loads(r.read())
        res = out["results"][0]
        if res.get("type") == "error":
            raise RuntimeError(res["error"]["message"])
        result = res["response"]["result"]
        cols = [c["name"] for c in result.get("cols", [])]
        return [dict(zip(cols, [c.get("value") for c in row]))
                for row in result.get("rows", [])]

    def execute_batch(self, stmts):
        """Many (sql, args) in one pipeline call."""
        def enc(args):
            return [{"type": "text", "value": str(a)} if a is not None
                    else {"type": "null"} for a in args]
        body = {"requests": [{"type": "execute",
                              "stmt": {"sql": sql, "args": enc(args)}}
                             for sql, args in stmts] + [{"type": "close"}]}
        req = urllib.request.Request(
            self.endpoint, data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {self.token}",
                     "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            out = json.loads(r.read())
        for res in out["results"]:
            if res.get("type") == "error":
                raise RuntimeError(res["error"]["message"])


def connect(path=None):
    if os.environ.get("APS_DB") == "turso":
        if os.environ.get("TURSO_DATABASE_URL") and os.environ.get("TURSO_AUTH_TOKEN"):
            return TursoDB()
        snap = HERE / "out" / "state_v2.sqlite"
        if not snap.exists():
            raise RuntimeError(f"{snap} missing — re-clone or see README.md")
        print(f"[db] Turso credentials missing — falling back to the shipped "
              f"read-only snapshot ({snap.name}); live/shared state needs the "
              f"portal .env (see README.md)")
        return LocalDB(str(snap), readonly=True)
    return LocalDB(path or str(HERE / "out" / "state.sqlite"))


def create_tables(db, schema):
    for name, t in schema["tables"].items():
        cols = list(t["columns"]) + ["source_email_id", "updated_at"]
        col_sql = ", ".join(f'"{c}" TEXT' for c in cols)
        db.execute(f'CREATE TABLE IF NOT EXISTS "{name}" (id INTEGER PRIMARY KEY, {col_sql})')
    db.execute("CREATE TABLE IF NOT EXISTS catchall (id INTEGER PRIMARY KEY, "
               "gmail_id TEXT, date TEXT, sender TEXT, subject TEXT, tag TEXT)")
    db.execute("CREATE TABLE IF NOT EXISTS ingest_log (gmail_id TEXT PRIMARY KEY, "
               "ts TEXT, ok INTEGER, model TEXT, effort TEXT, in_tok INTEGER, "
               "out_tok INTEGER, cache_read INTEGER, ops INTEGER, catchall_tag TEXT, "
               "anomalies TEXT, error TEXT)")


def check_schema_integrity(db, schema=None):
    """Refuse to ingest over a drifted or hand-edited schema.

    The prototype's schema is FROZEN after populate: there is no migration
    path by design. Two guards, both detection-not-prevention: (1) hash —
    schema.json must match the digest the discovery harness emitted beside
    it; (2) parity — every table's live columns must equal the schema's
    columns plus the system-stamped ones. Production would need signed
    schema artifacts and migrations run only by the harness.
    """
    raw = SCHEMA_PATH.read_bytes()
    digest_path = SCHEMA_PATH.parent / "schema.sha256"
    if not digest_path.exists():
        raise RuntimeError(f"{digest_path} missing — schema integrity "
                           "cannot be verified (see README.md)")
    if hashlib.sha256(raw).hexdigest() != digest_path.read_text().strip():
        raise RuntimeError(
            "schema.json does not match the digest the discovery harness "
            "emitted — hand-edits are not a sanctioned path; re-run the "
            "harness (discovery.py --refine) instead")
    schema = schema or load_schema()
    for name, t in schema["tables"].items():
        have = {r["name"] for r in
                db.execute(f"SELECT name FROM pragma_table_info('{name}')")}
        want = set(t["columns"]) | {"id", "source_email_id", "updated_at"}
        if have and have != want:
            raise RuntimeError(
                f"schema/DB drift on table {name!r} (missing "
                f"{sorted(want - have)}, extra {sorted(have - want)}) — the "
                "prototype's schema is frozen and has no migration path; "
                "restore the committed schema or rebuild the table state")


def processed_ids(db):
    return {r["gmail_id"] for r in db.execute("SELECT gmail_id FROM ingest_log WHERE ok = 1")}


def find_row(db, table, keys, match):
    """Locate a row whose normalized canonical-key values equal the op's."""
    want = {k: norm_key(match[k]) for k in keys if k in match}
    if len(want) != len(keys):
        return None  # op lacks full key — treated as anomaly upstream
    rows = db.execute(f'SELECT * FROM "{table}"')
    for r in rows:
        if all(norm_key(r.get(k) or "") == v for k, v in want.items()):
            return r
    return None


def apply_op(db, schema, op, email_id, email_ts):
    """Apply one envelope op. Returns (action, anomalies)."""
    anomalies = []
    table = op.get("table")
    if table not in schema["tables"]:
        return "skipped_unknown_table", [f"unknown table {table!r}"]
    tdef = schema["tables"][table]
    keys = tdef["canonical_keys"]
    valid = set(tdef["columns"])
    match = op.get("match") or {}
    fields = dict(op.get("set") or {})
    # match keys are also data: fold them into the row values
    for k, v in match.items():
        fields.setdefault(k, v)
    unknown = [k for k in fields if k not in valid]
    for k in unknown:
        anomalies.append(f"dropped unknown field {table}.{k}")
        fields.pop(k)
    if not all(k in match and str(match[k]).strip() for k in keys):
        return "skipped_incomplete_key", anomalies + [f"incomplete canonical key for {table}"]
    def _canon(v):
        # Booleans reach the store from two serializers (JSON true/false from
        # the extractor, Python bools via str() on the Turso HTTP path) —
        # canonicalize to '1'/'0' so one column never holds mixed spellings.
        if isinstance(v, bool):
            return "1" if v else "0"
        if isinstance(v, str) and v.strip().casefold() in ("true", "false"):
            return "1" if v.strip().casefold() == "true" else "0"
        return json.dumps(v) if isinstance(v, (list, dict)) else v
    fields = {k: _canon(v)
              for k, v in fields.items() if v is not None and str(v).strip() != ""}
    # "clear": fields whose recorded value the email states no longer holds
    # (nulls/empties in "set" stay dropped — omission remains the unknown
    # channel; clearing is explicit). Canonical keys are never cleared.
    clears = op.get("clear") or []
    if not isinstance(clears, list):
        anomalies.append(f"clear is not a list in {table} op")
        clears = []
    kept = []
    for c in map(str, clears):
        if c not in valid:
            anomalies.append(f"dropped unknown clear {table}.{c}")
        elif c in keys:
            anomalies.append(f"refused clear of canonical key {table}.{c}")
        elif c in fields:
            anomalies.append(f"clear ignored for {table}.{c} (also set)")
        else:
            kept.append(c)
    clears = kept
    if not fields and not clears:
        return "skipped_empty", anomalies
    row = find_row(db, table, keys, match)
    if row is None and clears and set(fields) <= set(match):
        # a pure cancellation must not conjure a row for an unknown entity
        return "skipped_clear_no_row", anomalies + [f"clear on nonexistent {table} row"]
    fields["source_email_id"] = email_id
    fields["updated_at"] = email_ts
    if row is None:
        if clears:
            anomalies.append(f"clear ignored on create: {table}.{', '.join(clears)}")
        cols = ", ".join(f'"{c}"' for c in fields)
        ph = ", ".join("?" for _ in fields)
        db.execute(f'INSERT INTO "{table}" ({cols}) VALUES ({ph})', list(fields.values()))
        return "create", anomalies
    assign = {**fields, **{c: None for c in clears}}
    sets = ", ".join(f'"{c}" = ?' for c in assign)
    db.execute(f'UPDATE "{table}" SET {sets} WHERE id = ?',
               list(assign.values()) + [row["id"]])
    return "update", anomalies
