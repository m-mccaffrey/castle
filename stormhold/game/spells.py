"""Spells, and the books that teach them.

You are not born knowing magic and there is no such thing as a class here.
You find or buy a tome, you read it, and if your wits and experience are up to
it the spell is yours for good. What you can cast is a record of where you have
been and what you spent your gold on.
"""

from collections import OrderedDict

# school     : for grouping in the spell book
# level      : character level needed to learn it
# int_req    : intelligence needed to learn it
# mana       : cost to cast
# rng        : range in tiles (0 = self, 1 = touch)
# dmg        : (count, sides, per_level_bonus) for attack spells
SPELLS = OrderedDict([
    # ---- Assault --------------------------------------------------------
    ("Spark",           dict(school="Assault", level=1,  int_req=9,  mana=2,  rng=6,  dmg=(1, 4, 0.5), desc="A snap of blue fire at one target.")),
    ("Frost Shard",     dict(school="Assault", level=3,  int_req=10, mana=4,  rng=7,  dmg=(1, 6, 0.6), slow=True, desc="A splinter of ice that stiffens what it strikes.")),
    ("Fire Bolt",       dict(school="Assault", level=5,  int_req=11, mana=6,  rng=8,  dmg=(2, 5, 0.8), burn=True, desc="A lance of flame. Sets the target alight.")),
    ("Lightning",       dict(school="Assault", level=8,  int_req=13, mana=9,  rng=9,  dmg=(3, 5, 1.0), pierce=True, desc="A bolt that carries on through everything in a line.")),
    ("Fireball",        dict(school="Assault", level=11, int_req=14, mana=14, rng=8,  dmg=(3, 6, 1.0), burst=1, burn=True, desc="Bursts on impact, catching everything beside it.")),
    ("Ice Storm",       dict(school="Assault", level=14, int_req=15, mana=18, rng=0,  dmg=(3, 7, 1.1), burst=3, slow=True, desc="A freezing gale on every side of you.")),
    ("Chain Lightning", dict(school="Assault", level=18, int_req=17, mana=24, rng=8,  dmg=(4, 7, 1.2), chain=3, desc="Leaps from one enemy to the next.")),
    ("Sunburst",        dict(school="Assault", level=22, int_req=19, mana=34, rng=0,  dmg=(5, 8, 1.4), burst=4, desc="A silent white flash. Undead fare worst of all.")),

    # ---- Warding --------------------------------------------------------
    ("Shield",          dict(school="Warding", level=2,  int_req=9,  mana=4,  rng=0, ac=4, dur=60, desc="Turns aside blows for a while.")),
    ("Stoneskin",       dict(school="Warding", level=7,  int_req=12, mana=9,  rng=0, ac=8, dur=45, desc="Your skin hardens. Slower, but far harder to hurt.")),
    ("Sanctuary",       dict(school="Warding", level=12, int_req=14, mana=16, rng=0, halve=True, dur=30, desc="Halves every wound taken for a short while.")),
    ("Bulwark",         dict(school="Warding", level=16, int_req=16, mana=20, rng=4, ac=6, dur=40, party=True, desc="Wards you and every companion nearby.")),

    # ---- Mending --------------------------------------------------------
    ("Mend Wounds",     dict(school="Mending", level=1,  int_req=9,  mana=4,  rng=1, heal=(2, 6, 1.0), desc="Closes cuts. Yours or a friend's.")),
    ("Cure Affliction", dict(school="Mending", level=4,  int_req=10, mana=6,  rng=1, cure=True, desc="Draws out poison and breaks a fever.")),
    ("Greater Mending", dict(school="Mending", level=9,  int_req=13, mana=12, rng=1, heal=(4, 8, 1.6), desc="Knits deep wounds closed.")),
    ("Circle of Mending", dict(school="Mending", level=15, int_req=15, mana=20, rng=4, heal=(4, 8, 1.4), party=True, desc="Heals every companion around you at once.")),
    ("Restoration",     dict(school="Mending", level=20, int_req=18, mana=30, rng=1, heal=(8, 8, 2.0), cure=True, desc="Makes a body whole again.")),

    # ---- Seeking --------------------------------------------------------
    ("Detect Life",     dict(school="Seeking", level=2,  int_req=9,  mana=3,  rng=0, detect="monsters", dur=80, desc="Shows every living thing on the floor.")),
    ("Cartography",     dict(school="Seeking", level=5,  int_req=11, mana=8,  rng=0, reveal=True, desc="The whole floor's plan, laid out in your mind.")),
    ("Revelation",      dict(school="Seeking", level=7,  int_req=12, mana=10, rng=0, identify=True, desc="Tells you truly what one thing in your pack is.")),
    ("Treasure Sense",  dict(school="Seeking", level=6,  int_req=11, mana=6,  rng=0, detect="items", dur=80, desc="Shows where the gold and the goods are lying.")),
    ("True Sight",      dict(school="Seeking", level=13, int_req=14, mana=14, rng=0, truesight=True, dur=60, desc="See in the dark, and see what is hidden.")),

    # ---- Passage --------------------------------------------------------
    ("Blink",           dict(school="Passage", level=4,  int_req=10, mana=6,  rng=0, blink=True, desc="A short hop out of trouble.")),
    ("Haste",           dict(school="Passage", level=8,  int_req=12, mana=10, rng=0, haste=True, dur=40, desc="You move at twice your usual pace.")),
    ("Featherweight",   dict(school="Passage", level=6,  int_req=11, mana=8,  rng=0, feather=True, dur=90, desc="Your burden stops mattering for a while.")),
    ("Passwall",        dict(school="Passage", level=17, int_req=16, mana=18, rng=1, passwall=True, desc="Opens a way through solid stone.")),
    ("Recall",          dict(school="Passage", level=10, int_req=13, mana=22, rng=0, recall=True, desc="Pulls you and everyone with you back to Aldershade.")),
])

SCHOOLS = ("Assault", "Warding", "Mending", "Seeking", "Passage")

BOOK_ICONS = {
    "Assault": "book_red", "Warding": "book_blue", "Mending": "book_green",
    "Seeking": "book_black", "Passage": "book_blue",
}


def spell_names():
    return list(SPELLS.keys())


def book_key_for(spell):
    return "tome"


def book_value(spell):
    """A tome costs roughly what the spell is worth knowing."""
    s = SPELLS[spell]
    return 120 + s["level"] * 95 + s["mana"] * 12


def can_learn(spell, level, intelligence):
    s = SPELLS.get(spell)
    if not s:
        return False, "That book is gibberish."
    if level < s["level"]:
        return False, f"You are not experienced enough for {spell} yet (needs level {s['level']})."
    if intelligence < s["int_req"]:
        return False, f"{spell} is beyond your wits (needs Intelligence {s['int_req']})."
    return True, ""


def spells_for_sale(depth, rng, count=5):
    """What the magic shop has on the shelf, scaled to how deep the party is."""
    pool = [n for n, s in SPELLS.items() if s["level"] <= max(3, depth + 3)]
    rng.shuffle(pool)
    return pool[:count]
