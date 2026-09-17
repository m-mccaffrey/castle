"""Level generation: the town of Aldershade, and the twenty-five floors of the
keep beneath it. Rooms and corridors, in the old style."""

import random

from ..common.constants import T, is_solid, TOWN_DEPTH, MAX_DEPTH


class Level:
    def __init__(self, w, h, depth, name):
        self.w = w
        self.h = h
        self.depth = depth
        self.name = name
        self.tiles = bytearray(w * h)
        self.rooms = []
        self.up_at = (1, 1)
        self.down_at = None
        self.deep_stairs_at = None      # uncovered when the last boss falls
        self.spawns = []
        self.loot_spots = []
        self.actors = {}            # id -> actor
        self.occupancy = {}         # (x, y) -> actor id
        self.ground = {}            # (x, y) -> list of items
        self.is_town = False
        self.theme = ""
        self.npcs = []
        self.spawn_point = (1, 1)
        self.boss_room = None
        self.boss_key = None
        self.traps = {}            # (x, y) -> {kind, found, armed}
        self.secrets = {}          # (x, y) -> {found}

    # ------------------------------------------------------------ queries --
    def idx(self, x, y):
        return y * self.w + x

    def in_bounds(self, x, y):
        return 0 <= x < self.w and 0 <= y < self.h

    def get(self, x, y):
        if not self.in_bounds(x, y):
            return T.VOID
        return self.tiles[y * self.w + x]

    def set(self, x, y, t):
        if self.in_bounds(x, y):
            self.tiles[y * self.w + x] = t

    def passable(self, x, y):
        """Terrain alone: is this tile walkable ground?"""
        return self.in_bounds(x, y) and not is_solid(self.tiles[y * self.w + x])

    def walkable(self, x, y, ignore_id=None):
        """Terrain plus whoever is standing there."""
        if not self.passable(x, y):
            return False
        occ = self.occupancy.get((x, y))
        return occ is None or occ == ignore_id

    def actor_at(self, x, y):
        aid = self.occupancy.get((x, y))
        return self.actors.get(aid) if aid is not None else None

    # ------------------------------------------------------------ actors ---
    def place(self, actor):
        self.actors[actor.id] = actor
        self.occupancy[(actor.x, actor.y)] = actor.id

    def remove(self, actor):
        self.actors.pop(actor.id, None)
        if self.occupancy.get((actor.x, actor.y)) == actor.id:
            del self.occupancy[(actor.x, actor.y)]

    def move_actor(self, actor, nx, ny):
        if self.occupancy.get((actor.x, actor.y)) == actor.id:
            del self.occupancy[(actor.x, actor.y)]
        actor.x, actor.y = nx, ny
        self.occupancy[(nx, ny)] = actor.id

    # ------------------------------------------------------------- items ---
    def add_ground_item(self, x, y, item):
        spot = self.find_floor(x, y)
        self.ground.setdefault(spot, []).append(item)
        return spot

    def items_at(self, x, y):
        return self.ground.get((x, y), [])

    def take_ground_item(self, x, y, item):
        pile = self.ground.get((x, y))
        if pile and item in pile:
            pile.remove(item)
            if not pile:
                del self.ground[(x, y)]
            return True
        return False

    # ------------------------------------------------------------ search ---
    def find_floor(self, x, y, max_r=12):
        """Nearest tile with open ground, ignoring who is standing on it."""
        if self.passable(x, y):
            return (x, y)
        for r in range(1, max_r + 1):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) != r:
                        continue
                    if self.passable(x + dx, y + dy):
                        return (x + dx, y + dy)
        return (x, y)

    def find_free(self, x, y, max_r=12, ignore_id=None):
        """Nearest tile that is both open ground and unoccupied."""
        if self.walkable(x, y, ignore_id):
            return (x, y)
        for r in range(1, max_r + 1):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) != r:
                        continue
                    if self.walkable(x + dx, y + dy, ignore_id):
                        return (x + dx, y + dy)
        return (x, y)


