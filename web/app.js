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
  ["over", "Overview"], ["sim", "Simulate"], ["disc", "Discovery"],
  ["pm", "Populate & Maintain"], ["h2h", "Head-to-head"],
];

function viewOverview() {
  $("#main").innerHTML = `
    <p class="premise">Animal Protective Services is a fictional dog rescue,
      built to mirror the day-to-day operations of a real local rescue.
      Operations like these actually run across many channels (Gmail, text
      threads, WhatsApp groups); for this demonstration, everything flows
      through one shared Gmail inbox. That inbox is where the operational
      state lives: who has which dog, which placements are confirmed versus
      tentative, what falls apart when one foster backs out. Normally,
      someone reconstructs all of that from scrollback before every
      decision.</p>
    <p class="premise">This site is a working prototype of the alternative:
      connect a model to the inbox and let it build the understanding of the
      operation. A frontier model discovered the schema from ~1,000 emails in
      the inbox, blind (no predefined schema, no custom extraction
      rules); a cheap model has maintained every record since, from each new
      email, at about $0.0004 per ingestion. Every table view renders from
      the discovered <code>schema.json</code>; nothing is hand-built per
      table.</p>
    <div class="tabguide">
      <div><a href="#/sim"><b>Simulate</b></a>: how the ~1,000-email world was
        constructed. A seeded simulator voicing real-inbox patterns behind a
        strict no-leak boundary, with ground truth kept only for grading.</div>
      <div><a href="#/disc"><b>Discovery</b></a>: the frontier model exploring
        the inbox cold and designing the schema, replayed from the committed
        transcript, round by round with live costs.</div>
      <div><a href="#/pm"><b>Populate &amp; Maintain</b></a>: a cheap model,
        following the extraction playbook the frontier model wrote, built
        these tables from every email and keeps them current; deliver the
        next email and watch it process, live.</div>
      <div><a href="#/h2h"><b>Head-to-head</b></a>: the same model answering
        an operational question with and without the tables, live, side by
        side.</div>
    </div>`;
}

function renderTabs(active) {
  $("#tabs").innerHTML = TABS.map(([id, label]) =>
    `<a href="#/${id}" class="${id === active ? "on" : ""}">${label}</a>`).join("");
}

function viewPlaceholder(id) {
  $("#main").innerHTML = `<p class="placeholder">Nothing here.</p>`;
}

/* shared password gate for backend-powered views */
function sessionGate(subnavHtml, intro, rerender) {
  if (localStorage.getItem("aps_session")) return true;
  $("#main").innerHTML = `
    ${subnavHtml}
    <p class="tdesc">${intro} Actions are gated: enter the demo password
      from the portal note. (Viewing everything else needs no password.)</p>
    <div class="toolbar">
      <input type="password" id="pw" placeholder="demo password">
      <button id="go">Unlock</button>
      <span id="pwmsg" class="muted"></span>
    </div>`;
  $("#go").onclick = async () => {
    const r = await fetch(BACKEND + "/api/login", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password: $("#pw").value }),
    });
    if (!r.ok) { $("#pwmsg").textContent = `no (${r.status})`; return; }
    localStorage.setItem("aps_session", (await r.json()).token);
    rerender();
  };
  return false;
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
    [f.dogs, "dogs across the full timeline, incl. scenarios not yet fired"],
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

function statsBlock() {
  return `
    <p class="tdesc"><b>How Haiku populated the database, following the
      instructions Fable wrote.</b> Scored after the fact against the
      simulator's ground truth, which the pipeline never sees:</p>
    <div class="stats">${(STATS?.stats || []).map((s) => `
      <div class="stat" title="source: ${esc(s.source)}">
        <div class="v">${esc(s.value)}</div>
        <div class="l">${esc(s.label)}</div>
        <div class="d">${esc(s.detail)}</div>
      </div>`).join("")}</div>`;
}

function subnav(active, ns) {
  const chips = tables().map((t) =>
    `<a class="chip ${active === t ? "on" : ""}" href="#/pm/${t}">${esc(t)}<span class="n">${ns[t] ?? ""}</span></a>`);
  chips.push(`<a class="chip live push ${active === "watch" ? "on" : ""}" href="#/pm/watch"><span class="dot"></span>watch it work</a>`);
  chips.push(`<a class="chip live ${active === "activity" ? "on" : ""}" href="#/pm/activity"><span class="dot"></span>live activity</a>`);
  return `<div class="subnav">${chips.join("")}</div>`;
}

