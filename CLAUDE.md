# CLAUDE.md

Self-building structured data (entities/relationships/workflows as tables, not free-form text) over a shared Gmail inbox. **`PLAN.md` is authoritative**
for architecture, phases, and locked semantics (ops envelope, apply rules,
harness contract, guardrails) — read it before building; `web/PLAN.md`
owns the demo web app. Any change to
architecture or a standing decision updates PLAN.md and this file in the
same commit.

## Hard rules

- **Never send email.** Drafts only (`drafts.create`). Inserts
  (`messages.insert`) only for scenario/custom simulation.
- The "ref" account (real rescue inbox) is read-only: consult → distill →
  discard. Nothing real is ever written to disk, quoted, or committed.
- The seeded APS inbox is the shared fixture: no bulk-delete, re-seed, or
  bulk scenario injection without the user's say-so.
- **Discovery blindness:** schema discovery happens only via the
  `discovery/` harness; `simulation/` internals and `ground_truth.json` are
  off-limits to discovery and ingestion (ground truth = post-hoc
  verification only). Never hand-edit discovery artifacts — re-run the
  harness instead.
- Secrets live at repo root, all gitignored (`.env`, `*credentials*.json`,
  `token*.json`, Turso token). Never echo or commit them. Token files may
  be legitimately absent (distributed via submission portal) — fail with a
  pointer to README.md, not a traceback.

## Git

Commit locally at every working milestone without asking. **Push only when
the user explicitly says so** — never carries forward. Check `git status`
for secret-like files before each commit.

## Conventions

- Models: extraction `claude-haiku-5-5` at effort medium, BLIND — the
  ingest path (including inside simulate_send_and_process) never reads
  `simulation/` specs or ground truth; scenario-pick and post-hoc grading
  are the only sanctioned uses. Reply drafts and the live head-to-head
  arms are **Opus 5.5** via the capped demo API key (backend + scripts).
  Pin `output_config.effort`; no `temperature`. Semantics per PLAN.md
  stages 3-4.
- DB: Turso is shared truth (`TURSO_DATABASE_URL` + `TURSO_AUTH_TOKEN` in
  `.env`; plain HTTP API, no client lib), local SQLite file for dev.
  Google Sheets is a mirror, never a store.
- API key: `set -a && . ./.env && set +a`. Scripts run from any cwd
  (anchor paths to `Path(__file__)`); `python3 -m py_compile` touched files.
