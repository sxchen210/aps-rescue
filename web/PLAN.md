# Web app — the demo's product surface

Hosted read-only web app over the live Turso DB; becomes the "prototype
link" and eventually replaces the Google Sheet as the demo's face. Built
stepwise: static viewing first, interactivity second. This file is the
authoritative plan for everything under `web/`; root PLAN.md points here.

## Decided

- **Five tabs, pipeline-ordered:** Simulate · Discovery · **Populate &
  Maintain** (default view on load) · Head-to-head · Adapt.
- Tabs ship as minimal placeholders until their phase lands (accepted;
  filled step by step).
- Discovery tab will be a **replay** of the committed
  `discovery_log*.jsonl` (timeline: round → tool → what it read → schema
  emerging → cost). No live discovery runs (slow, ~$6+, anticlimactic).
- Adapt tab: tabled. (When picked up: real signals — catchall share,
  anomaly log — plus the two committed refine case studies; no claim of
  automatic flagging, which doesn't exist.)
- Head-to-head tab: rendered from committed transcripts — showdown
  exhibit 1 + the QA set with BOTH gradings (self-graded and the blinded
  GPT-6 re-grade, q4 flip included), collapsible tool traces, "rendered
  from committed evidence" label.
- Static host: **GitHub Pages** (zero new accounts; W2 backend can also
  serve `web/` later if one origin is ever preferred).
- Gating: viewing is public (synthetic, read-only data); **actions are
  gated server-side** in W2 — password from the portal note → constant-time
  hash check → short-lived HMAC session token → required on every action
  endpoint, plus a global one-at-a-time lock and per-session rate limit.
  The browser never holds Gmail/Anthropic/Turso-write credentials.

## Tabled (decide later)

- Provenance email bodies: harness `emails` table in Turso vs.
  backend-proxied live Gmail fetch vs. thin-metadata hybrid. The W1
  provenance block is designed so either drops in without layout change.
- Backend host (Fly/Railway/Render), compose-your-own-email box, Sheet
  removal timing (demote → delete after `drafts_log` parity), cosmetic
  view gate.

## Architecture

- **No-build vanilla SPA**: `index.html` + `app.js` + `style.css`. No npm,
  no bundler — reviewers can read the whole front end; deploy = serve the
  folder. Hash routing (`#/pm/dogs`, `#/pm/dogs/17`, `#/h2h`, …).
- **Data layer: Turso only** (decided — no snapshot fallback). Browser →
  Turso HTTP API (`/v2/pipeline`) with a **read-only token**. If the DB is
  unreachable, the app shows an explicit "database unreachable" banner —
  never stale or silent data. (The committed `state_v2.sqlite` remains the
  CLI's no-token tier; the web app does not use it.)
- **Schema-agnostic by construction:** app code hardcodes no table or
  column names — tabs, columns, tooltips (descriptions), enum filter
  chips, record links (canonical keys), and related-records all derive
  from `schema.json`. This is the generality proof, stated on-page.
- **Generated data files, never hand-typed:**
  `scripts/build_web_assets.py` emits `web/data/schema.json` (copy of the
  discovery artifact) and `web/data/stats.json` (evidence-strip numbers
  from the verification record); later `web/data/exhibits.json` +
  `web/data/discovery_replay.json`. Deterministic; outputs committed.
- **W2 backend:** FastAPI (`app/server.py`) wrapping the existing
  `pipeline.simulate_send_and_process` — the five-beat `on_event` callback
  maps 1:1 onto an SSE stream (arrived → Haiku thinking → ops envelope →
  draft decision → changed). All secrets live in its environment only.

## Phases

**W1 — static viewing (now)**
1. `build_web_assets.py` + mint a read-only Turso token (owner step) +
   CORS validation against Turso from a browser context.
2. SPA shell: tab bar (placeholders for Simulate/Discovery/Adapt/H2H),
   routing, Turso data layer with an explicit unreachable-state banner,
   slim header evidence strip.
3. Populate & Maintain tab, sub-nav **Tables | Activity**:
   - Tables: schema-driven browser — client-side search, column sort,
     enum chips, booleans as ✓/—, NULL as faint dash, key cells link to
     records.
   - Record page: fields with schema descriptions; generic related
     records (other tables whose columns name this table's canonical
     key); provenance block (`source_email_id`, `updated_at`, "row-level,
     last writer" label, open-in-Gmail best-effort link).
   - Activity: `ingest_log` (+catchall join) newest-first, ~8s poll,
     new-row highlight — the page visibly moves when anyone fires
     `/aps-simulate-email` from Claude Code.
4. Deploy to GitHub Pages; smoke both data modes; add the URL to the
   portal-note draft (not the public README yet); root PLAN pointer.

**W2 — the button (after W1 review)**
1. Backend: login gate + `/api/simulate` (SSE), global lock, rate limit,
   pool-remaining counter; `drafts_log` harness table so the UI can show
   the draft it just wrote; gmail_io token-refresh write-back made
   tolerant of read-only filesystems.
2. P&M gains sub-nav **Watch it work**: fire-next-scenario button (hidden
   until a valid session), five beats streaming, then changed-row
   highlight in Tables.

**W3 — story tabs**: Head-to-head page (exhibits build + render);
Discovery replay timeline. Ask/compose: decide then.

**W4 — consolidation**: Sheet demotion/removal, README tier inversion
(hosted link = Tier 1, plugin = Tier 2, delegation = Tier 3), teardown
and shot-list updates, "time went here, deliberately" note.

## Done criteria

- W1: all five discovered tables render from live Turso with counts
  matching `pipeline.py status`; record/related/provenance views work;
  activity feed updates live during a terminal-fired simulate; the
  unreachable banner shows when the token/URL is wrong (tested); deployed
  URL loads cold in <2s; no hardcoded schema names anywhere in `app.js`.
- W2: a stranger without the password cannot cause any state change
  (verified by attempt); two concurrent fires serialize; a full fire
  renders all five beats and the table diff.

## Guardrails (inherited)

Never send email (drafts only); ingest stays blind (the web app is a READ
surface over harness outputs — it introduces no new path from
`simulation/` to the extractor); Turso write access exists only behind
the W2 backend; all numbers shown on-page are generated from committed
evidence files.
