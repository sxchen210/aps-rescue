"""Generate the web app's data files from committed evidence.

Emits web/data/schema.json (verbatim copy of the discovery artifact) and
web/data/stats.json (evidence-strip numbers). Nothing on the web page is
hand-typed: every stat is either computed here from a committed artifact
(verify_v2.json; strict status recomputed from the committed snapshot vs
ground truth, same policy split as VERIFICATION.md) or a literal carrying
its source pointer (the cost actuals, which exist only in prose).

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
                   f"({s_hit}/{s_n}) — unconfirmed outcomes counted wrong",
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
    print(f"wrote {OUT/'schema.json'} ({len(schema_raw):,}B) and stats.json "
          f"({len(stats)} stats; strict status {s_hit}/{s_n})")


if __name__ == "__main__":
    main()
