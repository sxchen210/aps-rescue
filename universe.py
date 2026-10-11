"""APS Rescue universe simulator.

Generates a causally-consistent 6-week world (dogs, fosters, events, vet days,
applications) and derives every email from its event stream. Output:

  out/universe/specs.jsonl        one spec per seed email (chronological)
  out/universe/scenarios.jsonl    held-out post-window specs for the live demo
  out/universe/ground_truth.json  true state: full timelines for verification
  out/universe/stats printed to stdout

Specs carry facts + persona + renderer; render.py turns them into text.
The LLM never decides what exists — it only voices what a spec dictates.
"""
import json
import random
import datetime as dt
from pathlib import Path

from personas import (ORG, SHARED, SHARED_DISPLAY, CITY, VENUE, SAFEHOUSE,
                      CLINIC, CLINIC_CITY, CLINIC_FRONTDESK, SHELTER,
                      PHOTOGRAPHER, STAFF, FIRST, LAST, DOG_NAMES,
                      FOSTER_VOICES, RENDERER_MIX, FREEMAIL)

SEED = 20261010
rng = random.Random(SEED)
PT = dt.timezone(dt.timedelta(hours=-7))

START = dt.datetime(2026, 8, 31, 6, 0, tzinfo=PT)
END = dt.datetime(2026, 10, 9, 18, 0, tzinfo=PT)
EVENT_DAYS = [dt.date(2026, 9, 5), dt.date(2026, 9, 19), dt.date(2026, 10, 3)]
NEXT_EVENT = dt.date(2026, 10, 17)                    # held-out
VET_DAYS = [dt.date(2026, 9, 9), dt.date(2026, 9, 23), dt.date(2026, 10, 7)]
NEXT_VET = dt.date(2026, 10, 21)                      # held-out
INTAKE_DAYS = [dt.date(2026, 9, 3), dt.date(2026, 9, 10), dt.date(2026, 9, 17),
               dt.date(2026, 9, 24), dt.date(2026, 10, 1), dt.date(2026, 10, 8)]
INTAKE_SIZES = [11, 12, 10, 13, 11, 12]

CLINIC_ADDR = f"{CLINIC}, 2418 Foothill Stage Rd, {CLINIC_CITY}, CA 94550"
CLINIC_FROM = f"{CLINIC} <frontdesk.crestviewvet@gmail.com>"


def ts_at(date, hour, minute=None):
    return dt.datetime(date.year, date.month, date.day, hour,
                       minute if minute is not None else rng.randrange(60),
                       rng.randrange(60), tzinfo=PT)


def jitter_reply(ts, max_hours=30, min_minutes=9):
    delta = dt.timedelta(minutes=min_minutes + rng.random() ** 2 * max_hours * 60)
    t = ts + delta
    if 0 <= t.hour < 7:  # nobody emails at 4am; push to morning
        t = t.replace(hour=rng.randrange(7, 10))
    return t


# --- entities -----------------------------------------------------------

def pick_renderer():
    r = rng.random()
    for (me, w) in RENDERER_MIX:
        if r < w:
            return {"model": me[0], "effort": me[1]}
        r -= w
    return {"model": RENDERER_MIX[0][0][0], "effort": RENDERER_MIX[0][0][1]}


def make_households(n=200):
    names, used = [], set()
    while len(names) < n:
        nm = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
        if nm not in used:
            used.add(nm)
            names.append(nm)
    out = []
    for i, nm in enumerate(names):
        first, last = nm.split()
        email = f"{first.lower()}.{last.lower()}{rng.choice(['','',str(rng.randrange(1,99))])}@{rng.choice(FREEMAIL)}"
        voice = rng.choices(FOSTER_VOICES, weights=[v["weight"] for v in FOSTER_VOICES])[0]
        out.append({
            "id": f"hh{i:03d}", "name": nm, "first": first, "email": email,
            "voice": voice["key"], "voice_desc": voice["desc"],
            "iphone": voice["iphone"] and rng.random() < 0.8,
            "quote_prob": voice["quote_prob"],
            "renderer": pick_renderer(),
            "prefs": {
                "size": rng.choice(["small", "small", "medium", "medium", "medium", "large", "any"]),
                "puppies_ok": rng.random() < 0.45,
                "kids": rng.random() < 0.4,
                "other_dog": rng.random() < 0.3,
                "cat": rng.random() < 0.25,
            },
            "state": "available", "dogs": [], "timeline": [],
        })
    return out


DOG_QUIRKS = ["blanket burrower", "world-class leaner", "tennis-ball economist",
              "velcro shadow", "sock collector", "professional napper",
              "zoomies at 8pm sharp", "gentle food-taker", "squirrel commentator",
              "puddle connoisseur", "stair skeptic", "doorbell critic",
              "crate purist", "car-ride philosopher", "lap optimist"]


def make_dog(name, intake_date, fixed_prob=0.15):
    size = rng.choice(["small", "small", "medium", "medium", "large"])
    age = rng.choice(["puppy", "young", "young", "adult", "adult", "senior"])
    return {
        "name": name, "sex": rng.choice(["M", "F"]),
        "size": size, "age_class": age,
        "breed": rng.choice(["terrier mix", "shepherd mix", "lab mix", "chihuahua mix",
                             "hound mix", "heeler mix", "spaniel mix", "poodle mix"]),
        "fixed": rng.random() < fixed_prob,
        "quirk": rng.choice(DOG_QUIRKS),
        "ok_small_dogs": rng.random() < 0.8, "ok_kids": rng.random() < 0.75,
        "intake": str(intake_date), "status": "intake",
        "foster_history": [], "photos_date": None, "bio_date": None,
        "posted_date": None, "events": [], "vet_date": None,
        "adopted": None, "timeline": [["intake", str(intake_date)]],
    }


