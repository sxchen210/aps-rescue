---
description: The premise of this prototype — start here
---
Present the following narrative in your own voice, faithful to its content
and order, compactly (one screen). Do not run tools first.

**The capability prediction.** Frontier models are now cheap enough to read
every message an organization receives as it arrives, and reliable enough
at structured extraction to turn those messages into database rows. That
makes a new kind of software possible: systems whose schema is not designed
by an engineer up front but DISCOVERED by a strong model from the
organization's own communications, then MAINTAINED continuously by a cheap
model for fractions of a cent — with the strong model returning only for
design, revision, and the judgment calls.

**The general product.** Any shared operations inbox — rescues, clinics,
property managers, small nonprofits — quietly encodes who/what/when state
that today lives in scrollback and in one coordinator's head. The product
gives such a team living tables built from their own mail: no CRM setup, no
data entry, schema shaped by plain-language onboarding questions ("Will you
need to find which fosters are free right now?"), every cell traceable to
the email that set it.

**This prototype** narrows that to one proof of concept: a fictional dog
rescue (APS Rescue) run from a real Gmail inbox seeded with ~950 synthetic
emails over nine simulated weeks. A strong model discovered a 5-table
schema from the inbox alone (blind — transcripts committed); a cheap model
populated and now maintains it at ~$0.0004/email, verified 97%+ against the
simulation's ground truth. The practical benefit on display: maintaining
structured data, workflows, and relationships OVER TIME means day-to-day
operational questions ("who's free?", "what's ready to post?") and reply
drafts come out right — where search-only inbox access returns confident,
stale, or incomplete answers (measured head-to-head, exhibits in the repo).

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
