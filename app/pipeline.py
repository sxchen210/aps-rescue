"""App core: simulate_send_and_process + catch-up ingestion + draft triage.

The engine every surface wraps (interactive injections, batch drip, the
web app's Watch-it-work button). Hard boundaries, per PLAN.md:
the ingest path NEVER reads simulation/ — scenario files are touched only
to pick what to send and to grade AFTER extraction; drafts are created,
never sent.

CLI (run from app/, env loaded, APS_DB=turso for shared state):
  python3 pipeline.py status
  python3 pipeline.py ingest                      # catch-up only
  python3 pipeline.py simulate --custom-body "…" --custom-from "Name <a@b>" \
                               --custom-subject "…"
  python3 pipeline.py simulate --pool pool.jsonl  # fire next unfired scenario
"""
import argparse
import json
import re
import sys
import time
import uuid
from email.utils import format_datetime, parsedate_to_datetime
from pathlib import Path

import anthropic

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "populate"))
import gmail_io
import db as dblib
from ingest import build_prompt, parse_envelope, PRICE_IN, PRICE_OUT, PRICE_CREAD, PRICE_CWRITE
from tools import GMAIL_TOOLS, SQL_TOOL, run_tool, SCHEMA_BRIEF

INSTRUCTIONS = (HERE.parent / "discovery" / "instructions.md").read_text()
DEFAULT_POOL = HERE.parent / "simulation" / "out" / "extension" / "pool.jsonl"
SHARED = "animalprotectiveservices2026@gmail.com"
HAIKU, OPUS = "claude-haiku-5-5", "claude-opus-5-5"
NEVER_DRAFT_TAGS = {"promo-marketing", "drive-share-notification", "donation"}
NEVER_DRAFT_SENDERS = re.compile(r"no-?reply|drive-shares|mailer-daemon", re.I)

TRIAGE_SYSTEM = """You handle the shared inbox of APS Rescue, a small \
foster-based dog rescue in Redwood City, CA (coordinators Dana, Priya, June \
and Tom sign with first names). An email just arrived (the user message, \
with its thread). Decide whether the org should reply, and if so draft it.

Use your tools to gather context first. Then output ONLY this JSON:
{"should_reply": true/false, "reason": "<one line>",
 "subject": "<subject>", "body": "<the reply>"}   // subject+body only if true

Draft rules (hard): never mention databases, records, systems or lookups — \
write as a person who knows the operation. Never ask for information the \
email or its thread already gives. Real names/dates/numbers only when \
verified; never invent. Warm, brief, concrete; sign as Dana. Bare \
state-updates that need no answer (e.g. a plain RSVP) get should_reply \
false. You have a budget of 12 tool calls."""


def _schema_brief():
    schema = dblib.load_schema()
    return "\n".join(f"- {t}: keys={d['canonical_keys']}; columns: {', '.join(d['columns'])}"
                     for t, d in schema["tables"].items())


# --------------------------------------------------------------------------
# events: the five-beat narrative goes through one callback
# --------------------------------------------------------------------------

def print_event(stage, text):
    bar = {"arrived": "1 · ARRIVED", "thinking": "2 · HAIKU THINKING (excerpt)",
           "decision": "3 · DECISION (ops envelope)", "draft": "4 · DRAFT DECISION",
           "changed": "5 · CHANGED", "info": "·"}
    print(f"\n── {bar.get(stage, stage)} " + "─" * max(1, 50 - len(bar.get(stage, stage))))
    print(text, flush=True)


# --------------------------------------------------------------------------
# catch-up ingestion (blind: email + thread tail + instructions only)
# --------------------------------------------------------------------------

def _list_all_ids(svc):
    ids, page = [], None
    while True:
        resp = gmail_io._retry_quota(lambda: svc.users().messages().list(
            userId="me", q="in:inbox OR in:sent", maxResults=500, pageToken=page).execute())
        ids += resp.get("messages", [])
        page = resp.get("nextPageToken")
        if not page:
            break
    return ids


