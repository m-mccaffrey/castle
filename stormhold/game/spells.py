"""Spells, and the books that teach them.

You are not born knowing magic and there is no such thing as a class here.
You find or buy a tome, you read it, and if your wits and experience are up to
it the spell is yours for good. What you can cast is a record of where you have
been and what you spent your gold on.
"""

from collections import OrderedDict

from ..common.constants import (CAST_SECONDS, CAST_SECONDS_SLOW,
                                INTERRUPTIBLE_FROM_SECONDS, TICKS_PER_SECOND)

# school     : for grouping in the spell book
# level      : character level needed to learn it
# int_req    : intelligence needed to learn it
# mana       : cost to cast
# rng        : range in tiles (0 = self, 1 = touch)
# dmg        : (count, sides, per_level_bonus) for attack spells
SPELLS = OrderedDict([
    # ---- Assault --------------------------------------------------------
    ("Spark",           dict(school="Attack", level=1,  int_req=9,  mana=2,  rng=6,  dmg=(1, 4, 0.5), desc="A snap of blue fire at one target.")),
    ("Frost Shard",     dict(school="Attack", level=3,  int_req=10, mana=4,  rng=7,  dmg=(1, 6, 0.6), slow=True, desc="A splinter of ice that stiffens what it strikes.")),
    ("Fire Bolt",       dict(school="Attack", level=5,  int_req=11, mana=6,  rng=8,  dmg=(2, 5, 0.8), burn=True, desc="A lance of flame. Sets the target alight.")),
    ("Lightning",       dict(school="Attack", level=8,  int_req=13, mana=9,  rng=9,  dmg=(3, 5, 1.0), pierce=True, desc="A bolt that carries on through everything in a line.")),
    ("Fireball",        dict(school="Attack", level=11, int_req=14, mana=14, rng=8,  dmg=(3, 6, 1.0), burst=1, burn=True, desc="Bursts on impact, catching everything beside it.")),
    ("Ice Storm",       dict(school="Attack", level=14, int_req=15, mana=18, rng=0,  dmg=(3, 7, 1.1), burst=3, slow=True, desc="A freezing gale on every side of you.")),
    ("Lull",            dict(school="Miscellaneous", level=6, int_req=12, mana=4, rng=7, sleep=600, desc="One creature sleeps, until something wakes it.")),
    ("Reshape",         dict(school="Miscellaneous", level=16, int_req=16, mana=6, rng=6, transmogrify=True, desc="Turns one creature into another. Could go either way.")),
    ("Chain Lightning", dict(school="Attack", level=18, int_req=17, mana=24, rng=8,  dmg=(4, 7, 1.2), chain=3, desc="Leaps from one enemy to the next.")),
    ("Sunburst",        dict(school="Attack", level=22, int_req=19, mana=34, rng=0,  dmg=(5, 8, 1.4), burst=4, desc="A silent white flash. Undead fare worst of all.")),

    # ---- Warding --------------------------------------------------------
    ("Shield",          dict(school="Defense", level=2,  int_req=9,  mana=4,  rng=0, ac=4, dur=60, desc="Turns aside blows for a while.")),
    ("Stoneskin",       dict(school="Defense", level=7,  int_req=12, mana=9,  rng=0, ac=8, dur=45, desc="Your skin hardens. Slower, but far harder to hurt.")),
    ("Sanctuary",       dict(school="Defense", level=12, int_req=14, mana=16, rng=0, halve=True, dur=30, desc="Halves every wound taken for a short while.")),
    # The original's three resistances, level 3 and 3 mana each. They halve
    # damage of their element and stack: two castings take dragon breath to a
    # quarter. Without these a breath weapon is simply a death sentence.
    ("Ward Fire",       dict(school="Defense", level=5,  int_req=11, mana=3, rng=0, resist="fire",      dur=90, desc="Flame washes over you and does half what it should.")),
    ("Ward Frost",      dict(school="Defense", level=5,  int_req=11, mana=3, rng=0, resist="cold",      dur=90, desc="Cold bites at half its strength.")),
    ("Ward Storm",      dict(school="Defense", level=5,  int_req=11, mana=3, rng=0, resist="lightning", dur=90, desc="Lightning finds you a poor conductor.")),
    ("Bulwark",         dict(school="Defense", level=16, int_req=16, mana=20, rng=4, ac=6, dur=40, party=True, desc="Wards you and every companion nearby.")),

    # ---- Mending --------------------------------------------------------
    ("Mend Wounds",     dict(school="Healing", level=1,  int_req=9,  mana=4,  rng=1, heal_flat=8, heal_frac=0.20, desc="Closes cuts. Yours or a friend's.")),
    ("Cure Affliction", dict(school="Healing", level=4,  int_req=10, mana=6,  rng=1, cure=True, desc="Draws out poison and breaks a fever.")),
    ("Greater Mending", dict(school="Healing", level=9,  int_req=13, mana=12, rng=1, heal_flat=16, heal_frac=0.40, desc="Knits deep wounds closed.")),
    ("Circle of Mending", dict(school="Healing", level=15, int_req=15, mana=20, rng=4, heal_flat=24, heal_frac=0.60, party=True, desc="Heals every companion around you at once.")),
    ("Restoration",     dict(school="Healing", level=20, int_req=18, mana=30, rng=1, heal_full=True, cure=True, desc="Makes a body whole again.")),

    # ---- Seeking --------------------------------------------------------
    ("Detect Life",     dict(school="Divination", level=2,  int_req=9,  mana=3,  rng=0, detect="monsters", dur=80, desc="Shows every living thing on the floor.")),
    ("Cartography",     dict(school="Divination", level=5,  int_req=11, mana=8,  rng=0, reveal=True, desc="The whole floor's plan, laid out in your mind.")),
    ("Revelation",      dict(school="Divination", level=7,  int_req=12, mana=10, rng=0, identify=True, desc="Tells you truly what one thing in your pack is.")),
    # "Clairvoyance ... maps a 10 by 10 area around you, and shows secret
    # doors and traps in it" - a near view that tells you more than the far
    # one does.
    ("Clairvoyance",    dict(school="Divination", level=4,  int_req=10, mana=5,  rng=0, clairvoyance=10, desc="The ground around you, and what is hidden in it.")),
    # "Detect Traps is certain within ten squares and falls off beyond."
    ("Detect Traps",    dict(school="Divination", level=3,  int_req=10, mana=4,  rng=0, find_traps=10, desc="Every trap nearby, and a chance at the far ones.")),
    ("Treasure Sense",  dict(school="Divination", level=6,  int_req=11, mana=6,  rng=0, detect="items", dur=80, desc="Shows where the gold and the goods are lying.")),
    ("True Sight",      dict(school="Divination", level=13, int_req=14, mana=14, rng=0, truesight=True, dur=60, desc="See in the dark, and see what is hidden.")),

    # ---- Passage --------------------------------------------------------
    ("Blink",           dict(school="Movement", level=4,  int_req=10, mana=6,  rng=0, blink=(5, 10), desc="A short hop out of trouble.")),
    ("Haste",           dict(school="Movement", level=8,  int_req=12, mana=10, rng=0, haste=True, dur=40, desc="You move at twice your usual pace.")),
    ("Lantern",         dict(school="Miscellaneous", level=1, int_req=9, mana=1, rng=6, light=True, desc="Light. A corridor gets a pool of it; a room gets all of it.")),
    ("Featherweight",   dict(school="Miscellaneous", level=6,  int_req=11, mana=8,  rng=0, feather=True, dur=90, desc="Your burden stops mattering for a while.")),
    ("Farstep",         dict(school="Movement", level=10, int_req=13, mana=10, rng=0, blink=(10, 40), desc="A long jump, and no saying exactly where you land.")),
    ("Passwall",        dict(school="Miscellaneous", level=17, int_req=16, mana=18, rng=1, passwall=True, desc="Opens a way through solid stone.")),
    ("Recall",          dict(school="Movement", level=10, int_req=13, mana=22, rng=0, recall=True, desc="Pulls you and everyone with you back to Aldershade.")),
])

