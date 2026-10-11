"""Shared tool surface: Gmail search/read + read-only SQL, used by the
runtime pipeline and the validation harnesses alike."""
import json
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
    "\n- catchall: gmail_id, date, sender, subject, tag (mail that fit no workflow)")


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

turso = dblib.TursoDB()


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
        sql = inp["sql"].strip()
        if sql.split(None, 1)[0].casefold() not in ("select", "with"):
            return "ERROR: read-only — SELECT/WITH statements only."
        rows = turso.execute(sql)
        return json.dumps(rows[:200], ensure_ascii=False)
    raise ValueError(name)


