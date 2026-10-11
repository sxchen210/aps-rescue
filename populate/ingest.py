"""Serial chronological ingestion: Haiku follows discovery/instructions.md.

One stateless single-shot call per email (email + thread tail only; the
model never sees the DB). Catch-up by gmail id: processes every inbox email
not yet in ingest_log, oldest first. Apply = db.apply_op (per-field merge,
provenance). Instructions are prompt-cached. Resumable and idempotent.

Usage:
  set -a && . ../.env && set +a
  python3 ingest.py [--limit N] [--effort medium|high] [--db PATH] [--skip N]
"""
import argparse
import json
import sys
import time
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root
import gmail_io
import db as dblib  # populate/db.py (run from populate/)

HERE = Path(__file__).resolve().parent
MODEL = "claude-haiku-5-5"
MAX_TOKENS = 6000
PRICE_IN, PRICE_OUT, PRICE_CREAD, PRICE_CWRITE = 0.10, 0.50, 0.01, 0.125


def fetch_corpus():
    """All inbox+sent messages with headers/bodies, grouped and sorted.
    Cached to out/corpus_cache.json; refetched only when the mailbox's
    message count changes (throttled to respect Gmail's per-minute quota)."""
    svc = gmail_io.service("aps")
    ids, page = [], None
    while True:
        resp = gmail_io._retry_quota(
            lambda: svc.users().messages().list(
                userId="me", q="in:inbox OR in:sent",
                maxResults=500, pageToken=page).execute())
        ids += resp.get("messages", [])
        page = resp.get("nextPageToken")
        if not page:
            break
        time.sleep(0.4)
    cache_path = HERE / "out" / "corpus_cache.json"
    if cache_path.exists():
        cached = json.loads(cache_path.read_text())
        if cached.get("n_messages") == len(ids):
            print(f"corpus cache hit ({len(ids)} messages)", flush=True)
            return cached["msgs"]
    threads = {}
    for m in ids:
        threads.setdefault(m["threadId"], None)
    msgs = []
    for i, tid in enumerate(threads):
        time.sleep(0.5)
        if i and i % 50 == 0:
            print(f"  fetching threads… {i}/{len(threads)}", flush=True)
        for m in gmail_io.get_thread("aps", tid, trim_quotes=True):
            m["thread_id"] = tid
            msgs.append(m)
    # chronological: Gmail Date headers parse unevenly; use internalDate via a
    # second metadata pass? get_thread lacks internalDate — sort by parsed Date.
    from email.utils import parsedate_to_datetime
    for m in msgs:
        try:
            m["_ts"] = parsedate_to_datetime(m["date"]).timestamp()
        except Exception:
            m["_ts"] = 0
    msgs.sort(key=lambda m: (m["_ts"], m["gmail_id"]))
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps({"n_messages": len(ids), "msgs": msgs}))
    return msgs


def email_block(m):
    hdr = (f"Date: {m['date']}\nFrom: {m['from']}\nTo: {m['to']}"
           + (f"\nCc: {m['cc']}" if m.get("cc") else "")
           + f"\nSubject: {m['subject']}")
    return hdr + "\n\n" + m["body"]


def build_prompt(m, prior):
    parts = ["=== EMAIL TO PROCESS ===", email_block(m)]
    if prior:
        parts.append("\n=== EARLIER MESSAGES IN THIS THREAD (oldest first, context only) ===")
        for p in prior[-3:]:
            parts.append(email_block({**p, "body": p["body"][:900]}))
    parts.append("\nEmit the JSON envelope for the EMAIL TO PROCESS now.")
    return "\n\n".join(parts)


