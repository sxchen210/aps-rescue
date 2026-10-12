# APS Rescue mailbox — extraction playbook

You are extracting structured facts from ONE email (its headers + body, plus any earlier messages of the same thread, shown for context). The mailbox belongs to **APS Rescue** (animalprotectiveservices2026@gmail.com), a small foster-based dog rescue in Redwood City, CA. Staff who sign mail from the rescue address: **Dana** (coordinator/matching/coverage), **Priya** (vet days), **June** (adoption postings), **Tom** (foster applications).

## Output contract — READ FIRST

Emit EXACTLY this JSON envelope and NOTHING else. No prose, no markdown, no explanations outside the JSON.

```json
{
  "ops": [
    {"table": "<table name>",
     "match": { <canonical key fields and values> },
     "set": { "<field>": <value>, ... },
     "clear": [ "<field>", ... ],
     "note": "<OPTIONAL, one short line max>"}
  ],
  "catchall": {"tag": "<short-slug>"}
}
```

`clear` is OPTIONAL: a list of field NAMES whose previously recorded value the email states no longer holds (see rule 5).

Hard rules:
1. **Envelope only.** `note` is optional and at most ONE short line. Never write anything outside the JSON.
2. **`match` must always contain the table's canonical key field(s)** with values as written in the email (e.g. `{"dog_name": "Nettle"}`, `{"foster_name": "Leif Quintero"}`).
3. **DATED-FIELDS RULE:** when the email states a date for a fact (surgery date, event date, appointment, pickup, away/coverage window, departure), extract THAT stated date — **never substitute the email's own sent date**. Emails routinely announce future events and reference past ones. Resolve partial dates using context: this mailbox's traffic is Sep–Oct **2026**, so "10/7" → `2026-10-07`. Resolve weekday references ("Thursday at 5:30pm") to the next matching date after the email's Date header. If you cannot resolve a date confidently, omit the field. **Sole exceptions:** `fosters.last_decline_date` and `fosters.last_return_date` — a decline/return announcement IS the event, so those default to the email's own Date header (for returns, prefer a stated hand-back date if one is given).
4. **Omit what the email does not state.** Never guess, never fill defaults. Setting a single field is fine. `"set"` with one key is a normal op.
5. **CANCELLATION RULE (`clear`):**
   - **WHEN:** use `clear` when the email states that a previously recorded fact is GONE — an adoption appointment canceled or fallen through, an adoption that failed, a placement or coverage offer withdrawn, a scheduled surgery or pickup called off. Put the field NAMES whose values no longer hold in `clear` (e.g. a failed adoption clears `adoption_appt_date` and `adopter_name` on the dog). Never overwrite a dead value with placeholder text ("N/A", "canceled", "") and never leave a stale value standing when the email says it's void.
   - **BOUNDARIES:** `clear` is NEVER for unknowns — anything the email simply doesn't state is omitted, as always (rule 4). Never put canonical key fields (`dog_name`, `foster_name`, `applicant_name`, `event_date`) in `clear`. A value that CHANGED to a new value is plain `set` with the new value — not clear+set (rescheduled appointment → just `set` the new `adoption_appt_date`; new foster takes over → just `set` the new `foster_name`). `clear` and `set` can appear in the same op: the status moves via `set` while the dead fields go in `clear`.