SCHOOLS = ("Attack", "Defense", "Healing", "Movement",
           "Divination", "Miscellaneous")

BOOK_ICONS = {
    "Attack": "book_red", "Defense": "book_blue", "Healing": "book_green",
    "Divination": "book_black", "Movement": "book_blue",
    "Miscellaneous": "book_black",
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


# Casting time. The original varies it by what the spell does rather than by
# how strong it is: "In general, attack spells are fast, but divination spells
# are slow." Identify and Remove Curse are its two 60-second spells, and
# anything from 30 seconds up can be interrupted.
# Revelation is our Identify; it is the one that takes a full minute.
_SLOW_SPELLS = ("Revelation",)

for _name, _s in SPELLS.items():
    _secs = CAST_SECONDS_SLOW if _name in _SLOW_SPELLS else \
        CAST_SECONDS.get(_s["school"], 5)
    _s["cast_seconds"] = _secs
    _s["cast_ticks"] = _secs * TICKS_PER_SECOND
    _s["interruptible"] = _secs >= INTERRUPTIBLE_FROM_SECONDS


# Which element each attack spell belongs to. The original's rule is symmetric:
# a creature built of an element takes only partial damage from it, and extra
# damage from its opposite - "fire-using creatures will take extra damage from
# the [cold] bolt, but cold-using creatures will take only partial damage".
ELEMENT_OF = {"Spark": "lightning", "Frost Shard": "cold", "Fire Bolt": "fire",
              "Lightning": "lightning", "Fireball": "fire", "Ice Storm": "cold",
              "Chain Lightning": "lightning"}
OPPOSITE = {"fire": "cold", "cold": "fire"}
RESIST_FACTOR = 0.5          # a creature of that element takes half
VULNERABLE_FACTOR = 1.5      # its opposite takes half again

for _n, _e in ELEMENT_OF.items():
    if _n in SPELLS:
        SPELLS[_n]["element"] = _e


def elemental_factor(element, monster_tpl):
    """Damage multiplier for an elemental attack against this creature."""
    if not element:
        return 1.0
    if element in (monster_tpl.get("immune") or ()):
        return 0.0          # "totally immune to the deepest cold"
    kin = monster_tpl.get("element")
    if kin == element:
        return RESIST_FACTOR
    if kin and OPPOSITE.get(kin) == element:
        return VULNERABLE_FACTOR
    return 1.0


# The original's character creation ends with "choose a starting spell" and a
# list of exactly six: Heal Minor Wounds, Detect Objects, Light, Magic Arrow,
# Phase Door and Shield - one of each school a beginner might want. These are
# ours, in the same order and the same roles. The level requirement is waived
# for the one you start with, exactly as it must be in the original: Phase
# Door is not a first-level spell there either.
STARTING_SPELLS = ("Mend Wounds", "Treasure Sense", "Lantern",
                   "Spark", "Blink", "Shield")


def starting_spell(name):
    """The chosen spell, or the first of the six if the choice was nonsense."""
    return name if name in STARTING_SPELLS else STARTING_SPELLS[0]
