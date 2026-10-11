"""Draft showdown (read-only): both arms draft a REPLY to a pre-registered
inbound email. Same model/effort/budget; Arm B adds the read-only SQL tool.
No Gmail writes — the inbound email is supplied in-prompt; the output is a
draft, nothing is inserted or sent.

Usage: set -a && . ../.env && set +a && python3 draft_compare.py
"""
import json
import time
from pathlib import Path

import anthropic

from qa_compare import MODEL, EFFORT, MAX_TOKENS, PRICE
from tools import GMAIL_TOOLS, SQL_TOOL, SCHEMA_BRIEF, run_tool

HERE = Path(__file__).resolve().parent
TOOL_BUDGET = 20

SYSTEM = """You handle the shared inbox of APS Rescue, a small foster-based \
dog rescue in Redwood City, CA, run by coordinators Dana, Priya, June and \
Tom who sign emails with their first names. Today is Sunday, October 12, 2026.

TASK: an email just arrived (the user message). Gather whatever context you \
need with your tools, then output ONLY the reply draft in exactly this form:

Subject: <subject>

<body>

No commentary before or after the draft. Draft rules (hard):
- Never mention databases, records, systems, tables, or lookups — write as a \
person who simply knows the operation.
- Never ask for information the sender's email or its thread already gives.
- Be concrete: real names, real numbers, real dates — only ones you have \
verified; do not invent or pad. If something genuinely can't be known, say \
so naturally rather than guessing.
- Match the org's voice: warm, brief, concrete. Sign as Dana.
- You have a budget of 20 tool calls."""

B_EXTRA = f"""

You ALSO have read-only SQL access to the rescue's operational database, \
built automatically from this same mailbox (it may contain errors; \
cross-check email when it matters). Schema:
{SCHEMA_BRIEF}"""


def draft(client, arm, scenario, usage):
    system = SYSTEM + (B_EXTRA if arm == "B" else "")
    tools = GMAIL_TOOLS + ([SQL_TOOL] if arm == "B" else [])
    email = (f"From: {scenario['from']}\nTo: APS Rescue shared inbox\n"
             f"Date: Sun, 12 Oct 2026 09:40:00 -0700\n"
             f"Subject: {scenario['subject']}\n\n{scenario['body']}")
    messages = [{"role": "user", "content": email}]
    log, calls = [], 0
    for _ in range(40):
        resp = None
        for attempt in range(4):
            try:
                resp = client.messages.create(
                    model=MODEL, max_tokens=MAX_TOKENS,
                    output_config={"effort": EFFORT},
                    system=[{"type": "text", "text": system,
                             "cache_control": {"type": "ephemeral"}}],
                    tools=tools, messages=messages)
                break
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(8 * (attempt + 1))
        u = resp.usage
        usage[0] += u.input_tokens
        usage[1] += u.output_tokens
        usage[2] += getattr(u, "cache_read_input_tokens", 0) or 0
        usage[3] += getattr(u, "cache_creation_input_tokens", 0) or 0
        tool_uses = [b for b in resp.content if getattr(b, "type", "") == "tool_use"]
        text = " ".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        if not tool_uses:
            return text.strip(), log, calls
        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for tu in tool_uses:
            calls += 1
            if calls > TOOL_BUDGET:
                results.append({"type": "tool_result", "tool_use_id": tu.id,
                                "content": "TOOL BUDGET EXHAUSTED — write the draft now."})
                continue
            try:
                out = run_tool(tu.name, tu.input)
            except Exception as e:
                out = f"TOOL ERROR: {type(e).__name__}: {e}"
            log.append({"call": tu.name,
                        "input": {k: str(v)[:140] for k, v in tu.input.items()}})
            results.append({"type": "tool_result", "tool_use_id": tu.id,
                            "content": str(out)})
        messages.append({"role": "user", "content": results})
    return "(no draft within round limit)", log, calls


def main():
    scenarios = json.loads((HERE / "out" / "draft_expectations.json").read_text())
    client = anthropic.Anthropic(max_retries=6)
    out_path = HERE / "out" / "draft_transcripts.jsonl"
    done = set()
    if out_path.exists():
        done = {(r["id"], r["arm"]) for r in
                (json.loads(l) for l in out_path.read_text().splitlines() if l.strip())}
    fh = open(out_path, "a")
    usage = [0, 0, 0, 0]
    for sc in scenarios:
        for arm in ("A", "B"):
            if (sc["id"], arm) in done:
                continue
            t0 = time.time()
            text, log, calls = draft(client, arm, sc, usage)
            cost = sum(x * p for x, p in zip(usage, PRICE)) / 1e6
            fh.write(json.dumps({"id": sc["id"], "arm": arm, "draft": text,
                                 "tool_log": log, "tool_calls": calls,
                                 "secs": round(time.time() - t0)},
                                ensure_ascii=False) + "\n")
            fh.flush()
            print(f"{sc['id']}/{arm}: {calls} calls, {round(time.time()-t0)}s | cum ${cost:.2f}",
                  flush=True)
    fh.close()
    print("ALL DONE")


if __name__ == "__main__":
    main()
