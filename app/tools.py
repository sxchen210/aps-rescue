"""Shared tool surface: Gmail search/read + read-only SQL, used by the
runtime pipeline and the validation harnesses alike."""
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "populate"))
import gmail_io
import db as dblib

schema = dblib.load_schema()
SCHEMA_BRIEF = "\n".join(
    f"- {t}: keys={d['canonical_keys']}; columns: {', '.join(d['columns'])}"
    for t, d in schema["tables"].items()) + (
    "\n- catchall: gmail_id, date, sender, subject, tag (mail that fit no workflow)"
    "\n- boolean-ish columns store '1'/'0' as TEXT — compare with = '1', not = true")


GMAIL_TOOLS = [
    {"name": "gmail_search",
     "description": "Search the shared mailbox (standard Gmail query syntax). Returns matching threads: id, subject, first sender, message count.",
     "input_schema": {"type": "object",
                      "properties": {"query": {"type": "string"},
                                     "limit": {"type": "integer", "minimum": 1, "maximum": 20}},
                      "required": ["query"]}},
    {"name": "gmail_get_thread",
     "description": "Read a full thread: every message with headers and body, oldest first.",
     "input_schema": {"type": "object",
                      "properties": {"thread_id": {"type": "string"}},
                      "required": ["thread_id"]}},
]
SQL_TOOL = {"name": "sql_query",
            "description": "Run ONE read-only SQL SELECT against the operational database. Returns rows as JSON (max 200).",
            "input_schema": {"type": "object",
                             "properties": {"sql": {"type": "string"}},
                             "required": ["sql"]}}

_DB = None


def _get_db():
    # Lazy so that importing this module never requires credentials; the
    # no-token tier falls back to the shipped snapshot inside dblib.connect().
    global _DB
    if _DB is None:
        _DB = dblib.connect()
    return _DB


# Write/DDL verbs rejected anywhere in the statement, not just as the first
# token: WITH cte AS (...) UPDATE ... is valid SQLite and sails past a
# prefix check. \b keeps identifiers like updated_at and pragma_table_info
# legal; replace() the scalar function stays legal, REPLACE INTO does not.
_SQL_WRITE = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|detach|pragma|vacuum|"
    r"reindex|analyze|begin|commit|rollback|savepoint|release|grant|revoke)\b"
    r"|\breplace\s+into\b", re.I)


def _strip_sql(q):
    """Blank string literals, quoted identifiers, and comments so the write
    scan can be neither fooled nor tripped by their contents."""
    out, i, n = [], 0, len(q)
    while i < n:
        c = q[i]
        if c in ("'", '"'):
            j = i + 1
            while j < n:
                if q[j] == c and j + 1 < n and q[j + 1] == c:
                    j += 2  # doubled quote = escaped
                elif q[j] == c:
                    break
                else:
                    j += 1
            out.append(c + c)
            i = j + 1
        elif q[i:i + 2] == "--":
            j = q.find("\n", i)
            i = n if j < 0 else j
        elif q[i:i + 2] == "/*":
            j = q.find("*/", i + 2)
            i = n if j < 0 else j + 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def safe_select(sql):
    """True only for a single SELECT / WITH...SELECT statement."""
    s = _strip_sql(sql or "").strip().rstrip(";").strip()
    if not s or ";" in s:
        return False
    if s.split(None, 1)[0].casefold() not in ("select", "with"):
        return False
    return not _SQL_WRITE.search(s)


def run_tool(name, inp):
    if name == "gmail_search":
        svc = gmail_io.service("aps")
        resp = gmail_io._retry_quota(lambda: svc.users().threads().list(
            userId="me", q=inp["query"], maxResults=int(inp.get("limit", 10))).execute())
        out = []
        for t in resp.get("threads", []):
            meta = gmail_io._retry_quota(lambda: svc.users().threads().get(
                userId="me", id=t["id"], format="metadata",
                metadataHeaders=["Subject", "From"]).execute())
            hdr = {h["name"]: h["value"] for h in meta["messages"][0]["payload"]["headers"]}
            out.append({"thread_id": t["id"], "subject": hdr.get("Subject", "")[:90],
                        "from": hdr.get("From", "")[:60], "messages": len(meta["messages"])})
        return json.dumps(out, ensure_ascii=False)
    if name == "gmail_get_thread":
        time.sleep(0.3)
        msgs = gmail_io.get_thread("aps", inp["thread_id"], trim_quotes=True)
        return gmail_io.render_thread(msgs, max_body=1500)[:45000]
    if name == "sql_query":
        sql = (inp.get("sql") or "").strip()
        if not safe_select(sql):
            return ("ERROR: read-only — one SELECT (or WITH ... SELECT) "
                    "statement only; write/DDL verbs are rejected anywhere "
                    "in the statement.")
        rows = _get_db().execute(sql)
        return json.dumps(rows[:200], ensure_ascii=False)
    raise ValueError(name)
