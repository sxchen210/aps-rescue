---
description: Process any email that arrived in the APS inbox (catch-up; no scenario fired)
---
Run from the repo root:
`set -a && . ./.env && set +a && cd app && APS_DB=turso python3 pipeline.py ingest`

This processes everything not yet ingested — most usefully, emails the user
(or anyone) sent to animalprotectiveservices2026@gmail.com directly. Relay
the five-beat narrative for each processed email as in /simulate-email. If
nothing was pending, say the inbox is fully processed and suggest sending
an email to the address and re-running this command.
