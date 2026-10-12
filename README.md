# APS Rescue — live demo guide

A proof of concept for **self-building structured data** — entities,
relationships, and workflows discovered from free-form communication and
represented in tables instead of remaining trapped in text. The setup: a real shared
Gmail inbox mirroring a local animal rescue's foster inbox, with ~1,000
simulated email correspondences; Fable suggested the schema from the inbox
alone, Haiku 5.5 ingested every email to build today's state, and the demo
shows that point in time — plus new emails being processed live, and the
strength a database gives when answering questions that search-only inbox
access gets wrong. Everything is
synthetic (a simulated rescue; see `simulation/`), everything runs live (a
real Gmail inbox, a hosted database, a public Google Sheet), and every
claim traces to committed evidence.

Open a Claude Code session in this repo and type **`/aps-overview`** — it
tells the story and the order to try things.

## Three ways in

**1. Just watch (no setup).** Open the Google Sheet (link in the portal
note, or run `/aps-status`): one tab per table, an Activity log of
everything the system has done, and a Drafts tab mirroring every reply it
has written. Then skim the evidence: `populate/VERIFICATION.md` (accuracy
vs ground truth, twice), `app/out/QA_COMPARE_REPORT.md` and
`app/out/showdown_exhibit_1.md` (head-to-head results),
`discovery/DISCOVERY_NOTES.md` + `discovery/discovery_log*.jsonl` (how the
schema was earned, round by round).

**2. Drive it (5-minute setup).**
- Clone this repo; open it in Claude Code (CLI, desktop app, or IDE).
- From the portal bundle, drop `token_apsdemo.json` and `.env` at the repo
  root (both gitignored). `.env` carries the Turso database credentials,
  the Sheet id, and an Anthropic API key used only by the ingestion and
  draft-triage scripts. **About that key:** it is usage-capped, scoped to
  this demo, and will be revoked when the demo window closes — shipping it
  is acceptable only because this is a temporary demonstration. It is also
  deliberate: metered API calls make every ingestion and draft an
  attributable line item, which is the instrumentation for the question
  this prototype exists to answer — whether maintained tables earn their
  keep on cost over time (see the measured economics in
  `populate/VERIFICATION.md`).
- `pip install -r requirements.txt`
- Type `/aps-overview`, then follow its order. Without the API key, the
  read-only commands (`/aps-status`, `/aps-ask`, `/aps-showdown`) still
  work fully; only `/aps-simulate-email` and `/aps-ingest` need it.

**3. See the real mailbox.** Ask to be added as a Gmail **delegate** on
animalprotectiveservices2026@gmail.com — you'll open the actual inbox and
Drafts folder from your own Google account, no shared password. (Or simply
email the address and run `/aps-ingest` to watch your message become rows.)

## The commands

| command | what it does |
|---|---|
| `/aps-overview` | the premise + guided order (start here) |
| `/aps-status` | table counts, scenarios remaining, Sheet link |
| `/aps-ask "…"` | NL→SQL over the live DB; queries and rows shown; provenance on request |
| `/aps-simulate-email` | fires the next pooled scenario into the real inbox; five-beat narrative: arrived → Haiku thinking → ops envelope → draft decision (with reason, YES or NO) → what changed |
| `/aps-ingest` | catch-up: processes anything that arrived by any means (your own emails included) |
| `/aps-showdown "…"` | the head-to-head: two agents, same model and budget, one with SQL access — answers and tool traces side by side |

## Honest framing (read before judging)

- **The showdown's connector arm is an emulation** of search-and-read inbox
  access — steelmanned (same model, equal budget, diligence-maximizing
  prompt, full traces committed), with its own limits: its search tool
  returns at most ~15–20 threads per query with no pagination, and both
  arms run under a fixed tool budget. What the results show: maintaining
  structured state improved completeness on the tested operational
  questions within that interaction budget (3 wins / 6 ties / 0 losses on
  the pre-registered QA set; the roster question in
  `app/out/showdown_exhibit_1.md`). Retrieval tied on single-thread
  lookups and entity-name sagas, and the ties are reported as ties.