# --- spec emission -------------------------------------------------------

specs, scenarios = [], []
_seq = [0]


def emit(ts, frm, to, subject, *, thread, kind, persona=None, facts=None,
         reply_to=None, cc=None, labels=None, held=False, renderer=None,
         scenario=None):
    _seq[0] += 1
    sid = f"m{_seq[0]:05d}"
    spec = {
        "id": sid, "ts": ts.isoformat(), "thread": thread,
        "from": frm, "to": to if isinstance(to, list) else [to],
        "cc": cc or [], "subject": subject, "kind": kind,
        "persona": persona, "facts": facts or {}, "reply_to": reply_to,
        "labels": labels or (["SENT"] if frm == SHARED_DISPLAY or "apsrescue" in frm
                             else ["INBOX", "UNREAD"]),
        "renderer": renderer,
    }
    if held:
        spec["scenario"] = scenario
        scenarios.append(spec)
    else:
        specs.append(spec)
    return sid


def staff_from(key):
    return STAFF[key]["from"]


def hh_from(h):
    return f"{h['name']} <{h['email']}>"


def foster_renderer(h):
    return h["renderer"]


STAFF_RENDERER = {"model": "claude-opus-5-5", "effort": "medium"}
CLINIC_RENDERER = {"model": "claude-opus-5-5", "effort": "low"}


# --- world build ---------------------------------------------------------

households = make_households()
dog_names = list(DOG_NAMES)
rng.shuffle(dog_names)
dogs = {}

def take_name():
    return dog_names.pop()

def available_households():
    return [h for h in households if h["state"] == "available"]

def match_household(dog, when):
    cands = [h for h in available_households()
             if (h["prefs"]["size"] in (dog["size"], "any"))
             and (dog["age_class"] != "puppy" or h["prefs"]["puppies_ok"])
             and (not h["prefs"]["kids"] or dog["ok_kids"])]
    return rng.choice(cands) if cands else (rng.choice(available_households())
                                            if available_households() else None)

def place(dog, h, when):
    h["state"] = "fostering"
    h["dogs"].append(dog["name"])
    h["timeline"].append(["fostering", str(when), dog["name"]])
    dog["foster_history"].append({"household": h["id"], "name": h["name"],
                                  "start": str(when), "end": None})
    dog["status"] = "in_foster"
    dog["timeline"].append(["in_foster", str(when), h["name"]])

def unplace(dog, when):
    h = next(x for x in households if dog["name"] in x["dogs"])
    h["dogs"].remove(dog["name"])
    if not h["dogs"]:
        h["state"] = "available"
        h["timeline"].append(["available", str(when)])
    dog["foster_history"][-1]["end"] = str(when)
    return h


# 10 pre-existing dogs (placed before the window; already photographed/posted)
for i in range(10):
    d = make_dog(take_name(), dt.date(2026, 8, 20), fixed_prob=0.5)
    d["photos_date"] = "2026-08-24"
    d["bio_date"] = "2026-08-26"
    d["posted_date"] = "2026-08-28"
    d["status"] = "in_foster"
    dogs[d["name"]] = d
    h = match_household(d, dt.date(2026, 8, 22))
    place(d, h, dt.date(2026, 8, 22))

# --- intake batches + placement offers -----------------------------------

for bdate, bsize in zip(INTAKE_DAYS, INTAKE_SIZES):
    batch = [make_dog(take_name(), bdate) for _ in range(bsize)]
    for d in batch:
        dogs[d["name"]] = d
    roster = "; ".join(f"{d['name']} ({d['age_class']} {d['sex']} {d['breed']}, {d['size']})"
                       for d in batch)
    t = f"intake_{bdate}"
    emit(ts_at(bdate, 9), staff_from("dana"), SHARED,
         f"{ORG}_{bdate.month}/{bdate.day}_Shelter pull from {SHELTER}",
         thread=t, kind="llm", persona="dana", renderer=STAFF_RENDERER,
         facts={"type": "intake_announcement", "count": bsize, "roster": roster,
                "pickup": f"{SAFEHOUSE} between 4-7pm",
                "done_at_intake": "DHPP + Bordetella, deworming, flea treatment",
                "unknown": "no records came with them"})
    for d in batch:
        h = match_household(d, bdate)
        if h is None:
            continue
        ot = f"offer_{d['name']}"
        offer_ts = ts_at(bdate, 10 + rng.randrange(6))
        oid = emit(offer_ts, staff_from("dana"), hh_from(h),
                   f"Foster match: {d['name']}?",
                   thread=ot, kind="llm", persona="dana", renderer=STAFF_RENDERER,
                   facts={"type": "placement_offer", "dog": d["name"],
                          "pitch": f"{d['age_class']} {d['sex']} {d['breed']}, {d['size']}, {d['quirk']}",
                          "pickup": f"{SAFEHOUSE}, today 4-7pm or tomorrow morning",
                          "household_first": h["first"]})
        accept = rng.random() < 0.92
        r_ts = jitter_reply(offer_ts, 10)
        rid = emit(r_ts, hh_from(h), SHARED, f"Re: Foster match: {d['name']}?",
                   thread=ot, kind="llm", persona=h["id"], reply_to=oid,
                   renderer=foster_renderer(h),
                   facts={"type": "offer_reply", "accept": accept, "dog": d["name"],
                          "detail": rng.choice(["asks one practical question",
                                                 "asks nothing, pure enthusiasm",
                                                 "negotiates pickup to tomorrow morning",
                                                 "asks about food/supplies at the den"])})
        if accept:
            place(d, h, r_ts.date())
            if rng.random() < 0.65:
                emit(jitter_reply(r_ts, 4), staff_from("dana"), hh_from(h),
                     f"Re: Foster match: {d['name']}?", thread=ot, kind="llm",
                     persona="dana", reply_to=rid, renderer=STAFF_RENDERER,
                     facts={"type": "offer_close", "dog": d["name"],
                            "household_first": h["first"],
                            "note": "confirms pickup detail, supplies at the den"})
        else:
            d["timeline"].append(["offer_declined", str(r_ts.date()), h["name"]])
            h2 = match_household(d, bdate)
            if h2 and h2 is not h:
                ot2 = f"offer2_{d['name']}"
                o2 = emit(jitter_reply(r_ts, 6), staff_from("dana"), hh_from(h2),
                          f"Foster match: {d['name']}?", thread=ot2, kind="llm",
                          persona="dana", renderer=STAFF_RENDERER,
                          facts={"type": "placement_offer", "dog": d["name"],
                                 "pitch": f"{d['age_class']} {d['sex']} {d['breed']}, {d['size']}, {d['quirk']}",
                                 "pickup": f"{SAFEHOUSE}, tomorrow 4-7pm",
                                 "household_first": h2["first"]})
                r2 = jitter_reply(jitter_reply(r_ts, 6), 8)
                emit(r2, hh_from(h2), SHARED, f"Re: Foster match: {d['name']}?",
                     thread=ot2, kind="llm", persona=h2["id"], reply_to=o2,
                     renderer=foster_renderer(h2),
                     facts={"type": "offer_reply", "accept": True, "dog": d["name"],
                            "detail": "accepts warmly"})
                place(d, h2, r2.date())