/* --- watch it work: fire a scenario through the gated backend --- */

const BACKEND = localStorage.getItem("aps_backend_url")
  || (window.APS_CONFIG || {}).backendUrl || "";

/* the last delivery's beats survive tab switches (and reloads, via
   sessionStorage) until the next delivery replaces them */
let LAST_RUN = (() => {
  try { return JSON.parse(sessionStorage.getItem("aps_last_run") || "[]"); }
  catch { return []; }
})();

function recordBeat(ev, data) {
  LAST_RUN.push([ev, data]);
  try { sessionStorage.setItem("aps_last_run", JSON.stringify(LAST_RUN)); } catch { /* fine */ }
}
const BEAT = {
  arrived: "1 · An email arrives in the inbox",
  thinking: "2 · Haiku's reasoning",
  decision: "3 · The ops envelope Haiku emitted (its notes are its own words)",
  draft: "4 · Reply decision (Opus 5.5, a different model, with Gmail + SQL tools)",
  changed: "5 · What changed",
};

async function viewWatch() {
  const ns = await counts().catch(() => ({}));
  if (!sessionGate(statsBlock() + subnav("watch", ns),
      `This view sends a real email into the live inbox and streams the
       pipeline processing it, beat by beat.`, viewWatch)) return;

  let remaining = "?";
  try {
    remaining = (await fetch(BACKEND + "/api/status").then((r) => r.json())).pool_remaining;
  } catch { /* backend unreachable; button will surface it */ }

  $("#main").innerHTML = `
    ${statsBlock()}
    ${subnav("watch", ns)}
    <p class="tdesc">The pool holds pre-written scenario emails from the same
      simulated universe, each with a hidden answer key. Pressing the button
      inserts the next one into the real Gmail inbox; the blind extractor
      processes it live and you watch every beat, then the tables update.
      One at a time, rate-limited. Scenario emails carry the simulated
      world's own dates (its history runs to 2026-10-16 and the pool
      continues from 10-17), so a delivered email's date reflects the world
      clock, not today.</p>
    <div class="toolbar">
      <button id="fire">Deliver the next email</button>
      <span class="muted">${esc(String(remaining))} scenarios remaining</span>
    </div>
    <div id="beats"></div>`;

  if (LAST_RUN.length) {
    $("#beats").insertAdjacentHTML("beforeend",
      `<p class="muted">The previous delivery, replayed:</p>`);
    for (const [ev, d] of LAST_RUN) renderBeat(ev, d, false);
  }

  $("#fire").onclick = async () => {
    const btn = $("#fire");
    btn.disabled = true;
    btn.textContent = "delivering…";
    $("#beats").innerHTML = "";
    LAST_RUN = [];
    try { sessionStorage.removeItem("aps_last_run"); } catch { /* fine */ }
    try {
      const resp = await fetch(BACKEND + "/api/simulate", {
        method: "POST",
        headers: { "Content-Type": "application/json",
                   Authorization: `Bearer ${localStorage.getItem("aps_session")}` },
        body: "{}",
      });
      if (resp.status === 401) { localStorage.removeItem("aps_session"); viewWatch(); return; }
      if (!resp.ok) {
        $("#beats").innerHTML = `<p class="placeholder">${esc((await r_text(resp)))}</p>`;
        return;
      }
      await readSSE(resp, (ev, data) => { recordBeat(ev, data); renderBeat(ev, data); });
      cache.clear();  // table views refetch fresh state
    } catch (e) {
      $("#beats").insertAdjacentHTML("beforeend",
        `<p class="placeholder">stream failed: ${esc(e.message)}</p>`);
    } finally {
      btn.disabled = false;
      btn.textContent = "Deliver the next email";
    }
  };
}

async function r_text(resp) {
  try { return JSON.stringify(await resp.json()); } catch { return `HTTP ${resp.status}`; }
}

async function readSSE(resp, onEvent) {
  const reader = resp.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const block = buf.slice(0, i); buf = buf.slice(i + 2);
      const ev = (block.match(/^event: (.*)$/m) || [])[1];
      const dataLine = (block.match(/^data: (.*)$/m) || [])[1];
      if (ev && dataLine !== undefined) onEvent(ev, JSON.parse(dataLine));
    }
  }
}

