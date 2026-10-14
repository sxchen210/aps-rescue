# Animal Protective Services — live demo guide

A proof of concept for **self-building structured data** — entities,
relationships, and workflows discovered from free-form communication and
represented in tables instead of remaining trapped in text. Animal
Protective Services is a fictional dog rescue built to mirror the
day-to-day operations of a real local rescue; operations like these run
across many channels (Gmail, text threads, WhatsApp groups), and this
demonstration narrows everything to one shared Gmail inbox, seeded with
~1,000 simulated correspondences. Fable suggested the schema from the
inbox alone, Haiku 5.5 ingested every email to build today's state, and
the demo shows that point in time — plus new emails being processed
live, and the strength a database gives when answering questions that
search-only inbox access gets wrong. Everything is synthetic (see
`simulation/`), everything runs live (a real Gmail inbox, a hosted
database, a hosted web app), and every claim traces to committed
evidence.

**Start here: <https://sxchen210.github.io/aps-rescue>** — four tabs that
tell the story in pipeline order (Simulate → Discovery → Populate &
Maintain → Head-to-head). Viewing needs nothing; the two live actions ask
for the demo password from the portal note.

## Three ways in

**1. The hosted demo (no setup).** The link above. *Populate & Maintain*
is the live state: every table rendered from the discovered
`schema.json`, row pages with provenance, and a live activity feed.
*Watch it work* (password) delivers the next pooled scenario email into
the real inbox and streams the pipeline beat by beat — Haiku's reasoning,
the ops envelope, the Opus reply decision, the changed rows. *Head-to-head*
(password) runs the same model with and without table access on a chosen
question, side by side, live. *Discovery* replays, round by round, how
the schema was earned blind.

**2. The repo (evidence, and driving it locally).** Clone and skim the
committed record: `populate/VERIFICATION.md` (accuracy vs ground truth,
policy stated), `app/out/QA_COMPARE_REPORT.md` and
`app/validation/third_party/` (head-to-head gradings, including the
independent blinded re-grade), `discovery/DISCOVERY_NOTES.md` +
`discovery/discovery_log*.jsonl` (the raw transcripts). With the portal
bundle (`token_apsdemo.json` + `.env` at the repo root, both gitignored),
the whole system also runs from your machine:
`pip install -r requirements.txt`, then the engine CLI
(`cd app && APS_DB=turso python3 pipeline.py status|sql|ingest|simulate`)
or the full backend (`python3 -m uvicorn app.server:app`). The bundle's
Anthropic key is usage-capped, demo-scoped, and revoked when the window
closes — shipping it is deliberate: metered calls make every ingestion
and draft an attributable line item (measured economics in
`populate/VERIFICATION.md`).

**3. See the real mailbox.** Ask to be added as a Gmail **delegate** on
animalprotectiveservices2026@gmail.com — you'll open the actual inbox and
Drafts folder from your own Google account, no shared password, and can
check any row's `source_email_id` against the real thread. (Or email the
address yourself — the next catch-up ingest turns your message into rows.)

## Honest notes (short form — the full versions live in the linked files)

- **The search arm is an emulation** — steelmanned (same model, equal
  budget, full traces committed) but capped at ~15–20 results per query,
  no pagination; the live Head-to-head tab runs on the same surface.
  Self-graded: 3 wins / 6 ties / 0 losses. Independent blinded re-grade
  (GPT-6, arms anonymized, counterbalanced): **1 / 6 / 1, with 1
  unadjudicated** — the ties and the roster win confirmed; one loss where
  the tables arm confidently asserted two DB-inherited errors. Both
  gradings + judge transcript + audit: `app/validation/third_party/`.
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

## The 90-second path

1. Open the site — *Populate & Maintain*: the live tables, all rendered
   from the discovered schema.
2. *Watch it work* → password → **Deliver the next email**: hold on
   Haiku's reasoning and the ops envelope, then see the changed rows and
   the draft Opus wrote.
3. *Head-to-head* → run the first question: the tables window finishes
   while the search window is still paging the inbox.
4. *Discovery* → the replay: 39 blind rounds, $6.34, the schema earned.

## Teardown

All credentials are demo-scoped, temporary, and revocable in one click
(Gmail token in the Google account's security page; Turso token in its
dashboard; the Anthropic key in the API console — usage-capped, retired
with the demo). The backend is one Fly app: `fly apps destroy
aps-rescue-demo` ends it; the demo password dies with it. To reset the
world: clear the inbox, re-run `scripts/aps_insert.py` (seed) and
`scripts/week1_inject.py` (extension), re-push Turso via
`scripts/push_turso.py --force`.
