# Third-party blind re-grade of the QA comparison

The QA comparison's published verdicts (B 3 · tie 6 · A 0 in
`app/out/QA_COMPARE_REPORT.md`) were graded by the author. This package
lets an independent judge — a different model vendor, or a person — re-grade
the same nine questions blind.

## What the judge sees

`blind_eval_package.md`, and nothing else: for each question, the question
text, the authoritative answer key (exported from the simulator), and the
two arms' final answers labeled Response 1 / Response 2. Which arm appears
first is counterbalanced (4 questions A-first, 5 B-first, order shuffled
with seed 20261012), so position never tracks arm. Stripped from the
package: arm labels, tool logs, tool-call counts, timings, and the
author's pre-registered predictions and rationales.

Answers are verbatim, so they may mention their own method (searching
mail, querying tables, SQL). Rule 2 of the judge instructions directs that
method mentions must not move scores; grading is facts-vs-key only.

## How to run it

1. Open a **fresh** chat with the judge model (no system context, no
   earlier conversation, no files beyond the package).
2. Paste or upload `blind_eval_package.md` only. **Never**
   `blinding_key.json` (the unblinding map) and never this file.
3. Save the judge's complete output to
   `third_party/judge_<model>_<date>.md`.

## Unblinding and reporting

```
python3 app/validation/unblind.py app/validation/third_party/judge_<model>_<date>.md
```

prints the per-question verdicts mapped back to arms and the A/tie/B
tally. The tally is reported as-is next to the self-graded result,
whichever way it points.

## Reproducing the package

`python3 app/validation/make_blind_package.py` rebuilds both files
deterministically from the committed evidence
(`app/out/qa_expectations.json`, `app/out/qa_transcripts.jsonl`).
