"""Items: weight, worn slots, enchantment, curses and identification.

Weight is in grams and bulk in cubic centimetres, the units the original
measures in. A coin weighs a gram, so a thousand of them weigh a kilo - which
is the whole reason the strongroom in town is worth walking to.

Nothing is identified when you find it. A potion is "a cloudy red potion" until
you drink one or pay Ulric to tell you what it is, and the appearance of each
kind is shuffled per world, so last game's knowledge is no help.
"""

import random

from ..common.constants import COPPER_GRAMS, COINS

# Copper is plentiful. Prices in the hundreds and thousands give the temple's
# services and the better gear something to bite on, and make a purse heavy
# enough that the strongroom is worth the walk.
VALUE_SCALE = 8

_next_item_id = [1]


def _new_id():
    _next_item_id[0] += 1
    return _next_item_id[0]


# --------------------------------------------------------------------------
#  Base item templates.
#    slot   : which equipment slot it occupies, if any
#    wt     : weight in grams
#    dmg    : (count, sides) melee dice
#    ac     : armour class contributed
#    depth  : shallowest floor it is generated on
# --------------------------------------------------------------------------

BASES = {
    # ---- blades ---------------------------------------------------------
    "dagger":      dict(name="Dagger", slot="weapon", icon="dagger", bulk=500, wt=500, value=20, dmg=(1, 4), depth=0, speed=80),
    "shortsword":  dict(name="Short Sword", slot="weapon", icon="shortsword", bulk=5000, wt=1000, value=50, dmg=(1, 6), depth=0, speed=90),
    "sabre":       dict(name="Sabre", slot="weapon", icon="sabre", bulk=5000, wt=1000, value=95, dmg=(1, 9), depth=3, speed=90),
    "longsword":   dict(name="Long Sword", slot="weapon", icon="longsword", bulk=8000, wt=1500, value=150, dmg=(2, 6), depth=4),
    "broadsword":  dict(name="Broad Sword", slot="weapon", icon="broadsword", bulk=9000, wt=1600, value=320, dmg=(2, 8), depth=8, str_req=13, two_handed=True, speed=105),
    # ---- hafted ---------------------------------------------------------
    "mace":        dict(name="Mace", slot="weapon", icon="mace", bulk=4375, wt=2000, value=70, dmg=(2, 4), depth=1, speed=105),
    "warhammer":   dict(name="War Hammer", slot="weapon", icon="hammer", bulk=7500, wt=1400, value=190, dmg=(2, 5), depth=6, str_req=12, speed=105),
    "axe":         dict(name="Battle Axe", slot="weapon", icon="axe", bulk=6000, wt=3000, value=230, dmg=(2, 8), depth=7, str_req=12, speed=125),
    "halberd":     dict(name="Halberd", slot="weapon", icon="halberd", bulk=36000, wt=4950, value=420, dmg=(2, 12), depth=12, str_req=15, two_handed=True, speed=140),
    "spear":       dict(name="Spear", slot="weapon", icon="spear", bulk=5000, wt=1500, value=85, dmg=(1, 10), depth=2),
    # No bows, and no arrows. The original has no missile weapon for the
    # player at all: you fight by walking into things, and everything that
    # reaches across a room is a spell. Monsters still shoot - the help file
    # has jotuns hurling boulders and a manticore flinging quills "with the
    # accuracy and effect of a company of crossbowmen" - and that is on the
    # monster side, where it belongs.
    # ---- staves and wands ------------------------------------------------
    "quarterstaff": dict(name="Quarterstaff", slot="weapon", icon="staff", bulk=25200, wt=750, value=60, dmg=(1, 5), depth=0, mana_bonus=4, speed=85),
    "runestaff":   dict(name="Rune Staff", slot="weapon", icon="staff", bulk=25200, wt=2025, value=400, dmg=(1, 7), depth=10, mana_bonus=15, speed=105),
    # Every other chargeable or consumable thing in BASES says what it is
    # with an explicit "kind" - this one did not, so item.kind fell through
    # to the "gear" default. Nothing ever checked kind == "wand" as a
    # result, including the Activate menu's own filter for what belongs on
    # it, so a wand sat in the weapon slot as a plain (and weak) dagger and
    # never came up as a thing you could zap.
    "wand":        dict(name="Wand", slot="weapon", icon="wand", bulk=2700, wt=360, value=300, dmg=(1, 3), depth=5, charges=(4, 9), recharge_hours=6, speed=80, kind="wand"),

    # ---- body armour -----------------------------------------------------
    "robe":        dict(name="Robe", slot="torso", icon="robe", bulk=12600, wt=900, value=25, ac=3, depth=0, mana_bonus=6),
    "leather":     dict(name="Suit of Leather Armour", slot="torso", icon="leather", bulk=24000, wt=5000, value=80, ac=6, depth=0),
    "studded":     dict(name="Suit of Studded Leather", slot="torso", icon="studded", bulk=25000, wt=7000, value=170, ac=12, depth=2),
    "ringmail":    dict(name="Suit of Ring Mail", slot="torso", icon="ringmail", bulk=30000, wt=8000, value=290, ac=18, depth=4, str_req=11),
    "chainmail":   dict(name="Suit of Chain Mail", slot="torso", icon="chainmail", bulk=30000, wt=10000, value=520, ac=30, depth=7, str_req=13),
    "scalemail":   dict(name="Suit of Scale Mail", slot="torso", icon="scalemail", bulk=30000, wt=9000, value=400, ac=24, depth=6, str_req=12),
    "bandedmail":  dict(name="Suit of Banded Mail", slot="torso", icon="chainmail", bulk=34000, wt=12000, value=900, ac=36, depth=11, str_req=15),
    "platemail":   dict(name="Suit of Plate Armour", slot="torso", icon="platemail", bulk=40000, wt=15000, value=1400, ac=42, depth=14, str_req=16),
    # ---- shields ---------------------------------------------------------
    "buckler":     dict(name="Buckler", slot="shield", icon="buckler", bulk=15000, wt=3000, value=45, ac=3, depth=0),
    "shield":      dict(name="Kite Shield", slot="shield", icon="shield", bulk=23400, wt=4050, value=140, ac=9, depth=3),
    "towershield": dict(name="Tower Shield", slot="shield", icon="tower", bulk=50000, wt=6000, value=390, ac=12, depth=9, str_req=14),
    # ---- the other slots -------------------------------------------------
    "cap":         dict(name="Leather Cap", slot="head", icon="cap", bulk=7200, wt=675, value=25, ac=3, depth=0),
    "helm":        dict(name="Steel Helm", slot="head", icon="helm", bulk=2000, wt=2500, value=130, ac=9, depth=4),
    "gloves":      dict(name="Leather Gloves", slot="arms", icon="gauntlets", bulk=4500, wt=450, value=20, ac=3, depth=0),
    "gauntlets":   dict(name="Gauntlets", slot="arms", icon="gauntlets", bulk=8100, wt=1575, value=110, ac=6, depth=5),
    "boots":       dict(name="Boots", slot="feet", icon="boots", bulk=10800, wt=1125, value=30, ac=3, depth=0),
    "leggings":    dict(name="Leggings", slot="legs", icon="leggings", bulk=16200, wt=2700, value=95, ac=6, depth=3),
    "cloak":       dict(name="Cloak", slot="back", icon="cloak", bulk=12600, wt=675, value=40, ac=3, depth=1),
    "belt":        dict(name="Two Slot Belt", slot="waist", icon="belt", bulk=4500, wt=450, value=35, ac=3, depth=1, kind="container", belt_slots=2, capacity=4000, bulk_capacity=8000),
    "belt3":       dict(name="Three Slot Belt", slot="waist", icon="belt", bulk=4700, wt=500, value=90, ac=3, depth=5, kind="container", belt_slots=3, capacity=6000, bulk_capacity=12000),
    "beltutil":    dict(name="Utility Belt", slot="waist", icon="belt", bulk=5200, wt=600, value=2400, ac=3, depth=14, kind="container", belt_slots=10, capacity=20000, bulk_capacity=40000),

    # ---- jewellery (always unidentified when found) ----------------------
    "ring_might":    dict(name="Ring of Might", slot="ring_left", icon="ring", bulk=900, wt=90, value=600, depth=3, kind="ring", bonus=("strength", 2)),
    "ring_grace":    dict(name="Ring of Grace", slot="ring_left", icon="ring", bulk=900, wt=90, value=600, depth=3, kind="ring", bonus=("dexterity", 2)),
    "ring_wit":      dict(name="Ring of Wit", slot="ring_left", icon="ring", bulk=900, wt=90, value=600, depth=3, kind="ring", bonus=("intelligence", 2)),
    "ring_health":   dict(name="Ring of Health", slot="ring_left", icon="ring", bulk=900, wt=90, value=650, depth=4, kind="ring", bonus=("constitution", 2)),
    "ring_warding":  dict(name="Ring of Warding", slot="ring_left", icon="ring", bulk=900, wt=90, value=800, depth=6, kind="ring", ac=9),
    "ring_burden":   dict(name="Ring of Burdens", slot="ring_left", icon="ring", bulk=900, wt=90, value=10, depth=2, kind="ring", bonus=("strength", -3), cursed=True),
    "amulet_ward":   dict(name="Amulet of Warding", slot="neck", icon="amulet", bulk=1800, wt=225, value=900, depth=7, kind="amulet", ac=12),
    "amulet_focus":  dict(name="Amulet of Focus", slot="neck", icon="amulet", bulk=1800, wt=225, value=750, depth=5, kind="amulet", mana_bonus=25),
    "amulet_vigour": dict(name="Amulet of Vigour", slot="neck", icon="amulet", bulk=1800, wt=225, value=750, depth=5, kind="amulet", hp_bonus=25),
    "amulet_doom":   dict(name="Amulet of Doom", slot="neck", icon="amulet", bulk=1800, wt=225, value=10, depth=4, kind="amulet", ac=-12, cursed=True),

    # ---- potions (appearance shuffled per world) -------------------------
    "potion_heal":    dict(name="Potion of Healing", icon="potion_red", bulk=3600, wt=675, value=19, depth=0, kind="potion", use="heal", power=30, stack=True),
    "potion_heal2":   dict(name="Potion of Great Healing", icon="potion_red", bulk=3600, wt=675, value=75, depth=7, kind="potion", use="heal", power=90, stack=True),
    "potion_mana":    dict(name="Potion of Mana", icon="potion_blue", bulk=3600, wt=675, value=22, depth=1, kind="potion", use="mana", power=30, stack=True),
    "potion_speed":   dict(name="Potion of Quickness", icon="potion_green", bulk=3600, wt=675, value=63, depth=4, kind="potion", use="haste", power=40, stack=True),
    "potion_might":   dict(name="Potion of Giant Strength", icon="potion_yellow", bulk=3600, wt=675, value=69, depth=5, kind="potion", use="might", power=40, stack=True),
    "potion_cure":    dict(name="Potion of Cleansing", icon="potion_clear", bulk=3600, wt=675, value=38, depth=3, kind="potion", use="cure", stack=True),
    "potion_sight":   dict(name="Potion of True Sight", icon="potion_purple", bulk=3600, wt=675, value=50, depth=4, kind="potion", use="sight", power=60, stack=True),
    "potion_float":   dict(name="Potion of Levitation", icon="potion_clear", bulk=3600, wt=675, value=44, depth=3, kind="potion", use="levitate", power=50, stack=True),
    "potion_poison":  dict(name="Draught of Sickness", icon="potion_green", bulk=3600, wt=675, value=10, depth=2, kind="potion", use="poison", power=12, bad=True, stack=True),

    # ---- scrolls (title shuffled per world) ------------------------------
    "scroll_map":     dict(name="Scroll of Cartography", icon="scroll", bulk=1800, wt=135, value=38, depth=1, kind="scroll", use="map", stack=True),
    "scroll_ident":   dict(name="Scroll of Revelation", icon="scroll", bulk=1800, wt=135, value=50, depth=2, kind="scroll", use="identify", stack=True),
    "scroll_teleport": dict(name="Scroll of Recall", icon="scroll", bulk=1800, wt=135, value=75, depth=3, kind="scroll", use="recall", stack=True),
    "scroll_blink":   dict(name="Scroll of Blinking", icon="scroll", bulk=1800, wt=135, value=44, depth=2, kind="scroll", use="blink", stack=True),
    "scroll_uncurse": dict(name="Scroll of Unbinding", icon="scroll", bulk=1800, wt=135, value=88, depth=5, kind="scroll", use="uncurse", stack=True),
    "scroll_enchant": dict(name="Scroll of Enchantment", icon="scroll", bulk=1800, wt=135, value=188, depth=6, kind="scroll", use="enchant", stack=True),
    "scroll_fire":    dict(name="Scroll of Conflagration", icon="scroll", bulk=1800, wt=135, value=100, depth=5, kind="scroll", use="firestorm", power=28, stack=True),
    "scroll_fear":    dict(name="Scroll of Terror", icon="scroll", bulk=1800, wt=135, value=63, depth=4, kind="scroll", use="fear", stack=True),

    # ---- tomes -----------------------------------------------------------
    # One base for every spell book. Which spell a book teaches lives on the
    # item, not on the base, so the name and price are filled in by
    # spells.make_tome. Books are never generated by key alone.
    "tome":           dict(name="Tome", icon="book_red", bulk=3600, wt=450, value=300, depth=1, kind="book"),

    # ---- sundries --------------------------------------------------------
    "gem":         dict(name="Gemstone", icon="gem", bulk=900, wt=90, value=350, depth=4, kind="treasure"),
    "bracers":     dict(name="Bracers", slot="bracers", icon="bracers", bulk=7200, wt=1125, value=55, ac=3, depth=1),
    "purse":       dict(name="Purse", slot="purse", icon="sack", bulk=500, wt=300, value=15, depth=0, kind="container", capacity=5000, bulk_capacity=6000, coins_only=True),
    "coins":       dict(name="copper pieces", icon="gold", bulk=0, wt=0, value=1, depth=0, kind="coins"),
    # The measured original sells three sizes, not one - we had been calling
    # the small one a "Backpack" and stopping there. Figures are its own:
    # `Wt | Bulk | Wt Max | Bulk Max`, read off the shop caption character
    # for character. The Large Pack's own caption also showed a non-zero
    # Bulk Fx, which would be strange on a plain pack (that effect is meant
    # for a Pack of Holding, below) and could not be cross-checked against a
    # second reading, so it is left at zero here rather than guessed at.
    "pack":        dict(name="Small Pack", slot="pack", icon="pack", bulk=1000, wt=1000, value=60, depth=0, kind="container", capacity=12000, bulk_capacity=50000),
    "packmed":     dict(name="Medium Pack", slot="pack", icon="pack", bulk=1500, wt=2000, value=150, depth=3, kind="container", capacity=22000, bulk_capacity=75000),
    "packlg":      dict(name="Large Pack", slot="pack", icon="pack", bulk=2000, wt=4000, value=320, depth=7, kind="container", capacity=35000, bulk_capacity=100000),
    "holdpack":    dict(name="Pack of Holding", slot="pack", icon="pack", bulk=1000, wt=1000, value=900, depth=9, kind="container", capacity=50000, bulk_capacity=150000, wt_fixed=5000, bulk_fixed=75000),
    # "Two slots we did not have: a Wand Quiver, and belts that are
    # containers sized in slots." A wand in the pack cannot be used; a wand in
    # the quiver can.
    "quiver":      dict(name="Wand Quiver", slot="quiver", icon="quiver", bulk=2000, wt=400, value=180, depth=5, kind="container", capacity=3000, bulk_capacity=9000, wands_only=True, belt_slots=3),
    # A bag's bulk follows what is in it; a chest's does not.
    "chest":       dict(name="Chest", slot=None, icon="chest", bulk=40000, wt=6000, value=70, depth=2, kind="container", capacity=30000, bulk_capacity=60000, bulk_fixed=40000),
    "sack":        dict(name="Sack", slot=None, icon="sack", bulk=700, wt=500, value=25, depth=0, kind="container", capacity=10000, bulk_capacity=12000),
}

