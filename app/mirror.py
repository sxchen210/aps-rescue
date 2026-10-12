"""One-way mirror: database -> Google Sheet.

Table tabs are fully rewritten each refresh (atomic enough at this scale);
Activity and Drafts are append-only and never wiped. SHEET_ID comes from
.env; the DB is Turso when APS_DB=turso, else the local SQLite file.

Usage: set -a && . ../.env && set +a && APS_DB=turso python3 mirror.py
"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "populate"))
import gmail_io
import db as dblib

TABLE_TABS = ["dogs", "fosters", "foster_applications", "events",
              "event_rsvps", "catchall"]
META_TABS = {"Activity": ["time", "event"],
             "Drafts": ["time", "in_reply_to", "to", "subject", "draft_body"]}


def sheet_id():
    sid = os.environ.get("SHEET_ID")
    env = Path(__file__).resolve().parent.parent / ".env"
    if not sid and env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("SHEET_ID="):
                sid = line.split("=", 1)[1].strip()
    if not sid:
        raise RuntimeError("SHEET_ID not set (see DEMO.md)")
    return sid


def ensure_tabs(svc, sid):
    meta = svc.spreadsheets().get(spreadsheetId=sid).execute()
    have = {s["properties"]["title"] for s in meta["sheets"]}
    want = TABLE_TABS + list(META_TABS)
    reqs = [{"addSheet": {"properties": {"title": t}}} for t in want if t not in have]
    if reqs:
        svc.spreadsheets().batchUpdate(spreadsheetId=sid, body={"requests": reqs}).execute()
    for t, hdr in META_TABS.items():
        got = svc.spreadsheets().values().get(spreadsheetId=sid, range=f"'{t}'!A1:E1").execute()
        if not got.get("values"):
            svc.spreadsheets().values().update(
                spreadsheetId=sid, range=f"'{t}'!A1", valueInputOption="RAW",
                body={"values": [hdr]}).execute()


def refresh_tables(db=None):
    """Rewrite every table tab from the DB. Returns {tab: n_rows}."""
    db = db or dblib.connect()
    svc = gmail_io.sheets_service()
    sid = sheet_id()
    ensure_tabs(svc, sid)
    counts = {}
    for t in TABLE_TABS:
        rows = db.execute(f'SELECT * FROM "{t}"')
        if rows:
            cols = [c for c in rows[0].keys() if c != "id"]
            values = [cols] + [[("" if r[c] is None else str(r[c])) for c in cols]
                               for r in rows]
        else:
            values = [["(empty)"]]
        svc.spreadsheets().values().clear(spreadsheetId=sid, range=f"'{t}'!A:Z").execute()
        svc.spreadsheets().values().update(
            spreadsheetId=sid, range=f"'{t}'!A1", valueInputOption="RAW",
            body={"values": values}).execute()
        counts[t] = len(rows)
    return counts


def append_activity(lines):
    svc = gmail_io.sheets_service()
    now = time.strftime("%Y-%m-%d %H:%M")
    svc.spreadsheets().values().append(
        spreadsheetId=sheet_id(), range="'Activity'!A:B",
        valueInputOption="RAW", insertDataOption="INSERT_ROWS",
        body={"values": [[now, ln] for ln in lines]}).execute()


def append_draft(to, subject, body, in_reply_to=""):
    svc = gmail_io.sheets_service()
    now = time.strftime("%Y-%m-%d %H:%M")
    svc.spreadsheets().values().append(
        spreadsheetId=sheet_id(), range="'Drafts'!A:E",
        valueInputOption="RAW", insertDataOption="INSERT_ROWS",
        body={"values": [[now, in_reply_to, to, subject, body]]}).execute()


if __name__ == "__main__":
    counts = refresh_tables()
    append_activity([f"mirror refresh: " + ", ".join(f"{t}={n}" for t, n in counts.items())])
    print("mirrored:", counts)
