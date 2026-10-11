"""Universe continuation: three simulated weeks beyond the seeded corpus.

Loads ground_truth.json as the starting world (a re-run of universe.py would
reshuffle the RNG and silently change the verified 831) and continues every
live arc under a NEW seed:

  Week 1  (Oct 10-16): full fidelity, inbound + staff outbound -> injected
          as history (Phase C). Snapshot ground truth AFTER week 1 is the
          verification target (ground_truth_v2.json).
  Weeks 2-3 (Oct 17-30): the FIRING POOL — inbound emails plus a whitelist
          of org blasts (intake/event/vet/planning). Staff 1:1 replies are
          excluded (live drafts take their place); inbound replies whose
          parent can never fire are dropped as orphans.

Outputs under out/extension/: specs_week1.jsonl, specs_pool.jsonl,
ground_truth_v2.json, stats on stdout. Spec schema matches universe.py, so
render.py renders both files unchanged. Where natural, specs carry
expected_ops for the live scorecard.
"""
import datetime as dt
import json
import random
from pathlib import Path

from personas import (ORG, SHARED, STAFF, FIRST, LAST, FOSTER_VOICES,
                      RENDERER_MIX, FREEMAIL, VENUE, SAFEHOUSE, CLINIC,
                      CLINIC_CITY, SHELTER, PHOTOGRAPHER)

HERE = Path(__file__).resolve().parent
GT = json.loads((HERE / "out" / "universe" / "ground_truth.json").read_text())

SEED = 20261012
rng = random.Random(SEED)
PT = dt.timezone(dt.timedelta(hours=-7))

WEEK1_END = dt.date(2026, 10, 16)
POOL_END = dt.date(2026, 10, 30)
INTAKES = [dt.date(2026, 10, 15), dt.date(2026, 10, 22), dt.date(2026, 10, 29)]
EVENTS = [dt.date(2026, 10, 17), dt.date(2026, 10, 31)]
VET_DAYS = [dt.date(2026, 10, 21)]
ROUNDUPS = [dt.date(2026, 10, 12)]  # stops after week 1: the tables replace it

EXTENSION_DOG_NAMES = """Breccia Chert Gneiss Loess Marl Tuff Karst Playa
Vernal Arroyo Wash Coulee Draw Swale Hollow Knoll Fell Pike Ghyll Beck
Thorn Furze Gorse Teasel Burdock Mallow Tansy Woad Flax Madder Henna
Umber Ochre Sepia Cobalt Cerulean Viridian Gale2 Sferic Lenticular Nacre""".split()
EXTENSION_DOG_NAMES = [n for n in EXTENSION_DOG_NAMES if n != "Gale2"]

dogs = GT["dogs"]
households = GT["households"]
hh_by_id = {h["id"]: h for h in households}
used_names = set(dogs)
name_pool = [n for n in EXTENSION_DOG_NAMES if n not in used_names]
rng.shuffle(name_pool)

STAFF_FROM = STAFF["dana"]["from"]  # all staff send from the shared address
STAFF_RENDERER = {"model": "claude-opus-5-5", "effort": "medium"}
DOG_QUIRKS = ["puddle inspector", "sunbeam locator", "gravel gourmet",
              "blanket architect", "squeaky-toy surgeon", "fence-line reporter",
              "slipper courier", "yawn choreographer", "leaf chaser",
              "dinner-time vocalist"]


def ts_at(date, hour, minute=None):
    return dt.datetime(date.year, date.month, date.day, hour,
                       minute if minute is not None else rng.randrange(60),
                       rng.randrange(60), tzinfo=PT)


def jitter_reply(ts, max_hours=24, min_minutes=8):
    t = ts + dt.timedelta(minutes=min_minutes + rng.random() ** 2 * max_hours * 60)
    if 0 <= t.hour < 7:
        t = t.replace(hour=rng.randrange(7, 10))
    return t


def pick_renderer():
    r = rng.random()
    for (me, w) in RENDERER_MIX:
        if r < w:
            return {"model": me[0], "effort": me[1]}
        r -= w
    return {"model": RENDERER_MIX[0][0][0], "effort": RENDERER_MIX[0][0][1]}


def hh_from(h):
    return f"{h['name']} <{h['email']}>"


specs = []
_seq = [0]


def emit(ts, frm, to, subject, *, thread, kind, persona=None, facts=None,
         reply_to=None, cc=None, renderer=None, expected_ops=None):
    _seq[0] += 1
    sid = f"x{_seq[0]:05d}"
    is_staff = frm == STAFF_FROM or SHARED in frm
    specs.append({
        "id": sid, "ts": ts.isoformat(), "thread": thread,
        "from": frm, "to": to if isinstance(to, list) else [to],
        "cc": cc or [], "subject": subject, "kind": kind,
        "persona": persona, "facts": facts or {}, "reply_to": reply_to,
        "labels": (["SENT"] + (["INBOX"] if SHARED in str(to) else [])) if is_staff
                  else ["INBOX", "UNREAD"],
        "renderer": renderer,
        "expected_ops": expected_ops,
    })
    return sid


# --- world helpers (same semantics as universe.py) -------------------------

def available_households():
    return [h for h in households if h["state"] == "available"]