# Spell books are generated from the spell list, so they live in spells.py.

# Appearances. Which description goes with which potion is decided once per
# world, so you have to learn them again every campaign.
POTION_LOOKS = [
    "cloudy red", "swirling blue", "bright green", "murky yellow",
    "violet", "silvery", "smoking black", "pale gold", "fizzing orange",
    "oily brown", "milky white", "deep crimson",
]
SCROLL_LOOKS = [
    "KHORAM VELT", "ASHEN TALLY", "OBRIN DAUGHE", "SEVEN SEVEN OAK",
    "MULLIGRUB", "TESSERAINE", "HOLLOW BELL", "QUARRENDON",
    "FIMBUL WEND", "GRIST AND GALL", "NINE OF SPARROWS", "UNDERWHELM",
]
RING_LOOKS = [
    "plain iron", "twisted silver", "jade", "obsidian", "coral",
    "engraved gold", "bone", "opal", "moonstone", "black pearl",
]
AMULET_LOOKS = ["tarnished", "octagonal", "spiral", "beaded", "wrought iron"]

ICON_BY_LOOK = {
    "cloudy red": "potion_red", "deep crimson": "potion_red",
    "swirling blue": "potion_blue", "silvery": "potion_clear",
    "milky white": "potion_clear", "bright green": "potion_green",
    "fizzing orange": "potion_yellow", "murky yellow": "potion_yellow",
    "pale gold": "potion_yellow", "violet": "potion_purple",
    "smoking black": "potion_purple", "oily brown": "potion_purple",
}


