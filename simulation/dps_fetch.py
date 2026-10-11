"""Distillation CLI: search and print threads from the reference inbox.

Read-only. Output is consumed transiently in a working session to write
structure cards (patterns/*.md); it is never saved or committed.

Usage:
  python3 dps_fetch.py --query "spay OR neuter" --sample 5
  python3 dps_fetch.py --thread <thread_id>
  python3 dps_fetch.py --stats            # light volume/shape numbers
"""
import argparse
import collections

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root: gmail_io
import gmail_io


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", default="")
    ap.add_argument("--sample", type=int, default=5)
    ap.add_argument("--thread")
    ap.add_argument("--max-body", type=int, default=1200)
    ap.add_argument("--stats", action="store_true")
    args = ap.parse_args()

    if args.thread:
        print(gmail_io.render_thread(
            gmail_io.get_thread("ref", args.thread), args.max_body))
        return

    if args.stats:
        prof = gmail_io.profile("ref")
        print(f"mailbox: {prof['emailAddress']} | ~{prof['messagesTotal']} messages total")
        threads = gmail_io.search_threads("ref", "newer_than:60d", limit=200)
        sizes = collections.Counter()
        for t in threads[:60]:
            msgs = gmail_io.get_thread("ref", t["id"], trim_quotes=False)
            sizes[min(len(msgs), 8)] += 1
        print("thread-size histogram (last 60 sampled, 8=8+):",
              dict(sorted(sizes.items())))
        return

    threads = gmail_io.search_threads("ref", args.query, limit=args.sample)
    print(f"{len(threads)} threads for query: {args.query!r}\n")
    for t in threads:
        msgs = gmail_io.get_thread("ref", t["id"], trim_quotes=True)
        print(f"==================== thread {t['id']} ({len(msgs)} msgs) ====================")
        print(gmail_io.render_thread(msgs, args.max_body))


if __name__ == "__main__":
    main()
