"""The web app's backend: a thin HTTP skin over the demo engine.

Endpoints:
  POST /api/login     {"password": ...} -> {"token", "pool_remaining"}
  POST /api/simulate  Bearer <token>; body {} (fire next pooled scenario)
                      or {"custom": {"from","subject","body"}} -> SSE stream
                      of the engine's beats (arrived/thinking/decision/
                      draft/changed/info) plus a final done or error event
  GET  /api/status    {"pool_remaining", "busy"}

  POST /api/showdown  Bearer <token>; {"qid": ...} -> SSE stream of TWO
                      concurrent Opus agent loops over the same question
                      (arm A: Gmail tools only; arm B: Gmail + read-only
                      SQL), events tagged a_*/b_*: thinking, tool, result,
                      answer, done. Questions come ONLY from the committed
                      allowlist (web/data/h2h_questions.json) by id — the
                      endpoint never accepts free text, so the gated key
                      cannot be used as a general model proxy.

Security model (see PLAN.md, stage 5): every real credential (Gmail token,
Anthropic key, Turso write token) lives only in this process's
environment; the browser holds nothing but a short-lived HMAC session
token. The portal password is checked server-side against a hash; one
heavy operation runs at a time (global lock); fires are rate-limited per
token and login failures per IP.
"""
import asyncio
import hashlib
import hmac
import json
import os
import queue
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "populate"))
sys.path.insert(0, str(ROOT / "app"))

# materialize the Gmail token from env before the engine first needs it
_tok = ROOT / "token_apsdemo.json"
if not _tok.exists() and os.environ.get("GMAIL_TOKEN_JSON"):
    _tok.write_text(os.environ["GMAIL_TOKEN_JSON"])

from fastapi import FastAPI, HTTPException, Request          # noqa: E402
from fastapi.middleware.cors import CORSMiddleware           # noqa: E402
from fastapi.responses import StreamingResponse              # noqa: E402

import anthropic                                             # noqa: E402

import pipeline                                              # noqa: E402
from tools import GMAIL_TOOLS, SQL_TOOL, SCHEMA_BRIEF, run_tool  # noqa: E402

H2H_QUESTIONS = {
    q["id"]: q["question"]
    for q in json.loads((ROOT / "web" / "data" / "h2h_questions.json").read_text())["questions"]
}

PASSWORD_SHA256 = os.environ.get("DEMO_PASSWORD_SHA256", "")
SIGNING_SECRET = os.environ.get("SIGNING_SECRET", "").encode()
TOKEN_TTL = 24 * 3600
FIRES_PER_HOUR = 6
LOGIN_FAILS_PER_15MIN = 5

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://sxchen210.github.io", "http://localhost:8742"],
    allow_methods=["*"], allow_headers=["*"])

run_lock = threading.Lock()
_fails: dict[str, list[float]] = {}
_fires: dict[str, list[float]] = {}


def _recent(d, key, window):
    now = time.time()
    d[key] = [t for t in d.get(key, []) if now - t < window]
    return d[key]


def _sign(exp: int) -> str:
    return hmac.new(SIGNING_SECRET, str(exp).encode(), hashlib.sha256).hexdigest()


def make_token() -> str:
    exp = int(time.time()) + TOKEN_TTL
    return f"{exp}.{_sign(exp)}"


def check_token(tok: str) -> bool:
    try:
        exp_s, sig = tok.split(".", 1)
        exp = int(exp_s)
    except ValueError:
        return False
    return hmac.compare_digest(_sign(exp), sig) and exp > time.time()


def pool_remaining() -> int:
    pool = pipeline.DEFAULT_POOL
    n = sum(1 for l in pool.read_text().splitlines() if l.strip())
    fired_path = Path(str(pool) + ".fired.json")
    f = len(json.loads(fired_path.read_text())) if fired_path.exists() else 0
    return max(n - f, 0)


def _auth(request: Request) -> str:
    tok = (request.headers.get("authorization") or "").removeprefix("Bearer ").strip()
    if not SIGNING_SECRET or not check_token(tok):
        raise HTTPException(401, "invalid or expired session")
    return tok


@app.get("/api/status")
def status():
    return {"pool_remaining": pool_remaining(), "busy": run_lock.locked()}


@app.post("/api/login")
async def login(request: Request):
    ip = request.client.host if request.client else "?"
    if len(_recent(_fails, ip, 900)) >= LOGIN_FAILS_PER_15MIN:
        raise HTTPException(429, "too many attempts; try again later")
    body = await request.json()
    got = hashlib.sha256(str(body.get("password", "")).encode()).hexdigest()
    if not PASSWORD_SHA256 or not hmac.compare_digest(got, PASSWORD_SHA256):
        _fails.setdefault(ip, []).append(time.time())
        raise HTTPException(401, "wrong password")
    return {"token": make_token(), "pool_remaining": pool_remaining()}


