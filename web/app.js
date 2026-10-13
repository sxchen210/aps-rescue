/* APS Rescue demo — schema-driven, read-only SPA over the live Turso DB.
   No build step, no dependencies. This file names no table and no column:
   everything below renders from data/schema.json, so the same code would
   render any schema the discovery agent produces. Turso-only by decision —
   if the DB is unreachable the page says so; it never falls back silently. */
"use strict";

/* ---------- config + tiny utilities ---------- */

const CFG = {
  url: localStorage.getItem("aps_turso_url") || (window.APS_CONFIG || {}).tursoUrl || "",
  token: localStorage.getItem("aps_turso_token") || (window.APS_CONFIG || {}).tursoToken || "",
};

const $ = (sel) => document.querySelector(sel);

function esc(v) {
  return String(v ?? "").replace(/[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function el(html) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstChild;
}

/* ---------- Turso data layer (read-only token; SELECTs only) ---------- */

let connOK = null;

function setConn(state, msg) {
  connOK = state;
  const c = $("#conn");
  c.className = "conn " + (state ? "live" : "down");
  c.textContent = state ? "● live database" : "● " + (msg || "database unreachable");
  const b = $("#banner");
  if (state) { b.hidden = true; }
  else {
    b.hidden = false;
    b.innerHTML = `Live database unreachable: ${esc(msg || "check the connection")}. `;
    const btn = el(`<button>Retry</button>`);
    btn.onclick = () => { cache.clear(); route(); };
    b.appendChild(btn);
  }
}

async function sqlBatch(stmts) {
  if (!CFG.url || !CFG.token) {
    setConn(false, "no database token configured");
    throw new Error("no config");
  }
  const body = {
    requests: stmts.map(([sql, args]) => ({
      type: "execute",
      stmt: { sql, args: (args || []).map((a) => a === null
        ? { type: "null" } : { type: "text", value: String(a) }) },
    })).concat([{ type: "close" }]),
  };
  let resp;
  try {
    resp = await fetch(CFG.url.replace(/\/$/, "") + "/v2/pipeline", {
      method: "POST",
      headers: { Authorization: `Bearer ${CFG.token}`, "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (e) { setConn(false, "network error"); throw e; }
  if (!resp.ok) { setConn(false, `HTTP ${resp.status}`); throw new Error(`HTTP ${resp.status}`); }
  const out = await resp.json();
  const results = [];
  for (const r of out.results.slice(0, stmts.length)) {
    if (r.type === "error") { setConn(false, r.error?.message); throw new Error(r.error?.message); }
    const res = r.response.result;
    const cols = res.cols.map((c) => c.name);
    results.push(res.rows.map((row) =>
      Object.fromEntries(cols.map((c, i) => [c, row[i]?.value ?? null]))));
  }
  setConn(true);
  return results;
}

const sql = async (q, args) => (await sqlBatch([[q, args]]))[0];

/* 30s cache so tab-hopping doesn't refetch; activity polling bypasses it */
const cache = new Map();
async function cached(key, fn) {
  const hit = cache.get(key);
  if (hit && Date.now() - hit.t < 30_000) return hit.v;
  const v = await fn();
  cache.set(key, { v, t: Date.now() });
  return v;
}

/* ---------- schema-driven helpers ---------- */

let SCHEMA = null;   // discovery artifact (verbatim copy)
let STATS = null;
// column name -> table it is the canonical key of (for cross-table links)
let KEY_OWNER = {};

function tables() { return Object.keys(SCHEMA.tables); }
function tdef(t) { return SCHEMA.tables[t]; }
function cols(t) { return Object.keys(tdef(t).columns); }

function fmtCell(table, col, v, linkKeys = true) {
  if (v === null || v === "") return `<span class="null">—</span>`;
  const meta = tdef(table).columns[col] || {};
  if (meta.type === "boolean") {
    return v === "1" ? `<span class="bool-y">✓</span>` : `<span class="null">—</span>`;
  }
  if (meta.type === "enum") return `<span class="enum-badge">${esc(v)}</span>`;
  // a value in a column named after another table's canonical key links there
  const owner = KEY_OWNER[col];
  if (linkKeys && owner) {
    return `<a class="key" href="#/pm/${esc(owner)}/k/${encodeURIComponent(v)}">${esc(v)}</a>`;
  }
  return esc(v);
}

/* ---------- views ---------- */

const TABS = [
  ["sim", "Simulate"], ["disc", "Discovery"], ["pm", "Populate & Maintain"],
  ["h2h", "Head-to-head"], ["adapt", "Adapt"],
];

function renderTabs(active) {
  $("#tabs").innerHTML = TABS.map(([id, label]) =>
    `<a href="#/${id}" class="${id === active ? "on" : ""}">${label}</a>`).join("");
}

const PLACEHOLDER = {
  h2h: `The head-to-head (the same model answering the same questions with and
        without these tables, self-graded and blind re-graded by a third party)
        is coming; the committed exhibits live in
        <a href="https://github.com/sxchen210/aps-rescue/tree/main/app/validation/third_party">app/validation/</a>.`,
  adapt: `How the schema adapts when the world outgrows it (the cancellation /
        clear-verb story). This tab is coming.`,
};

function viewPlaceholder(id) {
  $("#main").innerHTML = `<p class="placeholder">${PLACEHOLDER[id]}</p>`;
}

/* --- Simulate: how the universe was made --- */

let SIM = null;

async function viewSimulate() {
  if (!SIM) SIM = await fetch("data/sim.json").then((r) => r.json());
  const f = SIM.facts;
  const tiles = [
    [f.seed_emails.toLocaleString(), "seed emails, six simulated weeks"],
    [f.week1_emails, "more injected as a verified seventh week"],
    [f.pool_total, "scenarios pooled, ready to fire live"],
    [f.dogs, "dogs in the ground truth"],
    [f.households, "foster households"],
    [f.applications, "applications"],
    [f.pattern_cards, "email pattern cards"],
  ].map(([v, l]) =>
    `<div class="stat"><div class="v">${esc(String(v))}</div><div class="l">${esc(l)}</div></div>`).join("");

  $("#main").innerHTML = `
    <p class="tdesc">Every email in this inbox is synthetic. A real rescue's
      foster inbox was consulted read-only to keep the simulation honest, and
      a strict boundary (below) guarantees nothing real crossed over.
      Simulation buys two properties a real inbox cannot offer: <b>ground
      truth</b> (the emails derive from a simulated world, so the true state
      of every dog, foster, and appointment is known at every instant, and
      the tables the models build can be verified rather than eyeballed) and
      <b>a closed world</b> (all coordination happens over email, so every
      fact is traceable to inbox evidence). Full design:
      <a href="https://github.com/sxchen210/aps-rescue/blob/main/simulation/SIMULATION_DESIGN.md">SIMULATION_DESIGN.md</a>.</p>
    <p class="tdesc strong">The architecture rule: the LLM never decides what
      exists. It only voices it.</p>
    <div class="panel"><h3>Layer 1: the universe (pure Python, seeded)</h3>
      <div class="small"><code>universe.py</code> runs state machines over
      dogs, households, applications, and the calendar: shelter pull, intake,
      foster placement, spay/neuter days, photos, bio, posting, events,
      applications, adoptions, returns, vacations, coverage handoffs.
      It emits timestamped events plus ground-truth state at every instant.
      Deterministic and replayable from one seed, and endless: the world was
      extended once already (the verified seventh week plus the firing pool),
      and can be extended again any time.</div></div>
    <div class="panel"><h3>Layer 2: thread derivation (structure cards)</h3>
      <div class="small">Each event type maps to an email pattern in
      <code>patterns/*.md</code>: who writes first, the turn order, which
      facts move, timing jitter, group thread vs 1:1, reply quoting. The
      cards were distilled by observing the real reference inbox and contain
      structure only, never content.</div></div>
    <div class="panel"><h3>Layer 3: voice rendering (the only LLM step)</h3>
      <div class="small"><code>render.py</code> writes each email from a
      persona card, the matching structure card, the event's facts (must-say,
      must-not-contradict), and the thread tail. Every persona is bound at
      creation to a model-and-effort mix (terse mobile writers on a small
      model, polished correspondents on a strong one), so individuals stay
      consistent while the corpus varies, and style never correlates with
      workflow type.</div></div>
    <div class="panel"><h3>The leak boundary</h3>
      <div class="small">Before anything is seeded, <code>leakcheck.py</code>
      pulls the reference inbox's entities (names, addresses, dog names,
      venues) and long n-grams into memory only, scans the entire synthetic
      corpus for any entity hit or any shared phrase of about eight words,
      and fails the build on a single hit. Nothing harvested is written to
      disk. Dog names are deliberately disjoint by theme. Every corpus batch
      has passed at 0 hard hits; the latest additions passed at 0 hard, 0
      soft.</div></div>
    <div class="panel"><h3>Ground truth is for grading only</h3>
      <div class="small">The simulator's true state is the verification
      asset behind the numbers in the header strip. Neither
      <a href="#/disc">schema discovery</a> nor the extractor ever sees it;
      they see only the mailbox. It is consulted after the fact, to score
      what they built.</div></div>
    <p class="tdesc">Seeding: the rendered corpus is inserted into the real
      Gmail inbox chronologically with historical Date headers and real
      thread structure, so the mailbox reads as a lived-in operation rather
      than a dump. The world at a glance:</p>
    <div class="stats">${tiles}</div>`;
}

/* --- Discovery: the committed transcript, replayed --- */

let REPLAY = null;

async function viewDiscovery(idx) {
  if (!REPLAY) {
    REPLAY = await fetch("data/discovery_replay.json").then((r) => r.json());
  }
  const chapters = REPLAY.chapters;
  const i = Math.min(Math.max(idx || 0, 0), chapters.length - 1);
  const ch = chapters[i];

  const chips = chapters.map((c, j) =>
    `<a class="chip ${j === i ? "on" : ""}" href="#/disc/${j}">${esc(c.title)}
     <span class="n">$${c.final.cost.toFixed(2)}</span></a>`).join("");

  const rows = ch.rounds.map((r) => {
    const quote = r.text
      ? `<p class="fable-quote">${esc(r.text)}</p>` : "";
    const tools = r.tools.map((t) =>
      `<span class="toolchip"><b>${esc(t.name)}</b>${t.arg ? " " + esc(t.arg) : ""}</span>`).join(" ");
    return `<div class="round-row">
      <div class="round-no">r${r.round}<span class="round-cost">$${r.cost.toFixed(2)}</span></div>
      <div class="round-body">${quote}${tools}</div>
    </div>`;
  }).join("");

  const u = ch.final.usage || {};
  $("#main").innerHTML = `
    <p class="tdesc">Blind by construction: the model was connected to the
      mailbox with four tools (<code>inbox_stats</code>,
      <code>list_threads</code>, <code>get_thread</code>, <code>search</code>)
      and nothing else. No simulator internals, no ground truth, no hints.
      What follows is the committed transcript
      (<a href="https://github.com/sxchen210/aps-rescue/tree/main/discovery">discovery/</a>),
      not a re-enactment; the running total on the left is live API cost.</p>
    <p class="tdesc strong">Two files to keep straight:
      <a href="https://github.com/sxchen210/aps-rescue/blob/main/discovery/discovery.py"><code>discovery.py</code></a>
      is OUR side: the mission prompt given to the strong model (Fable),
      its four tools, and the ops-envelope contract it must design within.
      <a href="https://github.com/sxchen210/aps-rescue/blob/main/discovery/instructions.md"><code>instructions.md</code></a>
      is what FABLE wrote in return: the extraction playbook the cheap
      model (Haiku) follows, alone and from scratch, on every email that
      maintains the <a href="#/pm">Populate &amp; Maintain</a> tables.</p>
    <div class="subnav">${chips}</div>
    <p class="muted">${ch.intro} In all: ${ch.rounds.length} rounds,
      ${ch.tool_calls} tool calls, $${ch.final.cost.toFixed(2)}.</p>
    <div class="timeline">${rows}</div>
    <div class="panel" style="margin-top:14px">
      <h3>Artifacts accepted</h3>
      <div class="small">All three artifacts submitted and saved:
        ${(u.out || 0).toLocaleString()} tokens written,
        ${(u.cache_read || 0).toLocaleString()} read from cache,
        $${ch.final.cost.toFixed(2)} total. The structural sanity gate
        passed, and the schema it designed drives all of
        <a href="#/pm">Populate &amp; Maintain</a>: every tab, column,
        description, and badge there is generated from
        <code>schema.json</code>, nothing hand-built per table.</div>
    </div>`;
}

/* --- Populate & Maintain: tables --- */

const tstate = {}; // per-table UI state: {q, sort, dir, filters:{col:val}}

async function counts() {
  return cached("counts", async () => {
    const qs = tables().map((t) => [`SELECT COUNT(*) AS n FROM "${t}"`]);
    const res = await sqlBatch(qs);
    return Object.fromEntries(tables().map((t, i) => [t, res[i][0].n]));
  });
}

async function rowsOf(t) {
  return cached("rows:" + t, () =>
    sql(`SELECT * FROM "${t}" ORDER BY id`));
}

function subnav(active, ns) {
  const chips = tables().map((t) =>
    `<a class="chip ${active === t ? "on" : ""}" href="#/pm/${t}">${esc(t)}<span class="n">${ns[t] ?? ""}</span></a>`);
  chips.push(`<a class="chip ${active === "activity" ? "on" : ""}" href="#/pm/activity">activity<span class="n">live</span></a>`);
  return `<div class="subnav">${chips.join("")}</div>`;
}

async function viewTable(t) {
  const ns = await counts();
  const all = await rowsOf(t);
  const st = (tstate[t] ||= { sort: null, dir: 1, filters: {} });
  const def = tdef(t);
  const columns = cols(t).concat(["updated_at"]);
  const enumCols = cols(t).filter((c) => def.columns[c].type === "enum");

  let rows = all;
  for (const [c, v] of Object.entries(st.filters)) {
    if (v) rows = rows.filter((r) => r[c] === v);
  }
  if (st.sort) {
    const c = st.sort, d = st.dir;
    rows = [...rows].sort((a, b) => {
      const x = a[c], y = b[c];
      if (x === y) return 0;
      if (x === null || x === "") return 1;       // nulls last either way
      if (y === null || y === "") return -1;
      const nx = Number(x), ny = Number(y);
      if (!Number.isNaN(nx) && !Number.isNaN(ny)) return (nx - ny) * d;
      return String(x).localeCompare(String(y)) * d;
    });
  }

  const filterSel = enumCols.map((c) => {
    const opts = (def.columns[c].values || []).map((v) =>
      `<option value="${esc(v)}" ${st.filters[c] === v ? "selected" : ""}>${esc(v)}</option>`);
    return `<select data-f="${esc(c)}" title="filter ${esc(c)}">
      <option value="">${esc(c)}: all</option>${opts.join("")}</select>`;
  }).join("");

  const head = columns.map((c) => {
    const arrow = st.sort === c ? `<span class="arrow">${st.dir > 0 ? "▲" : "▼"}</span>` : "";
    const desc = def.columns[c]?.description || (c === "updated_at" ? "last write (system)" : "");
    return `<th data-c="${esc(c)}" title="${esc(desc)}">${esc(c)} ${arrow}</th>`;
  }).join("");

  const keyCols = new Set(def.canonical_keys);
  const body = rows.map((r) => `<tr>${columns.map((c) => {
    const inner = keyCols.has(c)
      ? `<a class="key" href="#/pm/${esc(t)}/${esc(r.id)}">${esc(r[c] ?? "—")}</a>`
      : fmtCell(t, c, r[c]);
    return `<td>${inner}</td>`;
  }).join("")}</tr>`).join("");

  $("#main").innerHTML = `
    ${subnav(t, ns)}
    <p class="tdesc">${esc(def.description || "")}</p>
    <div class="toolbar">
      ${filterSel}
      <span class="muted">${rows.length} of ${all.length} rows · click a header to sort ·
        hover a header for the discovered description</span>
    </div>
    <div class="tablewrap"><table>
      <thead><tr>${head}</tr></thead><tbody>${body}</tbody>
    </table></div>`;

  document.querySelectorAll(".toolbar select").forEach((s) => {
    s.onchange = () => { st.filters[s.dataset.f] = s.value; viewTable(t); };
  });
  document.querySelectorAll("th").forEach((h) => {
    h.onclick = () => {
      const c = h.dataset.c;
      if (st.sort === c) st.dir = -st.dir; else { st.sort = c; st.dir = 1; }
      viewTable(t);
    };
  });
}

/* --- record page --- */

async function viewRecord(t, id, byKey) {
  const ns = await counts();
  const all = await rowsOf(t);
  const def = tdef(t);
  const row = byKey
    ? all.find((r) => (r[def.canonical_keys[0]] ?? "").toLowerCase() === id.toLowerCase())
    : all.find((r) => String(r.id) === String(id));
  if (!row) {
    $("#main").innerHTML = `${subnav(t, ns)}<p class="placeholder">No such row.</p>`;
    return;
  }
  const title = def.canonical_keys.map((k) => row[k]).join(" · ");

  const fields = cols(t).map((c) => `
    <dt title="${esc(def.columns[c].description || "")}">${esc(c)}</dt>
    <dd>${fmtCell(t, c, row[c])}</dd>`).join("");

  // generic related records: any other table owning a column named like one
  // of this table's canonical keys (or vice versa), matched on value
  const related = [];
  for (const other of tables()) {
    if (other === t) continue;
    for (const k of def.canonical_keys) {
      if (cols(other).includes(k) && row[k]) {
        const rows = (await rowsOf(other)).filter(
          (r) => (r[k] ?? "").toLowerCase() === String(row[k]).toLowerCase());
        if (rows.length) related.push({ other, k, rows });
      }
    }
  }
  const relHtml = related.map(({ other, k, rows }) => `
    <div class="related"><h3>${esc(other)} <span class="muted">via ${esc(k)}</span></h3>
    <div class="tablewrap"><table><thead><tr>${cols(other).map((c) => `<th>${esc(c)}</th>`).join("")}</tr></thead>
    <tbody>${rows.map((r) => `<tr>${cols(other).map((c) =>
      `<td>${fmtCell(other, c, r[c])}</td>`).join("")}</tr>`).join("")}</tbody>
    </table></div></div>`).join("");

  const gid = row.source_email_id || "";
  $("#main").innerHTML = `
    ${subnav(t, ns)}
    <p class="crumbs"><a href="#/pm/${esc(t)}">${esc(t)}</a> / <strong>${esc(title)}</strong></p>
    <div class="record">
      <div><dl class="fields">${fields}</dl>${relHtml}</div>
      <div>
        <div class="panel">
          <h3>Provenance: row-level, last writer</h3>
          <div class="small">
            This row was last changed by email <code>${esc(gid)}</code>
            at ${esc(row.updated_at || "—")}. Earlier writes to other fields
            came from earlier emails (not tracked per field; a known limit).
          </div>
          <div class="small" style="margin-top:8px">
            <a href="https://mail.google.com/mail/u/0/#all/${encodeURIComponent(gid)}"
               rel="noopener">open in Gmail</a> (needs delegate access) ·
            <button id="copyq">copy gmail-search command</button>
          </div>
        </div>
        <div class="panel"><h3>About this page</h3>
          <div class="small muted">Rendered entirely from the discovered
          <code>schema.json</code>: fields, descriptions, badges, and the
          related tables above are all schema-derived, not hand-built.</div>
        </div>
      </div>
    </div>`;
  const btn = $("#copyq");
  if (btn) btn.onclick = () => {
    navigator.clipboard.writeText(
      `cd app && APS_DB=turso python3 pipeline.py gmail-thread ${gid}`);
    btn.textContent = "copied";
  };
}

/* --- activity feed --- */

let pollTimer = null;
let seenIds = null;

async function fetchActivity() {
  // rowid = processing order; email dates can be historical (seeded or
  // backdated), so "newest first" must mean most recently PROCESSED
  const [log, catchall] = await sqlBatch([
    [`SELECT rowid AS seq, * FROM ingest_log ORDER BY rowid DESC LIMIT 80`],
    [`SELECT gmail_id, subject, sender, tag FROM catchall ORDER BY id DESC LIMIT 200`],
  ]);
  const meta = Object.fromEntries(catchall.map((c) => [c.gmail_id, c]));
  return { log, meta };
}

function renderActivity({ log, meta }, ns) {
  const fresh = seenIds ? log.filter((r) => !seenIds.has(r.gmail_id)) : [];
  seenIds = new Set(log.map((r) => r.gmail_id));
  const rows = log.map((r) => {
    const m = meta[r.gmail_id];
    const what = m
      ? `<span class="tag">${esc(m.tag)}</span> ${esc(m.subject || "")} <span class="muted">· ${esc(m.sender || "")}</span>`
      : `${r.ops} table op${r.ops === "1" ? "" : "s"} applied <span class="muted">· email ${esc(r.gmail_id)}</span>`;
    const extra = [
      r.anomalies ? `<span class="muted">⚐ ${esc(r.anomalies)}</span>` : "",
      r.error ? `<span class="err">${esc(r.error)}</span>` : "",
    ].filter(Boolean).join(" ");
    const isFresh = fresh.some((f) => f.gmail_id === r.gmail_id);
    return `<div class="feed-row ${isFresh ? "fresh" : ""}">
      <span class="ts">${esc((r.ts || "").replace("T", " "))}</span>
      <span class="what">${what} ${extra}</span></div>`;
  }).join("");
  $("#main").innerHTML = `
    ${subnav("activity", ns)}
    <p class="tdesc">Every email the extractor has processed, newest first,
      refreshing every 8s. Fire a scenario from the Claude Code plugin
      (<code>/aps-simulate-email</code>) and watch it land here.</p>
    <div class="feed">${rows}</div>`;
}

async function viewActivity() {
  const ns = await counts();
  renderActivity(await fetchActivity(), ns);
  pollTimer = setInterval(async () => {
    try {
      cache.delete("counts");
      renderActivity(await fetchActivity(), await counts());
    } catch { /* banner already shown by data layer */ }
  }, 8000);
}

/* ---------- router + boot ---------- */

async function route() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; seenIds = null; }
  const parts = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  const tab = parts[0] || "pm";
  renderTabs(tab);
  try {
    if (tab === "sim") return await viewSimulate();
    if (tab === "disc") return await viewDiscovery(parseInt(parts[1] || "0", 10));
    if (tab !== "pm") return viewPlaceholder(tab);
    if (parts[1] === "activity") return await viewActivity();
    const t = parts[1] && SCHEMA.tables[parts[1]] ? parts[1] : tables()[0];
    if (parts[2] === "k" && parts[3]) return await viewRecord(t, decodeURIComponent(parts[3]), true);
    if (parts[2]) return await viewRecord(t, parts[2], false);
    return await viewTable(t);
  } catch (e) {
    $("#main").innerHTML = `<p class="placeholder">Could not load this view:
      ${esc(e.message)}. ${connOK === false ? "The live database is unreachable." : ""}</p>`;
  }
}

async function boot() {
  const [schema, stats] = await Promise.all([
    fetch("data/schema.json").then((r) => r.json()),
    fetch("data/stats.json").then((r) => r.json()),
  ]);
  SCHEMA = schema;
  STATS = stats;
  for (const t of tables()) {
    for (const k of tdef(t).canonical_keys) KEY_OWNER[k] ||= t;
  }
  $("#stats").innerHTML = STATS.stats.map((s) =>
    `<div class="stat" title="${esc(s.detail)} · source: ${esc(s.source)}">
       <div class="v">${esc(s.value)}</div><div class="l">${esc(s.label)}</div></div>`).join("");
  window.addEventListener("hashchange", route);
  if (!location.hash) location.hash = "#/pm";
  route();
}

boot();