def ingest_new(db, on_event=print_event, effort="medium", client=None):
    """Process every email not yet in ingest_log, oldest first.
    Returns list of per-email result dicts (for scorecards and triage)."""
    client = client or anthropic.Anthropic(max_retries=6)
    svc = gmail_io.service("aps")
    done = dblib.processed_ids(db)
    schema = dblib.load_schema()
    dblib.create_tables(db, schema)
    dblib.check_schema_integrity(db, schema)

    todo_ids = [m for m in _list_all_ids(svc) if m["id"] not in done]
    if not todo_ids:
        return []
    threads = {}
    for m in todo_ids:
        threads.setdefault(m["threadId"], None)
    for tid in threads:
        time.sleep(0.2)
        threads[tid] = gmail_io.get_thread("aps", tid, trim_quotes=True)
    pending = []
    for tid, msgs in threads.items():
        for i, m in enumerate(msgs):
            if m["gmail_id"] in done:
                continue
            m["thread_id"], m["prior"] = tid, msgs[:i]
            try:
                m["_ts"] = parsedate_to_datetime(m["date"]).timestamp()
            except Exception:
                m["_ts"] = 0
            pending.append(m)
    pending.sort(key=lambda m: (m["_ts"], m["gmail_id"]))

    usage = [0, 0, 0, 0]
    results = []
    for m in pending:
        on_event("arrived", f"From: {m['from']}\nSubj: {m['subject']}\n"
                            f"{(m['body'] or '')[:220]}")
        env, raw, err, thinking = None, "", None, ""
        for attempt in range(2):
            prompt = build_prompt(m, m["prior"])
            msg_text = ("Return ONLY the JSON envelope.\n\n" + prompt) if attempt else prompt
            try:
                resp = client.messages.create(
                    model=HAIKU, max_tokens=6000, output_config={"effort": effort},
                    # Haiku 5.5 withholds thinking text unless summarized
                    # display is requested (per its migration guide); this
                    # changes only what is RETURNED, not what it does.
                    thinking={"type": "adaptive", "display": "summarized"},
                    system=[{"type": "text", "text": INSTRUCTIONS,
                             "cache_control": {"type": "ephemeral"}}],
                    messages=[{"role": "user", "content": msg_text}])
            except Exception as e:
                err = f"api: {type(e).__name__}"
                time.sleep(5)
                continue
            for i, f in enumerate(("input_tokens", "output_tokens",
                                   "cache_read_input_tokens", "cache_creation_input_tokens")):
                usage[i] += getattr(resp.usage, f, 0) or 0
            thinking = " ".join(getattr(b, "thinking", "") for b in resp.content
                                if getattr(b, "type", "") == "thinking").strip()
            raw = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
            try:
                env = parse_envelope(raw)
                err = None
                break
            except (ValueError, json.JSONDecodeError) as e:
                err = f"parse: {e}"
        # Summarized thinking requested per the Haiku 5.5 migration guide;
        # relayed in full. Trivial emails may skip thinking entirely.
        on_event("thinking", thinking or
                 "(Haiku answered directly; no extended thinking was needed "
                 "for this email.)")

        ts = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(m["_ts"]))
        applied, anomalies, tag = [], [], None
        if env is not None:
            for op in env.get("ops", []):
                action, an = dblib.apply_op(db, schema, op, m["gmail_id"], ts)
                anomalies += an
                if action in ("create", "update"):
                    applied.append({"action": action, "table": op.get("table"),
                                    "match": op.get("match"), "set": op.get("set"),
                                    "clear": op.get("clear") or [],
                                    "note": op.get("note") or ""})
            tag = (env.get("catchall") or {}).get("tag")
            if not applied and not tag:
                tag, anomalies = "other", anomalies + ["defaulted to catchall:other"]
            if tag:
                db.execute("INSERT INTO catchall (gmail_id, date, sender, subject, tag) "
                           "VALUES (?,?,?,?,?)", [m["gmail_id"], ts, m["from"], m["subject"], tag])
        db.execute("INSERT OR REPLACE INTO ingest_log (gmail_id, ts, ok, model, effort, "
                   "in_tok, out_tok, cache_read, ops, catchall_tag, anomalies, error) "
                   "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                   [m["gmail_id"], ts, 1 if env is not None else 0, HAIKU, effort,
                    usage[0], usage[1], usage[2], len(applied), tag,
                    "; ".join(anomalies) or None, err])
        dec = "\n".join(f"{a['action'].upper()} {a['table']} · match {a['match']} · set "
                        f"{json.dumps(a['set'], ensure_ascii=False)[:180]}"
                        + (f" · clear {a['clear']}" if a["clear"] else "")
                        + (f"\n   its note: “{a['note']}”" if a["note"] else "")
                        for a in applied) \
              or f"(no table ops) catchall tag: {tag}"
        on_event("decision", dec)
        results.append({"email": m, "applied": applied, "catchall": tag, "error": err})
    cost = (usage[0]*PRICE_IN + usage[1]*PRICE_OUT + usage[2]*PRICE_CREAD
            + usage[3]*PRICE_CWRITE) / 1e6
    on_event("info", f"ingested {len(results)} email(s) · ${cost:.4f}")
    return results


