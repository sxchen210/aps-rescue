"""Score the populated DB against simulation ground truth (post-hoc only).

Compares what is comparable, field by field, and reports per-table accuracy
plus completeness (coverage arithmetic: every email -> ops or catchall) and
hallucinated-entity counts. Writes a JSON report; VERIFICATION.md is written
from it at the end of the phase.

Usage: python3 verify.py [--db out/state.sqlite] [--json out/verify.json]
"""
import argparse
import json
import re
import sqlite3
from pathlib import Path

HERE = Path(__file__).resolve().parent
GT_PATH = HERE.parent / "simulation" / "out" / "universe" / "ground_truth.json"


def norm(v):
    return re.sub(r"[^a-z0-9]", "", str(v or "").casefold())


def datepart(v):
    m = re.search(r"\d{4}-\d{2}-\d{2}", str(v or ""))
    return m.group(0) if m else None


def truthy(v):
    return str(v).strip().casefold() in ("true", "1", "yes", "y")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(HERE / "out" / "state.sqlite"))
    ap.add_argument("--json", default=None)
    ap.add_argument("--gt", default=None)
    args = ap.parse_args()

    gt = json.loads(Path(args.gt).read_text() if args.gt else GT_PATH.read_text())
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    def rows(table):
        try:
            return [dict(r) for r in conn.execute(f'SELECT * FROM "{table}"')]
        except sqlite3.OperationalError:
            return []

    report = {"tables": {}, "coverage": {}, "notes": []}

    # ---- dogs -------------------------------------------------------------
    db_dogs = {norm(r.get("dog_name")): r for r in rows("dogs")}
    gt_dogs = {k: v for k, v in gt["dogs"].items() if not v.get("held_out")}
    field_hits = {}
    missing, found = [], 0

    def check(field, got, want, weight_key=None):
        k = weight_key or field
        h = field_hits.setdefault(k, [0, 0])
        h[1] += 1
        if got is None and want is None:
            h[0] += 1
            return
        if got is not None and want is not None and norm(got) == norm(want):
            h[0] += 1

    STATUS_OK = {"in_foster": {"in_foster"},
                 "adopted": {"adopted", "pending_adoption"},
                 "intake": {"needs_foster", "in_foster"}}
    for name, d in gt_dogs.items():
        r = db_dogs.get(norm(name))
        if r is None:
            missing.append(name)
            continue
        found += 1
        check("sex", r.get("sex"), d.get("sex"))
        check("age_group", r.get("age_group"), d.get("age_class"))
        check("size", r.get("size"), d.get("size"))
        check("breed", r.get("breed"), d.get("breed"))
        check("intake_date", datepart(r.get("intake_date")), d.get("intake"))
        # status (set-valued acceptance)
        h = field_hits.setdefault("status", [0, 0])
        h[1] += 1
        if (r.get("status") or "").strip() in STATUS_OK.get(d["status"], {d["status"]}):
            h[0] += 1
        # current foster (only for dogs in foster at window end)
        if d["status"] == "in_foster" and d.get("foster_history"):
            seg = d["foster_history"][-1]
            check("foster_name", r.get("foster_name"), seg.get("name"))
        # vet date (dogs fixed in-window have one)
        if d.get("vet_date"):
            check("spay_neuter_date", datepart(r.get("spay_neuter_date")), d["vet_date"])
        # pipeline booleans
        for b, gk in (("photos_received", "photos_date"), ("bio_received", "bio_date"),
                      ("posted", "posted_date")):
            h = field_hits.setdefault(b, [0, 0])
            h[1] += 1
            if truthy(r.get(b)) == bool(d.get(gk)):
                h[0] += 1
        if d.get("adopted"):
            # emails only ever carry the adopter's FIRST name; GT full names
            # are unknowable from the corpus — compare first tokens.
            got_first = (str(r.get("adopter_name") or "").split() or [""])[0]
            want_first = d["adopted"]["adopter"].split()[0]
            check("adopter_name", got_first, want_first)
            check("adoption_appt_date", datepart(r.get("adoption_appt_date")),
                  d["adopted"]["date"])
    extra_dogs = [r.get("dog_name") for k, r in db_dogs.items()
                  if k not in {norm(n) for n in gt_dogs}]
    report["tables"]["dogs"] = {
        "gt_dogs": len(gt_dogs), "found": found, "missing": missing,
        "hallucinated": extra_dogs,
        "fields": {k: {"acc": round(v[0] / v[1], 3), "n": v[1]}
                   for k, v in sorted(field_hits.items())}}

    # ---- fosters ----------------------------------------------------------
    db_f = {norm(r.get("foster_name")): r for r in rows("fosters")}
    gt_fosterers = {}
    for d in gt_dogs.values():
        for seg in d.get("foster_history", []):
            gt_fosterers[norm(seg["name"])] = seg["name"]
    f_found = sum(1 for k in gt_fosterers if k in db_f)
    vac = [h for h in gt["households"] if h["state"] == "vacation"]
    churn = [h for h in gt["households"] if h["state"] == "churned"]
    vac_ok = sum(1 for h in vac if (db_f.get(norm(h["name"])) or {}).get("status") == "away")
    churn_ok = sum(1 for h in churn if (db_f.get(norm(h["name"])) or {}).get("status") == "departed")
    report["tables"]["fosters"] = {
        "gt_people_who_fostered": len(gt_fosterers), "found": f_found,
        "rows_in_db": len(db_f),
        "vacation_marked_away": f"{vac_ok}/{len(vac)}",
        "moved_marked_departed": f"{churn_ok}/{len(churn)}"}

    # ---- applications -----------------------------------------------------
    db_a = {norm(r.get("applicant_name")): r for r in rows("foster_applications")}
    AMAP = {"approved": {"approved", "intro_call_scheduled"},
            "declined": {"declined"}, "stall": {"received"},
            "received": {"received", "intro_call_scheduled"}}
    a_found = a_status = 0
    for a in gt["applications"]:
        r = db_a.get(norm(a["name"]))
        if r:
            a_found += 1
            if (r.get("status") or "").strip() in AMAP.get(a["outcome"], set()):
                a_status += 1
    report["tables"]["foster_applications"] = {
        "gt": len(gt["applications"]), "found": a_found,
        "status_correct": a_status, "rows_in_db": len(db_a)}

    # ---- events + rsvps ---------------------------------------------------
    db_e = {datepart(r.get("event_date")) for r in rows("events")}
    report["tables"]["events"] = {
        "gt": gt["event_days"], "found": sorted(x for x in db_e if x),
        "all_present": all(d in db_e for d in gt["event_days"])}
    db_r = {(datepart(r.get("event_date")), norm(r.get("dog_name")))
            for r in rows("event_rsvps")}
    gt_rsvp = {(e, norm(n)) for n, d in gt_dogs.items() for e in d.get("events", [])}
    inter = len(gt_rsvp & db_r)
    report["tables"]["event_rsvps"] = {
        "gt_confirmed": len(gt_rsvp), "found_matching": inter,
        "rows_in_db": len(db_r)}

    # ---- coverage ---------------------------------------------------------
    il = rows("ingest_log")
    ok = [r for r in il if int(r["ok"] or 0)]
    with_ops = sum(1 for r in ok if int(r["ops"] or 0) > 0)
    with_tag = sum(1 for r in ok if r["catchall_tag"])
    report["coverage"] = {
        "processed_ok": len(ok), "failed": len(il) - len(ok),
        "emails_with_ops": with_ops, "emails_catchalled": with_tag,
        "both": sum(1 for r in ok if int(r["ops"] or 0) > 0 and r["catchall_tag"]),
        "anomaly_emails": sum(1 for r in ok if r["anomalies"]),
        "catchall_rows": len(rows("catchall"))}

    out = json.dumps(report, indent=1, ensure_ascii=False)
    if args.json:
        Path(args.json).write_text(out)
    print(out)


if __name__ == "__main__":
    main()