# --- photos / bios / posting ---------------------------------------------

def household_of(dog):
    hid = dog["foster_history"][-1]["household"] if dog["foster_history"] else None
    return next((h for h in households if h["id"] == hid), None)

for d in dogs.values():
    if d["posted_date"] or not d["foster_history"]:
        continue
    h = household_of(d)
    if h is None:
        continue
    start = dt.date.fromisoformat(d["foster_history"][0]["start"])
    pdate = start + dt.timedelta(days=rng.randrange(2, 6))
    bdate2 = pdate + dt.timedelta(days=rng.randrange(1, 5))
    postdate = bdate2 + dt.timedelta(days=rng.randrange(1, 3))
    if postdate > END.date() - dt.timedelta(days=1):
        if rng.random() < 0.5:
            continue  # some dogs simply aren't posted yet — real state
        postdate = None
    t = f"bio_{d['name']}"
    pts = ts_at(pdate, 11 + rng.randrange(9))
    emit(pts, hh_from(h), SHARED, f"Photos of {d['name']}",
         thread=t, kind="llm", persona=h["id"], renderer=foster_renderer(h),
         facts={"type": "photos_submission", "dog": d["name"],
                "note": rng.choice(["park shots", "backyard set", "couch glamour shots",
                                     "walk photos, a little blurry"]),
                "quirk": d["quirk"]})
    d["photos_date"] = str(pdate)
    if rng.random() < 0.6:
        emit(jitter_reply(pts, 3), f"{h['name']} (via Google Docs) <drive-shares-dm-noreply@google.com>",
             SHARED, f"Document shared with you: \"{d['name']} photos\"",
             thread=f"share_{d['name']}p", kind="template",
             facts={"template": "drive_share", "file": f"{d['name']} photos",
                    "owner": h["name"]})
    bts = ts_at(bdate2, 10 + rng.randrange(10))
    emit(bts, hh_from(h), SHARED, f"Bio for {d['name']}",
         thread=t, kind="llm", persona=h["id"], renderer=foster_renderer(h),
         facts={"type": "bio_submission", "dog": d["name"], "quirk": d["quirk"],
                "home_rec": rng.choice(["fine with small dogs", "no cats please",
                                         "best as only dog", "great with kids",
                                         "needs a yard", "apartment-fine, low energy"])})
    d["bio_date"] = str(bdate2)
    if postdate:
        emit(ts_at(postdate, 9 + rng.randrange(8)), staff_from("june"), hh_from(h),
             f"Re: Bio for {d['name']}", thread=t, kind="llm", persona="june",
             renderer=STAFF_RENDERER,
             facts={"type": "posting_confirm", "dog": d["name"],
                    "household_first": h["first"]})
        d["posted_date"] = str(postdate)
        d["timeline"].append(["posted", str(postdate)])

# --- vet batch days -------------------------------------------------------

