---
description: Fire the next scenario email into the live inbox and process it end to end
---
Run (works as a project command or an installed plugin; takes a few minutes —
Haiku ingestion plus an Opus draft-triage call):
`cd ${CLAUDE_PLUGIN_ROOT:-.} && set -a && . ./.env && set +a && cd app && APS_DB=turso python3 pipeline.py simulate`

The engine inserts the next unfired scenario from the pool into the real
Gmail inbox, ingests EVERYTHING unprocessed (including emails anyone sent
directly), applies table ops, decides whether to draft a reply, refreshes
the Google Sheet, and prints a five-beat narrative:
1 ARRIVED · 2 HAIKU THINKING · 3 DECISION (ops envelope) · 4 DRAFT DECISION
· 5 CHANGED.

Relay the beats faithfully (quote them; don't paraphrase the ops envelope),
adding at most one short line of commentary per beat — e.g. point out when
beat 3 shows an UPDATE because the canonical-key lookup matched an existing
row. Close with where to look: the Sheet tabs that changed, the Drafts tab /
Gmail Drafts if a draft was created, and the scenario's scorecard line if
one printed. If the output says the pool is exhausted, say so and suggest
emailing the inbox directly + /aps-ingest instead.

Never read files under simulation/ to explain what happened — everything
you narrate must come from the pipeline output itself.

If `.env` is missing at that root (plugin installed from GitHub without
secrets), tell the user: the tokens live in their project checkout — open
the repo folder directly, or copy `.env`, `token_apsdemo.json` into the
plugin root shown by `echo ${CLAUDE_PLUGIN_ROOT}`.