# --------------------------------------------------------------------------
# draft triage: mechanical filter, then one Opus should_reply+draft call
# --------------------------------------------------------------------------

def _is_latest_inbound(m):
    msgs = gmail_io.get_thread("aps", m["thread_id"], trim_quotes=False)
    return msgs and msgs[-1]["gmail_id"] == m["gmail_id"] and SHARED not in m["from"]


def triage_and_draft(result, db, on_event=print_event, client=None):
    m = result["email"]
    if SHARED in m["from"]:
        on_event("draft", "NO (mechanical) — our own outbound mail.")
        return None
    if NEVER_DRAFT_SENDERS.search(m["from"]):
        on_event("draft", "NO (mechanical) — automated sender, no human to reply to.")
        return None
    if result.get("catchall") in NEVER_DRAFT_TAGS:
        on_event("draft", f"NO (mechanical) — machine mail ({result['catchall']}).")
        return None
    if not _is_latest_inbound(m):
        on_event("draft", "NO (mechanical) — not the latest message of its thread.")
        return None

    client = client or anthropic.Anthropic(max_retries=6)
    email_text = (f"From: {m['from']}\nDate: {m['date']}\nSubject: {m['subject']}\n\n{m['body']}")
    if m["prior"]:
        email_text += "\n\n=== EARLIER IN THIS THREAD ===\n" + "\n---\n".join(
            f"{p['from']}: {p['body'][:500]}" for p in m["prior"][-3:])
    system = TRIAGE_SYSTEM + "\n\nDatabase schema (read-only SQL):\n" + SCHEMA_BRIEF
    messages = [{"role": "user", "content": email_text}]
    calls = 0
    for _ in range(30):
        resp = client.messages.create(
            model=OPUS, max_tokens=8000, output_config={"effort": "high"},
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            tools=GMAIL_TOOLS + [SQL_TOOL], messages=messages)
        tool_uses = [b for b in resp.content if getattr(b, "type", "") == "tool_use"]
        text = " ".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        if not tool_uses:
            break
        messages.append({"role": "assistant", "content": resp.content})
        outs = []
        for tu in tool_uses:
            calls += 1
            content = ("TOOL BUDGET EXHAUSTED — decide and output the JSON now."
                       if calls > 12 else str(run_tool(tu.name, tu.input)))
            outs.append({"type": "tool_result", "tool_use_id": tu.id, "content": content})
        messages.append({"role": "user", "content": outs})
    try:
        start, end = text.find("{"), text.rfind("}")
        verdict = json.loads(text[start:end + 1])
    except Exception:
        on_event("draft", f"NO — triage output unparseable: {text[:160]}")
        return None
    if not verdict.get("should_reply"):
        on_event("draft", f"NO (judged) — {verdict.get('reason', '')}")
        return None
    on_event("draft", f"YES — {verdict.get('reason', '')}")
    sender = m["from"]
    d = gmail_io.create_draft("aps", to=sender, subject=verdict.get("subject") or f"Re: {m['subject']}",
                              body=verdict["body"], thread_id=m["thread_id"])
    return {"draft_id": d["id"], "body": verdict["body"], "reason": verdict.get("reason")}


# --------------------------------------------------------------------------
# simulate_send_and_process
# --------------------------------------------------------------------------

def _pool_next(pool_path):
    """Next unfired scenario: local fired-state first, one Gmail
    Message-ID verification for the candidate (shared-state safe)."""
    svc = gmail_io.service("aps")
    fired_path = Path(str(pool_path) + ".fired.json")
    fired = set(json.loads(fired_path.read_text())) if fired_path.exists() else set()
    for line in Path(pool_path).read_text().splitlines():
        if not line.strip():
            continue
        sc = json.loads(line)
        if sc["id"] in fired:
            continue
        q = f"rfc822msgid:{sc['message_id']}"
        hit = gmail_io._retry_quota(lambda: svc.users().messages().list(
            userId="me", q=q, maxResults=1).execute())
        if hit.get("messages"):
            fired.add(sc["id"])  # fired elsewhere; record and keep scanning
            continue
        fired.add(sc["id"])
        fired_path.write_text(json.dumps(sorted(fired)))
        return sc
    fired_path.write_text(json.dumps(sorted(fired)))
    return None


