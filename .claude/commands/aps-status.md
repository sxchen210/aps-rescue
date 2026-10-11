---
description: APS Rescue demo — world snapshot (tables, pool, sheet link)
---
Run from the repo root:
`set -a && . ./.env && set +a && cd app && APS_DB=turso python3 pipeline.py status`

Present the output as a compact snapshot: table row counts, scenarios
remaining in the pool, and the Google Sheet link (the no-login view of the
tables). Add one line reminding the user of the other commands:
/simulate-email, /aps-ingest, /ask "…", /showdown "…".