class Appearances:
    """Per-world shuffling of what unidentified things look like."""

    def __init__(self, seed):
        rng = random.Random(seed ^ 0x5EED)
        self.look = {}
        self.known = set()          # base keys the party has identified

        def assign(keys, looks):
            pool = list(looks)
            rng.shuffle(pool)
            for k, appearance in zip(keys, pool):
                self.look[k] = appearance

        assign([k for k, b in BASES.items() if b.get("kind") == "potion"], POTION_LOOKS)
        assign([k for k, b in BASES.items() if b.get("kind") == "scroll"], SCROLL_LOOKS)
        assign([k for k, b in BASES.items() if b.get("kind") == "ring"], RING_LOOKS)
        assign([k for k, b in BASES.items() if b.get("kind") == "amulet"], AMULET_LOOKS)

    def identify(self, key):
        self.known.add(key)

    def is_known(self, key):
        return key in self.known

    def icon_for(self, key, base):
        """Unidentified potions show the colour you actually see."""
        if base.get("kind") == "potion" and not self.is_known(key):
            return ICON_BY_LOOK.get(self.look.get(key, ""), "potion_clear")
        return base["icon"]

    def describe(self, key, base):
        kind = base.get("kind")
        look = self.look.get(key)
        if kind == "potion":
            return f"{article(look)} {look} potion"
        if kind == "scroll":
            return f'a scroll headed "{look}"'
        if kind == "ring":
            return f"{article(look)} {look} ring"
        if kind == "amulet":
            return f"{article(look)} {look} amulet"
        return base["name"]


