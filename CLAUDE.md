# CLAUDE.md

Prototype of self-building tables over a shared Gmail inbox. `PLAN.md` is the
authoritative architecture and phase arc (simulation → discovery → populate →
plugin → unattended). **Doc-evolution rule: any change to architecture or a
standing decision updates PLAN.md and CLAUDE.md in the same commit.**

## Accounts & secrets

- `animalprotectiveservices2026@gmail.com` ("aps" in `gmail_io.py`): the
  fictional rescue's shared inbox. The only writable account —
  `messages.insert` for scenario/custom injection and `drafts.create` for
  output. **Never send email. Drafts only.** Interviewer viewing happens via
  Gmail delegation, never shared passwords.
- foster@ reference account ("ref"): a real rescue's inbox, read-only by
  OAuth scope. Consult → distill → discard; nothing real is written to disk,
  quoted, or committed (`simulation/leakcheck.py` enforces the boundary).
- Secrets at repo root, all gitignored: `.env` (ANTHROPIC_API_KEY),
  `*credentials*.json`, `token*.json`, Turso token. Token files may be
  legitimately ABSENT on a fresh clone — they are distributed through the
  submission portal, not GitHub; scripts should fail with a pointer to
  DEMO.md, not a traceback. Never echo, copy, or commit secrets. Load the
  API key with `set -a && . ./.env && set +a`.

## Git workflow

Commit locally at every working milestone without asking. **Push only when
the user explicitly says to push** — a prior push request never carries
forward. Check `git status` for secret-like files before every commit.

## Phase discipline

- **Discovery blindness:** canonical schema discovery happens ONLY through
  the `discovery/discovery.py` harness (isolated tool-loop; sees nothing but
  its Gmail tools). Never hand-edit its artifacts to match universe
  knowledge; refinements re-run the harness. `simulation/` internals and
  `ground_truth.json` are off-limits to discovery and ingestion — ground
  truth exists solely for post-hoc verification (`VERIFICATION.md`).
- **Ingest means catch-up:** always process every email not yet in state
  (keyed by gmail id, idempotent) — never just the message that triggered
  the run. Scenario injection dedups globally via deterministic Message-IDs.
- **Extraction/apply semantics (locked):** serial chronological processing;
  stateless single-shot Haiku calls (email + thread tail, never the DB);
  output is the JSON ops envelope only; effort medium (A/B vs high on
  ground truth; low ruled out); generous max_tokens; apply is a
  timestamp-ordered per-field merge with mechanical create-vs-update and
  `source_email_id`/`updated_at` provenance on every write; stated dates
  beat email dates (the dated-fields rule). These rules are part of the
  discovery mission so the generated instructions enforce them.
- **Sanity gate:** between discovery and populate, review discovery output
  structurally only (parses, sane table count, envelope-compliant
  instructions). Degenerate → re-run discovery with a clarified mission;
  never hand-edit its artifacts.
- The seeded inbox is the shared fixture: no bulk-delete or re-seed without
  the user's say-so (`simulation/aps_insert.py` is idempotent via
  `simulation/out/seeded_ids.json`). Held-out scenarios
  (`simulation/out/universe/scenarios.jsonl`) are injected one at a time,
  never bulk-seeded.
- Draft-generation guardrails (hard rules): never narrate the database,
  never re-ask for something the thread already contains, prefer the thread
  over the table on conflict, match the sender's brevity and sign-off.

## Conventions

- Models: strong tier (Fable/Opus) for discovery and exemplars; cheap tier
  `claude-haiku-5-5` for per-email ingestion. In the plugin, ingestion runs
  as Haiku subagents on the interviewer's session (no API key distributed).
  Pin `output_config.effort`; current models reject `temperature`.
- Database: Turso (libSQL) is the shared source of truth, pre-seeded in
  Phase 3; the same code runs against a local SQLite file via one
  connection-string env var for dev. Google Sheets is a one-way mirror
  (tables + Drafts tab + activity log), never a store.
- Scripted model calls go through the API (reproducible, cost-measured);
  interactive work stays in the session.
- Run `python3 -m py_compile` on touched files; scripts must run from any
  cwd (anchor paths to `Path(__file__)`).
