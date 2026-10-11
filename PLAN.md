# Self-building tables over a shared inbox — plan

A busy shared mailbox encodes real operational state (who has which dog, what
happens Saturday, who's waiting on what) that today lives only in scrollback.
This prototype makes a strong model **discover** that structure, a cheap model
**maintain** it continuously, and the resulting tables power answers and
drafts that thread-search alone cannot produce.

**Stage: APS Rescue** — a fictional dog rescue run entirely out of
`animalprotectiveservices2026@gmail.com`. Every email is synthetic (see
`simulation/SIMULATION_DESIGN.md`); a real rescue inbox was consulted
read-only for structure, behind a leak-checked boundary.

## Architecture

```
                         Gmail inbox (the fixture + live arrivals)
                          ^  messages.insert        |  fetch (API)
                          |  drafts.create          v
 interviewer's Claude ----+----->  ingest (Haiku, catch-up by gmail id)
 session (plugin)                        |
                                         v
                       Turso (hosted libSQL = shared source of truth,
                        pre-seeded; same code runs on a local file for
                        dev via one connection string)
                                         |
                                         v
                       Google Sheets mirror (view link, no login:
                        one tab per table + Drafts tab + activity log)
```

Pull-based: nothing serves Gmail — Gmail serves us. Drafts are created, never
sent. One shared hosted DB means every interviewer sees the same world and
no one rebuilds state. Interviewers who want the real Gmail view get
**delegated access** (tested) — no password sharing, no login-challenge risk.

## Phase 1 — Simulation (DONE — see `simulation/SIMULATION_DESIGN.md`)

831 seed emails over six simulated weeks (Aug 31 – Oct 9, 2026) live in the
inbox with historical timestamps: 85 dogs (13 multi-home — "dog tetris"),
~200 households, events/vet days/applications, a posting-readiness rule,
~25% catchall noise. `simulation/out/ground_truth.json` holds true state at
every instant (verification asset); 8 held-out scenarios
(`simulation/out/universe/scenarios.jsonl`) are reserved for live injection.

## Phase 2 — Schema discovery (DONE — artifacts in `discovery/`)

`discovery/discovery.py` ran the strong model agentically against the live
inbox (four tools: `inbox_stats`, `list_threads`, `get_thread`, `search`),
**blind by construction** — it can see only what those tools return, never
`simulation/` or ground truth (which exists solely for Phase-3 scoring).

**Result:** original run 39 rounds / $6.34 (paged the full index, cited
thread evidence per workflow) + one operator-feedback revision via
`--refine` (fosters roster requested; $2.31). Sanity gate PASS. Artifacts,
all committed and never hand-edited: `schema.json` (**5 tables** — dogs 23
cols w/ 6-state lifecycle, fosters 11 cols w/ active/away/departed +
decline/return tracking, foster_applications 14, events 4, event_rsvps 5 —
plus 7 catchall tags), `instructions.md` (Haiku playbook, worked examples),
`DISCOVERY_NOTES.md` (evidence), `discovery_log*.jsonl` (full transcripts).

**The envelope contract** (embedded in the mission; what extraction emits
and Phase 3 consumes): `{"ops": [{"table", "match": {canonical keys},
"set": {field: value}, "note"?: ≤1 line}], "catchall"?: {"tag"}}` — plus
the dated-fields rule (stated dates, never the email's own timestamp),
omit-never-guess, and create-vs-update decided by the harness, not the
model.

**Process rules (standing):** structural sanity gate between discovery and
populate; degenerate output or operator feedback → re-run the harness
(`--refine`), never hand-edit artifacts. *Product note (context, not
scope): real customers are non-technical — in the product, schema revisions
surface as layman yes/no onboarding questions ("Will you need to find which
fosters are free right now?"); refine mode is this prototype's stand-in.*

## Phase 3 — Populate + verify + host (DONE — see `populate/VERIFICATION.md`)

All 831 emails ingested serially by Haiku at effort medium (A/B vs high:
tie; medium per rule): zero parse failures, zero anomalies, zero invented
entities, $0.36 total (~$0.0004/email). Scores vs ground truth: dogs 78/79
(status 97.4%, vet dates 49/49, adoption appts 20/20), fosters 90/90,
applications 33/33 w/ correct lifecycle, events 3/3, RSVPs 56/56, coverage
arithmetic exact. Misses decompose to pre-corpus facts (unknowable from
email) + one name-only dog + status-label lag on future-dated absences
(dates themselves 4/4). Discovery cost $8.65 vs populate $0.36 — the
two-tier economics in one line. After the user's review, the verified
state was pushed to Turso (`populate/push_turso.py`, 1,187 rows across 7
tables incl. the ingest log, exact count match) and the **Sheets mirror is
live** (`app/mirror.py`: table tabs + append-only Activity/Drafts, first
full refresh served from the hosted DB).

## Phase 4 — App layer + plugin (IN PROGRESS — mirror done; QA + draft showdowns validated)

Validated so far: QA comparison (B 3 / tie 6 / A 0, below) and the draft
showdown (`app/out/draft_transcripts.jsonl`, 4 pre-registered inbound
emails): decisive on inventory enumeration — connector arm named 5
available smalls, 0 correct; table arm 9/9 — modest edges on capacity and
negative-space, tie control held, both arms caught a false premise.

**Execution order (agreed):**
A. `app/pipeline.py`: `ingest_new()` + `simulate_send_and_process()` —
   dedup → insert → blind ingest → apply → scorecard vs spec facts →
   draft triage → mirror/Activity/Drafts; five-beat narrative; runs on
   Turso.
B. `simulation/universe_extend.py`: continuation from ground_truth (re-run
   would scramble the verified 831). Week 1 (Oct 10–16, ~130, in+outbound)
   = history to inject; Weeks 2–3 (Oct 17–30, **inbound-only**, ~150) =
   firing pool (scripted staff replies excluded — live drafts take their
   place). Old 8 held-outs fold in. Ground truth v2; render; leak check v2.
C. Inject Week 1: first ~15 interactive with expected-ops verification
   (acceptance suite), then batch-drip ~115; latest-inbound rule keeps
   Drafts to the open tail; verify v2 (~960 emails); mirror refresh.
D. Package pool: rendered text + spec answer keys + deterministic
   Message-IDs, fired oldest-first. Extension is rerunnable any week —
   the universe is endless (candidate post-submission cloud-tick job).

- **`app/` core:** `ingest_new(db, on_event)` (the ingest loop as a
  function), `mirror.py` (full-rewrite Sheet refresh: one tab per table +
  catchall + **Activity** log + **Drafts** tab; latest-run rows
  highlighted), and `simulate_send_and_process(scenario|custom_text)` —
  pick next un-injected scenario (Message-ID dedup) or custom text →
  `messages.insert` → blind catch-up ingest → apply → mirror → draft.
- **Blindness inside simulate (hard rule):** the function touches
  `simulation/` only to pick the next scenario email and to grade AFTER
  extraction (live scorecard: applied ops vs the scenario spec's facts).
  The ingest path imports nothing under `simulation/`; Haiku never sees
  specs or ground truth. DEMO.md pre-empts the "answers were in the repo"
  question by pointing at this separation + the discovery transcripts.
- **Thought-process narrative** (terminal + Activity tab), five beats per
  email: the email that arrived → trimmed Haiku thinking excerpt → the ops
  envelope + create/update as resolved → the DRAFT DECISION → what changed
  (cells, draft).
- **Draft triage (two-stage):** mechanical never-draft filter first (mail
  sent by the shared box, no-reply senders, machine catchall tags
  promo/drive-share/donation-receipt, and anything that is not the latest
  inbound message of its thread), then ONE Opus call returning
  {should_reply, reason, draft?} — so judged no-replies (bare RSVPs) and
  judged yes-replies to catchall (lost-dog redirect, volunteer ack) both
  work, and the decision is displayed either way with its reason.
- **Models:** extraction = `claude-haiku-5-5` (blind); `/ask` (NL→SQL,
  queries echoed) and reply drafts = **Opus 5.5** — via the interviewer's
  own Claude session (subagents; no API key distributed) in the plugin,
  via API in our testing. Draft guardrails: never narrate the database,
  never re-ask for what the thread contains, thread beats table on
  conflict, match the sender's brevity and sign-off.
- **Validated (read-only QA comparison, 9 pre-registered questions × both
  arms, same model/budget — `app/out/QA_COMPARE_REPORT.md`):** B 3 · tie 6 ·
  A 0. Clear win on derived roster state (~2.5× recall, equal precision,
  emergent map-then-verify + self-flagged DB errors); ties where the org's
  own mail caches answers and on entity-name sagas (search reconstructs
  those — demo centerpieces must be derived/drift questions, not named-dog
  stories). Maintenance gaps propagate to B (observed, 2 dogs). Scale
  argument: A capped out at 831 emails; the reference inbox is 117K.
- **`/ask` demo question classes** (where tables beat connector search):
  negative space ("ready to post but not posted?", "who hasn't RSVPed?"),
  aggregates, current-state-after-moves (tetris dogs, with provenance),
  joins ("which fosters are free this weekend?"), dated lookups (next vet
  list) — plus one honest single-thread tie shown for fairness.
- **Credentials:** portal bundle = Gmail token (re-authed once to add the
  `spreadsheets` scope — one token serves mail + sheet) + Turso token.
  Degraded no-token tier: `/ask` against a shipped read-only SQLite
  snapshot.
- Plugin commands are thin wrappers over `app/`: `/simulate-email`,
  `/ask`, `/aps-status`. DEMO.md + a recorded GIF as the no-setup
  fallback.

## Phase 5 — Unattended durability & hygiene

- One daily **Claude cloud schedule** under the owner's account: catch-up
  ingest + Sheet refresh, so mail sent while nobody runs the plugin still
  lands in the tables.
- Gmail **delegation** for interviewers who want the real mailbox view
  (added per-person by address).
- Hygiene: stated token revocation date, Turso token scoped to the demo DB,
  a "reset the demo world" note (re-seed from `simulation/out/corpus.jsonl`
  + re-populate).

## Owner setup checklist

- [x] Turso account + database + token — done; `TURSO_DATABASE_URL` +
      `TURSO_AUTH_TOKEN` in `.env`, connectivity verified
- [x] Sheets API enabled; token re-authed with spreadsheets scope; mirror
      sheet created + SHEET_ID in .env; first refresh live
- [x] Turso push reviewed and executed (1,187 rows verified)
- [ ] Portal bundle: `token_apsdemo.json` + Turso token + DEMO.md pointer
- [ ] Add interviewer delegates to the APS Gmail when known
- [ ] Set token revocation date after the interview window