- **Blindness:** schema discovery and all ingestion see only email —
  never the simulator's internals or ground truth (which exist solely for
  post-hoc scoring; the discovery transcripts prove the schema was earned).
- **Provenance is row-level, last-writer:** each row stores the id of the
  most recent email that changed it (`source_email_id`, `updated_at`) —
  not per-field history. Update a dog's photos and the row now points at
  the photo email, not at whichever email set its foster or vet date.
  `ingest_log` records which emails were applied, but not per-field
  attribution.
- **Verification is policy-scored:** the headline status figure accepts
  `pending_adoption` where ground truth says `adopted` but no confirmation
  email ever arrived — 14 of 89 dogs in v2; strict-exact status is 82.0%.
  Per-field accuracy varies (current foster 92.8%, bio flag 87.6%).
  Extraction is near-perfect on facts the mail stated; facts the mail
  never confirmed stay at their last evidenced state. Policy and full
  per-field breakdown: `populate/VERIFICATION.md`.
- **Known quirks, left in deliberately** (the DB is machine-built and
  unedited — with one disclosed exception: boolean *spellings* were
  normalized to `'1'`/`'0'` store-wide after a harness serialization bug
  left `'True'` and `'1'` mixed in the same columns; facts untouched,
  verification re-run identical — see VERIFICATION.md): one dog exists
  only in RSVP mentions and has no row (Monsoon);
  one row's foster was mis-extracted as a coordinator ("Shasta" → "Dana");
  two dogs appear in mail slightly before their intake week (generator
  slip); away/departed status labels can lag their — correctly extracted —
  dates. Hand-fixing any of this would break the "built automatically"
  claim; finding it took one query each, which is rather the point. One
  more: a fallen-through adoption left a stale appointment date and
  adopter name on Moraine's row — when that email was ingested, the ops
  contract had no way to remove a value. The contract has since gained an
  explicit `clear` verb; Moraine's row stays as ingested, the before-case.
- **Two apply-layer limits, known and left in:** a delayed email processed
  after newer mail can overwrite newer state — batches apply in date
  order, but there is no per-field temporal guard (the dated-fields rule
  softens this: queries prefer stated dates over status labels). And the
  discovered schema is frozen: adding a field after populate has no
  migration path — ingest checks the schema against its discovery-emitted
  digest and the live tables, and refuses drift rather than migrating.
  Production would need signed schema artifacts and harness-run
  migrations.
- **Scale note:** the corpus is ~950 emails and the search arm already hit
  its budget ceiling there; the reference inbox this simulation is modeled
  on holds 117,000+. We did not test at that volume — the expectation that
  the gap widens (a `SELECT` does not reread the mailbox; search-and-read
  must) is argument, not measurement.

## The 90-second path (drive these four in order)

1. `/aps-status` — counts + Sheet opens in a tab.
2. `/aps-simulate-email` — hold on beats 3 and 4 (ops envelope; draft
   decision with reason), then cut to the Sheet refreshing and the draft
   in the Drafts tab.
3. `/aps-ask "which dogs are ready to post right now?"` — SQL + rows +
   answer.
4. `/aps-showdown` finale — the two answers side by side; end on the
   provenance click-through (Sheet row → the email that last touched it).

## Teardown

All credentials are demo-scoped, temporary, and revocable in one click
(Gmail token in the Google account's security page; Turso token in its
dashboard; the Anthropic key in the API console — it is usage-capped and
will be deprecated when the demo window closes). To reset
the world: clear the inbox, re-run `simulation/aps_insert.py` (seed) and
`app/week1_inject.py` (extension), re-push Turso via
`populate/push_turso.py --force`, refresh the mirror.
