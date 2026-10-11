"""Voice renderer: turns universe specs into email text.

LLM messages: persona card + type guidance + facts + thread tail -> body.
Template messages (form dumps, drive shares, marketing): deterministic text.
Chronological within a thread (replies see prior rendered bodies); threads
render in parallel. Appends to out/corpus.jsonl as messages complete and
skips already-rendered ids, so it is crash-safe and resumable.

Usage: set -a && . ./.env && set +a && python3 render.py [--scenarios]
"""
import argparse
import concurrent.futures
import json
import random
import threading
import time
from pathlib import Path

import anthropic

from personas import STAFF, ORG, SHARED, VENUE, SAFEHOUSE, CLINIC, CLINIC_CITY

PRICES = {"claude-haiku-5-5": (0.10, 0.50), "claude-opus-5-5": (4.00, 20.00)}

GUIDANCE = {
    "intake_announcement": "Announce the shelter pull to the foster list: count, one-line roster, pickup window, what was done at intake, what's unknown. Energetic, grateful.",
    "placement_offer": "Offer this specific dog to this specific foster. One-line pitch, pickup logistics, easy out if timing is bad.",
    "offer_reply": "Reply to the foster-match offer. If accept=true, enthusiastic yes plus the detail noted; if false, apologetic decline with a brief reason (travel, timing).",
    "offer_close": "Short warm close: confirm pickup details, mention supplies at the den.",
    "photos_submission": "Foster sends photos of their dog: one or two lines about the photo set, one dog anecdote using the quirk.",
    "bio_submission": "Foster sends the bio questionnaire link (say 'questionnaire attached/linked' abstractly), includes the home recommendation and one behavioral observation tied to the quirk.",
    "posting_confirm": "Confirm the dog is now posted; one celebratory emoji max; optional share-the-listing ask.",
    "planning_blast": "Combined ops blast: (1) dogs listed are scheduled for spay/neuter on the vet date at the clinic — detailed instructions email comes ~4 days before, watch for it; (2) PHOTOS and BIOS due by the deadline so pups get posted; (3) photographer available (mention her no-driving quirk). Bulleted, caps for emphasis.",
    "planning_reply": "Short reply to the planning blast per the ask fact (clarify scheduling / deadline negotiation / bare ack).",
    "vet_blast": "The detailed vet-day instructions blast. State the default (den 6:30AM, volunteers drive both ways), the two opt-ins (overnight after 9PM; direct drop 7:30AM pickup 3-4PM), the midnight fasting rule in caps, reply-ASAP if opting in. Bulleted. Reassuring close.",
    "vet_optin": "Foster replies choosing their variant; include the extra item if given (describe any health thing observationally, never a diagnosis).",
    "vet_confirm": "Confirm the foster's variant. If crate_protocol: labeled crate, pee pads, NO food/water inside, last potty loop, where to leave it. If direct_tips: leave phone number (they finish early), collect cone + pain meds. Thank them warmly.",
    "event_blast": "Event RSVP blast: your foster is on the list for the event (date, venue, drop-off/pickup times); reply to confirm; extras welcome in reply; disregard-if-adopted clause.",
    "rsvp": "One-to-two-line RSVP naming the dog(s) per the flavor fact.",
    "forgot_forward": "Apologetic personal forward: forgot to add you to the event email that just went out for your dog; restate the gist in one line.",
    "adoption_heads_up": "Tell the foster their dog has an adoption appointment: who (first name), when, where, what to bring. Excited but acknowledges the bittersweet.",
    "adoption_reply": "Foster's reply per the tone fact.",
    "application_ack": "Thank the applicant; mention the foster guide while waiting for a volunteer interview; ask what time works to chat.",
    "application_detail": "Applicant shares household detail from their profile (hours alone, pets, kids, home) and asks 1-2 sincere questions.",
    "application_decline": "Two warm sentences: this round isn't the right fit (hint at the reason gently), genuine thanks, events are always open.",
    "application_interview": "Propose the specific interview slot; one logistical line.",
    "application_slot_confirm": "Confirm the slot in one or two lines.",
    "medical_concern": "Foster reports the concern exactly as described, observationally; what they've noticed, when it started; asks what to do; worried-but-level tone.",
    "medical_triage": "Acknowledge, thank them for flagging; the plan fact (vet volunteers review, circle back tomorrow morning, what to watch for). Calm.",
    "clinic_records": "Dense coordinator->clinic message: history, intake vaccines, the concern, the authorization sentence. Professional.",
    "clinic_reply": "Front desk replies warmly: flags it for the doctor, protocol note if relevant, then the small schedule-shift ask with 'if not, no worries!'. Sign as the frontdesk name + clinic team.",
    "one_liner_yes": "One line: yes, no problem.",
    "vacation_request": "Foster asks for coverage for their dog for the given dates; apologetic, flexible.",
    "swap_connect": "Connect the two fosters by first name; state who hands off to whom and when; ask feasibility; one self-aware aside.",
    "swap_accept": "Second foster accepts; proposes a handoff time; invites a quick email to coordinate.",
    "alumni_update": "Adopter update: the dog (old name, 'aka NEW_NAME now'), the milestone, then the ask. Double exclamation energy.",
    "alumni_reply": "Warm reply using the old name naturally; narrate the workaround fact honestly; sign off personally.",
    "volunteer_offer": "Short self-intro offering help per the gist.",
    "vague_interest": "One-liner from the public per the gist, no context.",
    "lost_dog": "Brief found-dog report near a landmark; asks if the rescue can take it.",
    "donation_note": "One or two lines about a small donation per the gist.",
    "catchall_reply": "Reply per the pointer fact: brief, warm, pointing them to the right place.",
}