# The original grades gear in its name: "Broken, Ripped, Rusty, Normal,
# Enchanted, Cursed". The first three are what a negative enchantment looks
# like, and which one you get depends on what the thing is made of.
DAMAGED = {
    "cloth": "Ripped", "leather": "Ripped",
    "metal": "Rusty", "wood": "Broken",
}
MATERIAL = {
    "robe": "cloth", "cloak": "cloth",
    "leather": "leather", "studded": "leather", "cap": "leather",
    "gloves": "leather", "boots": "leather", "leggings": "leather",
    "belt": "leather", "belt3": "leather", "beltutil": "leather",
    "buckler": "wood", "shield": "wood", "quarterstaff": "wood",
    "runestaff": "wood", "wand": "wood",
}


def damaged_prefix(key, base):
    """What a battered one of these is called."""
    material = MATERIAL.get(key)
    if material is None:
        material = "metal"                # mail, plate, blades, hafted
    return DAMAGED[material]


def magnitude(amount):
    """The adverb a property sentence opens its verb with, by size.

    The manual's own worked examples ("adds +2...") give no numeric bands,
    but the game's own vocabulary for a bigger effect is right there in the
    binary's string table alongside the plain wording - "makes the
    character strongly resistant", next to the unmodified "resistant" -
    and separately "greatly "/"very " sit next to the plain stat-increase
    template. The exact original cutoffs aren't recoverable from that
    table alone, so these bands are our own placement of that real
    vocabulary, not a sourced threshold.
    """
    amount = abs(amount)
    if amount >= 5:
        return "greatly "
    if amount >= 3:
        return "strongly "
    return ""


