# PLAN: Self-building tables prototype

Working plan. Build first, narrate after.

---

## Part 1: Long-term context (brief)

Today's AI tools (Claude, Gemini in Sheets, Airtable Omni, etc.) can build tables from your data, but only when the user asks and says what the table should be, and mostly as a one-shot. Three things nobody ships:
1. **Proactive discovery.** The system looks at a messy pile and recognizes, unprompted, that it can be organized.
2. **Dynamic schema induction.** It works out the entity types and fields from the user's actual work patterns instead of the user defining the table first.
3. **Long-term maintenance.** It keeps tables current by conforming new incoming messages to the schema over time.

The deeper framing: discovery should find recurring **processes** (for a rescue inbox: getting dogs to medical appointments, finding fosters, moving animals to adoption events), then translate them into **entities tracked in tables**. Tables are the right storage and query layer: deterministic for code, cheap for an LLM to read. The key design rule is that every table carries a **status/lifecycle field with allowed states** (e.g. inquiry → screening → approved → placed) plus **blocked_on**, **last_updated** and **source**. Without those, the process gets flattened into a lifeless contact list. Long-term vision, not being built now: this becomes a backend state and retrieval layer that answers questions and powers workflows inside Claude.

---

## Part 2: What we're testing now

**Hypothesis (riskiest first):** an LLM can do *proactive* process/schema discovery on a real messy inbox well enough to be worth keeping, and the schema holds up on mail it has never seen.

**Corpus: split by time.**

| Split | What | Used for |
|---|---|---|
| **Discovery window** | ~1,000 emails from a couple of months ago | Steps 1–2: build and freeze the schema, fill initial rows |
| **Holdout stream** | Everything after that window, up to the present | Step 3: the genuine "what happens next" |

The holdout contains processes and situations the discovery window never saw. That makes Step 3 an honest test, not a replay of mail the schema was built on.

### Step 0: Preprocess every email (before any model call)
- Strip quoted reply chains and signatures. The new content carries the state change; quoted history is noise and invites double-counting.
- Keep message ID, thread ID, date, from/to, subject, cleaned body.

### Step 1: Discovery (the crux, build first)
- **Input:** the discovery window (all ~1,000 if it fits after stripping; otherwise a 300–500 sample from it).
- **One strong-model call:** "What recurring PROCESSES is this person running? For each, what entity/table should we track, with what fields, including a status field with allowed states, blocked_on, last_updated and source?"
- **Output:** `schema.json` v1. Nothing filled in.
- **Gate:** I look at it. Are these the right processes and tables? Did it produce real lifecycle states, or just name/email/phone? **If no, stop.**
- **Then freeze v1.** From here on the schema changes only through logged escalations in Step 3, never by re-running discovery.
- **Open:** prompt-only vs. needing scaffolding (e.g. cluster threads first, then propose per cluster). The experiment decides.

### Step 2: Extraction (discovery window)
- **Input:** frozen schema v1 + the discovery-window emails.
- **Cheap model, per email/thread:** does this belong in a table? If so, emit a conforming row. Every value = `{value, source_email_id}`.
- **Gate:** spot-check ~20 rows. Are values correct and citations real? **If no, stop.**

### Step 3: Maintenance on the holdout stream (the differentiator)
- **Feed the later months in chronological batches of ~100**, oldest to newest.
- **Per batch:** cheap model conforms new emails to the *existing* schema and updates existing rows (stable row identity) or adds new ones.
- **Escalate** to the strong model when the cheap model is unsure or the email doesn't fit. Strong model either:
  - adds a backward-compatible field or table (append-only, no migration, old rows untouched), or
  - decides to skip.
- **Core judgment on every schema change:**
  - **Evolution:** a new process that legitimately started (good).
  - **Drift:** reinventing something v1 already covers (bad).
- **Watch *when*, not just *whether*:** a slow trickle of additions reads as healthy evolution; a sudden burst is either a genuinely new process or the model losing the plot.
- This is what no shipped product does, and where it's most likely to break.

---

## Minimal architecture

```
emails/discovery/   # older ~1,000, cleaned, one file per message
emails/holdout/     # later months, cleaned, one file per message
schema.json         # living schema; v1 frozen after Step 1, versioned on every change
rows.jsonl          # one row per record; each field = {value, source_email_id}
log.jsonl           # every escalation + schema change, with reason, batch #, date
run.py              # loop: batch -> cheap extract -> escalate if unsure -> update files
```

- Two model tiers: Haiku-class (cheap) + Sonnet/Opus-class (strong).
- No DB, no UI, no connectors, no Gmail integration.
- **Later, optional:** Gmail API (`messages.get format=raw` to read, `messages.insert` to populate a temp inbox) only if the demo needs a live-inbox visual.

---

## Metrics (these are the findings)

| Metric | What it tells us |
|---|---|
| Would I keep the discovered tables? (y/n per table) | Is discovery worth anything |
| Schema changes per batch, over time | Trickle (evolution) vs. burst (new process or breakdown) |
| Each schema change hand-labeled **evolution vs. drift** | The core result |
| Duplicate-field/table rate | Drift ("foster application" vs. "foster inquiry") |
| Escalation rate (+ rough cost per 1,000) | Is the two-tier split viable |
| Hand-checked citations (~20) | Are provenance links faithful |

**Biggest risk: schema drift.** A later batch reinvents a table or field v1 already covers. Likely fix: a "match against existing fields before creating a new one" step in the escalation logic. Solving that is the contribution.

---

## Open questions / next steps

- [ ] **(a)** Discovery: prompt-only, or does it need scaffolding (thread grouping, clustering)?
- [ ] **(b)** Confirm the discovery-window dates and how many months the holdout stream covers.
- [ ] **(c)** Pick the two model tiers.
- [ ] **(d)** Later: does the demo need the live Gmail layer?