def simulate_send_and_process(custom=None, pool=None, on_event=print_event):
    """Insert one email (pool-next or custom), then catch-up ingest, grade,
    and triage drafts. Returns a result summary."""
    db = dblib.connect()
    if custom:
        sc = {"from": custom["from"], "subject": custom["subject"],
              "body": custom["body"],
              "message_id": f"<sim-{uuid.uuid4().hex[:16]}@apsdemo.sim>",
              "expected_ops": None}
    else:
        sc = _pool_next(pool or DEFAULT_POOL)
        if sc is None:
            on_event("info", "pool exhausted — every scenario already fired")
            return None
    import datetime as dt
    # Pool scenarios carry the simulated world's own timeline (the seeded
    # history runs to 2026-10-16; the pool continues from 10-17), so a
    # fired scenario is inserted with its AUTHORED timestamp — otherwise
    # new arrivals would be dated before mail already in the inbox.
    # Custom emails are genuinely from now.
    date_hdr = format_datetime(dt.datetime.fromisoformat(sc["ts"])
                               if sc.get("ts") else dt.datetime.now().astimezone())
    gmail_io.insert_message("aps", from_addr=sc["from"], to=SHARED,
                            subject=sc["subject"], body=sc["body"], date=date_hdr,
                            message_id=sc["message_id"],
                            label_ids=["INBOX", "UNREAD"])
    on_event("info", f"inserted: {sc['subject']!r} from {sc['from']}")

    results = ingest_new(db, on_event=on_event)
    drafts = []
    for r in results:
        d = triage_and_draft(r, db, on_event=on_event)
        if d:
            drafts.append(d)

    score = None
    if sc.get("expected_ops"):
        mine = [a for r in results if r["email"]["subject"] == sc["subject"]
                for a in r["applied"]]
        exp = sc["expected_ops"]
        hits = sum(1 for e in exp if any(
            a["table"] == e["table"]
            and all(dblib.norm_key(a["match"].get(k, "")) == dblib.norm_key(v)
                    for k, v in e["match"].items())
            and all(c in (a.get("clear") or []) for c in e.get("clears_includes", []))
            for a in mine))
        score = f"scorecard: {hits}/{len(exp)} expected ops landed"
        on_event("info", score)

    ops = sum(len(r["applied"]) for r in results)
    on_event("changed", f"{ops} table op(s) applied · "
                        f"{len(drafts)} draft(s) created in Gmail Drafts")
    return {"scenario": sc["subject"], "results": results, "drafts": drafts, "score": score}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["status", "ingest", "simulate", "sql",
                                     "gmail-search", "gmail-thread"])
    ap.add_argument("arg", nargs="?", help="sql text / search query / thread id")
    ap.add_argument("--pool")
    ap.add_argument("--custom-from")
    ap.add_argument("--custom-subject")
    ap.add_argument("--custom-body")
    args = ap.parse_args()
    if args.cmd in ("sql", "gmail-search", "gmail-thread"):
        name, inp = {
            "sql": ("sql_query", {"sql": args.arg or ""}),
            "gmail-search": ("gmail_search", {"query": args.arg or "", "limit": 15}),
            "gmail-thread": ("gmail_get_thread", {"thread_id": args.arg or ""}),
        }[args.cmd]
        try:
            print(run_tool(name, inp))
        except RuntimeError as e:  # missing token etc. — pointer, not traceback
            print(f"ERROR: {e}")
        return
    try:
        _run_db_cmd(args)
    except RuntimeError as e:  # schema drift, missing creds — pointer, not traceback
        print(f"ERROR: {e}")
        sys.exit(1)


def _run_db_cmd(args):
    db = dblib.connect()
    if args.cmd == "status":
        for t in list(dblib.load_schema()["tables"]) + ["catchall", "ingest_log"]:
            n = db.execute(f'SELECT COUNT(*) AS c FROM "{t}"')[0]["c"]
            print(f"{t}: {n}")
        import os
        fired = Path(str(DEFAULT_POOL) + ".fired.json")
        n_fired = len(json.loads(fired.read_text())) if fired.exists() else 0
        n_pool = sum(1 for l in DEFAULT_POOL.read_text().splitlines() if l.strip())
        print(f"scenario pool: {n_pool - n_fired} of {n_pool} remaining")
    elif args.cmd == "ingest":
        results = ingest_new(db)
        for r in results:
            triage_and_draft(r, db)
    elif args.cmd == "simulate":
        custom = None
        if args.custom_body:  # dev/testing only
            custom = {"from": args.custom_from, "subject": args.custom_subject,
                      "body": args.custom_body}
        simulate_send_and_process(custom=custom, pool=args.pool)


if __name__ == "__main__":
    main()
