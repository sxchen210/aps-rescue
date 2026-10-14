# Simulated rescue inbox — design

**Stage:** a fictional dog-rescue org operating entirely out of one Gmail
account — `animalprotectiveservices2026@gmail.com` ("APS Rescue", Redwood
City, CA). Every email in it is synthetic. A real rescue's foster inbox is
consulted **read-only** to keep the simulation honest; a strict boundary
(below) guarantees no real content crosses over.

## Why simulate

Real rescue mail is full of personal information and can't be demoed or
committed. Simulation also buys two properties a real inbox can't offer:

1. **Ground truth.** Emails are derived from a simulated world, so the true
   state (every dog, foster, event, appointment at every instant) is known.
   Tables the models build can be *verified*, not eyeballed.
2. **A closed world.** All coordination happens over email — every decision
   visible in the inbox is traceable to evidence in the inbox.

## The universe

- ~200 foster households; ~50 actively fostering at any time. Availability
  churn is simulated: vacations, leaving town, pauses, new sign-ups.
- ~50 dogs cycling per month: shelter pull → intake → foster placement →
  photos → bio → posted → event attendance → application(s) → adoption
  (or return). Medical incidents arise independently.
- ~30 foster/adopter applications per month: form received → acknowledgment →
  interview scheduling → approval or decline.
- Biweekly Saturday adoption events (pet-store venue, drop-off/pickup times).
- Spay/neuter days (Wednesdays, partner vet clinic) with two logistics
  variants: direct drop-off/pickup at the clinic, or transport from home base
  (earlier drop-off).
- A small staff cast (4–5 coordinators) with distinct voices and role splits,
  plus a catchall stream (~25%: marketing, vague interest, acknowledgments,
  attachment-only notes).
- Seed period: ~6 simulated weeks ≈ 650 emails, then held-out **scenario
  events** for live demonstration ("simulate an email send").

## Architecture: the LLM never decides what exists — it only voices it

**Layer 1 — Universe simulator** (`universe.py`, pure Python, seeded RNG):
state machines over dogs, households, applications and the calendar emit a
timestamped `events.jsonl` plus ground-truth state tables at every instant.
Deterministic and replayable from the seed.

**Layer 2 — Thread derivation** (templates + `patterns/*.md` structure
cards): each event type maps to an email pattern — who writes first, the turn
order, which facts move, timing jitter, group-thread vs 1:1, reply-quoting.
Structure cards are distilled from observing the reference inbox (protocol
below) and contain structure only, never content.

**Layer 3 — Voice rendering** (`render.py`, the only LLM step): per email,
the prompt is a persona card + the matching structure card + the event's facts
(must-say / must-not-contradict) + the thread tail. For natural diversity,
each persona is bound at creation to a renderer mix — a model × effort pair
(Haiku low/medium/high for terse mobile writers, Opus low→high for polished
ones; staff voices anchored by strong-model exemplars) — so individuals stay
consistent while the corpus varies. Assignments are randomized within strata
so style never correlates with workflow type, and every email's (model,
effort) is recorded in `corpus.jsonl` alongside full headers and In-Reply-To
chains.

**Leak check** (`leakcheck.py`): before seeding, pull the reference inbox's
entities (names, emails, phones, addresses, dog names, venues) and n-grams
transiently into memory; scan the synthetic corpus for entity hits and any
shared long phrase (~8+ words); fail the build on any hit; discard the
reference data. Nothing from the real inbox is written to disk.

**Seeding** (`scripts/aps_insert.py`): insert the corpus chronologically into the APS
inbox via the Gmail API (`messages.insert`, `internalDateSource=dateHeader` so
historical timestamps display correctly). Idempotent — inserted message IDs
are tracked so re-runs don't duplicate. Drafts produced later by the system go
to the Drafts folder via `drafts.create`; nothing is ever auto-sent.

**Demo surface (later phase):** the same functions exposed by the demo
backend — delivering a held-out scenario pops the next pre-rendered event
and inserts it; table state is served live by the web app.

## Reference-inbox protocol: consult → distill → discard

The reference inbox is accessed read-only (enforced by OAuth scope), only to
learn *shapes*: thread structures, turn orders, timing, volume mix, voice
registers. Working rules:

- Real threads are read transiently during a working session and never written
  to disk, quoted, or committed.
- What survives a session is a structure card: participants, turns, facts
  moved, timing, tone adjectives. Never names, dates, phone numbers,
  addresses, verbatim sentences, or one-of-a-kind incidents.
- The leak checker enforces the boundary mechanically after generation.

## Tooling

| file | role |
|---|---|
| `gmail_io.py` | shared Gmail module; `ref` client (reference inbox, read-only scope) + `aps` client (demo inbox, read/insert/draft) |
| `dps_fetch.py` | CLI for distillation sessions: search + print threads from the reference inbox |
| `universe.py` | world simulator → `events.jsonl` + ground truth |
| `render.py` | event → email text via persona/structure cards (API: cheap model bulk, strong model exemplars) |
| `leakcheck.py` | entity + n-gram boundary scan |
| `scripts/aps_insert.py` (repo root) | idempotent chronological seeding of the APS inbox |

## Cost model

Orchestration, distillation and code run in the working session. Scripted
model calls (rendering, later live ingestion) use the API: the mixed-model
render of ~650 emails costs roughly $3–4 (Haiku bulk under a dollar; the
Opus share of personas accounts for the rest), strong-model exemplars add
cents. The entire corpus is reproducible from the seed for the same price.
