---
description: APS Rescue demo — world snapshot (tables, pool, sheet link)
---
Run (works as a project command or an installed plugin):
`cd ${CLAUDE_PLUGIN_ROOT:-.} && set -a && . ./.env && set +a && cd app && APS_DB=turso python3 pipeline.py status`

Present the output as a compact snapshot: table row counts, scenarios
remaining in the pool, and the Google Sheet link (the no-login view of the
tables). Add one line reminding the user of the other commands:
/simulate-email, /aps-ingest, /ask "…", /showdown "…".

If `.env` is missing at that root (plugin installed from GitHub without
secrets), tell the user: the tokens live in their project checkout — open
the repo folder directly, or copy `.env`, `token_apsdemo.json` into the
plugin root shown by `echo ${CLAUDE_PLUGIN_ROOT}`.