function renderBeat(ev, data, scroll = true) {
  const box = $("#beats");
  if (ev === "info") {
    box.insertAdjacentHTML("beforeend", `<p class="muted">${esc(data)}</p>`);
  } else if (ev === "thinking") {
    box.insertAdjacentHTML("beforeend", `<div class="panel">
      <h3>${esc(BEAT.thinking)}</h3><p class="fable-quote">${esc(data)}</p></div>`);
  } else if (ev === "done") {
    const s = data ? JSON.parse(data) : null;
    const drafts = (s?.drafts || []).map((d) =>
      `<div class="panel"><h3>The draft Opus wrote (saved to Gmail Drafts, never sent)</h3>
       <pre class="mailbody">${esc(d.body || "")}</pre></div>`).join("");
    box.insertAdjacentHTML("beforeend", `${drafts}
      <div class="panel"><h3>Done</h3><div class="small">
      ${s?.score ? esc(s.score) + ". " : ""}The tables above now reflect this
      email; open the affected table or the
      <a href="#/pm/activity">activity feed</a> to see it landed.</div></div>`);
  } else if (ev === "error") {
    box.insertAdjacentHTML("beforeend",
      `<p class="placeholder">engine error: ${esc(data)}</p>`);
  } else {
    box.insertAdjacentHTML("beforeend", `<div class="panel">
      <h3>${esc(BEAT[ev] || ev)}</h3><pre class="mailbody">${esc(data)}</pre></div>`);
  }
  if (scroll) box.lastElementChild?.scrollIntoView({ behavior: "smooth", block: "end" });
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
    ${statsBlock()}
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
        </div>
        <div class="panel"><h3>About this page</h3>
          <div class="small muted">Rendered entirely from the discovered
          <code>schema.json</code>: fields, descriptions, badges, and the
          related tables above are all schema-derived, not hand-built.</div>
        </div>
      </div>
    </div>`;
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
    ${statsBlock()}
    ${subnav("activity", ns)}
    <p class="tdesc">Every email the extractor has processed, newest first;
      refreshes every 15s.</p>
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
  }, 15000);
}

/* --- head-to-head: the same model, with and without the tables, live --- */

let H2H_QS = null;
let H2H_LAST = (() => {
  try { return JSON.parse(sessionStorage.getItem("aps_last_h2h") || "null"); }
  catch { return null; }
})();

const ARM_TITLE = {
  a: "Search-only · Opus 5.5 with Gmail tools",
  b: "Tables · Opus 5.5 with Gmail + read-only SQL",
};

async function viewH2H() {
  if (!H2H_QS) {
    H2H_QS = (await fetch("data/h2h_questions.json").then((r) => r.json())).questions;
  }
  if (!sessionGate("",
      `Two agents answer the same question live: the same model, the same
       budget, the only difference is that one can query the tables this
       inbox built. No grading is shown; watch what each one does.`,
      viewH2H)) return;

  const opts = H2H_QS.map((q, i) =>
    `<option value="${esc(q.id)}" ${i === 0 ? "selected" : ""}>${esc(q.question)}</option>`).join("");
  $("#main").innerHTML = `
    <p class="tdesc">Pick a question and run it. Both agents start at the
      same moment with the same tool budget; the left one can only search
      and read the mailbox, the right one can also query the live tables.
      Their summarized thinking, every tool call, and both answers stream
      in as they happen. These are live model runs, not replays; the
      committed, independently re-graded comparison lives in the
      <a href="https://github.com/sxchen210/aps-rescue/tree/main/app/validation/third_party">repository</a>.</p>
    <div class="toolbar">
      <select id="h2hq">${opts}</select>
      <button id="h2hrun">Run both arms</button>
      <span id="h2hmsg" class="muted"></span>
    </div>
    <div class="h2h-grid">
      ${["a", "b"].map((arm) => `
        <div class="h2h-col">
          <div class="h2h-head">${ARM_TITLE[arm]}
            <span class="muted" id="${arm}-stat"></span></div>
          <div class="h2h-win" id="${arm}-win"></div>
        </div>`).join("")}
    </div>`;

  if (H2H_LAST) {
    $("#h2hq").value = H2H_LAST.qid;
    $("#h2hmsg").textContent = "previous run, replayed";
    for (const [ev, d] of H2H_LAST.events) renderH2H(ev, d, false);
  }

  const timers = {};
  $("#h2hrun").onclick = async () => {
    const btn = $("#h2hrun");
    const qid = $("#h2hq").value;
    btn.disabled = true;
    btn.textContent = "running…";
    $("#h2hmsg").textContent = "";
    $("#a-win").innerHTML = ""; $("#b-win").innerHTML = "";
    H2H_LAST = { qid, events: [] };
    try { sessionStorage.removeItem("aps_last_h2h"); } catch { /* fine */ }
    const t0 = Date.now();
    for (const arm of ["a", "b"]) {
      timers[arm] = setInterval(() => {
        const el = $(`#${arm}-stat`);
        if (el) el.textContent = ` ${Math.round((Date.now() - t0) / 1000)}s`;
      }, 1000);
    }
    const stopTimer = (arm) => { clearInterval(timers[arm]); };
    try {
      const resp = await fetch(BACKEND + "/api/showdown", {
        method: "POST",
        headers: { "Content-Type": "application/json",
                   Authorization: `Bearer ${localStorage.getItem("aps_session")}` },
        body: JSON.stringify({ qid }),
      });
      if (resp.status === 401) { localStorage.removeItem("aps_session"); viewH2H(); return; }
      if (!resp.ok) { $("#h2hmsg").textContent = await r_text(resp); return; }
      await readSSE(resp, (ev, data) => {
        H2H_LAST.events.push([ev, data]);
        try { sessionStorage.setItem("aps_last_h2h", JSON.stringify(H2H_LAST)); } catch { /* fine */ }
        if (ev.endsWith("_done")) stopTimer(ev[0]);
        renderH2H(ev, data, true);
      });
    } catch (e) {
      $("#h2hmsg").textContent = `stream failed: ${e.message}`;
    } finally {
      stopTimer("a"); stopTimer("b");
      btn.disabled = false;
      btn.textContent = "Run both arms";
    }
  };
}

