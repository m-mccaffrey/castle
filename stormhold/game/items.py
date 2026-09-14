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
    "shortsword":  dict(name="Short Sword", slot="weapon", icon="shortsword", bulk=5000, wt=1000, value=50, dmg=(1, 6), depth=0),
    "sabre":       dict(name="Sabre", slot="weapon", icon="sabre", bulk=5000, wt=1000, value=95, dmg=(1, 8), depth=3, speed=90),
    "longsword":   dict(name="Long Sword", slot="weapon", icon="longsword", bulk=8000, wt=1500, value=150, dmg=(2, 4), depth=4),
    "broadsword":  dict(name="Broad Sword", slot="weapon", icon="broadsword", bulk=9000, wt=1600, value=320, dmg=(2, 6), depth=8, str_req=13),
    # ---- hafted ---------------------------------------------------------
    "mace":        dict(name="Mace", slot="weapon", icon="mace", bulk=4375, wt=2500, value=70, dmg=(1, 7), depth=1),
    "warhammer":   dict(name="War Hammer", slot="weapon", icon="hammer", bulk=7500, wt=1400, value=190, dmg=(2, 5), depth=6, str_req=12),
    "axe":         dict(name="Battle Axe", slot="weapon", icon="axe", bulk=6000, wt=3000, value=230, dmg=(1, 10), depth=7, str_req=12),
    "halberd":     dict(name="Halberd", slot="weapon", icon="halberd", bulk=36000, wt=4950, value=420, dmg=(2, 8), depth=12, str_req=15),
    "spear":       dict(name="Spear", slot="weapon", icon="spear", bulk=5000, wt=1500, value=85, dmg=(1, 8), depth=2),
    # ---- missile --------------------------------------------------------
    "shortbow":    dict(name="Short Bow", slot="weapon", icon="bow", bulk=18000, wt=1125, value=90, dmg=(1, 6), depth=1, missile="arrow", rng=7),
    "longbow":     dict(name="Long Bow", slot="weapon", icon="bow", bulk=27000, wt=1800, value=260, dmg=(1, 9), depth=6, missile="arrow", rng=9, str_req=12),
    "crossbow":    dict(name="Crossbow", slot="weapon", icon="crossbow", bulk=23400, wt=3150, value=380, dmg=(2, 6), depth=9, missile="bolt", rng=8, speed=140),
    "arrow":       dict(name="Arrow", icon="arrows", bulk=900, wt=45, value=2, depth=0, stack=True, ammo="arrow"),
    "bolt":        dict(name="Quarrel", icon="arrows", bulk=900, wt=90, value=3, depth=6, stack=True, ammo="bolt"),
    # ---- staves and wands ------------------------------------------------
    "quarterstaff": dict(name="Quarterstaff", slot="weapon", icon="staff", bulk=25200, wt=1800, value=60, dmg=(1, 6), depth=0, mana_bonus=4),
    "runestaff":   dict(name="Rune Staff", slot="weapon", icon="staff", bulk=25200, wt=2025, value=400, dmg=(1, 7), depth=10, mana_bonus=15),
    "wand":        dict(name="Wand", slot="weapon", icon="wand", bulk=2700, wt=360, value=300, dmg=(1, 3), depth=5, charges=(4, 9), recharge_hours=6),

    # ---- body armour -----------------------------------------------------
    "robe":        dict(name="Robe", slot="torso", icon="robe", bulk=12600, wt=900, value=25, ac=3, depth=0, mana_bonus=6),
    "leather":     dict(name="Leather Armour", slot="torso", icon="leather", bulk=24000, wt=5000, value=80, ac=6, depth=0),
    "studded":     dict(name="Studded Leather", slot="torso", icon="studded", bulk=25000, wt=7000, value=170, ac=12, depth=2),
    "ringmail":    dict(name="Ring Mail", slot="torso", icon="ringmail", bulk=30000, wt=8000, value=290, ac=18, depth=4, str_req=11),
    "chainmail":   dict(name="Chain Mail", slot="torso", icon="chainmail", bulk=30000, wt=10000, value=520, ac=30, depth=7, str_req=13),
    "scalemail":   dict(name="Scale Mail", slot="torso", icon="scalemail", bulk=30000, wt=9000, value=760, ac=24, depth=10, str_req=14),
    "platemail":   dict(name="Plate Armour", slot="torso", icon="platemail", bulk=40000, wt=15000, value=1400, ac=42, depth=14, str_req=16),
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
    "potion_heal":    dict(name="Potion of Healing", icon="potion_red", bulk=3600, wt=675, value=60, depth=0, kind="potion", use="heal", power=30),
    "potion_heal2":   dict(name="Potion of Great Healing", icon="potion_red", bulk=3600, wt=675, value=180, depth=7, kind="potion", use="heal", power=90),
    "potion_mana":    dict(name="Potion of Mana", icon="potion_blue", bulk=3600, wt=675, value=70, depth=1, kind="potion", use="mana", power=30),
    "potion_speed":   dict(name="Potion of Quickness", icon="potion_green", bulk=3600, wt=675, value=140, depth=4, kind="potion", use="haste", power=40),
    "potion_might":   dict(name="Potion of Giant Strength", icon="potion_yellow", bulk=3600, wt=675, value=160, depth=5, kind="potion", use="might", power=40),
    "potion_cure":    dict(name="Potion of Cleansing", icon="potion_clear", bulk=3600, wt=675, value=90, depth=3, kind="potion", use="cure"),
    "potion_sight":   dict(name="Potion of True Sight", icon="potion_purple", bulk=3600, wt=675, value=110, depth=4, kind="potion", use="sight", power=60),
    "potion_poison":  dict(name="Draught of Sickness", icon="potion_green", bulk=3600, wt=675, value=10, depth=2, kind="potion", use="poison", power=12, bad=True),

    # ---- scrolls (title shuffled per world) ------------------------------
    "scroll_map":     dict(name="Scroll of Cartography", icon="scroll", bulk=1800, wt=135, value=90, depth=1, kind="scroll", use="map"),
    "scroll_ident":   dict(name="Scroll of Revelation", icon="scroll", bulk=1800, wt=135, value=120, depth=2, kind="scroll", use="identify"),
    "scroll_teleport": dict(name="Scroll of Recall", icon="scroll", bulk=1800, wt=135, value=180, depth=3, kind="scroll", use="recall"),
    "scroll_blink":   dict(name="Scroll of Blinking", icon="scroll", bulk=1800, wt=135, value=100, depth=2, kind="scroll", use="blink"),
    "scroll_uncurse": dict(name="Scroll of Unbinding", icon="scroll", bulk=1800, wt=135, value=200, depth=5, kind="scroll", use="uncurse"),
    "scroll_enchant": dict(name="Scroll of Enchantment", icon="scroll", bulk=1800, wt=135, value=400, depth=6, kind="scroll", use="enchant"),
    "scroll_fire":    dict(name="Scroll of Conflagration", icon="scroll", bulk=1800, wt=135, value=220, depth=5, kind="scroll", use="firestorm", power=28),
    "scroll_fear":    dict(name="Scroll of Terror", icon="scroll", bulk=1800, wt=135, value=150, depth=4, kind="scroll", use="fear"),

    # ---- sundries --------------------------------------------------------
    "food":        dict(name="Ration", icon="food", bulk=5400, wt=900, value=15, depth=0, kind="food", stack=True),
    "torch":       dict(name="Torch", icon="torch", bulk=5400, wt=675, value=10, depth=0, kind="light", stack=True, light=1),
    "lantern":     dict(name="Lantern", icon="lantern", bulk=12600, wt=1800, value=250, depth=3, kind="light", light=3),
    "gem":         dict(name="Gemstone", icon="gem", bulk=900, wt=90, value=350, depth=4, kind="treasure"),
    "bracers":     dict(name="Bracers", slot="bracers", icon="bracers", bulk=7200, wt=1125, value=55, ac=3, depth=1),
    "purse":       dict(name="Purse", slot="purse", icon="sack", bulk=500, wt=300, value=15, depth=0, kind="container", capacity=5000, bulk_capacity=6000, coins_only=True),
    "coins":       dict(name="copper pieces", icon="gold", bulk=0, wt=0, value=1, depth=0, kind="coins"),
    "pack":        dict(name="Backpack", slot="pack", icon="pack", bulk=1000, wt=1000, value=60, depth=0, kind="container", capacity=12000, bulk_capacity=50000),
    "holdpack":    dict(name="Pack of Holding", slot="pack", icon="pack", bulk=1000, wt=1000, value=900, depth=9, kind="container", capacity=50000, bulk_capacity=150000, wt_fixed=5000, bulk_fixed=75000),
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


