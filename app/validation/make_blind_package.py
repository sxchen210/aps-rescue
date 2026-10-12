"""Build the blinded third-party evaluation package for the QA comparison.

Inputs (committed evidence): app/out/qa_expectations.json (questions +
ground-truth keys) and app/out/qa_transcripts.jsonl (both arms' runs).

The package shows a judge, per question: the question, the authoritative
answer key, and the two final answers labeled Response 1/2 — assignment
randomized per question with a fixed seed. Stripped on purpose: arm labels,
tool logs, tool-call counts, timings, and the author's pre-registered
predictions ("expect") and rationales ("why"), all of which would unblind
or bias the judge. Answers are verbatim: they may mention their own method
(searching mail, querying tables); the instructions direct the judge to
grade factual content only. The arm mapping lands in blinding_key.json —
never show that file to the judge.

Usage: python3 make_blind_package.py   (writes to third_party/)
"""
import json
import random
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = HERE / "third_party"
SEED = 20261012

INSTRUCTIONS = """\
# Blind evaluation: nine operational questions, two anonymous responses each

You are an impartial judge. Two assistant configurations each answered the
same nine operational questions about a small foster-based dog rescue. For
every question below you get the question, an ANSWER KEY, and two responses
labeled **Response 1** and **Response 2**. Which configuration appears as
Response 1 was randomized independently for every question, so you cannot
track a configuration across questions by position.

The rescue is entirely synthetic (a simulation). The ANSWER KEY is
authoritative ground truth exported from the simulator that generated the
world. It outranks both responses and anything you might guess.

## Rules

1. **Grade only against the answer key.** Use no outside knowledge. If a
   response asserts something the key neither confirms nor contradicts,
   treat it as unverifiable — neither credit nor penalty.
2. **Ignore methodology entirely.** Responses may describe how they worked
   (searching email, reading threads, querying records, SQL, etc.). Method
   references must not move your scores in either direction, and do not
   try to infer or reward what kind of system produced an answer. You are
   grading WHAT is claimed, never HOW it was obtained.
3. **Facts are names, numbers, dates, and statuses.** For each response,
   identify (a) key facts it got right, (b) claims that contradict the key
   or invent entities, (c) key facts it omitted.
4. **Score each response 0–10:**
   - 10 — every key fact present, nothing false.
   - 7–9 — most key facts, no false claims.
   - 4–6 — substantial correct content but material omissions, or a
     mostly-correct answer carrying a false claim.
   - 1–3 — mostly incomplete or materially wrong.
   - 0 — unresponsive or predominantly false.
   A confident false claim costs more than an omission. A correct fact
   offered with honest uncertainty still earns credit. If two responses
   carry the same facts, the one that accurately characterizes its own
   completeness outranks one that overclaims.
5. **Counts matter.** When the key states a count, compare the response's
   count (stated or implied by its list) against it.
6. **Verdict per question:** `1`, `2`, or `tie`, justified in 2–4
   sentences citing specific names or numbers. Score first, verdict from
   the scores; declare `tie` when the scores are equal or within 1.
7. If a key seems internally inconsistent with both responses in a way you
   cannot resolve from the key alone, say `cannot adjudicate` for that
   question instead of guessing.

## Required output format

For each question, emit exactly one JSON block:

```json
{"question": N,
 "score_1": X, "score_2": Y,
 "facts_right_1": [...], "facts_wrong_1": [...],
 "facts_right_2": [...], "facts_wrong_2": [...],
 "verdict": "1" | "2" | "tie" | "cannot adjudicate",
 "rationale": "2-4 sentences citing specific facts"}
```

After all nine, finish with one line:
`TALLY — Response-1 wins: a | ties: b | Response-2 wins: c`
(That tally is positional and meaningless on its own; the experimenters
unblind it afterwards.)

---
"""


def main():
    exp = json.loads((ROOT / "app" / "out" / "qa_expectations.json").read_text())
    recs = [json.loads(l) for l in
            (ROOT / "app" / "out" / "qa_transcripts.jsonl").read_text().splitlines()
            if l.strip()]
    ans = {(r["qid"], r["arm"]): r["answer"].strip() for r in recs}

    rng = random.Random(SEED)
    # balanced counterbalancing, not independent coin flips: with 9 items a
    # run of flips can land 7-2 and let position bias correlate with arm.
    firsts = ["A"] * 4 + ["B"] * 5
    rng.shuffle(firsts)
    parts, key = [INSTRUCTIONS], []
    for i, e in enumerate(sorted(exp, key=lambda x: int(x["id"][1:])), 1):
        r1 = firsts[i - 1]
        r2 = "B" if r1 == "A" else "A"
        key.append({"package_q": i, "qid": e["id"], "response_1": r1, "response_2": r2})
        parts.append(
            f"## Question {i}\n\n{e['question'].strip()}\n\n"
            f"**ANSWER KEY (authoritative):** {e['gt'].strip()}\n\n"
            f"### Response 1\n\n{ans[(e['id'], r1)]}\n\n"
            f"### Response 2\n\n{ans[(e['id'], r2)]}\n\n---\n")

    OUT.mkdir(exist_ok=True)
    pkg = OUT / "blind_eval_package.md"
    pkg.write_text("\n".join(parts))
    (OUT / "blinding_key.json").write_text(json.dumps(
        {"seed": SEED, "note": "NEVER show this file to the judge",
         "map": key}, indent=1))

    # leak scan: nothing from the stripped fields may appear
    text = pkg.read_text()
    for bad in ("Arm A", "Arm B", '"expect"', "tool_log", "tool_calls",
                "qa_transcripts", "pre-registered prediction"):
        assert bad not in text, f"leak: {bad}"
    method_hits = sum(1 for m in ("SELECT", "SQL", "database", "gmail",
                                  "inbox", "search")
                      if re.search(m, text, re.I))
    print(f"wrote {pkg.name} ({len(text):,} chars, 9 questions) + blinding_key.json")
    print(f"method-mention terms present in verbatim answers: {method_hits} "
          f"(expected — rule 2 instructs the judge to ignore them)")


if __name__ == "__main__":
    main()
