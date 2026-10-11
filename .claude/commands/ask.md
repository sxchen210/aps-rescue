---
description: Ask the APS tables an operational question (NL -> SQL, queries shown)
argument-hint: "which fosters are free this weekend?"
---
Question: $ARGUMENTS

You are answering from the rescue's live operational database (hosted
libSQL; built automatically from the inbox). Steps:

1. Read `discovery/schema.json` for tables/columns/keys. (Only this file —
   never anything under simulation/.)
2. Compose one or more read-only SQL queries. Execute each with:
   `set -a && . ./.env && set +a && cd app && APS_DB=turso python3 pipeline.py sql "<QUERY>"`
3. Show the user each SQL query and a compact view of the rows, then answer
   the question in plain language — names and numbers, not vibes. Every row
   carries provenance (source_email_id, updated_at): offer to pull the
   source email for any claim via
   `python3 pipeline.py gmail-search "rfc822msgid:<...>"` or a subject search.
4. Derived definitions to use: a foster is FREE when status='active', today
   is outside [away_start_date, away_end_date], and no dogs row points at
   them via foster_name or coverage_foster. A dog is READY TO POST when
   photos_received and bio_received are true, it is fixed (spay_neuter_date
   set or known fixed), and posted is not true.
5. If the tables genuinely can't answer, say so and name what's missing —
   don't guess. Note that the DB may contain extraction errors; cross-check
   email when a single fact is load-bearing.

Good example questions (the classes where tables beat search): who's free
right now; who hasn't RSVPed for the next event; dogs ready to post but not
posted; adoptions last month + average days intake->adoption; where is a
specific dog after multiple moves.
