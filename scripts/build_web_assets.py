"""Generate the web app's data files from committed evidence.

Emits web/data/schema.json (verbatim copy of the discovery artifact),
web/data/stats.json (evidence-strip numbers), and
web/data/discovery_replay.json (the committed discovery transcripts as a
renderable timeline — get_thread ids resolved to the subjects Fable
actually read, via the seeding state; presentation-only use of simulation
files, the extractor never sees them). Nothing on the web page is
hand-typed: every number is computed here from a committed artifact or is
a literal carrying its source pointer.

Usage: python3 scripts/build_web_assets.py   (deterministic; outputs committed)
"""
import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "data"


def norm(v):
    return re.sub(r"[^a-z0-9]", "", str(v or "").casefold())


def strict_status():
    """Strict-exact status score (the 82.0% figure), recomputed."""
    gt = json.loads((ROOT / "simulation" / "out" / "extension" /
                     "ground_truth_v2.json").read_text())
    conn = sqlite3.connect(f"file:{ROOT/'populate'/'out'/'state_v2.sqlite'}?mode=ro",
                           uri=True)
    conn.row_factory = sqlite3.Row
    db = {norm(r["dog_name"]): dict(r) for r in conn.execute("SELECT * FROM dogs")}
    n = hit = 0
    for name, g in gt["dogs"].items():
        if g.get("held_out"):
            continue
        r = db.get(norm(name))
        if r is None:
            continue
        n += 1
        if (r.get("status") or "").strip() == g["status"]:
            hit += 1
    return hit, n


CHAPTERS = [
    ("discovery_log.jsonl", "The discovery run",
     "Connected to the mailbox cold, with four tools and no other context, "
     "the strong model read until it understood the operation, then "
     "designed the schema and wrote the extraction playbook."),
    ("discovery_log_refine.jsonl", "Refine 1: fosters become first-class",
     "Operator feedback: “which fosters are free right now?” must "
     "be answerable. The model re-verified the away/decline/moving evidence "
     "and promoted the foster roster to its own table."),
    ("discovery_log_refine2.jsonl", "Refine 2: the clear verb",
     "The world produced cancellations the ops contract couldn't express "
     "(a fallen-through adoption left stale fields standing). The envelope "
     "gained an explicit clear list; the model re-read the real "
     "fall-through thread and made it the playbook's worked example."),
]


def discovery_replay():
    state = json.loads((ROOT / "simulation" / "out" / "seeded_ids.json").read_text())
    tid_to_name = {v: k for k, v in state["threads"].items()}
    name_to_subj = {}
    for f in ("corpus.jsonl", "extension/corpus_week1.jsonl",
              "extension/corpus_pool.jsonl"):
        p = ROOT / "simulation" / "out" / f
        if not p.exists():
            continue
        for line in p.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                name_to_subj.setdefault(r["thread"], r["subject"])

    def arg_of(t):
        name, inp = t["name"], t.get("input") or {}
        if name == "inbox_stats":
            return "mailbox overview"
        if name == "list_threads":
            return f"page {inp.get('page')}"
        if name == "search":
            q = inp.get("query", "")
            return f"“{q}”"
        if name == "get_thread":
            tid = inp.get("thread_id", "")
            subj = name_to_subj.get(tid_to_name.get(tid, ""), "")
            return subj or f"thread {tid[:10]}…"
        if name == "submit_artifacts":
            return "schema.json · instructions.md · DISCOVERY_NOTES.md"
        return ""

    chapters = []
    for fname, title, intro in CHAPTERS:
        rows = [json.loads(l) for l in
                (ROOT / "discovery" / fname).read_text().splitlines() if l.strip()]
        final = next((r for r in rows if r.get("final")), {})
        rounds, prev = [], 0.0
        for r in rows:
            if r.get("final"):
                continue
            rounds.append({
                "round": r["round"],
                "cost": r["cost_usd"],
                "text": (r.get("text") or "").strip(),
                "tools": [{"name": t["name"], "arg": arg_of(t)}
                          for t in r.get("tools", [])],
            })
            prev = r["cost_usd"]
        chapters.append({
            "title": title, "intro": intro, "rounds": rounds,
            "tool_calls": sum(len(r["tools"]) for r in rounds),
            "final": {"cost": final.get("cost_usd", prev),
                      "usage": final.get("usage", {}),
                      "submitted": final.get("submitted", False)},
        })
    (OUT / "discovery_replay.json").write_text(json.dumps(
        {"generated_by": "scripts/build_web_assets.py", "chapters": chapters},
        indent=1, ensure_ascii=False))
    return chapters


