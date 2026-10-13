# Self-building structured data over a shared inbox — plan

A busy shared mailbox encodes real operational state — entities,
relationships, workflows — that today lives only as free-form text in
scrollback. This prototype makes a strong model **discover** that
structure, a cheap model **maintain** it continuously as tables, and the
resulting state power answers and drafts that thread-search alone cannot
produce. The pipeline, and this plan, run in five stages:
**simulate → discover → populate → maintain → demo.**

**Stage world: APS Rescue** — a fictional dog rescue run entirely out of
`animalprotectiveservices2026@gmail.com`. Every email is synthetic
(`simulation/SIMULATION_DESIGN.md`); a real rescue inbox was consulted
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

Pull-based: nothing serves Gmail — Gmail serves us. Drafts are created,
never sent. One shared hosted DB means every interviewer sees the same
world. Interviewers who want the real Gmail view get delegated access.

## 1 — Simulate (DONE — `simulation/SIMULATION_DESIGN.md`)

831 seed emails over six simulated weeks (Aug 31 – Oct 9, 2026), living in
the real inbox with historical timestamps: 85 dogs (13 multi-home — "dog
tetris"), ~200 households, events, vet days, applications, ~25% catchall
noise. Deterministic generator; ground truth at every instant — used for
post-hoc scoring ONLY, never visible to discovery or ingestion. The
universe is endless: stage 4 extends it with a verified week of history
plus a pool of pre-rendered scenarios to fire live.

## 2 — Discover (DONE — artifacts + full transcripts in `discovery/`)

The strong model (Fable) explored the live inbox agentically and **blind**
— four Gmail tools, nothing else — and designed the schema plus the
extraction playbook a small model follows: 39 rounds / $6.34, then two
operator refines (fosters roster, $2.31; clear verb, $1.82). Result: **5
tables** + 7 catchall tags, `instructions.md` with worked examples,
evidence notes. Sanity gate PASS.

**The contract it authored (locked):** extraction emits only the envelope
`{"ops": [{"table", "match": {canonical keys}, "set": {field: value},
"clear"?: [field, ...], "note"?: ≤1 line}], "catchall"?: {"tag"}}` — with
the dated-fields rule (stated dates, never the email's own timestamp),
omit-never-guess (nulls/empties in `set` are dropped), and `clear` as the
only removal channel (facts stated gone; never canonical keys; a pure
cancellation never creates a row).

**Process rule (standing):** artifacts are never hand-edited — revisions
go through `discovery.py --refine` only, and the schema is **frozen**
after populate (no migration path, by decision; the harness emits
`schema.sha256`, and ingest refuses hash or schema/DB-parity drift). In
the product, revisions would surface as layman onboarding questions;
refine is this prototype's stand-in.

## 3 — Populate (DONE — `populate/VERIFICATION.md`)

All 831 emails ingested **serially, chronologically** by blind Haiku 5.5
(effort A/B medium-vs-high: tie → medium): zero parse failures, zero
anomalies, zero invented entities, $0.36 (~$0.0004/email; discovery $8.65
— the two-tier economics in one line).

**Apply semantics (locked):** create-vs-update by normalized
canonical-key lookup — the harness decides, never the model; per-field
merge; unknown fields/clears dropped and logged; booleans canonicalized to
'1'/'0'; provenance stamped row-level, last-writer (source_email_id,
updated_at). Accepted limit: no per-field temporal guard — a delayed old
email can overwrite newer state; dated fields mitigate.

**Verified:** dogs 78/79, status 97.4% under the stated equivalence policy
(strict-exact and per-field numbers in VERIFICATION.md), fosters 90/90,
applications 33/33, coverage arithmetic exact. Then pushed to Turso (1,187
rows, exact count match); Sheets mirror live.

## 4 — Maintain (DONE — `app/`)

The live loop every demo surface wraps: `pipeline.py ingest_new()`
(catch-up by gmail id, oldest first) and `simulate_send_and_process()`
(fire next pooled scenario or custom text → blind ingest → apply → live
scorecard vs the scenario's answer key → draft triage → mirror), narrated
in five beats: arrived → Haiku thinking → ops envelope → draft decision
with reason → what changed.

- **Draft triage, two-stage:** mechanical never-draft filter (own
  outbound, no-reply senders, machine catchall tags, not the latest
  inbound of its thread), then ONE Opus call → {should_reply, reason,
  draft?}; the decision is always shown with its reason. Guardrails: never
  narrate the database, never re-ask what the thread contains, thread
  beats table on conflict, match the sender's brevity.
- **Models:** extraction `claude-haiku-5-5` effort medium, blind; drafts
  and `/aps-ask` Opus 5.5 (session subagents in the plugin; API in our
  testing).
- **Extension, verified:** +121 week-1 emails injected with per-email
  answer keys (60/60 fully matched) → verify v2 over 953 emails: dogs
  89/90 (disclosures in VERIFICATION.md). Firing pool: ~106 inbound
  scenarios incl. 4 cancellation tests for the clear verb (the Lassen
  fall-through fired live: expected envelope exactly, scorecard 1/1).
- **Guards:** agent SQL passes a real read-only guard (one SELECT/WITH
  statement, write/DDL verbs rejected anywhere, literals/comments stripped
  first); no-credential runs fall back to a committed read-only snapshot;
  missing tokens fail with pointers, not tracebacks.

## 5 — Demo (plugin DONE; web app IN PROGRESS; owner checklist below)

Plugin commands are thin wrappers over `app/`: `/aps-overview` (premise,
start here), `/aps-status`, `/aps-ask "…"`, `/aps-simulate-email`,
`/aps-ingest`, `/aps-showdown "…"`. Three access tiers in README.md: watch
(Sheet + committed evidence), drive (portal bundle), real mailbox
(delegation). No unattended automation, by decision — mail waits for the
next `/aps-ingest`.

**Web app (the product surface — plan and phases in `web/PLAN.md`,
authoritative for everything under `web/`):** a hosted, schema-driven,
read-only SPA over Turso with five pipeline-ordered tabs (Populate &
Maintain is the default view), built stepwise — static tables + activity
feed first, then a password-gated backend for live simulate, then the
head-to-head and discovery-replay story tabs, then Sheet
demotion/removal and README tier inversion.

**Validation record (committed):**
- QA comparison, 9 pre-registered questions, same model/budget
  (`app/out/QA_COMPARE_REPORT.md`): self-graded **B 3 · tie 6 · A 0**.
  Blinded third-party re-grade (GPT-6, counterbalanced, answers-vs-key):
  **B 1 · tie 6 · A 1 · 1 unadjudicated** — all ties and the q1 roster
  centerpiece confirmed; q3 unadjudicated (the shipped key carried the
  pre-disclosed GT annotation error); q4 flipped to A on B's confidently
  asserted DB-inherited errors ("no question where table access hurt" is
  retracted in the report's addendum). Both tallies side by side, never
  averaged: `app/validation/third_party/RESULTS.md`. Open: corrected-key
  q3 re-grade; second judge.
- Draft showdown (4 pre-registered inbound emails): decisive on inventory
  enumeration — search arm 0/5 correct, tables arm 9/9; tie control held.
- Live showdown exhibit: `app/out/showdown_exhibit_1.md`.
- Question classes where tables win: negative space, aggregates,
  current-state-after-moves, joins, dated lookups — plus one honest
  single-thread tie shown for fairness.
- Credentials: portal bundle = Gmail token + Turso token + a usage-capped
  revocable Anthropic key (temporary, demo-only; metered per-call cost is
  the instrumentation for the table-economics question).

## Decisions log

- 10-10 — serial ingestion only ("email date ≠ fact date" is a real danger).
- 10-11 — ship the capped key in the bundle; no-token tier = committed
  read-only snapshot fallback.
- 10-11 — no cloud tick / unattended automation.
- 10-11 — hardening: lazy DB + real SQL guard + boolean spellings
  normalized store-wide (verify re-run identical).
- 10-12 — review round 2: `clear` added to the envelope (Moraine's stale
  row kept unedited as the before-exhibit); schema frozen with hash+parity
  gatekeeping; out-of-order apply documented, not guarded; provenance
  stays row-level.
- 10-12 — blind third-party re-grade run and recorded as-is (stage 5).

## Remaining (owner)

- [ ] Portal bundle: `token_apsdemo.json` + `.env` (Turso creds, SHEET_ID,
      capped Anthropic key) + README pointer
- [ ] Add interviewer Gmail delegates when known
- [ ] Set token revocation date after the interview window