for vdate in VET_DAYS:
    due = [d for d in dogs.values()
           if not d["fixed"] and d["status"] == "in_foster" and d["vet_date"] is None
           and dt.date.fromisoformat(d["foster_history"][0]["start"]) <= vdate - dt.timedelta(days=5)]
    rng.shuffle(due)
    due = due[:20]
    if not due:
        continue
    plan_date = vdate - dt.timedelta(days=6)
    bio_deadline = vdate - dt.timedelta(days=2)
    pt_ = ts_at(plan_date, 8, 45)
    plan_thread = f"plan_{vdate}"
    emit(pt_, staff_from("dana"), SHARED,
         "Planning ahead: spay/neuter and getting your pups posted!",
         thread=plan_thread, kind="llm", persona="dana", renderer=STAFF_RENDERER,
         facts={"type": "planning_blast", "vet_date": str(vdate), "clinic": CLINIC,
                "clinic_city": CLINIC_CITY,
                "bio_deadline": bio_deadline.strftime("%A %-m/%-d"),
                "photographer": PHOTOGRAPHER,
                "dogs": ", ".join(d["name"] for d in due)})
    for d in rng.sample(due, k=min(6, len(due))):
        h = household_of(d)
        if not h or rng.random() < 0.5:
            continue
        emit(jitter_reply(pt_, 26), hh_from(h), SHARED,
             "Re: Planning ahead: spay/neuter and getting your pups posted!",
             thread=plan_thread, kind="llm", persona=h["id"], reply_to=None,
             renderer=foster_renderer(h),
             facts={"type": "planning_reply", "dog": d["name"],
                    "ask": rng.choice(["confirm both dogs scheduled" if len(h["dogs"]) > 1
                                        else "confirm dog is scheduled",
                                        "photos this weekend okay?",
                                        "content-free ack"])})
    detail_date = vdate - dt.timedelta(days=3)
    dts = ts_at(detail_date, 9, 10)
    vt = f"vet_{vdate}"
    subj = f"{ORG}_{vdate.month}/{vdate.day} Wednesday_{CLINIC_CITY}_Spay/Neuter Appts"
    emit(dts, staff_from("priya"), SHARED, subj,
         thread=vt, kind="llm", persona="priya", renderer=STAFF_RENDERER,
         facts={"type": "vet_blast", "vet_date": str(vdate), "clinic": CLINIC_ADDR,
                "default": "drop off AND pick up at the den at 6:30AM — volunteers drive both ways",
                "opt_overnight": "drop the night before AFTER 9PM, dog sleeps at the den",
                "opt_direct": f"drive to {CLINIC_CITY} yourself: drop 7:30AM, pickup 3-4PM",
                "fasting": "all food and water STOPS at midnight",
                "dogs": ", ".join(d["name"] for d in due)})
    for d in due:
        h = household_of(d)
        if h is None:
            continue
        d["vet_date"] = str(vdate)
        d["fixed"] = True
        d["timeline"].append(["spay_neuter", str(vdate)])
        variant = rng.choices(["base", "overnight", "direct"], weights=[.5, .28, .22])[0]
        d["vet_variant"] = variant
        if variant == "base" and rng.random() < 0.45:
            continue  # silent default-takers
        r1ts = jitter_reply(dts, 30)
        r1 = emit(r1ts, hh_from(h), SHARED, f"Re: {subj}", thread=vt,
                  kind="llm", persona=h["id"], renderer=foster_renderer(h),
                  facts={"type": "vet_optin", "dog": d["name"], "variant": variant,
                         "extra": rng.choice(["none", "none",
                                               "asks: since at the vet anyway, can they look at a minor thing (describe observationally)",
                                               "asks pickup-time flexibility",
                                               "question stack: cone? pain meds schedule? calming options?"])})
        emit(jitter_reply(r1ts, 8), staff_from("priya"), hh_from(h), f"Re: {subj}",
             thread=vt, kind="llm", persona="priya", reply_to=r1,
             renderer=STAFF_RENDERER,
             facts={"type": "vet_confirm", "dog": d["name"], "variant": variant,
                    "household_first": h["first"],
                    "crate_protocol": variant != "direct",
                    "direct_tips": variant == "direct"})

# --- adoption events -------------------------------------------------------

for edate in EVENT_DAYS:
    attendees = [d for d in dogs.values() if d["status"] == "in_foster"
                 and d["posted_date"] and dt.date.fromisoformat(d["posted_date"]) <= edate]
    if not attendees:
        continue
    blast_date = edate - dt.timedelta(days=4)
    bt = ts_at(blast_date, 8, 20)
    et = f"event_{edate}"
    subj = f"**Response Needed!** Save the date: {edate.strftime('%B %-d')} event at Bark & Barrel"
    emit(bt, staff_from("dana"), SHARED, subj, thread=et, kind="llm",
         persona="dana", renderer=STAFF_RENDERER,
         facts={"type": "event_blast", "date": edate.strftime("%A, %B %-d"),
                "venue": VENUE, "dropoff": "10:30-11:00am", "pickup": "3:00pm",
                "extras": "nail trims / check-something-out requests welcome in your reply; supplies at the den",
                "disregard": "if your adoption appointment before Saturday goes through, disregard"})
    responders = [d for d in attendees if rng.random() < 0.8]
    for d in responders:
        h = household_of(d)
        if h is None:
            continue
        d["events"].append(str(edate))
        emit(jitter_reply(bt, 40), hh_from(h), SHARED, f"Re: {subj}", thread=et,
             kind="llm", persona=h["id"], renderer=foster_renderer(h),
             facts={"type": "rsvp", "dogs": [x for x in h["dogs"]],
                    "flavor": rng.choice(["bare confirm", "bare confirm", "bare confirm",
                                           "confirm + nail trim ask",
                                           "confirm + check-a-thing ask",
                                           "confirm with a question about timing"])})
    # forgot-to-add forward
    missed = [d for d in attendees if d not in responders]
    if missed:
        d = missed[0]
        h = household_of(d)
        if h:
            d["events"].append(str(edate))
            emit(jitter_reply(bt, 1, 20), staff_from("dana"), hh_from(h),
                 f"Fwd: {subj}", thread=f"{et}_fwd", kind="llm", persona="dana",
                 renderer=STAFF_RENDERER,
                 facts={"type": "forgot_forward", "dog": d["name"],
                        "household_first": h["first"],
                        "original_gist": f"event {edate.strftime('%A %B %-d')} at {VENUE}, drop 10:30-11, pick up 3pm, reply to confirm"})
            emit(jitter_reply(bt, 20), hh_from(h), SHARED, f"Re: Fwd: {subj}",
                 thread=f"{et}_fwd", kind="llm", persona=h["id"],
                 renderer=foster_renderer(h),
                 facts={"type": "rsvp", "dogs": [d["name"]], "flavor": "bare confirm"})
    # adoptions following the event
    lucky = [d for d in attendees if str(edate) in [e for e in d["events"]]]
    lucky = rng.sample(lucky, k=min(len(lucky), max(3, int(len(lucky) * 0.4))))
    for d in lucky:
        h = household_of(d)
        if h is None:
            continue
        adopter = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
        a_date = edate + dt.timedelta(days=rng.randrange(2, 5))
        if a_date > END.date():
            continue
        at = f"adopt_{d['name']}"
        a1 = ts_at(a_date - dt.timedelta(days=1), 10 + rng.randrange(7))
        m1 = emit(a1, staff_from("dana"), hh_from(h),
                  f"Adoption appointment for {d['name']}!",
                  thread=at, kind="llm", persona="dana", renderer=STAFF_RENDERER,
                  facts={"type": "adoption_heads_up", "dog": d["name"],
                         "adopter_first": adopter.split()[0],
                         "when": a_date.strftime("%A %-m/%-d") + rng.choice([" 5:30pm", " 6pm", " 11am"]),
                         "where": SAFEHOUSE, "household_first": h["first"],
                         "bring": "crate stays with you; bring his things and any meds" if d["sex"] == "M"
                                  else "crate stays with you; bring her things and any meds"})
        emit(jitter_reply(a1, 12), hh_from(h), SHARED,
             f"Re: Adoption appointment for {d['name']}!", thread=at, kind="llm",
             persona=h["id"], reply_to=m1, renderer=foster_renderer(h),
             facts={"type": "adoption_reply", "dog": d["name"],
                    "tone": rng.choice(["bittersweet but thrilled", "pure joy",
                                         "logistical confirm + one question"])})
        unplace(d, a_date)
        d["status"] = "adopted"
        d["adopted"] = {"date": str(a_date), "adopter": adopter}
        d["timeline"].append(["adopted", str(a_date), adopter])

