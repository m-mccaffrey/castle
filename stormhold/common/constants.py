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
CARRY_PER_STRENGTH = 100

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
    "head", "neck", "torso", "back", "arms", "waist",
    "legs", "feet", "shield", "weapon", "ring_left", "ring_right",
)

SLOT_LABELS = {
    "head": "Head", "neck": "Neck", "torso": "Body", "back": "Back",
    "arms": "Hands", "waist": "Waist", "legs": "Legs", "feet": "Feet",
    "shield": "Shield", "weapon": "Weapon",
    "ring_left": "Left ring", "ring_right": "Right ring",
}

RING_SLOTS = ("ring_left", "ring_right")

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
