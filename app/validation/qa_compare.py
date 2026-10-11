"""Two-arm QA comparison (read-only; no DB writes, no drafts).

Arm A — connector-style: Opus 5.5 + Gmail search/read tools (steelman).
Arm B — identical, PLUS read-only SQL against the hosted Turso DB.
Same model, same effort, same time anchor, same 25-call tool budget.

Writes out/qa_transcripts.jsonl. Usage: set -a && . ../.env && set +a &&
python3 qa_compare.py [--only q1,q5] [--arms A,B]
"""
import argparse
import json
import sys
import time
from pathlib import Path

import anthropic

HERE = Path(__file__).resolve().parent.parent  # app/
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "populate"))
import gmail_io
import db as dblib

MODEL = "claude-opus-5-5"
EFFORT = "high"
MAX_TOKENS = 12000
TOOL_BUDGET = 25
BUDGET_USD = 25.0
PRICE = (4.0, 20.0, 0.40, 5.0)  # in, out, cache_read, cache_write $/M

from tools import SCHEMA_BRIEF, GMAIL_TOOLS, SQL_TOOL, run_tool  # noqa

BASE_SYSTEM = """You are a diligent operations assistant for APS Rescue, a \
small foster-based dog rescue whose entire operation runs through one shared \
Gmail inbox. Today is Sunday, October 12, 2026.

Answer the user's question about current operations PRECISELY: name names, \
give numbers, be complete. Always state HOW you know (which emails you read \
/ what you queried). If the evidence available to you cannot fully answer \
the question, say exactly what you could not determine and why. Search \
thoroughly — try multiple phrasings, read whole threads, and cross-check \
before concluding. You have a budget of 25 tool calls; use them well."""

B_EXTRA = f"""

You ALSO have read-only SQL access to the rescue's operational database, \
which was built automatically from this same mailbox (it may contain \
errors; you may cross-check against email). Provenance columns \
(source_email_id, updated_at) show which email last set each row. Schema:
{SCHEMA_BRIEF}"""

def ask(client, arm, question, usage):
    system = BASE_SYSTEM + (B_EXTRA if arm == "B" else "")
    tools = GMAIL_TOOLS + ([SQL_TOOL] if arm == "B" else [])
    messages = [{"role": "user", "content": question}]
    log, calls = [], 0
    for rnd in range(40):
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
                                "content": "TOOL BUDGET EXHAUSTED — answer now with what you have."})
                log.append({"call": f"{tu.name} (budget exhausted)"})
                continue
            try:
                out = run_tool(tu.name, tu.input)
            except Exception as e:
                out = f"TOOL ERROR: {type(e).__name__}: {e}"
            log.append({"call": tu.name,
                        "input": {k: str(v)[:160] for k, v in tu.input.items()},
                        "result_head": str(out)[:200]})
            results.append({"type": "tool_result", "tool_use_id": tu.id,
                            "content": str(out)})
        messages.append({"role": "user", "content": results})
    return "(no final answer within round limit)", log, calls


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--arms", default="A,B")
    args = ap.parse_args()
    qs = json.loads((HERE / "out" / "qa_expectations.json").read_text())
    if args.only:
        keep = set(args.only.split(","))
        qs = [q for q in qs if q["id"] in keep]
    arms = args.arms.split(",")

    client = anthropic.Anthropic(max_retries=6)
    out_path = HERE / "out" / "qa_transcripts.jsonl"
    done = set()
    if out_path.exists():
        done = {(r["qid"], r["arm"]) for r in
                (json.loads(l) for l in out_path.read_text().splitlines() if l.strip())}
    fh = open(out_path, "a")
    usage = [0, 0, 0, 0]
    for q in qs:
        for arm in arms:
            if (q["id"], arm) in done:
                continue
            t0 = time.time()
            answer, log, calls = ask(client, arm, q["question"], usage)
            cost = sum(x * p for x, p in zip(usage, PRICE)) / 1e6
            fh.write(json.dumps({"qid": q["id"], "arm": arm, "question": q["question"],
                                 "answer": answer, "tool_log": log, "tool_calls": calls,
                                 "secs": round(time.time() - t0)}, ensure_ascii=False) + "\n")
            fh.flush()
            print(f"{q['id']}/{arm}: {calls} calls, {round(time.time()-t0)}s | cum ${cost:.2f}",
                  flush=True)
            if cost > BUDGET_USD:
                print("budget guard tripped")
                return
    fh.close()
    print("ALL DONE")


if __name__ == "__main__":
    main()