# --- applications ----------------------------------------------------------

app_count = 0
day = START.date()
applications = []
while day <= END.date():
    for _ in range(rng.choices([0, 1, 2], weights=[.35, .45, .2])[0]):
        app_count += 1
        nm = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
        first = nm.split()[0]
        email = f"{first.lower()}.{nm.split()[1].lower()}{rng.randrange(1,99)}@{rng.choice(FREEMAIL)}"
        at = f"app_{app_count:03d}"
        subj = f"Thank you for your foster application, {nm}"
        a_ts = ts_at(day, 8 + rng.randrange(13))
        occupations = ["teacher", "nurse", "software engineer", "retired", "grad student",
                       "project manager", "barista", "architect", "physical therapist"]
        profile = {
            "name": nm, "email": email, "city": rng.choice(
                ["Redwood City", "San Carlos", "Menlo Park", "Belmont", "San Mateo",
                 "Mountain View", "Sunnyvale", "Foster City"]),
            "occupation": rng.choice(occupations),
            "home": rng.choice(["house w/ yard", "apartment", "townhome", "condo"]),
            "hours_alone": rng.choice(["2-3", "4-5", "6-8", "9+"]),
            "kids": rng.choice(["none", "none", "ages 6 and 9", "age 12", "toddler"]),
            "other_pets": rng.choice(["none", "none", "one senior dog", "two cats", "one cat"]),
            "pref": rng.choice(["small only", "medium", "no puppies", "any", "low energy"]),
        }
        emit(a_ts, f"APS Foster <tom.apsrescue@gmail.com>",
             [SHARED, "info.apsrescue@gmail.com", email], subj,
             thread=at, kind="template",
             facts={"template": "application_form", "profile": profile})
        ack_ts = jitter_reply(a_ts, 20)
        ack = emit(ack_ts, staff_from("tom"), email, f"Re: {subj}", thread=at,
                   kind="llm", persona="tom", renderer=STAFF_RENDERER,
                   facts={"type": "application_ack", "applicant_first": first})
        arc = rng.choices(["proceed", "stall", "screen_out"], weights=[.38, .32, .30])[0]
        applications.append({"name": nm, "email": email, "date": str(day),
                             "profile": profile, "outcome": arc})
        if arc == "stall":
            continue
        q_ts = jitter_reply(ack_ts, 26)
        q = emit(q_ts, f"{nm} <{email}>", SHARED, f"Re: {subj}", thread=at,
                 kind="llm", persona=f"app_{app_count}", reply_to=ack,
                 renderer=pick_renderer(),
                 facts={"type": "application_detail", "profile": profile,
                        "applicant_first": first,
                        "note": "volunteers household detail and asks 1-2 honest questions"})
        if arc == "screen_out":
            emit(jitter_reply(q_ts, 22), staff_from("tom"), f"{nm} <{email}>",
                 f"Re: {subj}", thread=at, kind="llm", persona="tom", reply_to=q,
                 renderer=STAFF_RENDERER,
                 facts={"type": "application_decline", "applicant_first": first,
                        "reason_hint": profile["hours_alone"] + " hours alone" if profile["hours_alone"] in ("6-8", "9+")
                                       else "household fit"})
            applications[-1]["outcome"] = "declined"
        else:
            iv_ts = jitter_reply(q_ts, 20)
            emit(iv_ts, staff_from("tom"), f"{nm} <{email}>", f"Re: {subj}",
                 thread=at, kind="llm", persona="tom", reply_to=q,
                 renderer=STAFF_RENDERER,
                 facts={"type": "application_interview", "applicant_first": first,
                        "slot": rng.choice(["Tuesday 6pm", "Wednesday noon", "Thursday 5:30pm",
                                             "Saturday morning before the event"])})
            emit(jitter_reply(iv_ts, 10), f"{nm} <{email}>", SHARED, f"Re: {subj}",
                 thread=at, kind="llm", persona=f"app_{app_count}",
                 renderer=pick_renderer(),
                 facts={"type": "application_slot_confirm", "applicant_first": first})
            applications[-1]["outcome"] = "approved"
    day += dt.timedelta(days=1)