def sim_facts():
    """Counts for the Simulate tab, computed from committed files."""
    def nlines(p):
        return sum(1 for l in (ROOT / p).read_text().splitlines() if l.strip())
    gt = json.loads((ROOT / "simulation" / "out" / "extension" /
                     "ground_truth_full.json").read_text())
    facts = {
        "seed_emails": nlines("simulation/out/corpus.jsonl"),
        "week1_emails": nlines("simulation/out/extension/corpus_week1.jsonl"),
        "pool_total": nlines("simulation/out/extension/pool.jsonl"),
        "dogs": len(gt["dogs"]),
        "households": len(gt["households"]),
        "applications": len(gt["applications"]),
        "pattern_cards": len(list((ROOT / "simulation" / "patterns").glob("*.md"))),
    }
    (OUT / "sim.json").write_text(json.dumps(
        {"generated_by": "scripts/build_web_assets.py", "facts": facts},
        indent=1))
    return facts


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    schema_raw = (ROOT / "discovery" / "schema.json").read_text()
    (OUT / "schema.json").write_text(schema_raw)

    v = json.loads((ROOT / "populate" / "out" / "verify_v2.json").read_text())
    dogs, cov = v["tables"]["dogs"], v["coverage"]
    f = dogs["fields"]
    s_hit, s_n = strict_status()

    def pct(x):
        return f"{100 * x:.1f}%"

    stats = [
        {"label": "emails ingested", "value": f"{cov['processed_ok']:,}",
         "detail": f"{cov['failed']} failures; {cov['emails_catchalled']} catchalled",
         "source": "populate/out/verify_v2.json"},
        {"label": "dogs found", "value": f"{dogs['found']}/{dogs['gt_dogs']}",
         "detail": "vs simulator ground truth; 1 name-only miss",
         "source": "populate/out/verify_v2.json"},
        {"label": "fosters found",
         "value": f"{v['tables']['fosters']['found']}/{v['tables']['fosters']['gt_people_who_fostered']}",
         "detail": "every person who ever fostered",
         "source": "populate/out/verify_v2.json"},
        {"label": "status accuracy",
         "value": pct(f["status"]["acc"]),
         "detail": f"policy-scored; strict-exact {pct(s_hit / s_n)} "
                   f"({s_hit}/{s_n}); unconfirmed outcomes counted wrong",
         "source": "populate/VERIFICATION.md (policy stated there)"},
        {"label": "dated fields",
         "value": pct(f["spay_neuter_date"]["acc"]),
         "detail": f"vet dates {f['spay_neuter_date']['n']}/{f['spay_neuter_date']['n']}, "
                   f"adoption appts {f['adoption_appt_date']['n']}/{f['adoption_appt_date']['n']}",
         "source": "populate/out/verify_v2.json"},
        {"label": "maintenance cost", "value": "$0.0004/email",
         "detail": "populate run $0.36 total; discovery (strong model) $8.65",
         "source": "populate/VERIFICATION.md (cost actuals)"},
    ]
    (OUT / "stats.json").write_text(json.dumps(
        {"generated_by": "scripts/build_web_assets.py",
         "stats": stats}, indent=1, ensure_ascii=False))
    ch = discovery_replay()
    sf = sim_facts()
    print(f"wrote {OUT/'schema.json'} ({len(schema_raw):,}B), stats.json "
          f"({len(stats)} stats; strict status {s_hit}/{s_n}), "
          f"discovery_replay.json ({len(ch)} chapters, "
          f"{sum(len(c['rounds']) for c in ch)} rounds, "
          f"{sum(c['tool_calls'] for c in ch)} tool calls), "
          f"sim.json ({sf['seed_emails']}+{sf['week1_emails']} emails, "
          f"{sf['pool_total']} pooled)")


if __name__ == "__main__":
    main()
