"""Add four cancellation scenarios to the firing pool (clear-verb tests).

Review round 2 added an explicit "clear" list to the ops envelope; these
scenarios exercise it across the workflows the refined instructions cover:
adoption fall-through, coverage cancellation, health-note resolution, and
a dog pulled from the surgery list. Constructed against current universe
state (sanctioned use of simulation internals); candidate names were
checked against every unfired pool entry so nothing here contradicts a
scenario that fires later. The one designed dependency: the Marram pull
(c00004) sits AFTER the 10/21 vet blast (x00084) and Daniela's overnight
opt-in (x00095) in file order, so the facts it clears exist by the time it
fires. Idempotent: refuses to run twice.

Usage: python3 add_cancellation_scenarios.py
"""
import json
from pathlib import Path

POOL = Path(__file__).resolve().parent / "out" / "extension" / "pool.jsonl"


def sc(id_, ts, thread, from_, subject, body, type_, expected):
    return {"id": id_, "ts": ts, "thread": thread, "from": from_,
            "subject": subject, "body": body,
            "message_id": f"<{id_}.{thread.replace('_', '-')}@apsdemo.sim>",
            "labels": ["INBOX", "UNREAD"], "type": type_,
            "expected_ops": expected}


EARLY = [  # inserted right after the first pool entry
    sc("c00001", "2026-10-17T13:05:00-07:00", "cancel_Lassen",
       "Zoe <zoe.kmb@gmail.com>", "So sorry — we can't take Lassen",
       "Hi — this is a hard email to write. We met Lassen at his foster's "
       "place and he's wonderful, but my job situation changed suddenly "
       "last week (I'll be traveling most of every month through spring) "
       "and it wouldn't be fair to him. We have to back out of the "
       "adoption. I'm so sorry for the trouble — I hope he finds his "
       "people quickly.\n\nZoe",
       "cancellation_adoption",
       [{"table": "dogs", "match": {"dog_name": "Lassen"},
         "set_includes": ["status"],
         "clears_includes": ["adoption_appt_date", "adopter_name"]}]),
    sc("c00002", "2026-10-17T13:42:00-07:00", "cancel_coverage_Granite",
       "Farah Villanueva <farah.villanueva@gmail.com>",
       "Coverage for Granite — not needed after all",
       "Hi all — update from me: the trip is over early (the conference "
       "half of it was cancelled), we got home last night, and Granite is "
       "back with me as of this morning — thank you Devi, you're a star. "
       "So the coverage arrangement is done and you can take it off the "
       "books; I'm home and around from here on out.\n\nFarah",
       "cancellation_coverage",
       [{"table": "dogs", "match": {"dog_name": "Granite"},
         "clears_includes": ["coverage_foster", "coverage_start_date",
                             "coverage_end_date"]},
        {"table": "fosters", "match": {"foster_name": "Farah Villanueva"},
         "set_includes": ["status"],
         "clears_includes": ["away_start_date", "away_end_date"]}]),
    sc("c00003", "2026-10-17T14:12:00-07:00", "health_Gale_resolved",
       "Bennett Grimaldi <bennett.grimaldi@icloud.com>", "Gale - cough gone",
       "Good news for once: Gale's nighttime cough has been completely "
       "gone for over a week. The vet volunteer followed up with me "
       "yesterday and said we're all clear — nothing to treat, no "
       "follow-up needed. So that health note can be closed out. He's "
       "eating like a horse and sleeping like a rock.\n\nBennett",
       "cancellation_health_resolved",
       [{"table": "dogs", "match": {"dog_name": "Gale"},
         "clears_includes": ["health_note"]},
        {"table": "fosters", "match": {"foster_name": "Bennett Grimaldi"},
         "set_includes": ["status"]}]),
]
LATE = [  # inserted after x00091 (both 10/21 vet opt-ins have fired by then)
    sc("c00004", "2026-10-19T15:35:00-07:00", "vet_1021",
       "Daniela Quijano <daniela.quijano@gmail.com>",
       "Re: APS Rescue_10/21 Wednesday_Livermore_Spay/Neuter Appts",
       "Update on Marram: our vet volunteer listened to her chest "
       "yesterday and she still has a kennel-cough rattle, so she is NOT "
       "cleared for surgery. Please pull her from Wednesday's (10/21) "
       "list and cancel the overnight spot we'd arranged — we'll "
       "reschedule once she's fully clear.\n\nDaniela\n\nSent from my iPhone",
       "cancellation_vet_pull",
       [{"table": "dogs", "match": {"dog_name": "Marram"},
         "clears_includes": ["spay_neuter_date", "transport_option"]}]),
]


def main():
    rows = [json.loads(l) for l in POOL.read_text().splitlines() if l.strip()]
    if any(r["id"].startswith("c000") for r in rows):
        print("cancellation scenarios already present — nothing to do")
        return
    text = " ".join(r["subject"] + " " + r["body"] + " " + r["from"] for r in rows)
    for name in ("Lassen", "Zoe", "Granite", "Devi Villanueva", "Gale",
                 "Bennett Grimaldi"):
        assert name not in text, f"pool collision: {name}"
    out = []
    for r in rows:
        out.append(r)
        if r["id"] == "x00118":
            out.extend(EARLY)
        if r["id"] == "x00091":
            out.extend(LATE)
    assert len(out) == len(rows) + 4, "anchor entries not found"
    POOL.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in out) + "\n")
    print(f"pool: {len(rows)} -> {len(out)} entries "
          f"(c00001-3 after x00118; c00004 after x00091)")


if __name__ == "__main__":
    main()