def parse_envelope(text):
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object")
    env = json.loads(text[start:end + 1])
    if not isinstance(env.get("ops", []), list):
        raise ValueError("ops not a list")
    return env


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--skip", type=int, default=0, help="skip first N (A/B windows)")
    ap.add_argument("--effort", default="medium")
    ap.add_argument("--db", default=str(HERE / "out" / "state.sqlite"))
    args = ap.parse_args()

    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    schema = dblib.load_schema()
    db = dblib.connect(args.db)
    dblib.create_tables(db, schema)
    done = dblib.processed_ids(db)

    instructions = (HERE.parent / "discovery" / "instructions.md").read_text()
    client = anthropic.Anthropic(max_retries=6)

    print("fetching corpus from Gmail…", flush=True)
    msgs = fetch_corpus()
    print(f"corpus: {len(msgs)} messages | already processed: {len(done)}", flush=True)

    by_thread_seen = {}
    usage = [0, 0, 0, 0]
    n = 0
    for i, m in enumerate(msgs):
        prior = by_thread_seen.setdefault(m["thread_id"], [])
        if m["gmail_id"] in done or i < args.skip:
            prior.append(m)
            continue
        if args.limit and n >= args.limit:
            break
        n += 1
        prompt = build_prompt(m, prior)
        env, err, raw, resp = None, None, "", None
        for attempt in range(2):
            msg_text = ("Return ONLY the JSON envelope.\n\n" + prompt) if attempt else prompt
            try:
                resp = client.messages.create(
                    model=MODEL, max_tokens=MAX_TOKENS,
                    output_config={"effort": args.effort},
                    system=[{"type": "text", "text": instructions,
                             "cache_control": {"type": "ephemeral"}}],
                    messages=[{"role": "user", "content": msg_text}])
            except Exception as e:
                err = f"api: {type(e).__name__}"
                time.sleep(5)
                continue
            usage[0] += resp.usage.input_tokens
            usage[1] += resp.usage.output_tokens
            usage[2] += getattr(resp.usage, "cache_read_input_tokens", 0) or 0
            usage[3] += getattr(resp.usage, "cache_creation_input_tokens", 0) or 0
            raw = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
            try:
                env = parse_envelope(raw)
                err = None
                break
            except (ValueError, json.JSONDecodeError) as e:
                err = f"parse: {e} | raw: {raw[:150]}"
        ts = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(m["_ts"]))
        anomalies, n_ops, tag = [], 0, None
        if env is not None:
            for op in env.get("ops", []):
                action, an = dblib.apply_op(db, schema, op, m["gmail_id"], ts)
                anomalies += an
                if action in ("create", "update"):
                    n_ops += 1
                elif action.startswith("skipped"):
                    anomalies.append(action)
            tag = (env.get("catchall") or {}).get("tag")
            if n_ops == 0 and not tag:
                tag = "other"
                anomalies.append("no ops and no catchall -> defaulted to other")
            if tag:
                db.execute("INSERT INTO catchall (gmail_id, date, sender, subject, tag) "
                           "VALUES (?,?,?,?,?)",
                           [m["gmail_id"], ts, m["from"], m["subject"], tag])
        db.execute("INSERT OR REPLACE INTO ingest_log (gmail_id, ts, ok, model, effort, "
                   "in_tok, out_tok, cache_read, ops, catchall_tag, anomalies, error) "
                   "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                   [m["gmail_id"], ts, 1 if env is not None else 0, MODEL, args.effort,
                    resp.usage.input_tokens if env is not None else 0,
                    resp.usage.output_tokens if env is not None else 0,
                    getattr(resp.usage, "cache_read_input_tokens", 0) or 0 if env is not None else 0,
                    n_ops, tag, "; ".join(anomalies) if anomalies else None, err])
        prior.append(m)
        if n % 25 == 0:
            cost = (usage[0]*PRICE_IN + usage[1]*PRICE_OUT + usage[2]*PRICE_CREAD
                    + usage[3]*PRICE_CWRITE) / 1e6
            print(f"processed {n} | ops so far logged | ${cost:.2f}", flush=True)

    cost = (usage[0]*PRICE_IN + usage[1]*PRICE_OUT + usage[2]*PRICE_CREAD
            + usage[3]*PRICE_CWRITE) / 1e6
    fails = db.execute("SELECT COUNT(*) AS c FROM ingest_log WHERE ok = 0")[0]["c"]
    print(f"DONE: {n} processed this run | failures in log: {fails} | "
          f"tokens in/out/cached {usage[0]:,}/{usage[1]:,}/{usage[2]:,} | ${cost:.2f}",
          flush=True)


if __name__ == "__main__":
    main()
