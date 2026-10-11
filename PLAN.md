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

## Phase 2 — Schema discovery (CURRENT)

`discovery/discovery.py`: an **agentic harness** running the strong model in
a tool-use loop against the live inbox with exactly four tools —
`inbox_stats()`, `list_threads(page)`, `get_thread(id)`, `search(query)` —
and a mission: explore as much as needed, as many rounds as needed (the
corpus is small enough to read in full), then emit:

1. `discovery/schema.json` — tables, columns, lifecycle enums, canonical
   keys, a catchall bucket;
2. `discovery/instructions.md` — the extraction playbook written *for the
   cheap model*: per-email, emit JSON rows/updates against that schema;
3. `discovery/DISCOVERY_NOTES.md` — workflows found, with per-table evidence
   citations (thread ids);
4. `discovery/discovery_log.jsonl` — the full tool-use transcript, committed
   as evidence of *how* the schema was earned.

**Harness contract (given to the discovery agent verbatim, so the
instructions it writes enforce them):**

- Extraction output is ONLY a JSON operations envelope — no prose:
  `{"ops": [{"table", "match": {canonical key fields}, "set": {field:
  value}, "note"?: one line max}], "catchall"?: {"tag"}}`.
- `schema.json` must declare, per table: canonical key fields, lifecycle
  enums, and dated fields; plus a catchall tag taxonomy for mail that fits
  no workflow.
- **Dated-fields rule:** when an email states a date for a fact, extract
  that stated date into the dated field — never substitute the email's own
  timestamp (emails routinely announce future events and reference past
  ones).
- Create-vs-update is the harness's job (canonical-key lookup); any model
  opinion on it is advisory only.
- Unknown or unstated information is omitted, never guessed; emitting no
  ops is valid for pure-noise mail (tag it catchall instead).

**Sanity gate before populate:** a structural review only — schema parses,
table count is sane, instructions emit the envelope. A degenerate result
means re-running discovery with a clarified mission, never hand-editing its
artifacts toward known universe facts. **Operator feedback goes the same
way:** schema revisions run through the harness's refine mode
(`discovery.py --refine "<request>"` — prior artifacts fed back, agent
re-verifies against the mailbox and resubmits the full set).

**Product note (context, not current scope):** in the real product there
is no technical operator reviewing schemas. The onboarding agent must
surface capability forks as layman yes/no questions to non-technical
customers ("Will you need to find which fosters are free right now to do
foster match?") and update its own schema on the answers. The refine-mode
loop below is this prototype's stand-in for that onboarding conversation.

**Blindness by construction:** the harness process can see only what its
four tools return — not `simulation/`, not the universe code, not ground
truth. Ground truth is touched only afterward, to score the result. This is
also the product's actual onboarding mechanism, demonstrated end to end.

## Phase 3 — Populate, verify, host

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

- [ ] Turso account + database + token (no card needed)
- [ ] Enable Google Sheets API in the APS cloud project; create mirror sheet
      + view link
- [ ] Portal bundle: `token_apsdemo.json` + Turso token + DEMO.md pointer
- [ ] Add interviewer delegates to the APS Gmail when known
- [ ] Set token revocation date after the interview window
