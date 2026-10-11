# Self-building tables over a shared inbox — plan

A busy shared mailbox encodes real operational state (who has which dog, what
happens Saturday, who's waiting on what) that today lives only in scrollback.
This prototype makes a strong model **discover** that structure, a cheap model
**maintain** it continuously, and the resulting tables power answers and
drafts that thread-search alone cannot produce.

**Stage: APS Rescue** — a fictional dog rescue run entirely out of
`animalprotectiveservices2026@gmail.com`. Every email is synthetic (see
`simulation/SIMULATION_DESIGN.md`); a real rescue inbox was consulted
read-only for structure, behind a leak-checked boundary.

## Architecture (pull-based; nothing serves Gmail — Gmail serves us)

```
Gmail inbox  --(Gmail API fetch)-->  ingestion loop (Haiku)  -->  SQLite (truth, local file)
     ^                                                               |
     |                                                               v
 drafts.create <-- draft generation (tables + thread context)    Google Sheets mirror
 (never send)                                                    (cloud-visible state)
```

No remote database: SQLite is the local source of truth; the cloud-visible
surfaces are the inbox itself and the Sheets mirror. The simulator's held-out
scenarios are injected with `messages.insert` to simulate live arrival.

## Phase 1 — Simulation (DONE)

831 seed emails over six simulated weeks (Aug 31 – Oct 9, 2026), generated
from a deterministic universe and seeded into the live inbox with historical
timestamps. 85 dogs (13 with multiple foster homes), ~200 households, 33
applications, 3 adoption events, 3 vet days, returns/bridges/overflow
("dog tetris"), a posting-readiness rule (photos + bio + fixed), ~25%
catchall noise. Because emails derive from a simulated world,
`simulation/out/ground_truth.json` holds the true state at every instant —
later phases are *verifiable*, not eyeballed. 8 held-out scenario emails
(`simulation/out/universe/scenarios.jsonl`) are reserved for live demo
injection.

## Phase 2 — Schema discovery (CURRENT)

The strong model (Fable) reads the seeded inbox **cold, via the Gmail API
only** and produces:

1. `discovery/schema.json` — tables, columns, enums/lifecycles, canonical
   keys, a catchall bucket for mail that fits no workflow;
2. `discovery/instructions.md` — extraction instructions written *for the
   cheap model*: per-email, emit rows/updates as JSON against that schema;
3. `discovery/DISCOVERY_NOTES.md` — what workflows it found and why.

**Blindness rule (demo integrity):** discovery may read the inbox and nothing
else — never `simulation/` internals, the universe code, or ground truth.
The schema must be earned from the emails alone. Ground truth is touched
only afterward, to score the result.

## Phase 3 — Haiku populate (NEXT)

Chronological ingestion of all 831 emails by Haiku following the Phase-2
instructions: one email per call, rows upserted into SQLite via canonical
keys, every write mirrored to the Google Sheet. Then:

- **Verification:** diff final tables against `ground_truth.json` — a real
  accuracy number (dogs, placements, statuses, dates), on screen.
- **Economics:** measured cost of cheap-tier maintenance per email, vs the
  strong tier used once for discovery.
- **Live loop:** scenario emails injected one at a time → incremental
  ingestion → sheet cells update → reply drafts appear in Gmail Drafts
  (drafts only; nothing is ever auto-sent).

Draft-generation guardrails (hard rules): never narrate the database
("our records show…"), never re-ask for something the thread already
contains, prefer the thread over the table on conflict, match the sender's
brevity and sign-off conventions.

## Phase 4 — Demo surface

Claude-driven commands over the same pipeline: `/onboard` (run or replay
discovery), `/simulate-email <scenario>` (inject + watch ingestion reasoning
+ sheet update + draft), `/ask` (table-backed answers vs connector-style
search, side by side — e.g. "which dogs are ready to post but not fixed?").
Google Sheet pinned open; Gmail Drafts folder as the payoff shot.
