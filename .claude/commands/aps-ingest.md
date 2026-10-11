---
description: Process any email that arrived in the APS inbox (catch-up; no scenario fired)
---
Run (works as a project command or an installed plugin):
`cd ${CLAUDE_PLUGIN_ROOT:-.} && set -a && . ./.env && set +a && cd app && APS_DB=turso python3 pipeline.py ingest`

This processes everything not yet ingested — most usefully, emails the user
(or anyone) sent to animalprotectiveservices2026@gmail.com directly. Relay
the five-beat narrative for each processed email as in /simulate-email. If
nothing was pending, say the inbox is fully processed and suggest sending
an email to the address and re-running this command.

If `.env` is missing at that root (plugin installed from GitHub without
secrets), tell the user: the tokens live in their project checkout — open
the repo folder directly, or copy `.env`, `token_apsdemo.json` into the
plugin root shown by `echo ${CLAUDE_PLUGIN_ROOT}`.