# --- medical concerns + clinic handoffs -------------------------------------

in_foster_dogs = [d for d in dogs.values() if d["foster_history"]]
med_dogs = rng.sample(in_foster_dogs, k=min(10, len(in_foster_dogs)))
CONCERNS = ["favoring a back leg on stairs (no limp on walks)",
            "occasional dry cough at night", "scratching one ear a lot",
            "soft stool for two days", "a small scab on the flank",
            "not finishing meals since yesterday", "sneezing fits in the morning",
            "chewing a paw", "a cloudy left eye", "sleeping way more than usual"]
for d, concern in zip(med_dogs, CONCERNS):
    h = household_of(d)
    if h is None:
        continue
    start = dt.date.fromisoformat(d["foster_history"][0]["start"]) + dt.timedelta(days=rng.randrange(3, 12))
    if start > END.date() - dt.timedelta(days=2):
        continue
    mt = f"med_{d['name']}"
    m_ts = ts_at(start, 8 + rng.randrange(12))
    m1 = emit(m_ts, hh_from(h), SHARED, f"{d['name']} - {concern.split('(')[0].strip()}",
              thread=mt, kind="llm", persona=h["id"], renderer=foster_renderer(h),
              facts={"type": "medical_concern", "dog": d["name"], "concern": concern,
                     "observational": True})
    d["timeline"].append(["medical_concern", str(start), concern])
    tri_ts = jitter_reply(m_ts, 8)
    emit(tri_ts, staff_from("dana"), hh_from(h),
         f"Re: {d['name']} - {concern.split('(')[0].strip()}", thread=mt,
         kind="llm", persona="dana", reply_to=m1, renderer=STAFF_RENDERER,
         facts={"type": "medical_triage", "dog": d["name"],
                "household_first": h["first"],
                "plan": "vet volunteers will review; circle back tomorrow morning; watch for pain/appetite changes"})
    if rng.random() < 0.35:
        c_ts = jitter_reply(tri_ts, 20)
        c1 = emit(c_ts, staff_from("dana"), CLINIC_FROM,
                  f"Records for {d['name']}", thread=f"clinic_{d['name']}",
                  kind="llm", persona="dana", renderer=STAFF_RENDERER,
                  facts={"type": "clinic_records", "dog": d["name"],
                         "history": f"{d['age_class']} {d['breed']}, pulled from {SHELTER}, no prior records",
                         "intake_done": "DHPP, Bordetella, deworming, flea treatment",
                         "concern": concern,
                         "authorize": "x-rays/bloodwork if the doctor feels warranted"})
        c2_ts = jitter_reply(c_ts, 6)
        c2 = emit(c2_ts, CLINIC_FROM, SHARED,
                  f"Re: Records for {d['name']}", thread=f"clinic_{d['name']}",
                  kind="llm", persona="clinic", reply_to=c1, renderer=CLINIC_RENDERER,
                  facts={"type": "clinic_reply", "dog": d["name"],
                         "frontdesk": CLINIC_FRONTDESK,
                         "note": "flags for the doctor; small schedule-shift ask (15 minutes)"})
        emit(jitter_reply(c2_ts, 3), staff_from("dana"), CLINIC_FROM,
             f"Re: Records for {d['name']}", thread=f"clinic_{d['name']}",
             kind="llm", persona="dana", reply_to=c2, renderer=STAFF_RENDERER,
             facts={"type": "one_liner_yes"})

# --- vacations / coverage swaps ---------------------------------------------

fostering = [h for h in households if h["state"] == "fostering"]
for h in rng.sample(fostering, k=min(8, len(fostering))):
    if not h["dogs"]:
        continue
    dog = dogs[h["dogs"][0]]
    away = START.date() + dt.timedelta(days=rng.randrange(8, 32))
    if away > END.date() - dt.timedelta(days=3):
        continue
    h2 = match_household(dog, away)
    if h2 is None or h2 is h:
        continue
    st = f"swap_{dog['name']}_{away}"
    s_ts = ts_at(away - dt.timedelta(days=rng.randrange(3, 7)), 9 + rng.randrange(10))
    s1 = emit(s_ts, hh_from(h), SHARED, f"Out of town — coverage for {dog['name']}?",
              thread=st, kind="llm", persona=h["id"], renderer=foster_renderer(h),
              facts={"type": "vacation_request", "dog": dog["name"],
                     "dates": f"{away.strftime('%-m/%-d')}-{(away + dt.timedelta(days=rng.randrange(4, 9))).strftime('%-m/%-d')}"})
    s2_ts = jitter_reply(s_ts, 10)
    s2 = emit(s2_ts, staff_from("dana"), [hh_from(h), hh_from(h2)],
              f"Re: Out of town — coverage for {dog['name']}?", thread=st,
              kind="llm", persona="dana", reply_to=s1, renderer=STAFF_RENDERER,
              facts={"type": "swap_connect", "dog": dog["name"],
                     "from_first": h["first"], "to_first": h2["first"],
                     "handoff": "swap at the den or directly between you two"})
    emit(jitter_reply(s2_ts, 14), hh_from(h2), [SHARED, hh_from(h)],
         f"Re: Out of town — coverage for {dog['name']}?", thread=st, kind="llm",
         persona=h2["id"], reply_to=s2, renderer=foster_renderer(h2),
         facts={"type": "swap_accept", "dog": dog["name"], "to_first": h2["first"],
                "coordination": "proposes a handoff time, shares a quick-email preference"})
    # state: temp transfer
    unplace(dog, away)
    place(dog, h2, away)
    h["state"] = "vacation"
    h["timeline"].append(["vacation", str(away)])

