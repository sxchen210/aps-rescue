---
description: The premise of this prototype — start here
---
Present the following narrative in your own voice, faithful to its content
and order, compactly (one screen). Do not run tools first.

**The capability prediction.** Frontier models are now cheap enough to read
every message an organization receives as it arrives, and reliable enough
at structured extraction to turn those messages into database rows. That
makes a new kind of software possible: **self-building structured data** —
the entities, relationships, and workflows buried in an organization's
free-form communications, discovered by a strong model and represented in
tables rather than text, then MAINTAINED continuously by a cheap model for
fractions of a cent — with the strong model returning only for
design, revision, and the judgment calls.

**The general product.** Any shared operations inbox — rescues, clinics,
property managers, small nonprofits — quietly encodes who/what/when state
that today lives in scrollback and in one coordinator's head. The product
gives such a team living tables built from their own mail: no CRM setup, no
data entry, schema shaped by plain-language onboarding questions ("Will you
need to find which fosters are free right now?"), every row stamped with
the email that last changed it.

**This prototype** narrows that to one proof of concept. We set up a real
shared Gmail inbox that mirrors the activity of a local animal rescue's
foster inbox, and simulated ~1,000 email correspondences over nine weeks of
rescue operations — intakes, foster matching, vet days, adoption events,
applications, returns, noise. Then the pipeline ran exactly as the product
would: **Fable** went through the inbox and suggested the schema (blind —
its full exploration transcript is committed), and **Haiku 5.5** ingested
every email to build the state the database is in today, at ~$0.0004 per
email — scored field-by-field against the simulation's ground truth:
near-perfect on facts the mail actually stated (dated fields 100%), with
the gaps — facts no email ever confirmed — measured and itemized in
`populate/VERIFICATION.md`. The demo shows
that point in time — all mail so far processed — and then two things live:
NEW emails being processed as they arrive, and the strength a database
gives when answering questions: operational asks ("who's free?", "what's
ready to post?") and reply drafts come out right where search-only inbox
access returns confident, stale, or incomplete answers (measured
head-to-head; exhibits in the repo).

**Try it in this order:**
1. `/aps-status` — the world right now + the live Google Sheet link (open
   it in a tab and keep it visible).
2. `/aps-ask "which fosters are free right now?"` — tables answering with
   the SQL shown; try your own questions.
3. `/aps-simulate-email` — a new email arrives for real; watch the
   five-beat narrative: ingestion, table ops, draft decision, sheet update.
   Repeat as often as you like (100+ scenarios pooled).
4. Email animalprotectiveservices2026@gmail.com yourself, then
   `/aps-ingest` — your own words through the same pipeline.
5. `/aps-showdown "any small dogs available right now?"` — the head-to-head:
   same model with and without the tables, side by side.

Full reference, access tiers, evidence map, and honest caveats: DEMO.md.
