# QA comparison: connector-style vs. connector+tables (read-only)

2026-10-12 · 9 pre-registered questions × 2 arms · same Opus 5.5, same
effort, same steelman prompt and time anchor, equal 25-call tool budgets ·
Arm A = Gmail search/read tools · Arm B = identical + one read-only SQL
tool on the hosted DB (with a stated "the DB may contain errors" caveat) ·
total cost $11.80 · transcripts: `qa_transcripts.jsonl` · GT pre-registered
in `qa_expectations.json` (committed before the run).

## Scoreboard (verdicts are the author's, auditable against GT + transcripts)

| q | question (short) | expected | verdict |
|---|---|---|---|
| 1 | which fosters are free right now | B | **B — clear win** |
| 2 | posted-dog fosters who never RSVPed (Oct 3) | B | tie |
| 3 | Sept adoptions count + avg days | B | **B — partial win** |
| 4 | ready to post but not posted | B | **B — slight win** |
| 5 | who has Moraine / her situation | B | tie |
| 6 | what did the clinic say re Scree | tie | tie ✓ |
| 7 | vet-day logistics options | tie | tie ✓ |
| 8 | summarize Hana's last email | A | tie |
| 9 | Hoarfrost ear, verbatim | A | tie |

**B 3 · tie 6 · A 0** (self-graded; a blinded third-party re-grade returned
B 1 · tie 6 · A 1 · 1 unadjudicated — see the addendum at the end and
`app/validation/third_party/RESULTS.md`). No question where table access hurt; several where
it was decisive. Three of five pre-registered B-wins did NOT materialize as
predicted — documented below, because the misses teach more than the hits.

## The decisive case (q1, roster/derived state)

A exhausted its budget needle-hunting and answered: "this is a partial
answer… I haven't confirmed any of them" — 11 hedged candidates, all
correct (precision 11/11), **recall 11/27**. B opened with
`SELECT * FROM fosters`, used the roster as a candidate map, spent its
remaining calls cross-checking email, and returned **13 confirmed + 16
probable ≈ 29 of the true 27** with per-person justifications — and
unprompted flagged "the database has several mistakes… so I didn't rely on
it alone." Same budget, ~2.5× the recall, equal precision, self-auditing.

## Where predictions failed (and why that's valuable)

- **q2 (negative space) = tie.** Predicted unanswerable-by-search because
  the blast was BCC. Wrong: June's per-dog "X is POSTED!" emails are cached
  breadcrumbs that let A reconstruct the posted-set, then diff against RSVP
  replies. Lesson: *search competes wherever the org's own mail caches
  per-item state.* The table advantage concentrates where no email ever
  held the answer (q1) or where the cache has gone stale.
- **q5 (Moraine stale-truth) = tie.** Predicted A would stop at the
  adoption thread. Wrong: every relevant thread contains "Moraine," so one
  name-search surfaces the full saga; both arms reconstructed
  adoption→fall-through→declined take-back→Theo Sandoval in 11–12 calls.
  Lesson: *entity-name questions are search-friendly; the demo centerpiece
  should be roster/derived/drift questions, not named-dog sagas.* Moraine
  becomes the honesty exhibit, not the kill shot.
- **q8/q9 (predicted A-wins) = ties.** Tables neither helped nor hurt pure
  retrieval; B even used the DB to locate the right thread faster (5 calls
  vs 8 on q9).

## Real but partial wins

- **q3 (aggregate):** neither arm produced "9 adoptions, avg 19 days" —
  because the corpus contains **no adoption-confirmation emails** (a
  simulation gap: appointments are announced, outcomes never are). A
  refused the number with accurate epistemics; B inferred 4 confirmed
  adoptions from alumni "update!" emails and computed the correct 18–19-day
  average on the computable subset. B materially better; both bounded by
  the corpus.
- **q4 (drift):** B found 5/7 (DB missing bio flags for Col and Slate —
  the predicted *maintenance-gaps-propagate* failure, observed); A found
  4–5/7 independently missing the same two. B's edge is real but inherits
  the DB's ~97% not 100%.

## Disclosed defects found during judging

1. GT annotation error (mine): q3's note said "incl. Moraine" but the
   computed list correctly excludes her (the fall-through nulls her
   adoption). True count incl. the reversed adoption is 10.
2. Simulator quirk: the vacation-coverage state machine transfers the dog
   permanently, so GT says Helena holds Doldrum, while the emails imply
   coverage ended and Silas resumed. Both arms (and any honest reader)
   said Silas; judged per-email-evidence, not per-GT, for that item.

## Implications for the demo

1. Feature the **q1 class** (derived roster/join questions) and
   **drift-vs-cached-roundup** as the side-by-side centerpieces; retire
   named-entity sagas to the honesty section.
2. B's emergent *map-then-verify* behavior (SQL for candidates, email for
   confirmation, flags DB errors) is the product story — show the tool
   traces, not just answers.
3. Scale argument (state it, don't overclaim): A hit its recall ceiling at
   **831 emails with 25 calls**; the reference inbox is 117,650 emails.
   Search degrades with corpus size; `SELECT` does not.
4. Both arms were competent and honest throughout — the comparison shows a
   capability delta on specific question classes, not a broken baseline.

## Addendum (2026-10-12): blinded third-party re-grade

A GPT-6 judge re-graded all nine questions blind (final answers only, arms
anonymized as Response 1/2, order counterbalanced, graded against the
pre-registered keys): **B 1 · tie 6 · A 1 · 1 unadjudicated.** All six
ties above are confirmed, and q1 — the centerpiece — is confirmed as a
clear B win on the same coverage grounds. q3 went unadjudicated because
the pre-registered key carries the ground-truth annotation error disclosed
under defect 1 above ("9 incl. Moraine" beside a list without her). q4
flipped to A: B confidently asserted the DB's two missing bio flags
(Col, Slate) as fact, and confident false claims outweighed A's omission
under the judge's rubric. That flip means this report's line "No question
where table access hurt" is wrong as stated: on q4, inheriting the DB's
errors cost B the question — the ~97%-not-100% caveat above, realized.
Full results, caveats, and the judge transcript:
`app/validation/third_party/`.
