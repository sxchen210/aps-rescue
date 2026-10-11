"""Schema-discovery harness: a strong model explores the live inbox through
four tools and emits schema + extraction instructions + notes.

Blindness by construction: the model sees ONLY what these tools return.
Artifacts land in discovery/ (schema.json, instructions.md,
DISCOVERY_NOTES.md); the full tool transcript goes to discovery_log.jsonl.

Usage: set -a && . ./.env && set +a && python3 discovery.py
"""
import json
import sys
import time
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root
import gmail_io

HERE = Path(__file__).resolve().parent
MODEL = "claude-fable-5"
EFFORT = "high"
MAX_TOKENS = 16000
MAX_ROUNDS = 120
BUDGET_USD = 30.0
PRICE_IN, PRICE_OUT, PRICE_CREAD, PRICE_CWRITE = 10.0, 50.0, 1.0, 20.0  # proxy $/M

ENVELOPE = """{
  "ops": [
    {"table": "<table name>",
     "match": { <the table's canonical key fields and values> },
     "set": { <field>: <value>, ... },
     "note": "<OPTIONAL, one short line max>"}
  ],
  "catchall": {"tag": "<short-slug>"}   // only when the email fits no workflow
}"""

MISSION = f"""You are the onboarding agent for a product that turns a busy \
shared mailbox into self-maintaining structured tables. You have just been \
connected to a mailbox you know nothing about. Your job, in one session:

1. EXPLORE the mailbox through your tools until you genuinely understand its \
recurring workflows. You may fetch as much as you need, over as many rounds \
as you need — this mailbox is small enough to read in full, and you should \
err heavily toward reading more. Read whole threads, not just subjects. \
Hunt for: recurring operational workflows, entity lifecycles, who the \
staff/participants are, which emails are noise, and hard cases (one email \
carrying two workflows, corrections, returns/reversals, machine-generated \
mail).

2. DESIGN the smallest schema that captures the mailbox's operational state \
— the facts a staffer would otherwise dig through old threads to find. \
Requirements for schema.json (a single JSON object):
   - "tables": each with "description", "canonical_keys" (the field(s) that \
identify a row; values as they appear in email, the system normalizes), \
"columns" (name -> {{"type", "description", and for enums "values"}}), and \
lifecycle/status enums wherever a thing moves through stages.
   - Prefer EXPLICIT DATED FIELDS (e.g. an appointment date, an event date, \
a deadline) over vague status text wherever emails state dates.
   - "catchall_tags": a short taxonomy of slugs for mail that fits no \
workflow.
   - Keep it small: the fewest tables that cover what recurs. Provenance \
(source email id, updated-at) is stamped by the system automatically — do \
not include such columns.

3. WRITE instructions.md: the complete extraction playbook for a SMALL, \
FAST model. That model will receive ONLY your instructions plus ONE email \
(headers, body, and the earlier messages of its thread) per call — no \
database access, no memory, no conversation. Your instructions must make it \
emit EXACTLY this JSON envelope and nothing else — no prose outside it:

{ENVELOPE}

Hard rules your instructions must state and enforce:
   - Output is the envelope ONLY. The optional "note" is at most one short \
line; never write explanations outside the JSON.
   - "match" must always carry the table's canonical key fields.
   - DATED-FIELDS RULE: when the email states a date for a fact, extract \
that stated date into the dated field — NEVER substitute the email's own \
sent date. Emails routinely announce future events and reference past ones.
   - Omit what the email does not state — never guess or fill defaults. \
Setting only one field is fine. Emitting zero ops with a catchall tag is \
the correct output for noise.
   - Whether an op creates a new row or updates an existing one is decided \
by the system via canonical-key lookup — the extractor never decides this.
   - Include 4-6 worked examples in the instructions: typical emails of \
different workflows (write the example emails yourself, modeled on what you \
saw) each with the exact envelope the extractor should emit — including one \
multi-workflow email, one pure-noise email, and one correction/update.

4. WRITE DISCOVERY_NOTES.md: the workflows you found, how the mailbox \
operates, and per-table evidence — thread ids you actually read that \
justify each table and its lifecycle.

When — and only when — you are confident, call submit_artifacts ONCE with \
all three artifacts. Take your time; thoroughness beats speed."""

