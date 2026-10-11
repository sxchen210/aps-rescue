# DISCOVERY_NOTES — APS Rescue shared mailbox

**Mailbox:** animalprotectiveservices2026@gmail.com — 831 messages / 309 threads, Sep 1 – Oct 17, 2026. I paged the entire thread index (13 pages) and read full threads for every recurring pattern.

## What this operation is
APS Rescue is a small foster-based dog rescue in Redwood City, CA ("the den" = their safehouse). They pull dogs weekly from **San Benito County Animal Services**, place them with volunteer fosters, get them spayed/neutered at **Crestview Veterinary Clinic (Livermore)**, collect photos + a bio questionnaire, post the dog for adoption (rule: photos + bio + fixed = posted), run roughly biweekly Saturday adoption events at **Bark & Barrel Pet Supply**, and schedule adoption appointments at the den. Dogs are named after nature words (Nettle, Rime, Virga, Scarp…), which makes `dog_name` a reliable canonical key.

**Staff (all send from the shared address, distinguished by signature):**
- **Dana** — coordinator: shelter pulls, foster matching, returns, adoption appointments.
- **Priya** — vet-day logistics (spay/neuter transport).
- **June** — adoption postings/roundups.
- **Tom** — foster application intake.
- Also: Opal (volunteer photographer, mentioned), Noel (Crestview front desk).

## Workflows found (with thread evidence actually read)

### 1. Shelter pulls → dog intake (table `dogs`)
Broadcast `APS Rescue_<date>_Shelter pull from San Benito County Animal Services` listing each dog as "Name (age sex breed, size)", intake vaccines, den pickup window. Evidence: `1a11c681fad0007a` (10/8, 12 dogs), `1a0f85e3f5f1412a` (10/1), `1a0d441cd862b475` (9/24), `1a08c38b792b2184` (9/10), `1a0b04038556fd60` (9/17), `1a0682cc7fdbdbfb` (9/3).

### 2. Foster matching (dogs.status / foster_name)
Per-dog offers from Dana, accepted or declined by reply; staff confirmation sets pickup. Variants: "Foster match: X?" (`1a11d62ae2fa2149` Rime — accept; `1a11c887aaca44db` Virga — decline, then re-offer in `1a11ee2b7c35e2c7`), "Second chance for X?" after a failed placement (`1a0ff7b78c8a7b2e` Nettle), re-foster ask after failed adoption (`1a10d4b5902bfed0` Moraine — declined), overflow call-for-homes "Two more pups than homes" with a final plan email naming who takes whom (`1a0f932113fa08ec` Fjord/Crag), event-arranged pickup (`1a107c0ffa7f5eee` Crag), "Longer-term home for Isobar?" after a bridge stint (`1a0d46dab2b962da`).

### 3. Returns & bridge/coverage fostering (dogs)
- Foster gives up: "Struggling with X — I'm so sorry" (`1a0fe72f5fdd0ed0` Nettle/energy, `1a0d46ebbadb85a4` Typhoon, `1a0acd8556cc3e73` Glacier, `1a077905c4de0617` Flurry).
- Adoption falls through: "I'm so sorry — we can't keep Moraine" (landlord) `1a10c90704aa3679`, followed by re-matching.
- Foster moving: "We're moving — Isobar needs a new foster by 9/22" → bridge foster Yolanda 9/22–9/27 (`1a0ad2c03cc21301`).
- Vacation coverage: "Out of town — coverage for Ridge?" → Leif covers 9/24–10/2 (`1a0c5f35bfd22529`; also `1a0c6c87173effc7` Chicory, `1a0b13dc72a01a29` Doldrum).

