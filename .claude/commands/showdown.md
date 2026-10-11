---
description: Live A/B — connector-style search vs tables, same model, side by side
argument-hint: "any small dogs available right now?"
---
Question (or pasted inbound email) to run through BOTH arms: $ARGUMENTS

Spawn TWO subagents IN PARALLEL (one Agent call each, same message), then
present their outputs side by side. Fairness is the whole point: identical
task text, identical budgets, the ONLY difference is Arm B's SQL access.

Shared task text for both arms (fill in the question):
"You are a diligent operations assistant for APS Rescue, a small
foster-based dog rescue whose entire operation runs through one shared
Gmail inbox. Answer precisely and completely: name names, give numbers,
state HOW you know. Budget: at most 20 tool commands. All commands run from
the repo root with: cd ${CLAUDE_PLUGIN_ROOT:-.} && set -a && . ./.env && set +a && cd app &&
APS_DB=turso python3 pipeline.py <cmd>. You may use ONLY the commands listed below —
do NOT read repository files (especially nothing under simulation/), do not
use any other tools. Question: <QUESTION>"

- Arm A (connector-style) — allowed commands: `gmail-search "<query>"`,
  `gmail-thread <thread_id>`. Tell it to search multiple phrasings and
  cross-check before concluding.
- Arm B (tables) — Arm A's commands PLUS `sql "<SELECT …>"`, and paste the
  table/column list from discovery/schema.json into its prompt (read that
  file yourself; the subagent must not browse the repo). Tell it the DB was
  built automatically from this same mailbox and may contain errors.

When both return, render:
1. The question.
2. ARM A: its answer + a 3-5 line summary of what it searched/read.
3. ARM B: its answer + the SQL it ran.
4. A short neutral comparison: where the answers differ, which specific
   facts diverge, and how the user can verify (Sheet tab / provenance).
   If the arms tie, SAY they tie — single-thread questions are genuinely
   search-friendly, and honest ties make the wins credible.

If `.env` is missing at that root (plugin installed from GitHub without
secrets), tell the user: the tokens live in their project checkout — open
the repo folder directly, or copy `.env`, `token_apsdemo.json` into the
plugin root shown by `echo ${CLAUDE_PLUGIN_ROOT}`.