TOOLS = [
    {"name": "inbox_stats", "description": "Mailbox overview: address, total message and thread counts.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "list_threads",
     "description": "Paginated thread index, newest first. ~25 threads per page: id, message count, latest date, first subject, first sender. Pass page=1,2,3… until empty.",
     "input_schema": {"type": "object", "properties": {"page": {"type": "integer", "minimum": 1}},
                      "required": ["page"]}},
    {"name": "get_thread",
     "description": "Full text of one thread: every message with headers and body, oldest first.",
     "input_schema": {"type": "object", "properties": {"thread_id": {"type": "string"}},
                      "required": ["thread_id"]}},
    {"name": "search",
     "description": "Gmail search over the mailbox (standard Gmail query syntax). Returns matching threads in the same shape as list_threads.",
     "input_schema": {"type": "object", "properties": {"query": {"type": "string"},
                                                        "limit": {"type": "integer", "minimum": 1, "maximum": 40}},
                      "required": ["query"]}},
    {"name": "submit_artifacts",
     "description": "Submit the three final artifacts. Call exactly once, when confident. schema is a JSON object (not a string).",
     "input_schema": {"type": "object",
                      "properties": {"schema": {"type": "object"},
                                     "instructions_md": {"type": "string"},
                                     "notes_md": {"type": "string"}},
                      "required": ["schema", "instructions_md", "notes_md"]}},
]

svc_cache = {}


def thread_index_page(page, page_size=25):
    pages = svc_cache.setdefault("pages", [])
    svc = gmail_io.service("aps")
    while len(pages) < page:
        token = pages[-1]["next"] if pages else None
        resp = svc.users().threads().list(userId="me", maxResults=page_size,
                                          pageToken=token).execute()
        pages.append({"threads": resp.get("threads", []),
                      "next": resp.get("nextPageToken")})
        if not resp.get("nextPageToken"):
            break
    if page > len(pages):
        return []
    out = []
    for t in pages[page - 1]["threads"]:
        meta = svc.users().threads().get(
            userId="me", id=t["id"], format="metadata",
            metadataHeaders=["Subject", "From", "Date"]).execute()
        msgs = meta.get("messages", [])
        first = msgs[0]["payload"] if msgs else {}
        hdr = {h["name"]: h["value"] for h in first.get("headers", [])}
        out.append({"thread_id": t["id"], "messages": len(msgs),
                    "latest": msgs[-1].get("internalDate") if msgs else None,
                    "subject": hdr.get("Subject", "")[:90],
                    "from": hdr.get("From", "")[:60]})
    return out


