"""Pre-register the QA-comparison questions, expected winners, and
ground-truth answers (computed from simulation ground truth, never from the
DB either arm uses). Committed BEFORE the arms run.

Writes app/out/qa_expectations.json.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent  # app/
GT = json.loads((HERE.parent / "simulation" / "out" / "universe" / "ground_truth.json").read_text())
CORPUS = json.loads((HERE.parent / "populate" / "out" / "corpus_cache.json").read_text())["msgs"]

dogs = {k: v for k, v in GT["dogs"].items() if not v.get("held_out")}
households = GT["households"]


def hh_at(dog, day):
    for seg in dog["foster_history"]:
        if seg["start"] <= day and (seg["end"] is None or day < seg["end"]):
            return seg["name"]
    return None


def snippet(pred, n=1):
    out = []
    for m in CORPUS:
        if pred(m):
            out.append(f"{m['date'][:16]} | {m['subject'][:60]} | {m['body'][:200]}")
            if len(out) >= n:
                break
    return out


qs = []

# 1 — free fosters (B-win: join of roster state + current load, never emailed)
ever = {seg["name"] for d in dogs.values() for seg in d["foster_history"]}
free = sorted(h["name"] for h in households
              if h["name"] in ever and h["state"] == "available")
qs.append({
    "id": "q1", "expect": "B",
    "question": "Which of our fosters (people who have fostered for us before) are currently free — not fostering a dog right now and not away?",
    "gt": f"{len(free)} people: {', '.join(free)}",
    "why": "roster state x current placements; never co-located in any email"})

# 2 — negative space: posted-dog fosters who never RSVPed for Oct 3 (BCC blast)
day = "2026-10-03"
non_rsvp = set()
for name, d in dogs.items():
    if (d.get("posted_date") and d["posted_date"] <= day
            and not (d.get("adopted") and d["adopted"]["date"] < day)):
        holder = hh_at(d, day)
        if holder and day not in d.get("events", []):
            non_rsvp.add(f"{holder} ({name})")
qs.append({
    "id": "q2", "expect": "B",
    "question": "Which fosters with posted (adoptable) dogs never RSVPed to the October 3 adoption event?",
    "gt": f"{len(non_rsvp)}: {', '.join(sorted(non_rsvp))}",
    "why": "blast was BCC — no email enumerates invitees; absence is uncomputable by search"})

# 3 — aggregate arithmetic
sept = [(n, d) for n, d in dogs.items()
        if d.get("adopted") and "2026-09-01" <= d["adopted"]["date"] <= "2026-09-30"]
import datetime as dt
days = [(dt.date.fromisoformat(d["adopted"]["date"]) - dt.date.fromisoformat(d["intake"])).days
        for _, d in sept]
qs.append({
    "id": "q3", "expect": "B",
    "question": "How many dogs were adopted in September 2026, and what was their average number of days from intake to adoption?",
    "gt": f"{len(sept)} adoptions (incl. Moraine, whose adoption later fell through in October); "
          f"avg {sum(days)/len(days):.1f} days. Dogs: {', '.join(n for n, _ in sept)}",
    "why": "cross-month arithmetic over ~20 threads"})

# 4 — drift since the Oct 5 roundup
ready = sorted(n for n, d in dogs.items()
               if d["status"] == "in_foster" and d.get("photos_date") and d.get("bio_date")
               and d.get("fixed") and not d.get("posted_date"))
qs.append({
    "id": "q4", "expect": "B",
    "question": "Which dogs are ready to post right now (photos + bio in, spay/neuter done) but not yet posted?",
    "gt": f"{len(ready)}: {', '.join(ready) or 'none'}",
    "why": "the Oct 5 roundup email is a stale cache; state moved after it"})

# 5 — stale-thread truth
mor = dogs["Moraine"]
qs.append({
    "id": "q5", "expect": "B",
    "question": "Who has Moraine right now — what's her current situation?",
    "gt": f"status {mor['status']}, with {mor['foster_history'][-1]['name']} "
          f"(adoption on {mor['timeline'][-2][1] if len(mor['timeline'])>1 else '?'} fell through — landlord; "
          f"timeline tail: {mor['timeline'][-3:]})",
    "why": "strongest search signal (adoption appt thread) is stale truth"})

# 6/7 — expected ties (cached/single-thread answers)
qs.append({
    "id": "q6", "expect": "tie",
    "question": "What did the Crestview clinic say when we sent them Scree's records about the cloudy eye?",
    "gt": "Reference (from corpus): " + " || ".join(snippet(
        lambda m: "scree" in m["subject"].casefold() and "records" in m["subject"].casefold(), 2)),
    "why": "single-thread retrieval; connector-class strength"})
qs.append({
    "id": "q7", "expect": "tie",
    "question": "What are the drop-off and pickup logistics options for a spay/neuter day?",
    "gt": "den default 6:30AM both ways (volunteers drive); overnight drop at the den after 9PM night before; direct at Crestview Livermore 7:30AM drop / 3-4PM pickup; fasting from midnight",
    "why": "stated verbatim in every vet blast — a cached answer"})

# 8/9 — expect A (pure retrieval / verbatim nuance beats one-line note)
last_hana = [m for m in reversed(CORPUS) if "hana.faraday" in m["from"]][0]
qs.append({
    "id": "q8", "expect": "A",
    "question": "Summarize the most recent email Hana Faraday sent us.",
    "gt": f"Reference: {last_hana['date'][:16]} | {last_hana['subject'][:60]} | {last_hana['body'][:220]}",
    "why": "pure retrieval; tables add nothing"})
qs.append({
    "id": "q9", "expect": "A",
    "question": "What exactly did the foster report about Hoarfrost's ear, in their own words?",
    "gt": "Reference: " + " || ".join(snippet(
        lambda m: "hoarfrost" in m["subject"].casefold() and "ear" in m["subject"].casefold(), 1)),
    "why": "verbatim detail; the table keeps only a one-line health_note"})

out = HERE / "out"
out.mkdir(exist_ok=True)
(out / "qa_expectations.json").write_text(json.dumps(qs, indent=1, ensure_ascii=False))
for q in qs:
    print(f"{q['id']} [{q['expect']}] {q['question'][:70]}")
    print(f"   GT: {q['gt'][:140]}")