def article(word):
    """a or an, depending on how the next word starts."""
    return "an" if word[:1].lower() in "aeiou" else "a"


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
        # Only gear carries an enchantment; a potion is never "+2".
        if (self.known or shop) and base.get("slot"):
            if self.cursed and self.enchant <= 0:
                prefix = f"cursed {self.enchant:+d} " if self.enchant else "cursed "
            elif self.enchant:
                prefix = f"{self.enchant:+d} "
        elif self.enchant or self.cursed:
            pass                       # you cannot tell yet
        out = f"{prefix}{label}"
        if self.qty > 1:
            out = f"{self.qty} {pluralise(out, self.qty)}"
        if self.charges and self.known:
            out += f" ({self.charges} charges)"
        return out

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
        bits = []
        if b.get("dmg"):
            n, s = b["dmg"]
            bits.append(f"{n}d{s} damage")
        if b.get("ac"):
            bits.append(f"{b['ac']} armour")
        if self.known and self.enchant:
            bits.append(f"{self.enchant:+d} enchantment")
        if b.get("bonus"):
            stat, amount = b["bonus"]
            bits.append(f"{amount:+d} {stat}")
        if b.get("hp_bonus"):
            bits.append(f"+{b['hp_bonus']} max health")
        if b.get("mana_bonus"):
            bits.append(f"+{b['mana_bonus']} max mana")
        if b.get("missile"):
            bits.append(f"fires {b['missile']}s, range {b.get('rng', 7)}")
        if b.get("str_req"):
            bits.append(f"needs Strength {b['str_req']}")
        if b.get("capacity"):
            bits.append(f"holds {b['capacity'] / 1000:.0f} kg")
        bits.append(f"{self.weight} g")
        bits.append(f"bulk {self.bulk}")
        return ", ".join(bits)

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

def _eligible(depth, rng, kinds=None):
    out = []
    for key, b in BASES.items():
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
        return rng.randint(1, 1 + min(4, depth // 5)), False
    return 0, False


def generate_item(depth, rng, rich=False, kinds=None):
    pool = _eligible(depth, rng, kinds)
    if not pool:
        return Item("food")
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
