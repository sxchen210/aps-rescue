"""Fictional universe cast and style data for APS Rescue (Redwood City, CA).

Everything here is invented. Dog names deliberately use a weather / geology /
flora theme, disjoint from the reference inbox's food-and-drink theme, so no
coincidental collision is possible. Staff exemplar snippets below are authored
for this project as voice anchors — they are not derived from any real email.
"""

ORG = "APS Rescue"
SHARED = "animalprotectiveservices2026@gmail.com"
SHARED_DISPLAY = f"{ORG} Foster Team <{SHARED}>"
CITY = "Redwood City"
VENUE = "Bark & Barrel Pet Supply, Redwood City"
SAFEHOUSE = "the den (our Redwood City safehouse)"
CLINIC = "Crestview Veterinary Clinic"
CLINIC_CITY = "Livermore"
CLINIC_FRONTDESK = "Noel"
SHELTER = "San Benito County Animal Services"
PHOTOGRAPHER = "Opal (our volunteer photographer — she doesn't drive, so you'd meet her near downtown)"

# --- Staff -------------------------------------------------------------

STAFF = {
    "dana": {
        "name": "Dana Whitfield",
        "from": f"{ORG} <{SHARED}>",
        "role": "general coordinator (events, placements, posting nudges, alumni)",
        "voice": ("warm, fast, exclamation-heavy; short paragraphs; ALL-CAPS for "
                  "hard rules; signs 'Dana'; sometimes self-deprecating asides in "
                  "parentheses"),
        "signoff": "Dana",
        "exemplars": [
            "Good morning all!\n\nIf you're getting this, your foster pup is on the "
            "list for Saturday's event at Bark & Barrel. Please reply to confirm "
            "you'll be there — and if your dog needs a nail trim or you want us to "
            "look at anything, add it to your reply!\n\nDana",
            "Oh no, don't worry about it at all — these things happen! Let's get "
            "Mesa back to the den this week and I'll start looking for her next "
            "home. You gave her a great soft landing.\n\nDana",
        ],
    },
    "priya": {
        "name": "Priya Raghunathan",
        "from": f"{ORG} <{SHARED}>",
        "role": "vet-day coordinator (batch spay/neuter, clinic records)",
        "voice": ("organized, directive, bulleted instructions, caps for the "
                  "fasting rule, reassuring close; signs 'Priya'; triple "
                  "exclamation when thanking"),
        "signoff": "Priya",
        "exemplars": [
            "Hi everyone!\n\nYou're receiving this because your APS foster will be "
            "fixed this Wednesday at Crestview in Livermore. Volunteers are driving, "
            "so the DEFAULT is drop-off and pickup at the den at 6:30AM.\n\n"
            "IMPORTANT — all food and water STOPS at midnight. No breakfast, no "
            "treats, nothing. They will be perfectly fine, promise!\n\nPriya",
            "I have you confirmed for the overnight option! Crate clearly labeled "
            "with your pup's name on top, pee pads at the bottom, NO food or water "
            "inside. Last potty loop around the den and you're done. Thank you!!!\n\nPriya",
        ],
    },
    "tom": {
        "name": "Tom Okafor",
        "from": f"{ORG} <{SHARED}>",
        "role": "applications coordinator (intake of fosters, interviews, screening)",
        "voice": ("measured, kind, complete sentences, one question at a time; "
                  "signs 'Tom'; declines are two warm sentences, never argued"),
        "signoff": "Tom",
        "exemplars": [
            "Hi! Thank you for applying to foster with APS. While we match you with "
            "a volunteer for a quick intro chat, here's our foster guide with the "
            "basics. Is there a day and time this week that works best for a call?\n\nTom",
            "Thank you for the extra detail — honestly, with everyone out of the "
            "house that long, I don't think this round is the right fit for our "
            "dogs. I really do appreciate you thinking of us, and our adoption "
            "events are always open to you!\n\nTom",
        ],
    },
    "june": {
        "name": "June Castillo",
        "from": f"{ORG} <{SHARED}>",
        "role": "posting/web volunteer (bios, photos, website, social)",
        "voice": ("brisk, friendly, deadline-forward; loves a checklist; signs "
                  "'June'; celebrates postings with a single emoji"),
        "signoff": "June",
        "exemplars": [
            "Got it — Cirrus is POSTED! 🎉 If you get a minute, share his listing "
            "around; the first weekend up matters most.\n\nJune",
            "Friendly nudge: I still need a bio for Tundra by Tuesday so she's up "
            "before Saturday. The questionnaire takes ten minutes, promise.\n\nJune",
        ],
    },
}

# --- Foster/applicant name pools (fictional) ---------------------------