SYSTEM = (
    "You write ONE email inside a fictional simulation of a small dog rescue's "
    f"shared inbox ({ORG}). Everything is invented; never reference real "
    "organizations, people, or places beyond the facts given.\n"
    "Rules:\n"
    "- Output ONLY the email body. No subject line, no headers, no quoted "
    "earlier messages (those are added mechanically).\n"
    "- Stay in the persona's voice. Include their sign-off style.\n"
    "- Include every fact under FACTS naturally; contradict nothing.\n"
    "- NEVER invent new named people, dogs, streets, phone numbers, or URLs. "
    "If a link is implied, write it as a plain placeholder like "
    "'(questionnaire link)'.\n"
    "- Default length 40-120 words; one-liners where the guidance says so.\n"
    "- Plain text only."
)


def persona_card(spec, people):
    p = spec.get("persona") or ""
    if p in STAFF:
        s = STAFF[p]
        return (f"{s['name']}, {s['role']}. Voice: {s['voice']}. Sign-off: "
                f"'{s['signoff']}'.\nStyle exemplars (match the register, not "
                f"the content):\n---\n" + "\n---\n".join(s["exemplars"]))
    if p == "clinic":
        return (f"Front desk at {CLINIC} in {CLINIC_CITY}. Professional-warm, "
                "protocol-aware. Signs '{name}, Crestview Team'.")
    h = people.get(p)
    if h:
        return (f"{h['name']}, a volunteer foster. Voice: {h['voice_desc']}. "
                f"First name: {h['first']}.")
    first = (spec["facts"].get("applicant_first") or spec["facts"].get("name_first")
             or spec["from"].split("<")[0].strip().split()[0])
    return (f"{spec['from'].split('<')[0].strip()}, a member of the public "
            f"writing to a dog rescue. Natural, casual. First name: {first}.")


def build_prompt(spec, tail, people):
    t = spec["facts"].get("type")
    parts = [
        "PERSONA:\n" + persona_card(spec, people),
        "EMAIL TYPE: " + (t or "message") + " — " + GUIDANCE.get(t, "Write the message the facts describe."),
        "FACTS:\n" + json.dumps({k: v for k, v in spec["facts"].items() if k != "type"},
                                 ensure_ascii=False, indent=1),
    ]
    if tail:
        parts.append("EARLIER IN THIS THREAD (most recent last):\n" + tail)
    parts.append("Write the email body now.")
    return "\n\n".join(parts)


# --- deterministic templates -------------------------------------------------

def t_application_form(spec):
    pr = spec["facts"]["profile"]
    first, last = pr["name"].split()[0], pr["name"].split()[-1]
    return (
        f"Why do you want to become a foster home for {ORG}? I'd love to help a "
        "dog decompress while it finds its family\nAbout you\n"
        f"Your first name {first}\nYour last name {last}\n"
        f"City {pr['city']}\nState CA\n"
        f"Email Address {pr['email']}\n"
        "We do much of our communication through email. How often do you check "
        "email? Often\n"
        f"Occupation {pr['occupation']}\n"
        f"Home type {pr['home']}\nHours the dog would be alone {pr['hours_alone']}\n"
        f"Children at home {pr['kids']}\nOther pets {pr['other_pets']}\n"
        f"Size/age preference {pr['pref']}\n"
        f"We are based in Redwood City where dog/supply pickups, vet transports, "
        "and our events are held. Able to transport? Yes\n"
        "Ready to bring home a foster dog within the next 5-7 days? Yes"
    )


def t_drive_share(spec):
    f = spec["facts"]
    return (f"I've shared an item with you:\n\n{f['file']}\n(document link)\n\n"
            "It's not an attachment — it's stored online. To open this item, "
            "just click the link above.")