def run_tool(name, inp):
    if name == "inbox_stats":
        p = gmail_io.profile("aps")
        return {"address": p["emailAddress"], "messages_total": p["messagesTotal"],
                "threads_total": p["threadsTotal"]}
    if name == "list_threads":
        return thread_index_page(int(inp["page"]))
    if name == "get_thread":
        msgs = gmail_io.get_thread("aps", inp["thread_id"], trim_quotes=True)
        return gmail_io.render_thread(msgs, max_body=2000)
    if name == "search":
        svc = gmail_io.service("aps")
        resp = svc.users().threads().list(userId="me", q=inp["query"],
                                          maxResults=int(inp.get("limit", 15))).execute()
        out = []
        for t in resp.get("threads", []):
            meta = svc.users().threads().get(
                userId="me", id=t["id"], format="metadata",
                metadataHeaders=["Subject", "From"]).execute()
            hdr = {h["name"]: h["value"] for h in meta["messages"][0]["payload"]["headers"]}
            out.append({"thread_id": t["id"], "messages": len(meta.get("messages", [])),
                        "subject": hdr.get("Subject", "")[:90]})
        return out
    raise ValueError(f"unknown tool {name}")


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--refine", help="operator revision request; prior artifacts are fed back")
    args = ap.parse_args()

    client = anthropic.Anthropic(max_retries=6)
    if args.refine:
        prior = {f: (HERE / f).read_text() for f in
                 ("schema.json", "instructions.md", "DISCOVERY_NOTES.md")}
        opener = (
            "You previously completed discovery on this mailbox and submitted the "
            "artifacts below. The OPERATOR has reviewed them and requests a revision.\n\n"
            f"=== OPERATOR REQUEST ===\n{args.refine}\n\n"
            "=== YOUR PRIOR schema.json ===\n" + prior["schema.json"] + "\n\n"
            "=== YOUR PRIOR instructions.md ===\n" + prior["instructions.md"] + "\n\n"
            "=== YOUR PRIOR DISCOVERY_NOTES.md ===\n" + prior["DISCOVERY_NOTES.md"] + "\n\n"
            "Revise to satisfy the request. Keep everything that was right. Re-verify "
            "against the mailbox with your tools wherever the revision needs evidence, "
            "then call submit_artifacts ONCE with the COMPLETE updated artifact set "
            "(full documents, not diffs). All original contract rules still apply."
        )
        log = open(HERE / "discovery_log_refine.jsonl", "w")
        messages = [{"role": "user", "content": opener}]
    else:
        log = open(HERE / "discovery_log.jsonl", "w")
        messages = [{"role": "user", "content": "Begin. The mailbox is connected; your tools are live."}]
    usage = [0, 0, 0, 0]
    submitted = False

    for rnd in range(1, MAX_ROUNDS + 1):
        # rolling cache breakpoint: mark only the newest user message
        for m in messages:
            if isinstance(m["content"], list):
                for b in m["content"]:
                    if isinstance(b, dict):
                        b.pop("cache_control", None)
        last = messages[-1]
        if isinstance(last["content"], list) and last["content"]:
            last["content"][-1]["cache_control"] = {"type": "ephemeral"}

        resp = None
        for attempt in range(4):
            try:
                resp = client.messages.create(
                    model=MODEL, max_tokens=MAX_TOKENS,
                    output_config={"effort": EFFORT},
                    system=[{"type": "text", "text": MISSION,
                             "cache_control": {"type": "ephemeral"}}],
                    tools=TOOLS, messages=messages)
                break
            except Exception as e:
                if attempt == 3:
                    raise
                print(f"round {rnd}: {type(e).__name__}, retrying…", flush=True)
                time.sleep(10 * (attempt + 1))

        u = resp.usage
        usage[0] += u.input_tokens
        usage[1] += u.output_tokens
        usage[2] += getattr(u, "cache_read_input_tokens", 0) or 0
        usage[3] += getattr(u, "cache_creation_input_tokens", 0) or 0
        cost = (usage[0] * PRICE_IN + usage[1] * PRICE_OUT
                + usage[2] * PRICE_CREAD + usage[3] * PRICE_CWRITE) / 1e6

        texts = [b.text for b in resp.content if getattr(b, "type", "") == "text"]
        tool_uses = [b for b in resp.content if getattr(b, "type", "") == "tool_use"]
        log.write(json.dumps({
            "round": rnd, "stop": resp.stop_reason, "cost_usd": round(cost, 2),
            "text": " ".join(texts)[:2000],
            "tools": [{"name": b.name, "input": {k: (v[:200] if isinstance(v, str) else v)
                                                  for k, v in b.input.items()
                                                  if k in ("page", "thread_id", "query", "limit")}}
                      for b in tool_uses]}, ensure_ascii=False) + "\n")
        log.flush()
        print(f"round {rnd}: {len(tool_uses)} tool calls | ${cost:.2f} cumulative", flush=True)

        if cost > BUDGET_USD:
            print("BUDGET EXCEEDED — aborting", flush=True)
            break
        if not tool_uses:
            if resp.stop_reason == "end_turn":
                messages.append({"role": "assistant", "content": resp.content})
                messages.append({"role": "user", "content": [
                    {"type": "text",
                     "text": "Continue. When finished, call submit_artifacts."}]})
                continue
            print(f"stopping: stop_reason={resp.stop_reason}", flush=True)
            break

        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for tu in tool_uses:
            if tu.name == "submit_artifacts":
                schema = tu.input["schema"]
                (HERE / "schema.json").write_text(json.dumps(schema, indent=2, ensure_ascii=False))
                (HERE / "instructions.md").write_text(tu.input["instructions_md"])
                (HERE / "DISCOVERY_NOTES.md").write_text(tu.input["notes_md"])
                results.append({"type": "tool_result", "tool_use_id": tu.id,
                                "content": "Artifacts accepted and saved. You are done."})
                submitted = True
            else:
                try:
                    out = run_tool(tu.name, tu.input)
                    content = out if isinstance(out, str) else json.dumps(out, ensure_ascii=False)
                except Exception as e:
                    content = f"TOOL ERROR: {type(e).__name__}: {e}"
                results.append({"type": "tool_result", "tool_use_id": tu.id,
                                "content": content[:60000]})
        messages.append({"role": "user", "content": results})
        if submitted:
            break

    log.write(json.dumps({"final": True, "submitted": submitted,
                          "usage": {"in": usage[0], "out": usage[1],
                                    "cache_read": usage[2], "cache_write": usage[3]},
                          "cost_usd": round((usage[0] * PRICE_IN + usage[1] * PRICE_OUT
                                             + usage[2] * PRICE_CREAD + usage[3] * PRICE_CWRITE) / 1e6, 2)}) + "\n")
    log.close()
    print(f"DONE submitted={submitted} | in {usage[0]:,} out {usage[1]:,} "
          f"cache_read {usage[2]:,} | est ${(usage[0]*PRICE_IN+usage[1]*PRICE_OUT+usage[2]*PRICE_CREAD+usage[3]*PRICE_CWRITE)/1e6:.2f}",
          flush=True)
    sys.exit(0 if submitted else 1)


if __name__ == "__main__":
    main()
