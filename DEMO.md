# APS Rescue — live demo guide

A proof of concept for **self-building tables**: a strong model discovered a
database schema from a busy shared inbox, a cheap model maintains it
continuously, and the resulting state answers operational questions and
drafts replies that search-only inbox access gets wrong. Everything is
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
  draft-triage scripts.
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
  prompt, full traces committed). The claim it supports is architectural:
  retrieval alone cannot enumerate absences, aggregate hundreds of threads,
  or notice silently superseded conclusions. Screenshots of the actual
  Gmail connector answering the same questions are in the exhibits folder.
- **Blindness:** schema discovery and all ingestion see only email —
  never the simulator's internals or ground truth (which exist solely for
  post-hoc scoring; the discovery transcripts prove the schema was earned).
- **Known quirks, left in deliberately** (the DB is machine-built and
  unedited): one dog exists only in RSVP mentions and has no row (Monsoon);
  one row's foster was mis-extracted as a coordinator ("Shasta" → "Dana");
  two dogs appear in mail slightly before their intake week (generator
  slip); away/departed status labels can lag their — correctly extracted —
  dates. Hand-fixing any of this would break the "built automatically"
  claim; finding it took one query each, which is rather the point.
- **Scale note:** the corpus is ~950 emails and the search arm already hit
  its budget ceiling; the reference inbox this simulation is modeled on
  holds 117,000+. Search degrades with volume; `SELECT` does not.

## 90-second recording shot list (for the walkthrough video)

1. `/aps-status` — counts + Sheet opens in a tab.
2. `/aps-simulate-email` — hold on beats 3 and 4 (ops envelope; draft
   decision with reason), then cut to the Sheet refreshing and the draft
   in the Drafts tab.
3. `/aps-ask "which dogs are ready to post right now?"` — SQL + rows +
   answer.
4. `/aps-showdown` finale — the two answers side by side; end on the
   provenance click-through (Sheet cell → source email).

## Teardown

All credentials are demo-scoped and revocable in one click (Gmail token in
the Google account's security page; Turso token in its dashboard). To reset
the world: clear the inbox, re-run `simulation/aps_insert.py` (seed) and
`app/week1_inject.py` (extension), re-push Turso via
`populate/push_turso.py --force`, refresh the mirror.