def match_household(dog):
    cands = [h for h in available_households()
             if (h["prefs"]["size"] in (dog["size"], "any"))
             and (dog["age_class"] != "puppy" or h["prefs"]["puppies_ok"])]
    return rng.choice(cands) if cands else (rng.choice(available_households())
                                            if available_households() else None)


def place(dog, h, when):
    h["state"] = "fostering"
    h["dogs"].append(dog["name"])
    dog["foster_history"].append({"household": h["id"], "name": h["name"],
                                  "start": str(when), "end": None})
    dog["status"] = "in_foster"
    dog["timeline"].append(["in_foster", str(when), h["name"]])


def unplace(dog, when):
    h = next(x for x in households if dog["name"] in x["dogs"])
    h["dogs"].remove(dog["name"])
    if not h["dogs"]:
        h["state"] = "available"
    dog["foster_history"][-1]["end"] = str(when)
    return h


def household_of(dog):
    seg = dog["foster_history"][-1] if dog["foster_history"] else None
    return hh_by_id.get(seg["household"]) if seg and seg["end"] is None else None


def make_dog(name, intake_date):
    return {"name": name, "sex": rng.choice(["M", "F"]),
            "size": rng.choice(["small", "small", "medium", "medium", "large"]),
            "age_class": rng.choice(["puppy", "young", "young", "adult", "senior"]),
            "breed": rng.choice(["terrier mix", "shepherd mix", "lab mix",
                                 "chihuahua mix", "hound mix", "heeler mix",
                                 "spaniel mix", "poodle mix"]),
            "fixed": rng.random() < 0.15, "quirk": rng.choice(DOG_QUIRKS),
            "ok_small_dogs": True, "ok_kids": rng.random() < 0.75,
            "intake": str(intake_date), "status": "intake",
            "foster_history": [], "photos_date": None, "bio_date": None,
            "posted_date": None, "events": [], "vet_date": None,
            "adopted": None, "timeline": [["intake", str(intake_date)]]}


# ===========================================================================
# PRE-WEEK: resolve the Oct 7 vet day's posting backlog (the 18 waiting dogs)
# ===========================================================================

waiting = [d for d in dogs.values() if d["status"] == "in_foster"
           and not d["posted_date"] and d.get("bio_date") and d.get("photos_date")
           and d.get("fixed")]
for d in waiting:
    h = household_of(d)
    if not h:
        continue
    pdate = dt.date(2026, 10, 10) + dt.timedelta(days=rng.randrange(0, 3))
    emit(ts_at(pdate, 9 + rng.randrange(8)), STAFF_FROM, hh_from(h),
         f"Re: Bio for {d['name']}", thread=f"bio_{d['name']}", kind="llm",
         persona="june", renderer=STAFF_RENDERER,
         facts={"type": "posting_confirm", "dog": d["name"],
                "household_first": h["first"], "note": "posted right after the spay/neuter"},
         expected_ops=[{"table": "dogs", "match": {"dog_name": d["name"]},
                        "set_includes": ["posted"]}])
    d["posted_date"] = str(pdate)
    d["timeline"].append(["posted", str(pdate)])

# dogs with photos but no bio: nudge -> bio arrives
for d in list(dogs.values()):
    if d["status"] == "in_foster" and d.get("photos_date") and not d.get("bio_date"):
        h = household_of(d)
        if not h or rng.random() < 0.3:
            continue
        bdate = dt.date(2026, 10, 10) + dt.timedelta(days=rng.randrange(0, 5))
        bts = ts_at(bdate, 10 + rng.randrange(9))
        emit(bts, hh_from(h), SHARED, f"Bio for {d['name']}",
             thread=f"bio_{d['name']}", kind="llm", persona=h["id"],
             renderer=h["renderer"],
             facts={"type": "bio_submission", "dog": d["name"], "quirk": d["quirk"],
                    "home_rec": rng.choice(["great with kids", "no cats please",
                                             "apartment-fine", "needs a yard"])},
             expected_ops=[{"table": "dogs", "match": {"dog_name": d["name"]},
                            "set_includes": ["bio_received"]}])
        if rng.random() < 0.6:
            emit(jitter_reply(bts, 2), f"{h['name']} (via Google Docs) <drive-shares-dm-noreply@google.com>",
                 SHARED, f'Document shared with you: "{d['name']} bio"',
                 thread=f"xshare_{d['name']}", kind="template",
                 facts={"template": "drive_share", "file": f"{d['name']} bio",
                        "owner": h["name"]})
        d["bio_date"] = str(bdate)

# ===========================================================================
# WEEK 1 + POOL weeks: the continuing rhythm
# ===========================================================================

# -- posting roundup Oct 12 (last one; the tables replace it afterward)
ready, wait_bio, wait_fix = [], [], []
for d in dogs.values():
    if d["status"] != "in_foster" or d.get("posted_date"):
        continue
    if d.get("bio_date") and d.get("photos_date") and d.get("fixed"):
        ready.append(d["name"])
    elif d.get("photos_date") and not d.get("bio_date"):
        wait_bio.append(d["name"])
    elif d.get("bio_date") and not d.get("fixed"):
        wait_fix.append(f"{d['name']} (fix unscheduled)")