def can_walk_through(level, x, y):
    """Can a person get through this square, given enough turns?

    A closed door counts: you walk into it and it opens. Anything that asks
    "is the far side of the map reachable" has to think so too, or it will
    decide the whole keep behind the first door is unreachable.
    """
    return level.passable(x, y) or level.get(x, y) == T.DOOR


def reachable(level, sx, sy):
    """Flood fill of walkable terrain from a starting tile."""
    seen = {level.idx(sx, sy)}
    stack = [(sx, sy)]
    while stack:
        x, y = stack.pop()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if not level.in_bounds(nx, ny) or not can_walk_through(level, nx, ny):
                continue
            i = level.idx(nx, ny)
            if i in seen:
                continue
            seen.add(i)
            stack.append((nx, ny))
    return seen


# ===========================================================================
#  The keep
# ===========================================================================

THEMES = (
    ("the Cellars",        1,  4,  0.15, 0.20),
    ("the Flooded Vaults", 4,  9,  0.60, 0.20),
    ("the Bone Gallery",   8,  14, 0.10, 0.50),
    ("the Deep Warrens",   13, 19, 0.25, 0.40),
    ("the Stormworks",     18, 25, 0.20, 0.30),
)


def _theme_for(depth, rng):
    options = [t for t in THEMES if t[1] <= depth <= t[2]]
    return rng.choice(options) if options else THEMES[-1]


def _overlaps(a, b, pad=1):
    return (a["x"] - pad < b["x"] + b["w"] and a["x"] + a["w"] + pad > b["x"] and
            a["y"] - pad < b["y"] + b["h"] and a["y"] + a["h"] + pad > b["y"])


def _carve_room(level, r):
    for y in range(r["y"], r["y"] + r["h"]):
        for x in range(r["x"], r["x"] + r["w"]):
            level.set(x, y, T.FLOOR)


def _carve_corridor(level, ax, ay, bx, by, rng):
    x, y = ax, ay
    level.set(x, y, T.FLOOR)

    def step_x():
        nonlocal x
        while x != bx:
            x += 1 if x < bx else -1
            level.set(x, y, T.FLOOR)

    def step_y():
        nonlocal y
        while y != by:
            y += 1 if y < by else -1
            level.set(x, y, T.FLOOR)

    if rng.random() < 0.5:
        step_x(); step_y()
    else:
        step_y(); step_x()


def _wallify(level):
    """Wrap every open tile in stone so the map is sealed."""
    for y in range(level.h):
        for x in range(level.w):
            if level.get(x, y) != T.VOID:
                continue
            touches = False
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    t = level.get(x + dx, y + dy)
                    if t not in (T.VOID, T.WALL):
                        touches = True
                        break
                if touches:
                    break
            if touches:
                level.set(x, y, T.WALL)