### 4. Spay/neuter vet days (dogs: date, clinic, transport_option, health_note)
Group email `APS Rescue_<date> Wednesday_Livermore_Spay/Neuter Appts` lists the dogs + three logistics options (default den 6:30AM / overnight at den / direct to clinic); each foster replies to opt in, Priya confirms each with a crate checklist. Many replies piggyback a minor health concern to add to the clinic sheet. Evidence: `1a107ae748504560` (10/7, 19 msgs — incl. Bianca's self-corrected "mixed up my dogs" message, a great correction case), `1a0bf95c7616e280` (9/23, 25 msgs), `1a0777c8eee95cbc` (9/9). "Planning ahead: spay/neuter and getting your pups posted!" pre-announces the surgery list + photo/bio deadline (`1a0f8245cb2a9e58`, `1a0b00ba22959290`, `1a067f2712c68ee5`).

### 5. Health concerns (dogs.health_note)
Fosters email `"<Dog> - <symptom>"`; Dana routes to vet volunteers. Evidence: `1a111c52167ab0ae` (Hoarfrost ear), `1a0f8ac0c580d292` (Scree cloudy eye), `1a0ced93a95e669e` (Petrichor leg), `1a086ff4705ff810` (Talus appetite), `1a0ba4197e15311d`, `1a0b5b242fef44d0`, `1a0db8b472537069`, `1a0c134f67773b09`. "Records for <Dog>" emails to Crestview restate the concern + intake treatments (`1a0fd35417dd0cfd` Scree, `1a0c620a3a61cde6` Cascade, `1a05f08b75cd4c89` Isobar).

### 6. Photos → bio → posted pipeline (dogs: photos_received, bio_received, posted)
"Photos of X" then "Bio for X" from fosters; June confirms "officially POSTED 🎉" (`1a109068f1c5b825` Nettle — full pipeline in one thread; `1a129975d5e5ebd6` Marram). Weekly "Posting roundup" categorizes dogs: READY TO POST / WAITING ON BIO / WAITING ON FIX with the scheduled fix date (`1a10c991b02cc330` 10/5, `1a0a073408722feb` 9/14, `1a0e88c8b1763862` 9/28). Fosters ask "Is X posted yet?" and June replies with the bio/photos/vet checklist and the posting rule (`1a0b1ad16bace753` Granite, `1a0822f6258dcca8` Talus — states fix date 2026-09-09 explicitly).

### 7. Adoption appointments (dogs: adoption_appt_date, adopter_name, status)
"Adoption appointment for X!" names the adopter and a concrete date/time at the den; crate stays with the foster. 21 such threads; read `1a11369335a4bc16` (Lassen — adopter Zoe, Wed 10/7 11am) and `1a0cb43ca7a78079` (Moraine — adopter Helena; this adoption later failed, see §3, proving appointments ≠ adoption).

### 8. Foster applications (table `foster_applications`)
Automated form email "Thank you for your foster application, <Name>" (From "APS Rescue Applications", structured fields), then Tom sends the foster guide and schedules a 20–30 min intro call; some are declined outright. Evidence: `1a121c5ec380d555` (Hugo — received), `1a108e9ef0affff1` (Jasper Nakamura — call agreed Wed noon), `1a104290a73d3578` (Freya Nakamura — call Thu 5:30pm), `1a0ff9f3829af746` (Zainab Cervantes — **declined**: 6-8h alone not a fit). ~25 application threads total. No explicit "approved" email was observed; approval is implied when a person later receives foster-match offers — enum keeps `approved` for completeness.

### 9. Adoption events (tables `events`, `event_rsvps`)
"**Response Needed!** Save the date: <date> event at Bark & Barrel" with drop-off/pickup times; each foster replies confirming their dog, often requesting nail trims. Evidence: `1a0edc07577caeb4` (Oct 3, 29 msgs), `1a0a5a7cd0d90ad5` (Sep 19), `1a05d8f084132e36` (Sep 5), forgotten-recipient forwards `1a0edd9efef03fae` (Levant), `1a0a5d4c11bb0ee6`.

### 10. Non-workflow mail (catchall)
- **Promos** from pet-supply brands (TailMart / PawPals / Biscuit Barn / Happy Hound / Furry & Co., often mismatched From domains) — pure noise, ~12 threads.
- **Google Drive share notifications** "Document shared with you: 'X photos'" (drive-shares-dm-noreply@google.com) — machine duplicates of the photo workflow, ~25 threads; the substantive "Photos of X" email arrives separately.
- **Found-stray inquiries** from the public; rescue declines and redirects to animal control (`1a11d55034ae8eab`, `1a0e95547dcfe084`).
- **Donation** question (`1a08dfc0496797cf`).
- **Adopter updates** ("Cyclone update!" `1a10dd03b2d72d28`, Dune `1a1085e051f33f33`, Tundra `1a0bfd3f08f05269`, Altocumulus `1a0ca448264803e4`) — happy post-adoption notes; useful only as confirmation of `status: adopted`.

## Design decisions
- **4 tables.** `dogs` absorbs matching, returns, coverage, vet-day logistics, health notes, and the posting pipeline because every one of those facts is per-dog and the dog name is always present — one row answers "where is this dog and what's next for it?". `foster_applications` is a separate entity lifecycle. `events` + `event_rsvps` separate because RSVP rows are keyed per (event, dog) and the event itself carries the date/venue facts.
- **Dated fields over status text** wherever the mailbox states dates: intake_date, spay_neuter_date, adoption_appt_date, foster_pickup_date, coverage window, event_date, intro_call_date. Vet days, appointments and events are always announced days in advance — email sent dates would be wrong.
- **Hard cases covered in instructions:** multi-dog broadcast (one op per dog), one email carrying two workflows (vet opt-in + health concern; RSVP + health concern), in-email self-correction (`1a107ae748504560` msg 15), adoption reversal/returns, re-offers after declines, machine-generated mail (form emails = extractable; Drive pings & promos = noise).
- No "approved" application email was ever observed, and no explicit "adopted — done!" email exists either; adoption completion is inferred from adopter updates. The instructions tell the extractor exactly how to handle both.