r_ts = ts_at(dt.date(2026, 10, 12), 8, 10)
r1 = emit(r_ts, STAFF_FROM, SHARED, "Posting roundup — week of 10/12",
          thread="roundup_2026-10-12", kind="llm", persona="june",
          renderer=STAFF_RENDERER,
          facts={"type": "posting_roundup",
                 "ready_to_post": ", ".join(ready[:10]) or "none",
                 "waiting_on_bio": ", ".join(wait_bio[:10]) or "none",
                 "waiting_on_fix": ", ".join(wait_fix[:10]) or "none",
                 "rule": "photos + bio AND fixed = posted"})
emit(jitter_reply(r_ts, 5), STAFF_FROM, SHARED,
     "Re: Posting roundup — week of 10/12", thread="roundup_2026-10-12",
     kind="llm", persona="dana", reply_to=r1, renderer=STAFF_RENDERER,
     facts={"type": "roundup_reply", "note": "chases two bios, thanks June"})

# -- adoption events (Oct 17 blast lands in week 1; Oct 31 blast in pool)
for edate in EVENTS:
    blast_date = edate - dt.timedelta(days=4)
    attendees = [d for d in dogs.values() if d["status"] == "in_foster"
                 and d["posted_date"] and dt.date.fromisoformat(d["posted_date"]) <= edate]
    bt = ts_at(blast_date, 8, 20)
    et = f"event_{edate}"
    subj = f"**Response Needed!** Save the date: {edate.strftime('%B %-d')} event at Bark & Barrel"
    emit(bt, STAFF_FROM, SHARED, subj, thread=et, kind="llm", persona="dana",
         renderer=STAFF_RENDERER,
         facts={"type": "event_blast", "date": edate.strftime("%A, %B %-d"),
                "venue": VENUE, "dropoff": "10:30-11:00am", "pickup": "3:00pm",
                "extras": "nail trims / check-something-out requests welcome; supplies at the den",
                "disregard": "if your adoption appointment before Saturday goes through, disregard"},
         expected_ops=[{"table": "events", "match": {"event_date": str(edate)},
                        "set_includes": ["location"]}])
    for d in attendees:
        if rng.random() > 0.75:
            continue
        h = household_of(d)
        if not h:
            continue
        d["events"].append(str(edate))
        emit(jitter_reply(bt, 44), hh_from(h), SHARED, f"Re: {subj}", thread=et,
             kind="llm", persona=h["id"], renderer=h["renderer"],
             facts={"type": "rsvp", "dogs": [x for x in h["dogs"]],
                    "flavor": rng.choice(["bare confirm", "bare confirm",
                                           "confirm + nail trim ask",
                                           "confirm with a timing question"])},
             expected_ops=[{"table": "event_rsvps",
                            "match": {"event_date": str(edate), "dog_name": d["name"]},
                            "set_includes": ["rsvp"]}])
    # adoptions after the Oct 17 event (land in pool window as alumni later)
    if edate == dt.date(2026, 10, 17):
        lucky = rng.sample(attendees, k=min(len(attendees), 6))
        for d in lucky:
            h = household_of(d)
            if not h:
                continue
            adopter = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
            a_date = edate + dt.timedelta(days=rng.randrange(2, 5))
            at = f"adopt_{d['name']}"
            a1 = ts_at(a_date - dt.timedelta(days=1), 10 + rng.randrange(7))
            m1 = emit(a1, STAFF_FROM, hh_from(h),
                      f"Adoption appointment for {d['name']}!", thread=at,
                      kind="llm", persona="dana", renderer=STAFF_RENDERER,
                      facts={"type": "adoption_heads_up", "dog": d["name"],
                             "adopter_first": adopter.split()[0],
                             "when": a_date.strftime("%A %-m/%-d") + rng.choice([" 5:30pm", " 11am"]),
                             "where": SAFEHOUSE, "household_first": h["first"],
                             "bring": "crate stays with you; bring their things and any meds"},
                      expected_ops=[{"table": "dogs", "match": {"dog_name": d["name"]},
                                     "set_includes": ["adoption_appt_date"]}])
            emit(jitter_reply(a1, 12), hh_from(h), SHARED,
                 f"Re: Adoption appointment for {d['name']}!", thread=at,
                 kind="llm", persona=h["id"], reply_to=m1, renderer=h["renderer"],
                 facts={"type": "adoption_reply", "dog": d["name"],
                        "tone": rng.choice(["bittersweet but thrilled", "pure joy"])})
            unplace(d, a_date)
            d["status"] = "adopted"
            d["adopted"] = {"date": str(a_date), "adopter": adopter}
            d["timeline"].append(["adopted", str(a_date), adopter])

# -- planning blast (Oct 15, for the Oct 21 vet day) + vet-day cycle
due = [d for d in dogs.values() if not d["fixed"] and d["status"] == "in_foster"][:18]
pt_ = ts_at(dt.date(2026, 10, 15), 8, 45)
emit(pt_, STAFF_FROM, SHARED,
     "Planning ahead: spay/neuter and getting your pups posted!",
     thread="plan_2026-10-21", kind="llm", persona="dana", renderer=STAFF_RENDERER,
     facts={"type": "planning_blast", "vet_date": "2026-10-21", "clinic": CLINIC,
            "clinic_city": CLINIC_CITY, "bio_deadline": "Tuesday 10/20",
            "photographer": PHOTOGRAPHER,
            "dogs": ", ".join(d["name"] for d in due)})
