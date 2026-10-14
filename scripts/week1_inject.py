"""Phase C driver: inject week-1 history (enrich AND test).

Each corpus_week1 email is inserted with its original backdated timestamp,
threaded onto existing Gmail threads via the shared seeded-ids state, then
immediately ingested (blind) and scored against its expected_ops answer key.
Draft triage is OFF during history injection (staff replies are part of the
history); after the drip, one triage pass covers the genuinely open tail
(threads whose latest message is inbound and recent).

Usage (env loaded, APS_DB=turso):
  python3 week1_inject.py --limit 15 --verbose     # interactive acceptance
  python3 week1_inject.py                          # continue the rest
  python3 week1_inject.py --tail-triage            # open-tail drafts pass
"""
import argparse
import datetime as dt
import json
import re
import sys
import time
from email.utils import format_datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "populate"))
sys.path.insert(0, str(HERE.parent / "app"))
import gmail_io
import db as dblib
import pipeline

EXT = HERE.parent / "simulation" / "out" / "extension"
STATE_PATH = HERE.parent / "simulation" / "out" / "seeded_ids.json"
UNREAD_AFTER = "2026-10-15"


def mid_for(row):
    t = re.sub(r"[^A-Za-z0-9]+", "-", row["thread"])
    return f"<{row['id']}.{t}@apsdemo.sim>"


def quiet_event(stage, text):
    pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--tail-triage", action="store_true")
    args = ap.parse_args()

    db = dblib.connect()
    state = json.loads(STATE_PATH.read_text())
    rows = [json.loads(l) for l in (EXT / "corpus_week1.jsonl").read_text().splitlines()
            if l.strip()]
    rows.sort(key=lambda r: r["ts"])

    if args.tail_triage:
        done = 0
        results = []
        # open tail = inbound, recent, latest in its thread
        seen_threads = set()
        for r in reversed(rows):
            gid = state["msgs"].get(r["id"])
            if not gid or r["thread"] in seen_threads:
                continue
            seen_threads.add(r["thread"])
            if "animalprotective" in r["from"] or r["ts"][:10] < UNREAD_AFTER:
                continue
            msgs = gmail_io.get_thread("aps", state["threads"].get(r["thread"], ""),
                                       trim_quotes=True) if state["threads"].get(r["thread"]) else []
            if not msgs or msgs[-1]["gmail_id"] != gid:
                continue
            m = msgs[-1]
            m["thread_id"] = state["threads"][r["thread"]]
            m["prior"] = msgs[:-1]
            res = {"email": m, "catchall": None, "applied": []}
            d = pipeline.triage_and_draft(res, db)
            results.append((r["subject"], bool(d)))
            done += 1
        print(f"tail triage: {done} candidates -> {sum(1 for _, x in results if x)} drafts")
        for s, x in results:
            print(("DRAFT " if x else "no    ") + s[:60])
        return

    on_event = pipeline.print_event if args.verbose else quiet_event
    scorecards, n = [], 0
    for r in rows:
        if r["id"] in state["msgs"]:
            continue
        if args.limit and n >= args.limit:
            break
        n += 1
        labels = list(r["labels"])
        if "UNREAD" in labels and r["ts"][:10] < UNREAD_AFTER:
            labels.remove("UNREAD")
        date_hdr = format_datetime(dt.datetime.fromisoformat(r["ts"]))
        resp = gmail_io.insert_message(
            "aps", from_addr=r["from"], to=", ".join(r["to"]),
            cc=", ".join(r["cc"]) if r["cc"] else None,
            subject=r["subject"], body=r["body"], date=date_hdr,
            message_id=mid_for(r), label_ids=labels,
            thread_id=state["threads"].get(r["thread"]))
        state["msgs"][r["id"]] = resp["id"]
        state["threads"].setdefault(r["thread"], resp.get("threadId"))
        STATE_PATH.write_text(json.dumps(state))

        results = pipeline.ingest_new(db, on_event=on_event)
        mine = next((x for x in results if x["email"]["gmail_id"] == resp["id"]), None)
        verdict = "no-key"
        exp = r.get("expected_ops")
        if exp and mine:
            hits = 0
            for e in exp:
                for a in mine["applied"]:
                    if a["table"] != e["table"]:
                        continue
                    m_ok = all(dblib.norm_key(((a["match"] or {}).get(k)
                                               or (a["set"] or {}).get(k) or ""))
                               == dblib.norm_key(v) for k, v in e["match"].items())
                    f_ok = all(f in (a["set"] or {}) or f in (a["match"] or {})
                               for f in e.get("set_includes", []))
                    if m_ok and f_ok:
                        hits += 1
                        break
            verdict = f"{hits}/{len(exp)}"
        scorecards.append({"id": r["id"], "subject": r["subject"][:56],
                           "type": r["facts"].get("type") or r["facts"].get("template"),
                           "score": verdict,
                           "err": mine["error"] if mine else "NOT-INGESTED"})
        line = f"[{n}] {verdict:>7} | {r['facts'].get('type') or r['facts'].get('template'):<22} | {r['subject'][:48]}"
        print(line, flush=True)
    full = [s for s in scorecards if "/" in s["score"]]
    perfect = sum(1 for s in full if s["score"].split("/")[0] == s["score"].split("/")[1])
    print(f"\ninjected {n} | scored {len(full)} | fully-matched {perfect} | "
          f"errors {sum(1 for s in scorecards if s['err'])}")
    (HERE.parent / "app" / "out" / "week1_scorecards.jsonl").open("a").write(
        "\n".join(json.dumps(s) for s in scorecards) + "\n")


if __name__ == "__main__":
    main()