@app.post("/api/simulate")
async def simulate(request: Request):
    tok = _auth(request)
    if len(_recent(_fires, tok, 3600)) >= FIRES_PER_HOUR:
        raise HTTPException(429, f"rate limit: {FIRES_PER_HOUR} emails per hour")
    try:
        body = await request.json()
    except Exception:
        body = {}
    custom = body.get("custom")
    if custom and not all(custom.get(k) for k in ("from", "subject", "body")):
        raise HTTPException(400, "custom needs from, subject, body")

    if not run_lock.acquire(blocking=False):
        raise HTTPException(409, "a scenario is already running; watch the activity feed")
    _fires.setdefault(tok, []).append(time.time())

    q: queue.Queue = queue.Queue()

    def on_event(stage, text):
        q.put((stage, text))

    def runner():
        try:
            res = pipeline.simulate_send_and_process(custom=custom, on_event=on_event)
            summary = None
            if res:
                summary = {"scenario": res.get("scenario"), "score": res.get("score"),
                           "drafts": [{"body": d.get("body"), "reason": d.get("reason")}
                                      for d in (res.get("drafts") or [])]}
            q.put(("done", json.dumps(summary)))
        except Exception as e:  # surfaced to the stream, never a hung client
            q.put(("error", f"{type(e).__name__}: {e}"))
        finally:
            run_lock.release()
            q.put(None)

    threading.Thread(target=runner, daemon=True).start()

    async def gen():
        while True:
            item = await asyncio.to_thread(q.get)
            if item is None:
                break
            stage, text = item
            yield f"event: {stage}\ndata: {json.dumps(text, ensure_ascii=False)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


# ---------------- live head-to-head (two arms, one question) ----------------

H2H_TASK = (
    "You are a diligent operations assistant for APS Rescue, a small "
    "foster-based dog rescue whose entire operation runs through one shared "
    "Gmail inbox. Answer precisely and completely: name names, give "
    "numbers, state HOW you know. You may use at most {budget} tool calls. "
    "Question: {question}")
H2H_B_EXTRA = (
    "\n\nYou also have read-only SQL access to an operational database "
    "built AUTOMATICALLY from this same mailbox by an extraction model — "
    "it may contain errors; cross-check email when a single fact is "
    "load-bearing. Boolean-ish columns store '1'/'0' as text. Schema:\n"
    + SCHEMA_BRIEF)
H2H_BUDGET = {"a": 25, "b": 12}


def _showdown_arm(arm: str, question: str, q: queue.Queue):
    client = anthropic.Anthropic(max_retries=4)
    tools = GMAIL_TOOLS if arm == "a" else GMAIL_TOOLS + [SQL_TOOL]
    budget = H2H_BUDGET[arm]
    system = H2H_TASK.format(budget=budget, question=question)
    if arm == "b":
        system += H2H_B_EXTRA
    messages = [{"role": "user", "content": "Begin. Answer the question in the system prompt."}]
    used = 0
    t0 = time.time()
    try:
        while True:
            resp = client.messages.create(
                model="claude-opus-5-5", max_tokens=4000,
                thinking={"type": "adaptive", "display": "summarized"},
                system=system, tools=tools,
                tool_choice={"type": "none"} if used >= budget else {"type": "auto"},
                messages=messages)
            blocks = resp.content
            for b in blocks:
                if b.type == "thinking" and b.thinking:
                    q.put((f"{arm}_thinking", b.thinking))
                elif b.type == "text" and b.text.strip():
                    if resp.stop_reason != "tool_use":
                        q.put((f"{arm}_answer", b.text))
                    else:
                        q.put((f"{arm}_note", b.text))
            if resp.stop_reason != "tool_use":
                break
            messages.append({"role": "assistant", "content": blocks})
            results = []
            for b in blocks:
                if b.type == "tool_use":
                    used += 1
                    arg = b.input.get("sql") or b.input.get("query") or b.input.get("thread_id", "")
                    q.put((f"{arm}_tool", f"{b.name}: {arg}"))
                    try:
                        out = run_tool(b.name, b.input)
                    except Exception as e:
                        out = f"ERROR: {type(e).__name__}: {e}"
                    q.put((f"{arm}_result", out[:400]))
                    results.append({"type": "tool_result", "tool_use_id": b.id,
                                    "content": out[:45000]})
            if used >= budget:
                results.append({"type": "text", "text":
                                "Tool budget exhausted. Give your best final "
                                "answer now from what you have gathered."})
            messages.append({"role": "user", "content": results})
        q.put((f"{arm}_done", json.dumps(
            {"tool_calls": used, "seconds": round(time.time() - t0)})))
    except Exception as e:
        q.put((f"{arm}_done", json.dumps(
            {"error": f"{type(e).__name__}: {e}", "tool_calls": used,
             "seconds": round(time.time() - t0)})))


@app.post("/api/showdown")
async def showdown(request: Request):
    tok = _auth(request)
    if len(_recent(_fires, tok, 3600)) >= FIRES_PER_HOUR:
        raise HTTPException(429, f"rate limit: {FIRES_PER_HOUR} runs per hour")
    body = await request.json()
    question = H2H_QUESTIONS.get(str(body.get("qid", "")))
    if not question:
        raise HTTPException(400, "unknown question id")
    if not run_lock.acquire(blocking=False):
        raise HTTPException(409, "another run is in progress")
    _fires.setdefault(tok, []).append(time.time())

    q: queue.Queue = queue.Queue()
    done = {"n": 0}

    def wrap(arm):
        _showdown_arm(arm, question, q)
        done["n"] += 1
        if done["n"] == 2:
            run_lock.release()
            q.put(None)

    for arm in ("a", "b"):
        threading.Thread(target=wrap, args=(arm,), daemon=True).start()

    async def gen():
        while True:
            try:
                item = await asyncio.to_thread(q.get, True, 15)
            except queue.Empty:
                yield ": ping\n\n"   # keep the stream alive through long thinks
                continue
            if item is None:
                break
            stage, text = item
            yield f"event: {stage}\ndata: {json.dumps(text, ensure_ascii=False)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})