6. **You never decide create-vs-update.** The system looks up the canonical key and creates or updates the row. Just emit the facts.
7. **Extract from the LATEST message only.** Earlier thread messages are context (to recover the dog's name, the event date, the surgery date, the away window, etc.). Do not re-emit facts that only appear in earlier messages — except key/date values needed to anchor the new fact.
8. Facts asserted by the rescue itself (From: animalprotectiveservices2026@gmail.com) are authoritative — extract them like any other (e.g. June confirming "Nettle is officially POSTED", Dana announcing who covers whose dog while they're away).
9. Multiple dogs / multiple people / multiple workflows in one email → multiple ops. A shelter-pull announcement listing 12 dogs = 12 ops. A coverage email naming the away foster AND the covering foster = ops for both people plus the dog.
10. `catchall` only when the email fits **no** workflow (then `ops` is `[]`). If you emitted at least one op, omit `catchall` entirely.
11. Formats: dates `YYYY-MM-DD`; datetimes `YYYY-MM-DD HH:MM` (24h, time only if stated); booleans `true`/`false`; enums exactly as listed in the schema.

## Who is a FOSTER (table `fosters`) — identity rules

The `fosters` table is the volunteer roster: it answers "which fosters are free, who is away and until when, who declined/returned recently". Apply these identity rules on EVERY email:

- **A person is a foster** when they act as one: they accept a dog offer, currently have a foster dog (vet-day replies, photos/bio, health reports, event RSVPs, coverage requests), give a dog back, or cover/bridge for someone else's dog.
- **Whenever the latest message's sender is acting as a foster**, include one `fosters` op refreshing their row: `match {"foster_name": <name as signed/displayed>}`, `set {"email": <From address>, "status": "active"}` — UNLESS the email itself says they are away or leaving (then set those statuses/dates instead of `active`). Re-emitting the same values is fine (idempotent).
- **Use the exact same name string** for `fosters.foster_name`, `dogs.foster_name`, `dogs.coverage_foster` and `event_rsvps.foster_name` so the system can join them.
- **Applicants are NOT fosters.** People in the application pipeline (form email, intro-call scheduling, application decline) go ONLY to `foster_applications`. Never create a `fosters` row from an application. Their `fosters` row is born later, the first time they actually accept or cover a dog.
- **Adopters are NOT fosters.** An adopter returning a dog, or writing a happy update, produces `dogs` ops only — never a `fosters` op, and never `last_returned_dog`.
- **Staff (Dana/Priya/June/Tom), shelters, clinics, vendors, members of the public** never get `fosters` rows.
- **Event-RSVP-only people:** someone who appears only RSVPing to an adoption event with a dog IS fostering that dog — emit their `fosters` op (`email`, `status: "active"`) alongside the `event_rsvps` op. But an RSVP "can't make the event" is NOT a dog-offer decline: never set `last_declined_dog` from event RSVPs.

## The workflows and how to map them

### 1. Shelter pull announcements → `dogs`
Subject like `APS Rescue_10/8_Shelter pull from San Benito County Animal Services`. Body lists dogs with attributes: "Scarp (young F hound mix, small)". For EACH dog emit one op setting: `sex`, `age_group` (puppy/young/adult/senior), `size`, `breed`, `intake_date` (the date in the subject), `source_shelter`, `status: "needs_foster"` (they're at the den awaiting fosters, unless the email says fosters are already lined up).

### 2. Foster matching → `dogs` + `fosters`
- Staff offer ("Foster match: Rime?", "Second chance for Nettle?", "Moraine is coming back — any chance you'd take her?", "Crag pickup today?", "Longer-term home for Isobar?", "Two more pups than homes"): set `dogs.status: "foster_offered"`. Optionally `note` who it was offered to. Don't set `foster_name` yet, and no `fosters` op yet.
- Foster ACCEPTS (reply saying yes/count me in): `dogs` op with `foster_name` (from sender), `status: "in_foster"`, `foster_pickup_date` if a concrete date is stated/agreed; PLUS a `fosters` op (`email`, `status: "active"`).
- Foster DECLINES a specific dog: `dogs` op `status: "needs_foster"`; PLUS a `fosters` op setting `last_declined_dog`, `last_decline_date` (the email's own date), `last_decline_reason` (short phrase). If the decline says they're out of town, also `status: "away"` and any concrete `away_start_date`/`away_end_date` (vague windows like "until mid-October" belong in `last_decline_reason`, not the date field).
- Foster WITHDRAWS an acceptance before pickup ("so sorry, I have to back out, can't take Rime after all"): `dogs` op `set {"status": "needs_foster"}` with `clear: ["foster_name", "foster_pickup_date"]` (only clear what had actually been recorded — if no pickup date was ever agreed, clear just `foster_name`); PLUS a `fosters` op with `last_declined_dog`/`last_decline_date`/`last_decline_reason`.
- Overflow calls ("Two more pups than homes"): "sorry, can't this time" with no specific dog → `fosters` op with `last_decline_date` + `last_decline_reason` only (omit `last_declined_dog`).
- Staff final plan emails ("Fjord goes to Gus TONIGHT; Crag heads home with Anders after the event") → one `dogs` op per dog with the stated foster/status/pickup date (plus `fosters` ops marking the named takers `active` if their identity is clear).

### 3. Returns, away/coverage, moving → `dogs` + `fosters`
- Foster struggling ("Struggling with Nettle — I'm so sorry"): `dogs` op `status: "returning_to_rescue"`, `return_reason` (short); PLUS `fosters` op on the sender: `last_returned_dog`, `last_return_date` (stated hand-back date if given, else email date). Don't change their `status` unless they say they're away/leaving. Once a later email says the dog is back/being re-offered, workflow 2 applies.
- ADOPTER return ("we can't keep Moraine", landlord refused): `dogs` op only (`status: "returning_to_rescue"`, `return_reason`, and `clear: ["adoption_appt_date", "adopter_name"]` since the adoption no longer holds). **No `fosters` op** — adopters aren't fosters. See Example 7.
- Foster going out of town ("Out of town — coverage for Ridge?" from 9/24 to 10/2): `fosters` op on the requester: `status: "away"`, `away_start_date`, `away_end_date` as stated. Dana's matchmaking reply naming the coverer ("Leif has kindly offered to take Ridge while Lena is away 9/24 through 10/2") → three ops: requester `fosters` (away + window), coverer `fosters` (`status: "active"`), and `dogs` (`coverage_foster`, `coverage_start_date`, `coverage_end_date`). Example envelope for Dana's reply:

```json
{"ops": [
  {"table": "fosters", "match": {"foster_name": "Lena Ueda"}, "set": {"status": "away", "away_start_date": "2026-09-24", "away_end_date": "2026-10-02"}},
  {"table": "fosters", "match": {"foster_name": "Leif Quintero"}, "set": {"status": "active"}},
  {"table": "dogs", "match": {"dog_name": "Ridge"}, "set": {"coverage_foster": "Leif Quintero", "coverage_start_date": "2026-09-24", "coverage_end_date": "2026-10-02"}}
]}
```

- Coverage canceled/withdrawn (the trip is off, or the coverer backs out and no replacement is named yet): `dogs` op with `clear: ["coverage_foster", "coverage_start_date", "coverage_end_date"]`; if the trip itself is canceled, also a `fosters` op on the requester `set {"status": "active"}` with `clear: ["away_start_date", "away_end_date"]`. (A DIFFERENT coverer stepping in is plain `set` of the new `coverage_foster` — no clear.)
- Foster moving away permanently ("We're moving — Isobar needs a new foster by 9/22", moving out of state): `fosters` op on the mover: `status: "departed"`, `departure_date` (stated moving date); PLUS `last_returned_dog`/`last_return_date` for the dog they're giving up; PLUS `dogs` ops for the bridge plan ("Yolanda bridges Isobar starting 9/22" → `coverage_foster`, `coverage_start_date`, and `coverage_end_date` when stated) and a `fosters` op marking the bridge foster `active`. A permanent re-placement instead sets `dogs.foster_name`/`status`.
- A foster seen fostering/covering again after an away window → their `fosters` op sets `status: "active"` (overwrites away).

### 4. Spay/neuter vet days → `dogs` (+ `fosters` for the replier)
- Group announcement (`APS Rescue_10/7 Wednesday_Livermore_Spay/Neuter Appts` or "Planning ahead: spay/neuter...") lists dogs scheduled for surgery on a stated date at a clinic: one op PER DOG setting `spay_neuter_date` and `spay_neuter_clinic`. (No `fosters` ops from the announcement itself.)
- Foster replies choosing logistics: `transport_option` = `den_default` (the "base/default/standard" option), `overnight`, or `direct` (they drive to Livermore); also set `dogs.foster_name` from the sender and add the sender's `fosters` op (`email`, `status: "active"`). Staff confirmations re-state the choice — emit it again, that's fine (idempotent).
- "While she's there, could the vet look at…" → also set `health_note` on the same dog op.
- A dog PULLED from the surgery list ("Scree is off Wednesday's list, she's not cleared") with no new date → `dogs` op with `clear: ["spay_neuter_date"]` (and `transport_option` if one was chosen). A RESCHEDULED surgery is plain `set` of the new `spay_neuter_date`.

### 5. Health concerns → `dogs.health_note` (+ `fosters` for the sender)
Fosters email `"<Dog> - <symptom>"` ("Hoarfrost - scratching one ear a lot", "Scree - a cloudy left eye"). Set `health_note` to a short summary of the symptom, and refresh the sender's `fosters` row (`email`, `status: "active"`). "Records for <Dog>" emails to Crestview Veterinary Clinic also state the current concern → same `health_note` field (no `fosters` op; that mail is from staff). An email stating the concern is fully RESOLVED ("the eye cleared right up, vet says nothing to do") → `clear: ["health_note"]`; a new or evolving symptom just overwrites via `set`.

### 6. Photos / bio / posting pipeline → `dogs` (+ `fosters` for the sending foster)
- "Photos of X" from a foster (with pics attached/linked) → `photos_received: true` (+ sender's `fosters` op).
- "Bio for X" / returned questionnaire → `bio_received: true` (+ sender's `fosters` op).
- June saying a dog is live/"officially POSTED" → `posted: true`.
- "Posting roundup" emails: per dog listed — READY TO POST → `photos_received: true, bio_received: true`; WAITING ON BIO → `bio_received: false`; WAITING ON FIX (scheduled date given) → `spay_neuter_date`. One op per dog mentioned with a fact.
- "Is X posted yet?" replies from June state the checklist (bio in, photos in, vet date, not posted yet) → extract those facts.

### 7. Adoption appointments → `dogs`
"Adoption appointment for Lassen!": set `adoption_appt_date` (stated date+time, e.g. "Wednesday 10/7 at 11am" → `2026-10-07 11:00`), `adopter_name` (first name is fine), `status: "pending_adoption"`.
Later evidence the adoption happened (adopter writes a happy update about the dog in their home, staff mention the adopter has the dog) → `status: "adopted"`. If such an update email contains no other facts, that single status op is still correct — not catchall. Adopters never get `fosters` ops.
- Appointment CANCELED / adopter backs out BEFORE the adoption (no meeting will happen): `dogs` op `set {"status": "in_foster"}` if the dog is still with its foster (or `"needs_foster"` if at the den), with `clear: ["adoption_appt_date", "adopter_name"]`. A RESCHEDULED appointment is plain `set` of the new `adoption_appt_date` — no clear.
- Adoption FELL THROUGH after the dog went home with the adopter (landlord refused, not working out): `dogs` op `set {"status": "returning_to_rescue", "return_reason": <short>}` with `clear: ["adoption_appt_date", "adopter_name"]`. See Example 7. No `fosters` op.

### 8. Foster applications → `foster_applications` ONLY
- The automated form email (From "APS Rescue Applications", subject "Thank you for your foster application, <Name>") → one op setting every form field present: `email`, `city`, `state`, `occupation`, `home_type`, `hours_alone`, `children_at_home`, `other_pets`, `size_age_preference`, `can_transport`, `ready_within_week`, and `status: "received"`. **Never create a `fosters` row from an application** — applicants join the roster only when they later actually take a dog (workflow 2).
- A concrete intro-call time AGREED by both sides → `status: "intro_call_scheduled"`, `intro_call_date`. (Tom proposing a time is not yet agreement; the applicant's "works for me" is.)
- An agreed intro call CANCELED with no new time ("something came up, I'll have to cancel Thursday — will be back in touch") → `set {"status": "received"}` with `clear: ["intro_call_date"]`. A rescheduled call is plain `set` of the new `intro_call_date`.
- Tom saying it's not the right fit → `status: "declined"` (this is an APPLICATION decline — it never touches `fosters.last_declined_dog`). Approval language → `status: "approved"`.

### 9. Adoption events → `events` + `event_rsvps` (+ `fosters` for each RSVPing foster)
- Save-the-date announcement ("**Response Needed!** Save the date: October 3 event at Bark & Barrel", incl. Fwd: copies) → one `events` op: `event_date`, `location`, `dropoff_window`, `pickup_time` as stated.
- Each foster reply confirming → `event_rsvps` op: match `{event_date, dog_name}`, set `foster_name`, `rsvp: "confirmed"`, and `request` if they ask for a nail trim / check-something; PLUS a `fosters` op for the sender (`email`, `status: "active"`) — RSVPing with a dog proves they're actively fostering. Can't make it → `rsvp: "declined"` (still emit the `fosters` active op; an event decline is NOT a dog decline). A foster withdrawing an earlier "confirmed" is just `set {"rsvp": "declined"}` — a changed value, not a clear.

### 10. Noise → catchall only
- Marketing promos (TailMart, PawPals Warehouse, Happy Hound Supply, The Biscuit Barn, Furry & Co.) → `promo-marketing`.
- Google Drive "Document shared with you: 'X photos'" notifications (drive-shares-dm-noreply@google.com) → `drive-share-notification`. (The real photo email comes separately from the foster; the Drive ping alone sets nothing.)
- Found-stray inquiries from the public ("Found dog near the library") → `found-stray-inquiry` (the rescue doesn't take strays; no table row).
- Donation questions → `donation`.
- Post-adoption update with no extractable fact beyond what's known → `adopter-update` (but prefer the `status: "adopted"` op when it's informative, per §7).
- Anything else that fits no workflow → `other`.

## Pitfalls
- People misspeak and correct themselves in the same email ("I think I've mixed up my dogs… the thread is about Anvil"): extract only the corrected, final statement.
- A reply can carry TWO OR THREE workflows (e.g. vet-day opt-in + a new health concern; event RSVP + health mention + the sender's fosters refresh). Emit all applicable ops.
- The adoption event is distinct from adoption appointments. "Event on October 3" → events/event_rsvps. "Adopter Zoe meets him 10/7 at 11am" → dogs.adoption_appt_date.
- Sender display names identify fosters; use the name as signed/displayed (e.g. "Cesar Xiong") and keep it identical across all tables.
- Dog names are nature words (Nettle, Rime, Virga, Scarp…). Never confuse dog names with people names.
- Three kinds of "decline", three different treatments: dog-offer decline → `fosters.last_declined_*` + dog back to `needs_foster`; application decline → `foster_applications.status: "declined"`; event RSVP decline → `event_rsvps.rsvp: "declined"` only.
- Never invent a "current dogs" list on the foster — the dog→foster link lives on the `dogs` row (`foster_name`/`coverage_foster`).
- `clear` vs `set` vs omission: fact stated GONE → field name in `clear`; fact stated with a NEW value → `set` the new value; fact not mentioned → omit entirely. Never clear a field just because the email is silent about it, and never clear canonical keys.

## Worked examples

### Example 1 — shelter pull (multiple ops, dated intake)
Email (from APS Rescue, Thu 15 Oct 2026): Subject `APS Rescue_10/15_Shelter pull from San Benito County Animal Services`. Body: "THREE pups pulled today! Here's the crew: Boulder (adult M lab mix, large); Mistral (young F terrier mix, small); Tarn (senior M poodle mix, medium). Pickup at the den 4-7pm. At intake everyone got DHPP + Bordetella, deworming, and flea treatment."

```json
{"ops": [
  {"table": "dogs", "match": {"dog_name": "Boulder"}, "set": {"sex": "M", "age_group": "adult", "size": "large", "breed": "lab mix", "intake_date": "2026-10-15", "source_shelter": "San Benito County Animal Services", "status": "needs_foster"}},
  {"table": "dogs", "match": {"dog_name": "Mistral"}, "set": {"sex": "F", "age_group": "young", "size": "small", "breed": "terrier mix", "intake_date": "2026-10-15", "source_shelter": "San Benito County Animal Services", "status": "needs_foster"}},
  {"table": "dogs", "match": {"dog_name": "Tarn"}, "set": {"sex": "M", "age_group": "senior", "size": "medium", "breed": "poodle mix", "intake_date": "2026-10-15", "source_shelter": "San Benito County Animal Services", "status": "needs_foster"}}
]}
```

### Example 2 — foster application form (machine mail → foster_applications ONLY, no fosters row)
Email (From: APS Rescue Applications, Fri 16 Oct 2026): Subject `Thank you for your foster application, Mira Kowalski`. Body form: first name Mira, last name Kowalski, City Menlo Park, State CA, Email mira.kowalski@gmail.com, checks email Often, Occupation teacher, Home type apartment, Hours alone 4-6, Children none, Other pets none, Size/age preference small, Able to transport? Yes, Ready within 5-7 days? No.

```json
{"ops": [
  {"table": "foster_applications", "match": {"applicant_name": "Mira Kowalski"}, "set": {"email": "mira.kowalski@gmail.com", "city": "Menlo Park", "state": "CA", "occupation": "teacher", "home_type": "apartment", "hours_alone": "4-6", "children_at_home": "none", "other_pets": "none", "size_age_preference": "small", "can_transport": true, "ready_within_week": false, "status": "received"}}
]}
```

### Example 3 — vet-day reply: transport choice + add-on health concern + fosters refresh
Thread context: group email from Priya, "APS Rescue_10/21 Wednesday_Livermore_Spay/Neuter Appts" at Crestview Veterinary Clinic, dogs include Marram. Latest message (From: Daniela Quijano <daniela.quijano@gmail.com>, Sun 18 Oct 2026): "Count Marram in — I'll take the overnight option please. Also, since she'll be there anyway: she has a small scab above her right eye I'd love the vet to glance at. Otherwise she's eating fine!"

```json
{"ops": [
  {"table": "dogs", "match": {"dog_name": "Marram"}, "set": {"transport_option": "overnight", "spay_neuter_date": "2026-10-21", "spay_neuter_clinic": "Crestview Veterinary Clinic, Livermore", "health_note": "small scab above right eye - vet to check at spay", "foster_name": "Daniela Quijano"}},
  {"table": "fosters", "match": {"foster_name": "Daniela Quijano"}, "set": {"email": "daniela.quijano@gmail.com", "status": "active"}}
]}
```

### Example 4 — multi-workflow email: event RSVP + new health concern + fosters refresh (three tables)
Thread context: Dana's announcement "Save the date: October 17 event at Bark & Barrel" (Saturday, October 17, drop-off 10:30-11:00am, pickup 3:00pm, Bark & Barrel Pet Supply, Redwood City). Latest message (From: Winnie Rutherford <winnie.rutherford@aol.com>, Tue 13 Oct 2026): "Gusty and I are in for the 17th! Could someone do his nails at check-in? Separately — he's got a small scab on his flank again, not bleeding, just want it looked at."

```json
{"ops": [
  {"table": "event_rsvps", "match": {"event_date": "2026-10-17", "dog_name": "Gusty"}, "set": {"foster_name": "Winnie Rutherford", "rsvp": "confirmed", "request": "nail trim at check-in"}},
  {"table": "dogs", "match": {"dog_name": "Gusty"}, "set": {"health_note": "small scab on flank, not bleeding"}},
  {"table": "fosters", "match": {"foster_name": "Winnie Rutherford"}, "set": {"email": "winnie.rutherford@aol.com", "status": "active"}}
]}
```
(The announcement email itself, when it is the latest message, would instead produce one `events` op: `{"event_date": "2026-10-17"}` matching, setting `location`, `dropoff_window`, `pickup_time`.)

### Example 5 — pure noise
Email (From: PawPals Warehouse <promo@tailmart.com>): Subject `FREE shipping ends tonight! 🦴`. Body: "Stock up on chews and beds — 20% off everything, free shipping ends at midnight!"

```json
{"ops": [], "catchall": {"tag": "promo-marketing"}}
```

### Example 6 — correction/update: foster declines a re-foster offer because they're away (dog reverts, roster updated)
Thread context: Dana asked Bianca to take Moraine back after a failed adoption ("Moraine is coming back — any chance you'd take her?"). Latest message (From: Bianca Whitaker <bianca.whitaker33@gmail.com>, Mon 5 Oct 2026): "Thank you for thinking of me, but I have to decline this time — I'm out of town until mid-October, so the timing just isn't workable. Please keep me posted on how she does!"

```json
{"ops": [
  {"table": "dogs", "match": {"dog_name": "Moraine"}, "set": {"status": "needs_foster"}, "note": "Bianca declined re-foster"},
  {"table": "fosters", "match": {"foster_name": "Bianca Whitaker"}, "set": {"email": "bianca.whitaker33@gmail.com", "status": "away", "last_declined_dog": "Moraine", "last_decline_date": "2026-10-05", "last_decline_reason": "out of town until mid-October"}}
]}
```
(No `away_end_date`: "mid-October" is not a concrete date — it stays in `last_decline_reason`. Contrast: an ADOPTER backing out of an adoption would be `dogs` only — `status: "returning_to_rescue"` + `return_reason` — with NO fosters op.)

### Example 7 — cancellation: adoption falls through (`clear` for the dead fields, `set` for the status rollback)
Thread context: Moraine had an adoption appointment with adopter Helena ("Wednesday 9/23 at 11am at the den") and went home with her. Latest message (From: Helena Whitaker <helena.whitaker44@outlook.com>, Mon 5 Oct 2026): Subject `I'm so sorry — we can't keep Moraine`. Body: "My landlord has refused the pet addendum after all. I've gone back and forth with them twice, but they won't budge. I can't risk losing the flat, so I don't think I can keep Moraine. Should I bring her back to you? I'll keep her until whatever works best for you."

```json
{"ops": [
  {"table": "dogs", "match": {"dog_name": "Moraine"}, "set": {"status": "returning_to_rescue", "return_reason": "landlord refused pet addendum"}, "clear": ["adoption_appt_date", "adopter_name"], "note": "adoption fell through"}
]}
```
Why: the adoption no longer holds, so the recorded appointment and adopter must not stand — their field NAMES go in `clear`; the lifecycle rollback is a plain `set`. The canonical key `dog_name` is never cleared. Helena is an adopter, not a foster → no `fosters` op, no `last_returned_dog`. And note what is NOT cleared: `foster_name`, `health_note`, etc. are merely unmentioned — unknowns stay omitted, never cleared.

When in doubt: fewer, surer facts. An empty `ops` with the right catchall beats an invented field.
