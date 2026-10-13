"""Seed the APS demo inbox from the rendered corpus.

Chronological messages.insert with dateHeader timestamps; outbound staff mail
gets SENT, inbound gets INBOX (+UNREAD only for the freshest days, so the
inbox looks lived-in rather than 841-unread). Gmail threadIds are captured
from each thread's first insert and passed explicitly afterward, so threads
assemble deterministically. Idempotent via out/seeded_ids.json.

Usage: python3 aps_insert.py [--corpus out/corpus.jsonl] [--limit N]
"""
import argparse
import json
import re
import time
from pathlib import Path

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root: gmail_io
import gmail_io

SIM_OUT = Path(__file__).resolve().parent.parent / "simulation" / "out"

UNREAD_AFTER = "2026-10-07"


def mid_for(row):
    t = re.sub(r"[^A-Za-z0-9]+", "-", row["thread"])
    return f"<{row['id']}.{t}@apsdemo.sim>"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=str(SIM_OUT / "corpus.jsonl"))
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    rows = [json.loads(l) for l in Path(args.corpus).read_text().splitlines() if l.strip()]
    rows.sort(key=lambda r: r["ts"])
    if args.limit:
        rows = rows[:args.limit]

    state_path = SIM_OUT / "seeded_ids.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {"msgs": {}, "threads": {}}
    chain = {}  # thread -> list of message-ids (rebuilt every run for headers)

    inserted = skipped = failed = 0
    for i, r in enumerate(rows):
        mids = chain.setdefault(r["thread"], [])
        my_mid = mid_for(r)
        if r["id"] in state["msgs"]:
            mids.append(my_mid)
            skipped += 1
            continue
        in_reply_to = mids[-1] if mids else None
        references = " ".join(mids[-10:]) if mids else None
        labels = list(r["labels"])
        if "UNREAD" in labels and r["ts"][:10] < UNREAD_AFTER:
            labels.remove("UNREAD")
        from email.utils import format_datetime
        import datetime as dt
        date_hdr = format_datetime(dt.datetime.fromisoformat(r["ts"]))
        for attempt in range(4):
            try:
                resp = gmail_io.insert_message(
                    "aps", from_addr=r["from"], to=", ".join(r["to"]),
                    cc=", ".join(r["cc"]) if r["cc"] else None,
                    subject=r["subject"], body=r["body"], date=date_hdr,
                    message_id=my_mid, in_reply_to=in_reply_to,
                    references=references, label_ids=labels,
                    thread_id=state["threads"].get(r["thread"]))
                state["msgs"][r["id"]] = resp["id"]
                state["threads"].setdefault(r["thread"], resp.get("threadId"))
                mids.append(my_mid)
                inserted += 1
                break
            except Exception as e:
                if attempt == 3:
                    failed += 1
                    print(f"FAILED {r['id']}: {type(e).__name__}: {e}")
                else:
                    time.sleep(2 * (attempt + 1))
        if (inserted + skipped) % 50 == 0:
            state_path.write_text(json.dumps(state))
            print(f"progress: {inserted} inserted, {skipped} skipped, {failed} failed "
                  f"({i+1}/{len(rows)})", flush=True)
    state_path.write_text(json.dumps(state))
    prof = gmail_io.profile("aps")
    print(f"DONE: {inserted} inserted, {skipped} skipped, {failed} failed")
    print(f"mailbox now: {prof['emailAddress']} with {prof['messagesTotal']} messages, "
          f"{len(state['threads'])} threads tracked")


if __name__ == "__main__":
    main()