FIRST = """Avery Bennett Caleb Daniela Elias Farah Gavin Hana Iris Jonah Keiko
Liam Mara Nadia Owen Paulo Quinn Rosa Silas Talia Umar Vera Wes Ximena Yusuf
Zoe Arlo Bianca Cormac Devi Ezra Freya Gus Helena Idris Jade Kofi Lena Marcus
Noor Otis Priya Rohan Selma Theo Uma Vikram Willa Xander Yara Zainab Anders
Brielle Cesar Darya Emmett Fiona Grant Hollis Imani Jasper Kira Lorenzo Maeve
Nils Octavia Pearl Reuben Sana Tobias Ursula Vince Winnie Yolanda Zeke Anouk
Blair Colette Dmitri Esme Flynn Greta Hugo Ines Jules Katya Leif Mirela Nico
Odette Petra Raina Stellan Tessa""".split()

LAST = """Ashford Barlow Cervantes Delgado Eastman Faraday Gallo Hartwell
Ibarra Jessup Kowalski Lindqvist Moreau Nakamura Obi Pemberton Quintero
Rutherford Sandoval Tran Ueda Valdez Whitaker Xiong Yates Zamora Beaumont
Callahan Drummond Ellsworth Fontaine Grimaldi Holloway Ivanova Jarrett
Kessler Lombardi Merchant Novak Oyelaran Prescott Quijano Rosales Sterling
Thackeray Underwood Villanueva Wexford Yamada Zielinski Abernathy Birkeland
Castellano Dubois Engstrom Ferreira Goldbaum Huang Iqbal Jimenez""".split()

# --- Dog names: weather / geology / flora (disjoint theme) --------------

DOG_NAMES = """Cirrus Nimbus Zephyr Gale Monsoon Drizzle Sleet Frost Tundra
Glacier Aurora Mistral Squall Chinook Haboob Derecho Bora Levant Sirocco
Mesa Butte Canyon Ridge Bluff Dune Delta Fjord Tarn Moraine Scree Talus
Basalt Flint Shale Slate Quartzite Granite Gypsum Obsidian Pumice Rhyolite
Sierra Cascade Teton Olympus Denali Shasta Lassen Whitney Juniper Sage
Aspen Cedar Rowan Bramble Thistle Yarrow Sorrel Tamarack Larch Alder
Hawthorn Elderberry Nettle Fennel Chicory Vetch Sedge Rush Cattail Marram
Gusty Breeze Cyclone Typhoon Tempest Flurry Graupel Rime Hoarfrost Virga
Petrichor Isobar Doldrum Cumulus Stratus Altocumulus Anvil Downburst
Crag Spire Col Cairn Scarp Kettle Drumlin Esker Outwash Bedrock""".split()

# --- Foster voice archetypes & renderer mix -----------------------------

FOSTER_VOICES = [
    {"key": "terse_mobile", "desc": "telegraphic one-liners, no greeting, no sign-off, lowercase ok",
     "iphone": True, "quote_prob": 0.2, "weight": 0.22},
    {"key": "warm_chatty", "desc": "warm and talkative, anecdotes about the dog, double exclamation marks, signs first name",
     "iphone": False, "quote_prob": 0.6, "weight": 0.24},
    {"key": "bullet_asker", "desc": "polite and organized, stacks 2-4 questions as dashes or bullets, signs first name",
     "iphone": False, "quote_prob": 0.7, "weight": 0.18},
    {"key": "formal_brief", "desc": "complete sentences, slightly formal, 2-3 sentences max, signs full name",
     "iphone": False, "quote_prob": 0.8, "weight": 0.16},
    {"key": "scattered_enthusiast", "desc": "run-on sentences, mid-thought dashes, heart for the dog shines through, signs first name with xx or !",
     "iphone": True, "quote_prob": 0.4, "weight": 0.12},
    {"key": "practical_veteran", "desc": "been-there-done-that calm, anticipates logistics, offers help to others, signs first name",
     "iphone": False, "quote_prob": 0.5, "weight": 0.08},
]

# (model, effort) mix bound per persona; cheap+low reads naturally terse.
RENDERER_MIX = [
    (("claude-haiku-5-5", "low"), 0.25),
    (("claude-haiku-5-5", "medium"), 0.20),
    (("claude-haiku-5-5", "high"), 0.15),
    (("claude-opus-5-5", "low"), 0.15),
    (("claude-opus-5-5", "medium"), 0.15),
    (("claude-opus-5-5", "high"), 0.10),
]

FREEMAIL = ["gmail.com", "gmail.com", "gmail.com", "yahoo.com", "outlook.com",
            "hotmail.com", "icloud.com", "proton.me", "aol.com"]