# --- alumni follow-ups -------------------------------------------------------

adopted = [d for d in dogs.values() if d["adopted"]]
NEW_NAMES = ["Biscuit", "Waffles", "Captain", "Mochi", "Peanut", "Ziggy"]
for d, newname in zip(rng.sample(adopted, k=min(5, len(adopted))), NEW_NAMES):
    a_date = dt.date.fromisoformat(d["adopted"]["date"]) + dt.timedelta(days=rng.randrange(6, 14))
    if a_date > END.date():
        continue
    at = f"alumni_{d['name']}"
    adopter = d["adopted"]["adopter"]
    aemail = f"{adopter.split()[0].lower()}.{adopter.split()[1].lower()}@{rng.choice(FREEMAIL)}"
    a1 = emit(ts_at(a_date, 10 + rng.randrange(8)), f"{adopter} <{aemail}>", SHARED,
              f"{d['name']} update!", thread=at, kind="llm",
              persona=f"alumni_{d['name']}", renderer=pick_renderer(),
              facts={"type": "alumni_update", "dog": d["name"], "new_name": newname,
                     "milestone": rng.choice(["first beach trip", "aced the first vet visit",
                                               "learned to sit", "made a dog-park friend"]),
                     "ask": rng.choice(["old listing photos", "records copy", "food recommendation"])})
    emit(jitter_reply(ts_at(a_date, 15), 8), staff_from("dana"), f"{adopter} <{aemail}>",
         f"Re: {d['name']} update!", thread=at, kind="llm", persona="dana",
         reply_to=a1, renderer=STAFF_RENDERER,
         facts={"type": "alumni_reply", "dog": d["name"], "new_name": newname,
                "workaround": "files too large for the shared mailbox; will send from personal account"})

# --- catchall ---------------------------------------------------------------

BRANDS = ["PawPals Warehouse", "Furry & Co.", "The Biscuit Barn", "TailMart",
          "Happy Hound Supply"]
day = START.date()
vol_count = 0
while day <= END.date():
    if rng.random() < 0.3:
        emit(ts_at(day, 6 + rng.randrange(3)),
             f"{rng.choice(BRANDS)} <promo@{rng.choice(BRANDS).lower().replace(' ', '').replace('&', 'and').replace('.', '')}.com>",
             SHARED, rng.choice(["🐾 Weekend deal: 20% off everything!",
                                  "Your pets deserve this 🦴",
                                  "FREE shipping ends tonight!",
                                  "New fall collection for good dogs"]),
             thread=f"mkt_{day}_{rng.randrange(99)}", kind="template",
             facts={"template": "marketing"})
    if rng.random() < 0.12:
        vol_count += 1
        nm = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
        email = f"{nm.split()[0].lower()}{rng.randrange(100,999)}@{rng.choice(FREEMAIL)}"
        vt_ = f"vol_{vol_count}"
        kinds = [("volunteer_offer", "offers weekend transport help"),
                 ("vague_interest", "asks if any small dogs are available right now"),
                 ("lost_dog", "asks about a found dog in their neighborhood"),
                 ("donation_note", "made a small donation, asks where it goes")]
        kind_key, gist = rng.choice(kinds)
        v_ts = ts_at(day, 9 + rng.randrange(11))
        v1 = emit(v_ts, f"{nm} <{email}>", SHARED,
                  {"volunteer_offer": "Volunteering?", "vague_interest": "Small dogs?",
                   "lost_dog": "Found dog near the library",
                   "donation_note": "Donation"}[kind_key],
                  thread=vt_, kind="llm", persona=f"public_{vol_count}",
                  renderer=pick_renderer(),
                  facts={"type": kind_key, "gist": gist, "name_first": nm.split()[0]})
        emit(jitter_reply(v_ts, 24), staff_from("dana"), f"{nm} <{email}>",
             "Re: " + {"volunteer_offer": "Volunteering?", "vague_interest": "Small dogs?",
                       "lost_dog": "Found dog near the library",
                       "donation_note": "Donation"}[kind_key],
             thread=vt_, kind="llm", persona="dana", reply_to=v1,
             renderer=STAFF_RENDERER,
             facts={"type": "catchall_reply", "re": kind_key,
                    "name_first": nm.split()[0],
                    "pointer": {"volunteer_offer": "warm ack, we'll reach out when a run comes up",
                                "vague_interest": "point to the website and Saturday events",
                                "lost_dog": "redirect to animal control / lost-pet groups",
                                "donation_note": "thanks; goes to vet care"}[kind_key]})
    day += dt.timedelta(days=1)

# --- held-out scenarios (post-window, for the live demo) ---------------------

sc = 0
def scen(label):
    global sc
    sc += 1
    return f"s{sc:02d}_{label}"

s_ts = dt.datetime(2026, 10, 13, 8, 30, tzinfo=PT)
label = scen("event_blast")
emit(s_ts, staff_from("dana"), SHARED,
     f"**Response Needed!** Save the date: October 17 event at Bark & Barrel",
     thread=f"event_{NEXT_EVENT}", kind="llm", persona="dana",
     renderer=STAFF_RENDERER, held=True, scenario=label,
     facts={"type": "event_blast", "date": "Saturday, October 17", "venue": VENUE,
            "dropoff": "10:30-11:00am", "pickup": "3:00pm",
            "extras": "nail trims / check-something-out requests welcome; supplies at the den",
            "disregard": "if your adoption appointment before Saturday goes through, disregard"})

