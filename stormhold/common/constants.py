"""Tuning values and shared vocabulary.

Time is the important idea here. Stormhold is turn-based: nothing in the world
moves until somebody acts. Time is counted in abstract ticks, and every action
costs some. A creature acts when the clock reaches its next-action time.
"""

PROTOCOL_VERSION = 1
GAME_NAME = "Stormhold"

# ---------------------------------------------------------------- time -----
TICKS_PER_TURN = 100        # one unhurried action by an average person
MOVE_COST = 100
ATTACK_COST = 100
CAST_COST = 100
PICKUP_COST = 100
DROP_COST = 50
QUAFF_COST = 100
READ_COST = 100
EQUIP_COST = 100            # putting armour on takes a real moment
SWAP_COST = 50
REST_COST = 100
STAIRS_COST = 100
FREE_COST = 0               # rummaging in your own pack costs nothing

# Forty ticks to the game-second. Measured against the original: one step at
# 100% speed advances its clock by exactly 2.5 game-seconds, checked over
# runs of 2, 8, 16 and 24 moves. MOVE_COST is 100 ticks, so 100/40 = 2.5s.
TICKS_PER_SECOND = 40


def format_clock(ticks):
    total = int(ticks // TICKS_PER_SECOND)
    days, rest = divmod(total, 86400)
    hours, rest = divmod(rest, 3600)
    minutes, seconds = divmod(rest, 60)
    return f"{days}d,{hours:02d}:{minutes:02d}:{seconds:02d}"


# How far the world may run ahead of a player who has not acted yet. Beyond
# this it stops and says who everyone is waiting for. Two turns is enough that
# nobody notices a pause for thought, and short enough that nobody gets left
# behind.
GRACE_TICKS = 200

# ---------------------------------------------------------------- tiles ----
class T:
    VOID = 0
    FLOOR = 1
    WALL = 2
    DOOR = 3
    DOOR_OPEN = 4
    STAIRS_DOWN = 5
    STAIRS_UP = 6
    WATER = 7
    RUBBLE = 8
    GRASS = 9
    ROAD = 10
    TREE = 11
    SHOP_FLOOR = 12
    ALTAR = 13


TILE_NAMES = {
    T.VOID: "void", T.FLOOR: "floor", T.WALL: "wall", T.DOOR: "door",
    T.DOOR_OPEN: "door_open", T.STAIRS_DOWN: "stairs_down",
    T.STAIRS_UP: "stairs_up", T.WATER: "water", T.RUBBLE: "rubble",
    T.GRASS: "grass", T.ROAD: "road", T.TREE: "tree",
    T.SHOP_FLOOR: "shop_floor", T.ALTAR: "altar",
}

SOLID = frozenset({T.VOID, T.WALL, T.DOOR, T.TREE})
OPAQUE = frozenset({T.VOID, T.WALL, T.DOOR, T.TREE})
SLOW = frozenset({T.WATER, T.RUBBLE})       # costs half again to cross


def is_solid(t):
    return t in SOLID


def is_opaque(t):
    return t in OPAQUE


# Eight-way movement, clockwise from north.
DIRS = ((0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1))
DIR_NAMES = ("north", "north-east", "east", "south-east",
             "south", "south-west", "west", "north-west")

# ------------------------------------------------------------- character ---
STATS = ("strength", "dexterity", "intelligence", "constitution")
STAT_ABBR = {"strength": "Str", "dexterity": "Dex",
             "intelligence": "Int", "constitution": "Con"}

STAT_MIN = 3
STAT_MAX = 25
START_STAT = 8              # every stat starts here...
START_POINTS = 16           # ...and you have this many to spread around

MAX_LEVEL = 30

# Experience needed to reach each level.
def _xp_table():
    table = [0, 0]
    for lvl in range(2, MAX_LEVEL + 2):
        table.append(int(18 * (lvl - 1) ** 2.4))
    return table


XP_TABLE = _xp_table()


def xp_for_level(level):
    return XP_TABLE[min(level + 1, len(XP_TABLE) - 1)]


# ----------------------------------------------------------- encumbrance ---
# Weight is in tenths of a pound, so a long sword at 60 is six pounds and a
# hundred gold coins weigh one. That last detail is why the bank matters.
# Measured from the original by running it: max carry weight rises exactly
# 2000 of its units per point of strength, dead linear across the whole
# chargen range, with a constant offset. Its unit is a hundredth of a pound
# (a small pack reads 1000, i.e. ten pounds); ours is a tenth, so the same
# law in our units is 200 per point plus a 10lb offset.
CARRY_PER_STRENGTH = 200
CARRY_BASE = 100

# What a shop charges and what it pays. Measured: a short sword costs 1470 and
# sells back for 840; a club costs 105 and sells back for 60. Both are the same
# pair of multipliers on one base value (1050 and 75), and the 4/7 ratio holds
# exactly, so the markup is not per-item haggling.
SHOP_BUY_MARKUP = 1.4
SHOP_SELL_RATE = 0.8

# A character starts with this much copper in the purse.
START_COPPER = 1500

ENCUMBRANCE = (
    #  name           fraction of capacity,  multiplier on how long moving takes
    ("Unencumbered", 0.50, 1.00),
    ("Burdened",     0.75, 1.25),
    ("Stressed",     1.00, 1.50),
    ("Strained",     1.25, 2.00),
    ("Overtaxed",    1.50, 3.00),
    ("Overloaded",   99.0, None),      # None means you are going nowhere
)


def encumbrance_for(weight, capacity):
    """Return (tier name, time multiplier) for a load. None means stuck."""
    if capacity <= 0:
        return ENCUMBRANCE[-1][0], ENCUMBRANCE[-1][2]
    ratio = weight / capacity
    for name, limit, mult in ENCUMBRANCE:
        if ratio <= limit:
            return name, mult
    return ENCUMBRANCE[-1][0], ENCUMBRANCE[-1][2]


# ------------------------------------------------------------ equipment ----
# Worn slots, in the order the character sheet lists them.
SLOTS = (
    "head", "neck", "back", "torso", "bracers", "arms", "waist",
    "legs", "feet", "shield", "weapon", "ring_left", "ring_right",
    "pack", "purse",
)

SLOT_LABELS = {
    "head": "Helmet", "neck": "Neckwear", "back": "Overgarment",
    "torso": "Armour", "bracers": "Bracers", "arms": "Gauntlets",
    "waist": "Belt", "legs": "Leggings", "feet": "Boots",
    "shield": "Shield", "weapon": "Weapon",
    "ring_left": "Right ring", "ring_right": "Left ring",
    "pack": "Pack", "purse": "Purse",
}

# Where each slot sits on the figure, as a fraction of the drawing area, so a
# leader line can be drawn from the box to the body part it belongs to.
SLOT_ANCHORS = {
    "head":       (0.50, 0.11),
    "neck":       (0.50, 0.22),
    "back":       (0.30, 0.30),
    "torso":      (0.50, 0.34),
    "bracers":    (0.26, 0.44),
    "arms":       (0.76, 0.50),
    "weapon":     (0.20, 0.52),
    "shield":     (0.82, 0.40),
    "waist":      (0.50, 0.53),
    "ring_left":  (0.19, 0.56),
    "ring_right": (0.81, 0.56),
    "legs":       (0.50, 0.66),
    "feet":       (0.50, 0.88),
    "pack":       (0.36, 0.30),
    "purse":      (0.62, 0.55),
}

# Slots laid out around the figure: which column, and in what order.
DOLL_TOP = ("head", "neck", "back")
DOLL_LEFT = ("torso", "bracers", "weapon", "ring_left", "waist", "pack")
DOLL_RIGHT = ("shield", "arms", "legs", "ring_right", "feet", "purse")

RING_SLOTS = ("ring_left", "ring_right")

# What you can hold without a pack: your two hands, near enough.
BARE_HANDS_WEIGHT = 120
BARE_HANDS_BULK = 30

# Bulk is NOT a strength limit. In the original the character sheet reports a
# body bulk maximum of 1000000 regardless of strength - it never binds. What
# actually limits bulk is the pack you are wearing, whose own window caption
# reads "Wt current (max) Bulk current (max)". So the body figure here is a
# formality and the real constraint lives in pack_limits().
BODY_BULK_CAPACITY = 1_000_000

# --------------------------------------------------------------- world -----
TOWN_DEPTH = 0
MAX_DEPTH = 25
SIGHT_DUNGEON = 8
SIGHT_TOWN = 18
BOSS_DEPTHS = (12, 25)

# Death: you drop what you carried and wake at the temple, lighter of purse.
DEATH_GOLD_PENALTY = 0.20
DEATH_XP_PENALTY = 0.10
RESURRECT_HP_FRACTION = 0.40

REGEN_TICKS = 600           # one point of natural healing per this many ticks


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def chebyshev(ax, ay, bx, by):
    return max(abs(ax - bx), abs(ay - by))