def _add_doors(level, rng):
    """One door to a doorway.

    This used to walk each room's edge ring on its own and roll for every
    floor square in a wall line, which is how you got two doors in a row and
    two doors side by side opening on the same stub of corridor: two rooms
    back to back each put one on their own side, and a two-wide gap got one
    of each. Doors are now chosen for the whole floor at once, and a place
    is passed over if there is already a door beside it, or another two
    along the same corridor with nothing but floor between - an airlock
    nobody built on purpose.
    """
    candidates = []
    seen = set()
    for room in level.rooms:
        edges = []
        for x in range(room["x"] - 1, room["x"] + room["w"] + 1):
            edges.append((x, room["y"] - 1))
            edges.append((x, room["y"] + room["h"]))
        for y in range(room["y"] - 1, room["y"] + room["h"] + 1):
            edges.append((room["x"] - 1, y))
            edges.append((room["x"] + room["w"], y))
        for x, y in edges:
            if (x, y) in seen or level.get(x, y) != T.FLOOR:
                continue
            seen.add((x, y))
            horiz = level.get(x - 1, y) == T.WALL and level.get(x + 1, y) == T.WALL
            vert = level.get(x, y - 1) == T.WALL and level.get(x, y + 1) == T.WALL
            if horiz or vert:
                candidates.append((x, y, (0, 1) if horiz else (1, 0)))

    rng.shuffle(candidates)
    placed = set()
    for x, y, (ax, ay) in candidates:
        if any((x + dx, y + dy) in placed
               for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
            continue                      # shoulder to shoulder with another
        if any((x + ax * step, y + ay * step) in placed for step in (-2, 2)):
            continue                      # one behind the other down a corridor
        if rng.random() < 0.72:
            level.set(x, y, T.DOOR)
            placed.add((x, y))


def _decorate(level, water, rubble, rng):
    for room in level.rooms:
        if room.get("special"):
            continue
        roll = rng.random()
        if roll < water * 0.35 and room["w"] > 4 and room["h"] > 4:
            cx = room["x"] + room["w"] // 2
            cy = room["y"] + room["h"] // 2
            rad = rng.randint(1, min(room["w"], room["h"]) // 2)
            for y in range(cy - rad, cy + rad + 1):
                for x in range(cx - rad, cx + rad + 1):
                    if level.get(x, y) == T.FLOOR and (x - cx) ** 2 + (y - cy) ** 2 <= rad * rad:
                        level.set(x, y, T.WATER)
        elif roll < water * 0.35 + 0.18 and room["w"] >= 5 and room["h"] >= 5:
            # Pillars, never on the centre tile: stairs and bosses live there.
            for y in range(room["y"] + 1, room["y"] + room["h"] - 1, 2):
                for x in range(room["x"] + 1, room["x"] + room["w"] - 1, 2):
                    if (x, y) == (room["cx"], room["cy"]):
                        continue
                    if rng.random() < 0.6:
                        level.set(x, y, T.WALL)
        if rng.random() < rubble:
            for _ in range(rng.randint(1, 5)):
                x = rng.randint(room["x"], room["x"] + room["w"] - 1)
                y = rng.randint(room["y"], room["y"] + room["h"] - 1)
                if level.get(x, y) == T.FLOOR:
                    level.set(x, y, T.RUBBLE)


def _seal_unreachable(level, sx, sy):
    ok = reachable(level, sx, sy)
    for y in range(level.h):
        for x in range(level.w):
            i = level.idx(x, y)
            if can_walk_through(level, x, y) and i not in ok:
                level.tiles[i] = T.WALL
    return ok


def generate_dungeon(depth, seed):
    rng = random.Random(seed ^ (depth * 0x9E3779B9))
    name, _, _, water, rubble = _theme_for(depth, rng)

    w = min(86, 46 + int(depth * 1.5))
    h = min(56, 32 + int(depth * 0.8))
    level = Level(w, h, depth, f"{name}, level {depth}")
    level.theme = name

    target = 10 + depth // 2 + rng.randint(0, 4)
    attempts = 0
    while len(level.rooms) < target and attempts < 1200:
        attempts += 1
        rw = rng.randint(4, 11)
        rh = rng.randint(4, 8)
        room = {"x": rng.randint(2, w - rw - 3), "y": rng.randint(2, h - rh - 3),
                "w": rw, "h": rh}
        if any(_overlaps(room, o, 2) for o in level.rooms):
            continue
        room["cx"] = room["x"] + rw // 2
        room["cy"] = room["y"] + rh // 2
        level.rooms.append(room)
        _carve_room(level, room)

    if len(level.rooms) < 2:
        return generate_dungeon(depth, seed + 1)

    # Spanning tree of corridors, then a few loops so it is not a pure maze.
    connected = [level.rooms[0]]
    pending = level.rooms[1:]
    while pending:
        best = best_from = None
        best_d = None
        for a in connected:
            for b in pending:
                d = (a["cx"] - b["cx"]) ** 2 + (a["cy"] - b["cy"]) ** 2
                if best_d is None or d < best_d:
                    best_d, best, best_from = d, b, a
        _carve_corridor(level, best_from["cx"], best_from["cy"], best["cx"], best["cy"], rng)
        connected.append(best)
        pending.remove(best)
    for _ in range(1 + len(level.rooms) // 5):
        a, b = rng.choice(level.rooms), rng.choice(level.rooms)
        if a is not b:
            _carve_corridor(level, a["cx"], a["cy"], b["cx"], b["cy"], rng)

    if depth >= 2 and rng.random() < 0.45:
        rng.choice(level.rooms[1:])["special"] = "vault"

    _decorate(level, water, rubble, rng)
    # Walls first: doors are placed where a floor square has wall on both
    # sides, and until _wallify has run there are no walls to find - so this
    # ran in the wrong order and the whole keep had no doors at all.
    _wallify(level)
    _add_doors(level, rng)

    first = level.rooms[0]
    level.up_at = (first["cx"], first["cy"])
    level.set(first["cx"], first["cy"], T.STAIRS_UP)

    far = max(level.rooms[1:], key=lambda r: (r["cx"] - first["cx"]) ** 2 + (r["cy"] - first["cy"]) ** 2)
    if depth == MAX_DEPTH:
        # Vaelrik's floor. The altar stays where it always was, and the way
        # down is not there yet: the stairs behind the throne are uncovered
        # when he falls, so the story still ends here for anybody who wants
        # it to. `deep_stairs_at` is where they will be.
        level.set(far["cx"], far["cy"], T.ALTAR)
        level.deep_stairs_at = (far["cx"], far["cy"] - 1)
    else:
        level.down_at = (far["cx"], far["cy"])
        level.set(far["cx"], far["cy"], T.STAIRS_DOWN)
    far["special"] = far.get("special") or "end"

    # A fountain or a throne here and there: both "can have beneficial or
    # harmful effects, or may do nothing at all", which is the point.
    for room in level.rooms[1:]:
        if room is far or room.get("special"):
            continue
        roll = rng.random()
        if roll < 0.10:
            level.set(room["cx"], room["cy"], T.FOUNTAIN)
            room["special"] = "fountain"
        elif roll < 0.15:
            level.set(room["cx"], room["cy"], T.THRONE)
            room["special"] = "throne"

    ok = _seal_unreachable(level, first["cx"], first["cy"])

    for room in level.rooms:
        if room is first:
            continue                      # never ambush the arrival room
        density = 0.09 if room.get("special") == "vault" else 0.035
        count = max(1, round(room["w"] * room["h"] * density))
        for _ in range(count):
            x = rng.randint(room["x"], room["x"] + room["w"] - 1)
            y = rng.randint(room["y"], room["y"] + room["h"] - 1)
            if level.passable(x, y) and level.idx(x, y) in ok:
                level.spawns.append((x, y, room.get("special") == "vault"))
        loot = rng.randint(3, 5) if room.get("special") == "vault" else (
            rng.randint(1, 2) if rng.random() < 0.55 else 0)
        for _ in range(loot):
            x = rng.randint(room["x"], room["x"] + room["w"] - 1)
            y = rng.randint(room["y"], room["y"] + room["h"] - 1)
            if level.passable(x, y) and level.idx(x, y) in ok:
                level.loot_spots.append((x, y, room.get("special") == "vault"))

    if depth in (12, 25):
        level.boss_room = far
        level.boss_key = "warden_of_ash" if depth == 12 else "vaelrik"

    from .traps import place_hazards
    place_hazards(level, rng)
    return level


# ===========================================================================
#  Aldershade. Hand-laid, because a town you come home to a hundred times
#  should be somewhere you know by heart.
# ===========================================================================

def _building(level, x, y, w, h, door_side, door_offset):
    for j in range(y, y + h):
        for i in range(x, x + w):
            edge = i in (x, x + w - 1) or j in (y, y + h - 1)
            level.set(i, j, T.WALL if edge else T.SHOP_FLOOR)
    if door_side == "south":
        door = (x + door_offset, y + h - 1)
    elif door_side == "north":
        door = (x + door_offset, y)
    elif door_side == "west":
        door = (x, y + door_offset)
    else:
        door = (x + w - 1, y + door_offset)
    level.set(door[0], door[1], T.DOOR_OPEN)
    return door


def _path(level, x0, y0, x1, y1):
    x, y = x0, y0
    while x != x1:
        x += 1 if x < x1 else -1
        if level.get(x, y) in (T.GRASS, T.TREE):
            level.set(x, y, T.ROAD)
    while y != y1:
        y += 1 if y < y1 else -1
        if level.get(x, y) in (T.GRASS, T.TREE):
            level.set(x, y, T.ROAD)


def generate_town(seed=1):
    rng = random.Random(seed ^ 0xA1DE)
    w, h = 58, 42
    level = Level(w, h, TOWN_DEPTH, "Aldershade")
    level.is_town = True
    level.theme = "town"

    for y in range(h):
        for x in range(w):
            border = x < 2 or y < 2 or x >= w - 2 or y >= h - 2
            level.set(x, y, T.TREE if border else T.GRASS)
    for _ in range(120):                       # ragged treeline
        x, y = rng.randint(2, w - 3), rng.randint(2, h - 3)
        if min(x - 2, y - 2, w - 3 - x, h - 3 - y) <= 1 and rng.random() < 0.7:
            level.set(x, y, T.TREE)

    road_x, road_y = w // 2, h // 2
    for y in range(3, h - 3):
        level.set(road_x, y, T.ROAD)
        level.set(road_x + 1, y, T.ROAD)
    for x in range(4, w - 4):
        level.set(x, road_y, T.ROAD)
        level.set(x, road_y + 1, T.ROAD)

    # The square, with the town well at its heart.
    for y in range(road_y - 4, road_y + 6):
        for x in range(road_x - 5, road_x + 7):
            level.set(x, y, T.ROAD)
    for dy in range(2):
        for dx in range(2):
            level.set(road_x + dx, road_y + dy, T.WATER)

    # The keep gate, at the head of the north road.
    level.down_at = (road_x, 4)
    level.set(road_x, 4, T.STAIRS_DOWN)
    level.set(road_x + 1, 4, T.ROAD)
    for x in range(road_x - 5, road_x + 7):
        level.set(x, 2, T.WALL)
        level.set(x, 3, T.ROAD if x in (road_x, road_x + 1) else T.WALL)

    # Seven trades, three to a side and the bank on the south road.
    plan = [
        ("weaponsmith", "Bolgar the Weaponsmith",  4,  7,  11, 7, "east", 3),
        ("armourer",    "Hesta the Armourer",      4,  17, 11, 7, "east", 3),
        ("general",     "Pell's General Store",    4,  27, 11, 7, "east", 3),
        ("magic",       "The Gilded Retort",       w - 15, 7,  11, 7, "west", 3),
        ("sage",        "Ulric the Sage",          w - 15, 17, 11, 7, "west", 3),
        ("temple",      "Temple of the Quiet Hour", w - 15, 27, 11, 7, "west", 3),
        ("junk",        "Rusty Nan's Oddments",    road_x + 8, h - 10, 11, 7, "north", 5),
        ("bank",        "Aldershade Strongroom",   road_x - 6, h - 10, 13, 7, "north", 6),
    ]
    sprites = {
        "weaponsmith": "npc_smith", "armourer": "npc_armourer",
        "general": "npc_trader", "magic": "npc_alchemist",
        "sage": "npc_sage", "temple": "npc_priest", "bank": "npc_banker",
        "junk": "npc_trader",
    }

    for shop, name, bx, by, bw, bh, side, off in plan:
        door = _building(level, bx, by, bw, bh, side, off)
        if side == "east":
            _path(level, door[0] + 1, door[1], road_x, door[1])
        elif side == "west":
            _path(level, door[0] - 1, door[1], road_x + 1, door[1])
        else:
            _path(level, door[0], door[1] - 1, door[0], road_y + 1)
        level.npcs.append({
            "shop": shop, "name": name, "sprite": sprites[shop],
            "x": bx + bw // 2, "y": by + bh // 2,
        })

    level.spawn_point = (road_x, road_y + 6)
    level.up_at = level.spawn_point
    return level
