# Verification: Haiku-populated tables vs. simulation ground truth

Run: 2026-10-11. All **831** inbox emails ingested serially (chronological,
stateless single-shot `claude-haiku-5-5` calls at `effort: medium`, following
`discovery/instructions.md` verbatim). **Zero parse failures, zero apply
anomalies, zero hallucinated entities.** Scored post-hoc against
`simulation/out/universe/ground_truth.json` (the simulator's true state —
never visible to discovery or ingestion). Raw report: `out/verify_full.json`.

## Headline

| table | result |
|---|---|
| dogs | **78/79 found**, 0 invented. status **97.4%**, current foster **93.1%**, spay/neuter date **100%** (49/49), adoption appointment date **100%** (20/20), adopter first name **100%** (20/20) |
| fosters | **90/90** people who fostered found; away/departure **dates 4/4 correct** (labels 2/4, see below); 6 extra rows = real offer-decliners, not inventions |
| foster_applications | **33/33 found, 33/33 lifecycle status correct** |
| events | **3/3** with dates, venue, times |
| event_rsvps | **56/56** (event, dog) confirmations matched |
| coverage | 831 = 742 emails→ops + 90 catchalled (1 both), auditable arithmetic; catchall share 10.8% |

Cost actuals: full populate **$0.36** (A/B included; ~**$0.0004/email**;
6.1M instruction tokens served from cache). Discovery (strong model, both
runs) was $8.65. The two-tier economics in one line: the schema cost ~25×
the entire three-month table population.

## Reading the imperfect numbers honestly

- **The ~88.5% cluster** (sex, age, size, breed, intake_date, photos/posted
  booleans ≈ 69/78): the 9 misses are all **pre-corpus dogs** — placed before
  the mailbox window, so their intake rosters, photos, and bios were never in
  any email. On dogs whose facts were actually evidenced, these fields are at
  or near **100%**. This is the system correctly refusing to guess.
- **The 1 missing dog (Monsoon)**: a pre-corpus dog who appears only inside
  three multi-dog RSVP replies — name-only mentions, zero attributes stated.
  Its RSVPs were captured; a `dogs` row was never seeded. 1/79, with nothing
  extractable beyond the name.
- **adopter_name**: ground truth stores invented full names, but emails only
  ever said first names; compared on what the corpus could know (first
  name), it's 20/20. The verifier was corrected to score this fairly.
- **fosters away/departed labels (2/4)**: all four rare-transition people
  have the **correct dates** (away windows, departure date). Two keep
  `status: active` because the announcing email *predates* the absence — at
  send time they weren't away yet. The schema's own availability rule
  ("free = active AND today outside the away window") still answers
  correctly from the dates; the enum label lags the calendar, the dated
  fields don't. A dated-fields win, and a known limitation of
  last-writer-wins status labels.
- **foster_name 93.1%** (54/58): misses concentrate in coverage/bridge
  handoffs where "who holds the dog *right now*" turns on which email came
  last; the coverage_* fields carry the windows.

## Effort A/B (pre-registered: medium vs high, low ruled out)

120-email windows, separate DBs: high gained one dog's age/breed; medium
found one extra foster; parse failures zero in both. **Medium selected**
per the tie rule (cheaper, faster). Record: `out/verify_medium.json`,
`out/verify_high.json`.

## Caveats

- Ground truth includes facts never emailed (pre-corpus dog attributes,
  adopter surnames); scoring counts only email-knowable facts as misses
  where identifiable, and this file flags each adjustment.
- Status labels are as-of-last-email; queries about "now" should prefer
  dated fields where present (the schema was designed accordingly).
- Single run, single seed corpus; numbers are for this fixture.

## v2 — after the week-1 extension injection (2026-10-12)

953 emails processed (831 seed + 121 injected + 1 live test), zero
failures. Against the as-of-Oct-16 ground truth: dogs **89/90** (Monsoon
remains the one name-only miss), status **97.8%**, vet dates and adoption
fields **100%**, fosters **98/98**, applications 40/40 found, events 4/4,
RSVPs 56/56. Per-email answer keys during injection: **60/60 fully
matched** (15 acceptance + 45 batch). Disclosures: (1) two extension
dogs ("Sferic", "Tuff") appear in medical emails dated before their
generated intake week — a generator causality slip; the extractor
correctly created rows from the emails, so they score as "ahead of
truth," not inventions; (2) the verifier's application-status map lacks
the new "received" outcome, so 7 correct rows show unscored; (3) the
away/departed status-label lag persists (dates correct, 4/4).