def t_marketing(spec):
    rng = random.Random(spec["id"])
    lines = [
        rng.choice(["Spend $40+ and spoil your pet this weekend.",
                    "Members save more. Today only.",
                    "New arrivals your dog will flip for.",
                    "Stock up on fall essentials for your best friend."]),
        "", "Shop now: (store link)", "",
        "No longer want these emails? Unsubscribe: (link)",
        rng.choice(["*Exclusions apply.", "*While supplies last.", ""]),
    ]
    return "\n".join(lines)


TEMPLATES = {"application_form": t_application_form,
             "drive_share": t_drive_share,
             "marketing": t_marketing}


# --- quoting / artifacts -----------------------------------------------------

def quoted_tail(prev, spec):
    d = prev["ts"][:10]
    frm = prev["from"].split("<")[0].strip() or prev["from"]
    q = "\n".join("> " + ln for ln in prev["body"].splitlines()[:5])
    return f"\n\nOn {d}, {frm} wrote:\n{q}"


def finish_body(body, spec, prev, people):
    body = body.strip()
    h = people.get(spec.get("persona") or "")
    rng = random.Random(spec["id"])
    if h and h.get("iphone") and rng.random() < 0.8:
        body += "\n\nSent from my iPhone"
    if prev is not None:
        qp = (h or {}).get("quote_prob", 0.5)
        if rng.random() < qp:
            body += quoted_tail(prev, spec)
    return body


# --- main --------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", action="store_true",
                    help="render out/universe/scenarios.jsonl instead of specs")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0,
                    help="render only the first N threads (smoke test)")
    args = ap.parse_args()

    src = Path("out/universe/scenarios.jsonl" if args.scenarios else "out/universe/specs.jsonl")
    out_path = Path("out/scenario_corpus.jsonl" if args.scenarios else "out/corpus.jsonl")
    specs = [json.loads(l) for l in src.read_text().splitlines() if l.strip()]
    gt = json.loads(Path("out/universe/ground_truth.json").read_text())
    people = {h["id"]: h for h in gt["households"]}

    done = set()
    if out_path.exists():
        done = {json.loads(l)["id"] for l in out_path.read_text().splitlines() if l.strip()}
    todo_threads = {}
    for s in specs:
        todo_threads.setdefault(s["thread"], []).append(s)
    for v in todo_threads.values():
        v.sort(key=lambda s: s["ts"])

    client = anthropic.Anthropic(max_retries=6)
    lock = threading.Lock()
    fh = open(out_path, "a")
    usage = {}
    n_done = [len(done)]

    def render_llm(spec, tail):
        r = spec["renderer"] or {"model": "claude-haiku-5-5", "effort": "medium"}
        last = None
        for attempt in range(3):
            try:
                resp = client.messages.create(
                    model=r["model"], max_tokens=2048,
                    output_config={"effort": r["effort"]},
                    system=SYSTEM,
                    messages=[{"role": "user", "content": build_prompt(spec, tail, people)}],
                )
                text = "".join(b.text for b in resp.content
                               if getattr(b, "type", "text") == "text").strip()
                u = usage.setdefault(r["model"], [0, 0])
                u[0] += resp.usage.input_tokens
                u[1] += resp.usage.output_tokens
                if text:
                    return text
                last = RuntimeError("empty body")
            except Exception as e:  # transport; SDK already retried
                last = e
                time.sleep(3 * (attempt + 1))
        raise last

    # threads partially done re-render only missing ids; the quoting tail is
    # rebuilt from already-rendered rows when present
    rendered_rows = {}
    if out_path.exists():
        for l in out_path.read_text().splitlines():
            if l.strip():
                r = json.loads(l)
                rendered_rows[r["id"]] = r

    def do_thread_resumable(thread_specs):
        prev = None
        for spec in thread_specs:
            if spec["id"] in done:
                prev = rendered_rows.get(spec["id"], prev)
                continue
            tail = f"From {prev['from']}:\n{prev['body'][:450]}" if prev else ""
            if spec["kind"] == "template":
                body = TEMPLATES[spec["facts"]["template"]](spec)
            else:
                body = render_llm(spec, tail)
                body = finish_body(body, spec, prev, people)
            row = dict(spec)
            row["body"] = body
            with lock:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                fh.flush()
                n_done[0] += 1
                if n_done[0] % 25 == 0:
                    print(f"rendered {n_done[0]}/{len(specs)}", flush=True)
            prev = row

    groups = sorted(todo_threads.values(), key=lambda v: v[0]["ts"])
    if args.limit:
        groups = groups[:args.limit]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        list(ex.map(do_thread_resumable, groups))
    fh.close()

    cost = sum(u[0] * PRICES[m][0] / 1e6 + u[1] * PRICES[m][1] / 1e6
               for m, u in usage.items())
    print(f"DONE: {n_done[0]}/{len(specs)} rendered -> {out_path}")
    for m, u in usage.items():
        print(f"  {m}: in {u[0]:,} out {u[1]:,}")
    print(f"  render cost this run: ${cost:.2f}")


if __name__ == "__main__":
    main()