function renderH2H(ev, data, scroll) {
  const arm = ev[0];
  const kind = ev.slice(2);
  const win = $(`#${arm}-win`);
  if (!win) return;
  if (kind === "thinking") {
    win.insertAdjacentHTML("beforeend", `<p class="fable-quote">${esc(data)}</p>`);
  } else if (kind === "note") {
    win.insertAdjacentHTML("beforeend", `<p class="muted small-note">${esc(data)}</p>`);
  } else if (kind === "tool") {
    if (data.startsWith("sql_query:")) {
      win.insertAdjacentHTML("beforeend",
        `<pre class="sqlchip">${esc(data.slice(10).trim())}</pre>`);
    } else {
      win.insertAdjacentHTML("beforeend",
        `<div><span class="toolchip">${esc(data)}</span></div>`);
    }
  } else if (kind === "result") {
    win.insertAdjacentHTML("beforeend",
      `<details class="h2h-res"><summary>result</summary><pre class="mailbody">${esc(data)}</pre></details>`);
  } else if (kind === "answer") {
    win.insertAdjacentHTML("beforeend",
      `<div class="panel"><h3>Final answer</h3><pre class="mailbody">${esc(data)}</pre></div>`);
  } else if (kind === "done") {
    let s = {};
    try { s = JSON.parse(data); } catch { /* fine */ }
    const stat = $(`#${arm}-stat`);
    if (stat) stat.textContent = s.error
      ? ` failed: ${s.error}`
      : ` done · ${s.tool_calls} tool calls · ${s.seconds}s`;
  }
  if (scroll) win.scrollTop = win.scrollHeight;
}

/* ---------- router + boot ---------- */

/* renders serialize: a fast later navigation can't be overwritten by a
   slower earlier one still awaiting its data */
let _routeChain = Promise.resolve();
function route() {
  _routeChain = _routeChain.then(_route).catch(() => {});
}

async function _route() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; seenIds = null; }
  const parts = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  const tab = parts[0] || "over";
  renderTabs(tab);
  try {
    if (tab === "over") return viewOverview();
    if (tab === "sim") return await viewSimulate();
    if (tab === "disc") return await viewDiscovery(parseInt(parts[1] || "0", 10));
    if (tab === "h2h") return await viewH2H();
    if (tab !== "pm") return viewPlaceholder(tab);
    if (parts[1] === "watch") return await viewWatch();
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
  window.addEventListener("hashchange", route);
  if (!location.hash) location.hash = "#/over";
  route();
}

boot();