def article(word):
    """a or an, depending on how the next word starts."""
    return "an" if word[:1].lower() in "aeiou" else "a"


def with_article(name):
    """"a Normal Dagger", but "Gauntlets" and "3 Potions of Healing".

    Names that already begin with a count, and names of things that are
    grammatically plural - bracers, boots, gauntlets, leggings - take no
    article at all.
    """
    if not name:
        return name
    if name[:1].isdigit():
        return name
    first = name.split()[0].lower()
    if first in ("a", "an", "the"):
        return name          # an unidentified thing describes itself already
    last = name.split()[-1].lower().strip('.,!"')
    if last.endswith("s") and not last.endswith("ss"):
        return name
    return f"{article(name)} {name}"


def pluralise(label, qty):
    """Two Potions of Healing, not two Potion of Healings."""
    if qty <= 1:
        return label
    if " of " in label:
        head, _, tail = label.partition(" of ")
        return f"{pluralise(head, qty)} of {tail}"
    lower = label.lower()
    if lower.endswith(("s", "x", "z", "ch", "sh")):
        return label + "es"
    if lower.endswith("y") and not lower.endswith(("ay", "ey", "oy", "uy")):
        return label[:-1] + "ies"
    return label + "s"


class Item:
    """One concrete object in the world."""

    __slots__ = ("id", "key", "base", "enchant", "cursed", "known", "qty",
                 "charges", "contents", "spell", "gold_amount", "metal",
                 "recharge_at", "custom_name")

    def __init__(self, key, enchant=0, cursed=False, qty=1, charges=0, spell=None):
        self.id = _new_id()
        self.key = key
        self.base = BASES.get(key) or {}
        self.enchant = enchant
        self.cursed = cursed
        self.known = False          # has THIS item's enchantment been revealed
        self.qty = qty
        self.charges = charges
        self.recharge_at = None
        self.contents = [] if self.base.get("kind") == "container" else None
        self.spell = spell          # for spell books
        self.gold_amount = 0        # value in copper, on a pile of coins
        self.metal = "copper"       # what that pile is actually made of
        self.custom_name = None     # whatever the player chose to call it

    # ------------------------------------------------------------ queries --
    @property
    def slot(self):
        return self.base.get("slot")

    @property
    def kind(self):
        return self.base.get("kind", "gear")

    @property
    def stackable(self):
        return bool(self.base.get("stack"))

    @property
    def bulk(self):
        fixed = self.base.get("bulk_fixed")
        if fixed:
            return fixed
        """How much room it takes up, as opposed to how much it weighs."""
        if self.kind == "coins":
            return max(0, self.gold_amount // 400)
        b = self.base.get("bulk", 5) * max(1, self.qty)
        if self.contents:
            # A full pack is bulkier than an empty one, but it packs down:
            # what is inside counts for half.
            b += sum(i.bulk for i in self.contents) // 2
        return b

    @property
    def weight(self):
        """What this weighs to whatever is carrying it.

        A magical container reports a fixed figure instead of its contents.
        The original's manual: "If non-zero, the Wt. Fx and Bulk Fx columns are
        used instead of the sum of the contents (plus whatever intrinsic weight
        and bulk the container has) in calculating the value reported to the
        parent." So a pack of holding weighs the same full as it does empty.
        """
        if self.kind == "coins":
            # every coin weighs a gram, so a pile's weight is how many coins
            # it is, not what it is worth
            worth = dict(COINS)[self.metal]
            return (self.gold_amount // worth) * COPPER_GRAMS
        fixed = self.base.get("wt_fixed")
        if fixed:
            return fixed
        w = self.base.get("wt", 10) * max(1, self.qty)
        if self.contents:
            w += sum(i.weight for i in self.contents)
        return w

    def value(self, appearances=None):
        if self.kind == "coins":
            return max(1, self.gold_amount)
        v = self.base.get("value", 10) * VALUE_SCALE * max(1, self.qty)
        v += self.enchant * 900
        if self.cursed:
            v = max(1, v // 8)
        return max(1, int(v))

    def damage(self):
        return self.base.get("dmg", (1, 2))

    def ac(self):
        return self.base.get("ac", 0) + self.enchant

    def to_hit(self):
        return self.enchant

    def name(self, appearances=None, shop=False):
        """What to call it, given what the party knows."""
        if self.custom_name and not shop:
            # Their words, not ours: never try to pluralise a chosen name.
            return (f"{self.qty} x {self.custom_name}" if self.qty > 1
                    else self.custom_name)
        base = self.base
        identified = shop or appearances is None or appearances.is_known(self.key)
        if not identified and base.get("kind") in ("potion", "scroll", "ring", "amulet"):
            label = appearances.describe(self.key, base)
            return f"{self.qty} {pluralise(label, self.qty)}" if self.qty > 1 else label

        if self.kind == "coins":
            return f"{self.gold_amount} copper"
        label = base.get("name", self.key)
        if self.spell:
            label = f"Tome of {self.spell}"
        prefix = ""
        # Only gear carries an enchantment; a potion is never "+2". The
        # manual is explicit that the *name* only ever says which grade a
        # thing is - "the name will also indicate if the object is
        # Enchanted or Cursed" - never the number. A raw "+2 Long Sword"
        # was never what the original showed; the +2 itself belongs in the
        # identified description (see describe()), not the name. Any
        # equippable, non-container item grades this way, not only the
        # ones with a damage die or an armour value - a Ring of Might
        # carries the same Normal/Enchanted/Cursed word a sword does.
        gradeable = base.get("slot") and base.get("kind") != "container"
        if gradeable:
            if self.known or shop:
                if self.cursed:
                    prefix = "Cursed "
                elif self.enchant < 0:
                    prefix = f"{damaged_prefix(self.key, base)} "
                elif self.enchant > 0:
                    prefix = "Enchanted "
                else:
                    prefix = "Normal "
            elif self.enchant or self.cursed:
                prefix = "Enchanted "     # magical, but you cannot read it yet
            else:
                prefix = "Normal "
        # "A spent wand becomes a Dead Wand."
        if base.get("charges") and self.known and self.charges <= 0:
            label = f"Dead {label}"
        out = f"{prefix}{label}"
        if self.qty > 1:
            out = f"{self.qty} {pluralise(out, self.qty)}"
        if self.charges and self.known:
            out += f" ({self.charges} charges)"
        return out

    def is_glowing(self, shop=False):
        """Whether the icon should carry the enchanted glow.

        Mirrors the "Enchanted " branch of name() exactly: gear that has
        been identified (or is sitting in a shop, already labelled) as
        genuinely beneficially magical, as opposed to cursed, damaged, or
        merely mundane. Cursed and damaged gear looks the same as it
        always did - the glow is a promise, not a warning.
        """
        base = self.base
        gradeable = base.get("slot") and base.get("kind") != "container"
        if not gradeable:
            return False
        return (self.known or shop) and not self.cursed and self.enchant > 0

    def describe(self, appearances=None):
        """The detail line shown when an item is selected.

        Anything still unidentified gives away nothing but its weight - the
        whole point of paying Ulric is that you cannot read it off the label.
        """
        b = self.base
        hidden = (appearances is not None
                  and b.get("kind") in ("potion", "scroll", "ring", "amulet")
                  and not appearances.is_known(self.key))
        if hidden:
            return f"unidentified, {self.weight} g, bulk {self.bulk} cc"

        # A ring or amulet's armour value is a magical property, learned
        # only on identification, the same as its stat bonus would be; a
        # suit of armour's is a plain physical fact, visible on sight.
        is_accessory = b.get("kind") in ("ring", "amulet")
        bits = []
        if b.get("dmg"):
            n, s = b["dmg"]
            bits.append(f"{n}d{s} damage")
        if b.get("ac") and not is_accessory:
            bits.append(f"{b['ac']} armour")
        speed = b.get("speed")
        if b.get("dmg") and speed and speed != 100:
            # Otherwise the heaviest weapon in the game looks like a pure
            # upgrade on the label and is a third slower in the hand.
            bits.append(f"{'slow' if speed > 100 else 'quick'} to swing "
                        f"({speed}%)")
        if b.get("str_req"):
            bits.append(f"needs Strength {b['str_req']}")
        if b.get("capacity"):
            bits.append(f"holds {b['capacity'] / 1000:.0f} kg")
        bits.append(f"{self.weight} g")
        bits.append(f"bulk {self.bulk}")

        # "Each property description has three parts: 1. What you have to
        # do to the object for the property to apply ... 2. What it does
        # ... 3. How long it lasts" - down to the wording: an "Amulet of
        # Resist Fire" reads "When wielded, makes the character more
        # resistant to fire, until removed." Weapons, armour and amulets
        # are wielded; potions, scrolls and wands are activated. Every
        # property a worn thing can carry lasts only "until removed" - it
        # is the wearing that makes it work.
        verb = "activated" if b.get("kind") in ("potion", "scroll", "wand") else "wielded"
        props = []
        if b.get("ac") and is_accessory:
            props.append(f"When {verb}, {magnitude(b['ac'])}adds {b['ac']:+d} "
                         f"to your Armor Value, until removed.")
        if b.get("bonus"):
            stat, amount = b["bonus"]
            props.append(f"When {verb}, {magnitude(amount)}adds {amount:+d} "
                         f"to your {stat.title()}, until removed.")
        if b.get("hp_bonus"):
            props.append(f"When {verb}, {magnitude(b['hp_bonus'])}adds "
                         f"{b['hp_bonus']:+d} to your maximum hit points, "
                         f"until removed.")
        if b.get("mana_bonus"):
            props.append(f"When {verb}, {magnitude(b['mana_bonus'])}adds "
                         f"{b['mana_bonus']:+d} to your maximum mana, "
                         f"until removed.")
        if self.known and self.enchant:
            if b.get("dmg"):
                props.append(f"When wielded, {magnitude(self.enchant)}adds "
                             f"{self.enchant:+d} to your chance to hit and "
                             f"to damage, until removed.")
            else:
                props.append(f"When wielded, {magnitude(self.enchant)}adds "
                             f"{self.enchant:+d} to your Armor Value, "
                             f"until removed.")

        out = ", ".join(bits)
        if props:
            out += ". " + " ".join(props)
        return out

    # --------------------------------------------------------------- data --
    def to_dict(self):
        return {"id": self.id, "key": self.key, "e": self.enchant, "g": self.gold_amount,
                "c": self.cursed, "k": self.known, "q": self.qty,
                "ch": self.charges, "sp": self.spell, "cn": self.custom_name,
                "in": [i.to_dict() for i in self.contents] if self.contents else None}

    @staticmethod
    def from_dict(d):
        it = Item(d["key"], d.get("e", 0), d.get("c", False),
                  d.get("q", 1), d.get("ch", 0), d.get("sp"))
        it.id = d.get("id", it.id)
        it.known = d.get("k", False)
        it.gold_amount = d.get("g", 0)
        it.custom_name = d.get("cn")
        if d.get("in"):
            it.contents = [Item.from_dict(x) for x in d["in"]]
        return it


# --------------------------------------------------------------- generation -

# Spell books are not drawn from the base table - a bare "tome" teaches
# nothing - so they are rolled for separately, before the table is consulted.
BOOK_CHANCE = 0.05


def _eligible(depth, rng, kinds=None):
    out = []
    for key, b in BASES.items():
        if key == "tome":
            continue            # only ever made by spells.make_tome
        if b.get("depth", 0) > depth + 2:
            continue
        if kinds and b.get("kind", "gear") not in kinds:
            continue
        gap = depth - b.get("depth", 0)
        weight = 0.5 if gap < 0 else 1.0 / (1.0 + gap * 0.5)
        out.append((key, weight))
    return out


def _weighted(rng, pairs):
    total = sum(w for _, w in pairs)
    r = rng.random() * total
    for value, w in pairs:
        r -= w
        if r <= 0:
            return value
    return pairs[-1][0]


def roll_enchantment(depth, rng):
    """Most things are plain. Some are blessed. A few will bite you."""
    roll = rng.random()
    if roll < 0.06 + depth * 0.004:
        return -rng.randint(1, 3), True             # cursed
    if roll < 0.30 + depth * 0.012:
        # +5 is the best the written floors produce. Below them the smiths
        # of the deep keep going, a point per ten floors, so that a character
        # who lives down there has something left to find.
        best = 1 + min(4, depth // 5) + max(0, (depth - 25) // 10)
        return rng.randint(1, best), False
    return 0, False


def generate_item(depth, rng, rich=False, kinds=None):
    # Character creation tells the player "you learn magic from books you find
    # or buy", and until now the keep never dropped one: the only books in the
    # world were the four on the magic shop's shelf. Spell damage is the only
    # damage that grows with character level, so a party that cannot find
    # books cannot keep up with the deep floors.
    if kinds is None and rng.random() < BOOK_CHANCE:
        from .spells import make_tome, spells_for_sale
        return make_tome(spells_for_sale(depth, rng, 1)[0])

    pool = _eligible(depth, rng, kinds)
    if not pool:
        return Item("sack")
    key = _weighted(rng, pool)
    base = BASES[key]

    if base.get("stack"):
        qty = rng.randint(3, 14) if base.get("ammo") else rng.randint(1, 3)
        return Item(key, qty=qty)
    if base.get("charges"):
        lo, hi = base["charges"]
        return Item(key, charges=rng.randint(lo, hi))

    enchant, cursed = 0, False
    if base.get("slot"):
        enchant, cursed = roll_enchantment(depth + (5 if rich else 0), rng)
    if base.get("cursed"):
        cursed = True
    return Item(key, enchant=enchant, cursed=cursed)


def generate_gold(depth, rng):
    """A single find early on is a few hundred copper, not a handful."""
    return rng.randint(10 + depth * 6, 40 + depth * 22) * 12


# Which metals turn up at which depth. Deep finds come in better coin, which
# is the point: the same fortune weighs a thousandth as much in platinum, and
# every coin weighs a gram whatever it is made of.
COIN_DEPTHS = ((0, ("copper",)),
               (3, ("copper", "silver")),
               (8, ("silver", "gold")),
               (14, ("gold", "platinum")),
               (20, ("platinum",)))


def coin_metal(depth, rng):
    choices = COIN_DEPTHS[0][1]
    for floor, metals in COIN_DEPTHS:
        if depth >= floor:
            choices = metals
    return rng.choice(choices)
