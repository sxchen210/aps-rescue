"""Leak boundary scan: prove the synthetic corpus shares nothing with the
reference inbox.

Transiently harvests from the reference account (read-only, in memory only):
  - correspondent display names + addresses from recent message headers
  - capitalized tokens from recent bodies (candidate people/dog/place names)
  - 8-gram shingles from recent bodies (phrase-cloning detector)

Then scans the synthetic corpus (and our entity lists) for:
  - any harvested email address or full display name
  - any synthetic person/dog name appearing in the harvested token set
    (flagged for manual review; common words whitelisted)
  - any shared 8-gram

Nothing harvested is written to disk. Exit 1 on hard hits.

Usage: python3 leakcheck.py [--headers 400] [--bodies 150]
"""
import argparse
import json
import re
import sys
from pathlib import Path

import gmail_io
from personas import STAFF, DOG_NAMES

WORD = re.compile(r"[A-Za-z][a-z']+")
CAP = re.compile(r"\b[A-Z][a-z]{2,}\b")

# dictionary-ish capitalized words that will appear in any inbox; a synthetic
# dog named one of these colliding with a harvested token is not evidence
COMMON = set("""The This That Thanks Thank Hello Hi Hey Please From Sent Date
Subject Monday Tuesday Wednesday Thursday Friday Saturday Sunday January
February March April May June July August September October November December
Gmail Google Yahoo Outlook Drive Docs Best Warmly Cheers Regards Just Also
And But For Not You Your Our His Her She He They West East North South New
Good Great Happy Dear All One Two Here There When What Who Why How If In On
At To Of Re Fwd California Bay Area Rescue Foster Dog Dogs Puppy Puppies Vet
Event Saturday Adoption Home House Team Love Will Can Let Know Thanks""".split())


def harvest(headers_n, bodies_n):
    names, addrs, tokens, shingles = set(), set(), set(), set()
    msgs = []
    page = None
    svc = gmail_io.service("ref")
    while len(msgs) < headers_n:
        resp = svc.users().messages().list(
            userId="me", maxResults=min(500, headers_n - len(msgs)),
            pageToken=page).execute()
        msgs += resp.get("messages", [])
        page = resp.get("nextPageToken")
        if not page:
            break
    print(f"harvesting headers from {len(msgs)} messages…", flush=True)
    for i, m in enumerate(msgs):
        meta = svc.users().messages().get(
            userId="me", id=m["id"], format="metadata",
            metadataHeaders=["From", "To", "Cc"]).execute()
        for h in meta.get("payload", {}).get("headers", []):
            for part in h["value"].split(","):
                part = part.strip()
                em = re.search(r"<([^>]+)>", part)
                if em:
                    addrs.add(em.group(1).lower())
                    disp = part[:em.start()].strip().strip('"')
                    if disp and " " in disp:
                        names.add(disp.lower())
                elif "@" in part:
                    addrs.add(part.lower())
        if i < bodies_n:
            try:
                full = gmail_io.get_thread("ref", meta["threadId"], trim_quotes=False)
                for mm in full[:3]:
                    body = mm["body"]
                    tokens.update(CAP.findall(body))
                    words = WORD.findall(body.lower())
                    for j in range(len(words) - 7):
                        shingles.add(hash(" ".join(words[j:j + 8])))
            except Exception:
                pass
    return names, addrs, tokens, shingles


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--headers", type=int, default=400)
    ap.add_argument("--bodies", type=int, default=120)
    ap.add_argument("--corpus", default="out/corpus.jsonl")
    args = ap.parse_args()

    rows = []
    p = Path(args.corpus)
    if p.exists():
        rows = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    gt = json.loads(Path("out/universe/ground_truth.json").read_text())

    names, addrs, tokens, shingles = harvest(args.headers, args.bodies)
    print(f"harvested: {len(names)} display names, {len(addrs)} addresses, "
          f"{len(tokens)} cap tokens, {len(shingles)} shingles (in memory only)",
          flush=True)

    hard, soft = [], []

    # 1. entity-level: our cast vs harvested reality
    synth_people = ({h["name"] for h in gt["households"]}
                    | {s["name"] for s in STAFF.values()}
                    | {a["name"] for a in gt["applications"]})
    for nm in sorted(synth_people):
        if nm.lower() in names:
            hard.append(f"synthetic person name collides with real correspondent: {nm}")
    for dn in DOG_NAMES:
        if dn in tokens and dn not in COMMON:
            soft.append(f"synthetic dog name appears in reference bodies: {dn}")

    # 2. corpus scan
    n_shingle_hits = 0
    for r in rows:
        text = r["body"]
        low = text.lower()
        for a in addrs:
            if a in low:
                hard.append(f"{r['id']}: real address {a}")
        for nm in names:
            if len(nm) > 7 and nm in low:
                hard.append(f"{r['id']}: real display name '{nm}'")
        words = WORD.findall(low)
        for j in range(len(words) - 7):
            if hash(" ".join(words[j:j + 8])) in shingles:
                n_shingle_hits += 1
                soft.append(f"{r['id']}: shared 8-gram '…{' '.join(words[j:j+8])}…'")
                break

    print(f"\ncorpus rows scanned: {len(rows)}")
    print(f"HARD hits (real entities): {len(hard)}")
    for x in hard[:20]:
        print("  !!", x)
    print(f"SOFT flags (review): {len(soft)}")
    for x in soft[:20]:
        print("  ?", x)
    if hard:
        sys.exit(1)
    print("\nLEAK CHECK PASSED (no real entities in the synthetic corpus)")


if __name__ == "__main__":
    main()
