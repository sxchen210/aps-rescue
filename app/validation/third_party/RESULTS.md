# Blind third-party re-grade — results (run 1: GPT-6, 2026-10-12)

Judge: ChatGPT (GPT-6), fresh chat, given only `blind_eval_package.md`.
Saved transcript: `judge_gpt-6_2026-10-12.md`. Unblinded mechanically with
`unblind.py`; the full grading audit (every fact-count in the judge's
output re-checked against the answer keys) was done by a separate agent
session and is summarized here.

## Both tallies, side by side

| grading | B wins | ties | A wins | unadjudicated |
|---|---|---|---|---|
| author (self-graded, `app/out/QA_COMPARE_REPORT.md`) | 3 | 6 | 0 | 0 |
| blind third-party (GPT-6) | 1 | 6 | 1 | 1 |

## Per question

| qid | self-grade | judge (unblinded) | agree |
|---|---|---|---|
| q1 free-foster roster | B clear win | **B** | yes — the centerpiece claim survives blind review (26/27 vs 11/27 coverage, same grounds) |
| q2 coverage holders | tie | tie | yes |
| q3 adoptions + avg days | B partial win | **cannot adjudicate** | no — the pre-registered key says "9 adoptions (incl. Moraine)" beside a 9-dog list that excludes her; that is the ground-truth annotation error already disclosed in the self-grade report, shipped to the judge uncorrected, and the judge correctly refused to guess |
| q4 ready-to-post | B slight win | **A** | no — both arms found the same 5 of 7; the judge weighted B's two confident false claims ("Col/Slate aren't fixed yet" — exactly the DB's missing bio flags) above A's plain omission and hedged miss, per the rubric's confident-error-costs-more rule. The 4-vs-6 margin was a discretionary call; a tie was defensible |
| q5 Moraine saga | tie | tie | yes |
| q6 Scree/Crestview | tie | tie (10/9, within-1) | yes |
| q7 vet-day logistics | tie | tie | yes |
| q8, q9 single-thread lookups | tie | tie | yes |

Agreement 7/9; both disagreements are on self-graded B wins.

## What this does to the self-graded claim

- All six self-graded ties are independently confirmed, and q1 — the
  result the demo leans on — is confirmed as a clear B win on the same
  grounds (coverage).
- The self-grade report's sentence "No question where table access hurt"
  does not survive the blind run: on q4, the tables arm asserted two
  DB-inherited errors confidently and that cost it the question. The
  report carries an addendum saying so.
- q3 is evidence about the package, not the arms: the known key defect
  made the punt inevitable. A corrected-key re-grade of q3 alone is the
  honest fix, not re-counting it for either side.

## Caveats (from the audit)

- Single judge, single pass, nine questions; per-question score magnitudes
  are noisy — only verdicts are worth citing.
- Blinding is positional only: the verbatim answers mention their own
  methods, so the judge could have inferred which system was which. The
  audit found no sign it did so in scoring (no rationale references
  method; the two decided questions split 1–1 across arms).
- Two keys carry known simulator quirks (q2's vacation-coverage holder,
  q7's 6:30-both-ways default); the judge applied them symmetrically, so
  no verdict moved.
- Audit verdict on the judge run: sound-with-caveats — fact extraction
  accurate against the keys in every checked case, rubric applied
  consistently; q4's margin is the one discretionary call.

## Open follow-ups (not yet run)

Corrected-key re-grade of q3; a second judge (different model or an
order-swapped rerun) before leaning on any per-question verdict beyond q1.
