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

## Phase 3 — Populate, verify, host (CURRENT — gated on user's schema verdict)

- `ingest.py`: **serial, chronological** ingestion of all 831 emails by
  Haiku following the discovered instructions — one stateless single-shot
  call per email (email + its thread tail only; the model never sees the
  DB), generous max_tokens so the JSON can never truncate, **idempotent by
  gmail id** (ingest always means "process everything unprocessed," never
  just one message).
- Effort: **medium** by default; an A/B vs **high** on ~60 ground-truth
  emails decides empirically (low is ruled out); result recorded in
  VERIFICATION.md.
- Apply semantics: timestamp-ordered, **per-field merge** (an op overwrites
  only the fields it sets; corrections win, unrelated facts survive);
  create-vs-update derived mechanically via normalized canonical-key
  lookup; unknown fields dropped and logged, never voiding the op; every
  write stamped with `source_email_id` / `updated_at` provenance so any
  value traces to the email that set it.
- **System tables (harness-owned, not part of the discovered schema, like
  provenance):** `catchall` (gmail_id, date, from, subject, tag) materializes
  every catchall emission so coverage is auditable arithmetic — each of the
  831 emails lands as table ops or a catchall row — plus ingest bookkeeping
  (processed gmail ids, usage/cost per email).
- Runs against a local SQLite file first. Then **verification**: diff final
  tables against `ground_truth.json` → `VERIFICATION.md` with real accuracy
  numbers (dogs, placements, statuses, dates) and measured per-email cost.
- Flip the connection string and push the verified state to **Turso** — by
  the time an interviewer arrives, the shared DB already holds the world.
- Build the **Sheets mirror** + view link.

## Phase 4 — Plugin (the interviewer experience)

Installable from the repo; compute is the interviewer's own Claude session.

- `/simulate-email [next | custom "…"]` — inject the next held-out scenario
  (Message-ID dedup: two interviewers can't double-inject) or a custom
  email; then auto-ingest.
- Ingest-as-catch-up self-heals shared state, including emails anyone sent
  to the inbox directly (which is encouraged: "email it anything
  dog-rescue-flavored and watch").
- `/ask "…"` — NL→SQL against the shared Turso DB, queries shown in the
  terminal.
- Extraction runs as **Haiku subagents** following
  `discovery/instructions.md` — no Anthropic API key is distributed.
- Reply drafts: created in Gmail Drafts AND mirrored to the Sheet's Drafts
  tab. Guardrails: never narrate the database, never re-ask for something
  the thread contains, prefer thread over table on conflict, match the
  sender's brevity and sign-off.
- **Credentials via the submission portal, not GitHub**: the portal bundle
  carries `token_apsdemo.json` (gmail.modify, throwaway account) and the
  Turso token; `DEMO.md` says "drop them at the repo root" (gitignore
  already covers them). The public repo alone still supports a degraded
  tier: `/ask` against a shipped read-only SQLite snapshot.
- `DEMO.md` + a recorded GIF of the full loop as the no-setup fallback.

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
- [ ] Enable Google Sheets API in the APS cloud project; create mirror sheet
      + view link
- [ ] Portal bundle: `token_apsdemo.json` + Turso token + DEMO.md pointer
- [ ] Add interviewer delegates to the APS Gmail when known
- [ ] Set token revocation date after the interview window
