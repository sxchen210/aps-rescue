# CLAUDE.md

Prototype of self-building tables over a shared Gmail inbox. Read `PLAN.md`
for the phase arc (simulation → schema discovery → haiku populate → demo).

## Accounts & secrets

- `animalprotectiveservices2026@gmail.com` ("aps" in `gmail_io.py`): the
  fictional rescue's shared inbox. The only writable account —
  `messages.insert` for scenario injection and `drafts.create` for output.
  **Never send email. Drafts only.**
- foster@ reference account ("ref"): a real rescue's inbox, read-only by
  OAuth scope. Consult → distill → discard: real content is read transiently,
  never written to disk, quoted, or committed. `simulation/leakcheck.py`
  enforces the boundary over generated text.
- Secrets live at repo root: `.env` (ANTHROPIC_API_KEY), `*credentials*.json`,
  `token*.json` — all gitignored. Never echo, copy, or commit them. Load the
  API key with `set -a && . ./.env && set +a`.

## Git workflow

Commit locally at every working milestone without asking. **Push only when
the user explicitly says to push** — a prior push request never carries
forward. Check `git status` for secret-like files before every commit.

## Phase discipline

- **Discovery blindness:** Phase-2 schema discovery reads the inbox via the
  Gmail API only. It must not read `simulation/` code, specs, or
  `ground_truth.json` — the schema is earned from emails alone. Ground truth
  is used only for post-hoc verification in Phase 3+.
- Scenario emails (`simulation/out/universe/scenarios.jsonl`) are held out
  for live demo injection; don't seed them in bulk.
- The seeded inbox is the fixture: don't bulk-delete or re-seed it without
  the user's say-so (`simulation/aps_insert.py` is idempotent via
  `simulation/out/seeded_ids.json`).

## Conventions

- Models: strong tier = Fable/Opus for discovery and exemplars; cheap tier =
  `claude-haiku-5-5` for per-email ingestion. Pin `output_config.effort`;
  current models reject the `temperature` param.
- Scripted model calls go through the API (reproducible, cost-measured);
  interactive work stays in the session.
- SQLite is the local source of truth; Google Sheets is a one-way mirror for
  cloud visibility. No remote database.
- Run `python3 -m py_compile` on touched files; scripts should run from any
  cwd (anchor paths to `Path(__file__)`).