remaining = [d for d in dogs.values() if d["status"] == "in_foster"][:3]
for d in remaining:
    h = household_of(d)
    if not h:
        continue
    emit(dt.datetime(2026, 10, 13, 9 + rng.randrange(6), rng.randrange(60), tzinfo=PT),
         hh_from(h), SHARED,
         "Re: **Response Needed!** Save the date: October 17 event at Bark & Barrel",
         thread=f"event_{NEXT_EVENT}", kind="llm", persona=h["id"],
         renderer=foster_renderer(h), held=True, scenario=scen("rsvp"),
         facts={"type": "rsvp", "dogs": h["dogs"], "flavor": "bare confirm"})

emit(dt.datetime(2026, 10, 15, 8, 45, tzinfo=PT), staff_from("dana"), SHARED,
     "Planning ahead: spay/neuter and getting your pups posted!",
     thread=f"plan_{NEXT_VET}", kind="llm", persona="dana",
     renderer=STAFF_RENDERER, held=True, scenario=scen("planning_blast"),
     facts={"type": "planning_blast", "vet_date": str(NEXT_VET), "clinic": CLINIC,
            "clinic_city": CLINIC_CITY, "bio_deadline": "Tuesday 10/20",
            "photographer": PHOTOGRAPHER,
            "dogs": ", ".join(d["name"] for d in dogs.values()
                              if not d["fixed"] and d["status"] == "in_foster")})

batch = [make_dog(take_name(), dt.date(2026, 10, 15)) for _ in range(6)]
for d in batch:
    d["held_out"] = True
    dogs[d["name"]] = d
emit(dt.datetime(2026, 10, 15, 9, 10, tzinfo=PT), staff_from("dana"), SHARED,
     f"{ORG}_10/15_Shelter pull from {SHELTER}",
     thread="intake_2026-10-15", kind="llm", persona="dana",
     renderer=STAFF_RENDERER, held=True, scenario=scen("intake"),
     facts={"type": "intake_announcement", "count": 6,
            "roster": "; ".join(f"{d['name']} ({d['age_class']} {d['sex']} {d['breed']}, {d['size']})" for d in batch),
            "pickup": f"{SAFEHOUSE} between 4-7pm",
            "done_at_intake": "DHPP + Bordetella, deworming, flea treatment",
            "unknown": "no records came with them"})

nm = "Harriet Lindqvist"
emit(dt.datetime(2026, 10, 12, 11, 5, tzinfo=PT),
     f"APS Foster <tom.apsrescue@gmail.com>",
     [SHARED, "info.apsrescue@gmail.com", "harriet.lindqvist7@yahoo.com"],
     f"Thank you for your foster application, {nm}", thread="app_live1",
     kind="template", held=True, scenario=scen("application"),
     facts={"template": "application_form",
            "profile": {"name": nm, "email": "harriet.lindqvist7@yahoo.com",
                        "city": "San Carlos", "occupation": "librarian",
                        "home": "house w/ yard", "hours_alone": "2-3",
                        "kids": "none", "other_pets": "one senior dog",
                        "pref": "medium"}})

d_live = [d for d in dogs.values() if d["status"] == "in_foster" and not d.get("held_out")][:1]
if d_live:
    d = d_live[0]
    h = household_of(d)
    emit(dt.datetime(2026, 10, 13, 19, 40, tzinfo=PT), hh_from(h), SHARED,
         f"{d['name']} - chewing a paw", thread=f"med_live_{d['name']}",
         kind="llm", persona=h["id"], renderer=foster_renderer(h), held=True,
         scenario=scen("medical"),
         facts={"type": "medical_concern", "dog": d["name"],
                "concern": "chewing a front paw since yesterday evening",
                "observational": True})

# --- write outputs -----------------------------------------------------------

out = Path("out/universe")
out.mkdir(parents=True, exist_ok=True)
specs.sort(key=lambda s: s["ts"])
scenarios.sort(key=lambda s: s["ts"])
(out / "specs.jsonl").write_text("\n".join(json.dumps(s, ensure_ascii=False) for s in specs))
(out / "scenarios.jsonl").write_text("\n".join(json.dumps(s, ensure_ascii=False) for s in scenarios))

gt = {
    "org": {"name": ORG, "shared": SHARED, "city": CITY, "venue": VENUE,
            "clinic": CLINIC_ADDR, "shelter": SHELTER},
    "window": {"start": START.isoformat(), "end": END.isoformat()},
    "event_days": [str(x) for x in EVENT_DAYS], "vet_days": [str(x) for x in VET_DAYS],
    "dogs": dogs, "households": households, "applications": applications,
}
(out / "ground_truth.json").write_text(json.dumps(gt, ensure_ascii=False, indent=1))

# stats
import collections
kinds = collections.Counter(s["facts"].get("type") or s["facts"].get("template") for s in specs)
llm = sum(1 for s in specs if s["kind"] == "llm")
by_model = collections.Counter((s.get("renderer") or {}).get("model") for s in specs if s["kind"] == "llm")
print(f"seed emails: {len(specs)} | llm-rendered: {llm} | template: {len(specs)-llm}")
print(f"held-out scenario emails: {len(scenarios)}")
print("renderer mix:", dict(by_model))
print("top types:", kinds.most_common(14))
status = collections.Counter(d["status"] for d in dogs.values() if not d.get("held_out"))
print("dog status at window end:", dict(status))
print("households fostering at end:", sum(1 for h in households if h['state']=='fostering'),
      "| available:", sum(1 for h in households if h['state']=='available'),
      "| vacation:", sum(1 for h in households if h['state']=='vacation'))
print("applications:", len(applications), collections.Counter(a['outcome'] for a in applications))