for vdate in VET_DAYS:
    dts = ts_at(vdate - dt.timedelta(days=3), 9, 10)
    vt = f"vet_{vdate}"
    subj = f"{ORG}_{vdate.month}/{vdate.day} Wednesday_{CLINIC_CITY}_Spay/Neuter Appts"
    emit(dts, STAFF_FROM, SHARED, subj, thread=vt, kind="llm", persona="priya",
         renderer=STAFF_RENDERER,
         facts={"type": "vet_blast", "vet_date": str(vdate),
                "clinic": f"{CLINIC}, 2418 Foothill Stage Rd, {CLINIC_CITY}, CA 94550",
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
        if variant == "base" and rng.random() < 0.45:
            continue
        r1ts = jitter_reply(dts, 30)
        emit(r1ts, hh_from(h), SHARED, f"Re: {subj}", thread=vt, kind="llm",
             persona=h["id"], renderer=h["renderer"],
             facts={"type": "vet_optin", "dog": d["name"], "variant": variant,
                    "extra": rng.choice(["none", "none",
                                          "asks: can they glance at a small thing while there (describe observationally)",
                                          "question stack: cone? meds schedule?"])},
             expected_ops=[{"table": "dogs", "match": {"dog_name": d["name"]},
                            "set_includes": ["transport_option"]}])

# -- intakes (Oct 15 uses the six reserved held-out dogs + new names)
for i, bdate in enumerate(INTAKES):
    if i == 0:
        batch = [dogs[n] for n, d in dogs.items() if d.get("held_out")]
        for d in batch:
            d.pop("held_out", None)
            d["intake"] = str(bdate)
            d["timeline"] = [["intake", str(bdate)]]
        while len(batch) < 11 and name_pool:
            d = make_dog(name_pool.pop(), bdate)
            dogs[d["name"]] = d
            batch.append(d)
    else:
        batch = []
        while len(batch) < rng.randrange(10, 13) and name_pool:
            d = make_dog(name_pool.pop(), bdate)
            dogs[d["name"]] = d
            batch.append(d)
    roster = "; ".join(f"{d['name']} ({d['age_class']} {d['sex']} {d['breed']}, {d['size']})"
                       for d in batch)
    t = f"intake_{bdate}"
    emit(ts_at(bdate, 9), STAFF_FROM, SHARED,
         f"{ORG}_{bdate.month}/{bdate.day}_Shelter pull from {SHELTER}",
         thread=t, kind="llm", persona="dana", renderer=STAFF_RENDERER,
         facts={"type": "intake_announcement", "count": len(batch), "roster": roster,
                "pickup": f"{SAFEHOUSE} between 4-7pm",
                "done_at_intake": "DHPP + Bordetella, deworming, flea treatment",
                "unknown": "no records came with them"},
         expected_ops=[{"table": "dogs", "match": {"dog_name": d["name"]},
                        "set_includes": ["intake_date"]} for d in batch])
    for d in batch:
        h = match_household(d)
        if h is None:
            continue
        ot = f"offer_{d['name']}"
        offer_ts = ts_at(bdate, 10 + rng.randrange(6))
        oid = emit(offer_ts, STAFF_FROM, hh_from(h), f"Foster match: {d['name']}?",
                   thread=ot, kind="llm", persona="dana", renderer=STAFF_RENDERER,
                   facts={"type": "placement_offer", "dog": d["name"],
                          "pitch": f"{d['age_class']} {d['sex']} {d['breed']}, {d['size']}, {d['quirk']}",
                          "pickup": f"{SAFEHOUSE}, today 4-7pm or tomorrow morning",
                          "household_first": h["first"]})
        r_ts2 = jitter_reply(offer_ts, 10)
        emit(r_ts2, hh_from(h), SHARED, f"Re: Foster match: {d['name']}?",
             thread=ot, kind="llm", persona=h["id"], reply_to=oid,
             renderer=h["renderer"],
             facts={"type": "offer_reply", "accept": True, "dog": d["name"],
                    "detail": rng.choice(["asks one practical question",
                                           "pure enthusiasm",
                                           "asks about supplies at the den"])},
             expected_ops=[{"table": "dogs", "match": {"dog_name": d["name"]},
                            "set_includes": ["foster_name"]}])
        place(d, h, r_ts2.date())
        if rng.random() < 0.6:
            emit(jitter_reply(r_ts2, 5), STAFF_FROM, hh_from(h),
                 f"Re: Foster match: {d['name']}?", thread=ot, kind="llm",
                 persona="dana", renderer=STAFF_RENDERER,
                 facts={"type": "offer_close", "dog": d["name"],
                        "household_first": h["first"],
                        "note": "confirms pickup, supplies at the den"})
        # photos/bio trickle over the following week
        pdate = r_ts2.date() + dt.timedelta(days=rng.randrange(2, 6))
        if pdate <= POOL_END:
            pts = ts_at(pdate, 11 + rng.randrange(8))
            emit(pts, hh_from(h), SHARED, f"Photos of {d['name']}",
                 thread=f"bio_{d['name']}", kind="llm", persona=h["id"],
                 renderer=h["renderer"],
                 facts={"type": "photos_submission", "dog": d["name"],
                        "note": rng.choice(["park shots", "couch set", "yard photos"]),
                        "quirk": d["quirk"]},
                 expected_ops=[{"table": "dogs", "match": {"dog_name": d["name"]},
                                "set_includes": ["photos_received"]}])
            d["photos_date"] = str(pdate)
            if rng.random() < 0.5:
                emit(jitter_reply(pts, 2),
                     f"{h['name']} (via Google Docs) <drive-shares-dm-noreply@google.com>",
                     SHARED, f'Document shared with you: "{d['name']} photos"',
                     thread=f"xshare_{d['name']}p", kind="template",
                     facts={"template": "drive_share", "file": f"{d['name']} photos",
                            "owner": h["name"]})

# -- applications (~5/week through pool end)
day = dt.date(2026, 10, 10)
app_n = 0
while day <= POOL_END:
    for _ in range(rng.choices([0, 1, 2], weights=[.4, .45, .15])[0]):
        app_n += 1
        nm = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
        first, last = nm.split()[0], nm.split()[-1]
        email = f"{first.lower()}.{last.lower()}{rng.randrange(1, 99)}@{rng.choice(FREEMAIL)}"
        at = f"xapp_{app_n:03d}"
        subj = f"Thank you for your foster application, {nm}"
        a_ts = ts_at(day, 8 + rng.randrange(12))
        profile = {"name": nm, "email": email,
                   "city": rng.choice(["Redwood City", "San Carlos", "Belmont", "San Mateo"]),
                   "occupation": rng.choice(["teacher", "nurse", "engineer", "retired", "barista"]),
                   "home": rng.choice(["house w/ yard", "apartment", "townhome"]),
                   "hours_alone": rng.choice(["2-3", "4-5", "6-8"]),
                   "kids": rng.choice(["none", "none", "age 10"]),
                   "other_pets": rng.choice(["none", "one cat", "one senior dog"]),
                   "pref": rng.choice(["small only", "medium", "any", "no puppies"])}
        emit(a_ts, f"{ORG} Applications <{SHARED}>", [SHARED, email], subj,
             thread=at, kind="template",
             facts={"template": "application_form", "profile": profile},
             expected_ops=[{"table": "foster_applications",
                            "match": {"applicant_name": nm},
                            "set_includes": ["email"]}])
        ack_ts = jitter_reply(a_ts, 20)
        ack = emit(ack_ts, STAFF_FROM, email, f"Re: {subj}", thread=at,
                   kind="llm", persona="tom", renderer=STAFF_RENDERER,
                   facts={"type": "application_ack", "applicant_first": first})
        if rng.random() < 0.6:
            emit(jitter_reply(ack_ts, 26), f"{nm} <{email}>", SHARED, f"Re: {subj}",
                 thread=at, kind="llm", persona=f"xapp_{app_n}", reply_to=ack,
                 renderer=pick_renderer(),
                 facts={"type": "application_detail", "profile": profile,
                        "applicant_first": first,
                        "note": "volunteers household detail, asks 1-2 questions"})
        GT["applications"].append({"name": nm, "email": email, "date": str(day),
                                   "profile": profile, "outcome": "received"})
    day += dt.timedelta(days=1)

# -- medical concerns (2 in week 1, 2 in pool)
CONCERNS = ["licking a front paw raw-ish, no limp", "one droopy ear since yesterday",
            "sneezing fits after the park", "skipping breakfast two days running"]
cands = [d for d in dogs.values() if d["status"] == "in_foster" and d["foster_history"]]
for i, concern in enumerate(CONCERNS):
    d = rng.choice(cands)
    h = household_of(d)
    if not h:
        continue
    mdate = dt.date(2026, 10, 11 + i * 4)
    mt = f"xmed_{d['name']}"
    m_ts = ts_at(mdate, 8 + rng.randrange(11))
    m1 = emit(m_ts, hh_from(h), SHARED, f"{d['name']} - {concern.split(',')[0]}",
              thread=mt, kind="llm", persona=h["id"], renderer=h["renderer"],
              facts={"type": "medical_concern", "dog": d["name"], "concern": concern,
                     "observational": True},
              expected_ops=[{"table": "dogs", "match": {"dog_name": d["name"]},
                             "set_includes": ["health_note"]}])
    if mdate <= WEEK1_END:
        emit(jitter_reply(m_ts, 8), STAFF_FROM, hh_from(h),
             f"Re: {d['name']} - {concern.split(',')[0]}", thread=mt, kind="llm",
             persona="dana", reply_to=m1, renderer=STAFF_RENDERER,
             facts={"type": "medical_triage", "dog": d["name"],
                    "household_first": h["first"],
                    "plan": "vet volunteers review; circle back tomorrow; watch appetite/pain"})

# -- one vacation + one return in week 1 (fresh roster churn)
fostering = [h for h in households if h["state"] == "fostering" and h["dogs"]]
hv = rng.choice(fostering)
dogv = dogs[hv["dogs"][0]]
away = dt.date(2026, 10, 14)
h2 = match_household(dogv)
if h2 and h2 is not hv:
    st = f"xswap_{dogv['name']}"
    s_ts = ts_at(dt.date(2026, 10, 11), 9 + rng.randrange(9))
    s1 = emit(s_ts, hh_from(hv), SHARED, f"Out of town — coverage for {dogv['name']}?",
              thread=st, kind="llm", persona=hv["id"], renderer=hv["renderer"],
              facts={"type": "vacation_request", "dog": dogv["name"],
                     "dates": "10/14-10/20"},
              expected_ops=[{"table": "fosters", "match": {"foster_name": hv["name"]},
                             "set_includes": ["away_start_date"]}])
    s2_ts = jitter_reply(s_ts, 10)
    s2 = emit(s2_ts, STAFF_FROM, [hh_from(hv), hh_from(h2)],
              f"Re: Out of town — coverage for {dogv['name']}?", thread=st,
              kind="llm", persona="dana", reply_to=s1, renderer=STAFF_RENDERER,
              facts={"type": "swap_connect", "dog": dogv["name"],
                     "from_first": hv["first"], "to_first": h2["first"],
                     "handoff": "swap at the den or directly"})
    emit(jitter_reply(s2_ts, 12), hh_from(h2), [SHARED, hh_from(hv)],
         f"Re: Out of town — coverage for {dogv['name']}?", thread=st, kind="llm",
         persona=h2["id"], reply_to=s2, renderer=h2["renderer"],
         facts={"type": "swap_accept", "dog": dogv["name"], "to_first": h2["first"],
                "coordination": "proposes a handoff time"})
    unplace(dogv, away)
    place(dogv, h2, away)
    hv["state"] = "vacation"
    hv["timeline"].append(["vacation", str(away)])

hr_cands = [h for h in households if h["state"] == "fostering" and h["dogs"] and h is not h2]
hr = rng.choice(hr_cands)
dret = dogs[hr["dogs"][0]]
rt = f"xreturn_{dret['name']}"
rr_ts = ts_at(dt.date(2026, 10, 13), 8 + rng.randrange(10))
rr1 = emit(rr_ts, hh_from(hr), SHARED, f"Struggling with {dret['name']} — I'm so sorry",
           thread=rt, kind="llm", persona=hr["id"], renderer=hr["renderer"],
           facts={"type": "foster_return", "dog": dret["name"],
                  "reason": "separation anxiety too intense for our schedule"},
           expected_ops=[{"table": "fosters", "match": {"foster_name": hr["name"]},
                          "set_includes": ["last_returned_dog"]}])
emit(jitter_reply(rr_ts, 6), STAFF_FROM, hh_from(hr),
     f"Re: Struggling with {dret['name']} — I'm so sorry", thread=rt, kind="llm",
     persona="dana", reply_to=rr1, renderer=STAFF_RENDERER,
     facts={"type": "return_gracious", "dog": dret["name"],
            "household_first": hr["first"],
            "logistics": "bring everything to the den; soft landings count"})
unplace(dret, rr_ts.date())
dret["timeline"].append(["returned_by_foster", str(rr_ts.date()),
                         "separation anxiety"])
h3 = match_household(dret)
if h3:
    ot3 = f"xreoffer_{dret['name']}"
    o3_ts = jitter_reply(rr_ts, 12)
    o3 = emit(o3_ts, STAFF_FROM, hh_from(h3), f"Second chance for {dret['name']}?",
              thread=ot3, kind="llm", persona="dana", renderer=STAFF_RENDERER,
              facts={"type": "placement_offer", "dog": dret["name"],
                     "pitch": f"{dret['age_class']} {dret['sex']} {dret['breed']}, {dret['quirk']}; "
                              "first home wasn't the right fit — needs patient people",
                     "pickup": f"{SAFEHOUSE}, anytime after 4pm",
                     "household_first": h3["first"]})
    r3_ts = jitter_reply(o3_ts, 12)
    emit(r3_ts, hh_from(h3), SHARED, f"Re: Second chance for {dret['name']}?",
         thread=ot3, kind="llm", persona=h3["id"], reply_to=o3, renderer=h3["renderer"],
         facts={"type": "offer_reply", "accept": True, "dog": dret["name"],
                "detail": "accepts, ready for the challenge"})
    place(dret, h3, r3_ts.date())

# -- planning replies (inbound, parent = week-1 planning blast)
for d in rng.sample(due, k=min(6, len(due))):
    h = household_of(d)
    if not h:
        continue
    emit(jitter_reply(pt_, 30), hh_from(h), SHARED,
         "Re: Planning ahead: spay/neuter and getting your pups posted!",
         thread="plan_2026-10-21", kind="llm", persona=h["id"],
         renderer=h["renderer"],
         facts={"type": "planning_reply", "dog": d["name"],
                "ask": rng.choice(["confirm dog is scheduled", "photos this weekend ok?",
                                    "content-free ack"])})

# -- posting queries (fosters of just-posted dogs asking + June answering)
pq = [d for d in dogs.values() if d.get("posted_date")
      and "2026-10-10" <= d["posted_date"] <= "2026-10-13"]
for d in rng.sample(pq, k=min(4, len(pq))):
    h = household_of(d)
    if not h:
        continue
    q_ts = ts_at(dt.date.fromisoformat(d["posted_date"]) - dt.timedelta(days=1),
                 10 + rng.randrange(8))
    q1 = emit(q_ts, hh_from(h), SHARED, f"Is {d['name']} posted yet?",
              thread=f"xpq_{d['name']}", kind="llm", persona=h["id"],
              renderer=h["renderer"], facts={"type": "posting_query", "dog": d["name"]})
    emit(jitter_reply(q_ts, 8), STAFF_FROM, hh_from(h),
         f"Re: Is {d['name']} posted yet?", thread=f"xpq_{d['name']}", kind="llm",
         persona="june", reply_to=q1, renderer=STAFF_RENDERER,
         facts={"type": "posting_query_reply", "dog": d["name"],
                "household_first": h["first"],
                "explanation": "photos+bio are in; goes up right after the fix — any day now"})

# -- alumni updates (inbound starters; adopters of settled dogs)
NEW_NAMES = ["Pickle", "Noodle", "Tater", "Bowie", "Juno", "Scout", "Pippa"]
alums = [d for d in dogs.values() if d.get("adopted")]
for d, nn in zip(rng.sample(alums, k=min(7, len(alums))), NEW_NAMES):
    a_date = dt.date(2026, 10, 10) + dt.timedelta(days=rng.randrange(0, 18))
    if a_date <= dt.date.fromisoformat(d["adopted"]["date"]):
        continue
    adopter = d["adopted"]["adopter"]
    aemail = f"{adopter.split()[0].lower()}.{adopter.split()[1].lower()}@{rng.choice(FREEMAIL)}"
    a1 = emit(ts_at(a_date, 10 + rng.randrange(8)), f"{adopter} <{aemail}>", SHARED,
              f"{d['name']} update!", thread=f"xal_{d['name']}", kind="llm",
              persona=f"xal_{d['name']}", renderer=pick_renderer(),
              facts={"type": "alumni_update", "dog": d["name"], "new_name": nn,
                     "milestone": rng.choice(["first beach trip", "learned shake",
                                               "sleeping through the night", "made a cat friend"]),
                     "ask": rng.choice(["old listing photos", "food recommendation",
                                         "just sharing joy, no ask"])})
    if a_date <= WEEK1_END:
        emit(jitter_reply(ts_at(a_date, 15), 8), STAFF_FROM, f"{adopter} <{aemail}>",
             f"Re: {d['name']} update!", thread=f"xal_{d['name']}", kind="llm",
             persona="dana", reply_to=a1, renderer=STAFF_RENDERER,
             facts={"type": "alumni_reply", "dog": d["name"], "new_name": nn,
                    "workaround": "photos too large to attach; share link instead"})

# -- catchall noise through the window
day = dt.date(2026, 10, 10)
ca_n = 0
BRANDS = ["PawPals Warehouse", "Furry & Co.", "TailMart"]
while day <= POOL_END:
    if rng.random() < 0.45:
        emit(ts_at(day, 6 + rng.randrange(3)),
             f"{rng.choice(BRANDS)} <promo@tailmartmail.com>", SHARED,
             rng.choice(["🐾 Fall savings for good dogs!", "FREE shipping this weekend",
                          "New arrivals your pup will love"]),
             thread=f"xmkt_{day}_{rng.randrange(99)}", kind="template",
             facts={"template": "marketing"})
    if rng.random() < 0.25:
        ca_n += 1
        nm = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
        email = f"{nm.split()[0].lower()}{rng.randrange(100, 999)}@{rng.choice(FREEMAIL)}"
        kind_key, gist, subj = rng.choice([
            ("vague_interest", "asks if any medium dogs are available", "Medium dogs?"),
            ("volunteer_offer", "offers weekend transport help", "Can I help with transport?"),
            ("donation_note", "made a small donation, asks where it goes", "Donation"),
            ("lost_dog", "asks about a found dog near the park", "Found dog by Stafford Park")])
        v_ts = ts_at(day, 9 + rng.randrange(10))
        v1 = emit(v_ts, f"{nm} <{email}>", SHARED, subj, thread=f"xca_{ca_n}",
                  kind="llm", persona=f"xpub_{ca_n}", renderer=pick_renderer(),
                  facts={"type": kind_key, "gist": gist, "name_first": nm.split()[0]})
        if day <= WEEK1_END:
            emit(jitter_reply(v_ts, 24), STAFF_FROM, f"{nm} <{email}>", "Re: " + subj,
                 thread=f"xca_{ca_n}", kind="llm", persona="dana", reply_to=v1,
                 renderer=STAFF_RENDERER,
                 facts={"type": "catchall_reply", "re": kind_key,
                        "name_first": nm.split()[0],
                        "pointer": {"vague_interest": "point to the website and Saturday events",
                                    "volunteer_offer": "warm ack, we'll reach out",
                                    "donation_note": "thanks; goes to vet care",
                                    "lost_dog": "redirect to animal control"}[kind_key]})
    day += dt.timedelta(days=1)

# ===========================================================================
# partition: week 1 (inject) vs pool (fire later), snapshot gt v2
# ===========================================================================

specs.sort(key=lambda s: s["ts"])
wk1_cut = f"{WEEK1_END}T23:59:59"
week1 = [s for s in specs if s["ts"][:19] <= wk1_cut]
week1_ids = {s["id"] for s in week1}
BLAST_WHITELIST = {"intake_announcement", "event_blast", "vet_blast", "planning_blast"}

pool = []
for s in specs:
    if s["id"] in week1_ids:
        continue
    is_staff = SHARED in s["from"]
    ftype = s["facts"].get("type") or s["facts"].get("template")
    if is_staff and ftype not in BLAST_WHITELIST and s["kind"] != "template":
        continue  # staff 1:1 replies: live drafts take their place
    if s["reply_to"] is not None:
        parent_ok = (s["reply_to"] in week1_ids or any(
            p["id"] == s["reply_to"] and (SHARED not in p["from"]
                                          or (p["facts"].get("type") in BLAST_WHITELIST))
            for p in specs))
        if not parent_ok:
            continue  # orphan: its parent can never exist in the inbox
    pool.append(s)

out = HERE / "out" / "extension"
out.mkdir(parents=True, exist_ok=True)
(out / "specs_week1.jsonl").write_text(
    "\n".join(json.dumps(s, ensure_ascii=False) for s in week1))
(out / "specs_pool.jsonl").write_text(
    "\n".join(json.dumps(s, ensure_ascii=False) for s in pool))

# ground truth v2 = AS-OF week-1-end projection (the verification target);
# the full Oct-30 state goes to ground_truth_full.json (pool-window truth).
import copy
CUT = str(WEEK1_END)

def as_of(dog):
    d = copy.deepcopy(dog)
    for f in ("photos_date", "bio_date", "posted_date", "vet_date"):
        if d.get(f) and d[f] > CUT:
            d[f] = None
    if d.get("vet_date") is None and d.get("fixed"):
        # fixed either at intake or at a vet day <= cut; undo post-cut fixes
        fixed_pre = any(t[0] == "spay_neuter" and t[1] <= CUT for t in d["timeline"])
        intake_fixed = not any(t[0] == "spay_neuter" for t in d["timeline"])
        d["fixed"] = fixed_pre or intake_fixed
    d["events"] = [e for e in d.get("events", []) if e <= CUT]
    if d.get("adopted") and d["adopted"]["date"] > CUT:
        d["adopted"] = None
    open_seg = any(seg["start"] <= CUT and (seg["end"] is None or seg["end"] > CUT)
                   for seg in d["foster_history"])
    if d["intake"] > CUT:
        return None  # dog doesn't exist yet at the cutoff
    if d.get("adopted"):
        d["status"] = "adopted"
    elif open_seg:
        d["status"] = "in_foster"
    else:
        d["status"] = "intake"
    d["timeline"] = [t for t in d["timeline"] if t[1] <= CUT]
    return d

gt2 = {"org": GT["org"], "window": GT["window"],
       "event_days": GT["event_days"] + ["2026-10-17"],
       "vet_days": GT["vet_days"],
       "extension": {"week1_end": str(WEEK1_END), "pool_end": str(POOL_END),
                     "seed": SEED},
       "dogs": {}, "households": [], "applications": []}
for n, d in dogs.items():
    snap = as_of(d)
    if snap is not None:
        gt2["dogs"][n] = snap
for h in households:
    hc = copy.deepcopy(h)
    holding = [n for n, d in gt2["dogs"].items()
               if d["status"] == "in_foster" and d["foster_history"]
               and any(seg["household"] == h["id"] and seg["start"] <= CUT
                       and (seg["end"] is None or seg["end"] > CUT)
                       for seg in d["foster_history"])]
    hc["dogs"] = holding
    vac = any(t[0] == "vacation" and t[1] <= CUT for t in hc.get("timeline", []))
    if hc["state"] not in ("churned",):
        hc["state"] = "vacation" if (vac and not holding) else (
            "fostering" if holding else "available")
    gt2["households"].append(hc)
gt2["applications"] = [a for a in GT["applications"] if a["date"] <= CUT]
(out / "ground_truth_v2.json").write_text(json.dumps(gt2, ensure_ascii=False, indent=1))
GT["extension"] = gt2["extension"]
(out / "ground_truth_full.json").write_text(json.dumps(GT, ensure_ascii=False, indent=1))

import collections
kinds = collections.Counter((s["facts"].get("type") or s["facts"].get("template"))
                            for s in week1)
print(f"week1: {len(week1)} specs | pool: {len(pool)} specs | "
      f"llm week1: {sum(1 for s in week1 if s['kind']=='llm')}")
print("week1 top types:", kinds.most_common(10))
kinds2 = collections.Counter((s["facts"].get("type") or s["facts"].get("template"))
                             for s in pool)
print("pool top types:", kinds2.most_common(10))
print("pool with expected_ops:", sum(1 for s in pool if s.get("expected_ops")))
print("dogs now:", len(dogs), "| in_foster:",
      sum(1 for d in dogs.values() if d['status'] == 'in_foster'))
