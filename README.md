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
  root (both gitignored). `.env` carries the Turso credentials, the Sheet
  id, and an Anthropic API key used only by ingestion and draft triage —
  usage-capped, demo-scoped, revoked when the window closes. Shipping it
  is deliberate: metered calls make every ingestion and draft an
  attributable line item (measured economics: `populate/VERIFICATION.md`).
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

## Honest notes (short form — the full versions live in the linked files)

- **The showdown's search arm is an emulation** — steelmanned (same model,
  equal budget, full traces committed) but capped at ~15–20 results per
  query, no pagination. Self-graded: 3 wins / 6 ties / 0 losses.
  Independent blinded re-grade (GPT-6, arms anonymized, counterbalanced):
  **1 / 6 / 1, with 1 unadjudicated** — the ties and the roster win
  confirmed; one loss where the tables arm confidently asserted two
  DB-inherited errors. Both gradings + judge transcript + audit:
  `app/validation/third_party/`.
- **Blindness:** discovery and ingestion see only email — never simulator
  internals or ground truth (post-hoc scoring only; transcripts committed).
- **Verification is policy-scored:** status 97.8% under the stated policy,
  82.0% strict-exact; per-field varies (foster 92.8%, bio flag 87.6%).
  Policy and breakdown: `populate/VERIFICATION.md`.
- **Provenance is row-level, last-writer** (`source_email_id`,
  `updated_at`) — not per-field history.
- **The DB is machine-built and unedited** (one disclosed exception:
  boolean spelling normalization; facts untouched, verification re-run
  identical). Known quirks left in: Monsoon (mentions only, no row),
  Shasta's foster mis-extracted as "Dana", two dogs appearing slightly
  before their intake week, status labels lagging their correct dates, and
  Moraine's stale appointment (ingested before the contract had a `clear`
  verb; kept as the before-exhibit). Finding each took one query.
- **Known limits, left in:** no per-field temporal guard (a delayed old
  email can overwrite newer state; dated fields mitigate), and the schema
  is frozen — drift is detected and refused, never migrated. Scale beyond
  this ~950-email corpus (the reference inbox holds 117K+) is argument,
  not measurement.

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
the world: clear the inbox, re-run `scripts/aps_insert.py` (seed) and
`scripts/week1_inject.py` (extension), re-push Turso via
`scripts/push_turso.py --force`, refresh the mirror.
