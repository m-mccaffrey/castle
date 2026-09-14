"""Traps and secret doors.

Neither is visible until somebody looks for it. Searching costs a turn, which
is the whole point: hurrying down a corridor is faster and riskier, and taking
your time is slower and safer. That trade is the reason the Search button sits
on the toolbar next to Get and Rest.
"""

import random

# The original's trap list, read from its own strings. Ours had been invented;
# this is the real spread - damage, status, movement, and one that raises the
# dead. Effects and numbers are still ours, the taxonomy is not. The original
# also has a trap door (drops you a level) and an animation trap (raises the
# dead); both are recorded in docs/reference-run.md and not built yet.
TRAPS = {
    "arrow":    dict(name="arrow trap",    dmg=(2, 6),  desc="An arrow leaps from the dark!"),
    "dart":     dict(name="dart trap",     dmg=(2, 5),  desc="A dart springs from the wall!"),
    "blade":    dict(name="blade trap",    dmg=(3, 8),  desc="A scything blade sweeps out at you!"),
    "fire":     dict(name="fire trap",     dmg=(2, 6),  desc="Fire roars up from the flagstones!", burn=5),
    "acid":     dict(name="acid trap",     dmg=(2, 6),  desc="Acid sprays across you!", burn=3),
    "poison":   dict(name="poison gas trap", dmg=(1, 3), desc="A cloud of gas surrounds you!", poison=4),
    "sleep":    dict(name="sleep gas trap", dmg=(0, 0), desc="A cloud of gas surrounds you!", hold=True),
    "slow":     dict(name="slow gas trap", dmg=(0, 0),  desc="A cloud of gas surrounds you!", slow=True),
    "pit":      dict(name="pit",           dmg=(2, 7),  desc="You fell into a pit!", stun=True),
    "deadfall": dict(name="deadfall",      dmg=(3, 9),  desc="The ceiling comes down on you!", stun=True),
    "teleport": dict(name="teleport trap", dmg=(0, 0),  desc="The floor twists away beneath you!", teleport=True),
    "glyph":    dict(name="glyph of warding", dmg=(0, 0), desc="You trigger a hidden glyph!", alarm=True),
}

TRAP_BY_DEPTH = (
    (1, ("dart", "arrow", "pit", "glyph")),
    (5, ("dart", "arrow", "pit", "glyph", "poison", "sleep", "blade")),
    (10, ("dart", "arrow", "pit", "glyph", "poison", "sleep", "blade",
          "fire", "acid", "slow", "deadfall")),
    (15, ("blade", "fire", "acid", "slow", "deadfall", "poison", "teleport")),
)


def trap_kinds_for(depth):
    kinds = TRAP_BY_DEPTH[0][1]
    for floor, options in TRAP_BY_DEPTH:
        if depth >= floor:
            kinds = options
    return kinds


def place_hazards(level, rng):
    """Scatter traps and hide a few doors. Never in the room you arrive in."""
    if level.depth <= 0:
        return
    level.traps = {}
    level.secrets = {}

    arrival = level.rooms[0] if level.rooms else None
    kinds = trap_kinds_for(level.depth)
    count = 2 + level.depth // 3 + rng.randint(0, 3)

    candidates = []
    for room in level.rooms[1:] if level.rooms else []:
        for _ in range(3):
            x = rng.randint(room["x"], room["x"] + room["w"] - 1)
            y = rng.randint(room["y"], room["y"] + room["h"] - 1)
            if level.passable(x, y):
                candidates.append((x, y))
    rng.shuffle(candidates)
    for spot in candidates[:count]:
        if spot == level.up_at or spot == level.down_at:
            continue
        level.traps[spot] = {"kind": rng.choice(kinds), "found": False, "armed": True}

    # A handful of walls that are really doors, always with floor on both sides.
    secret_count = rng.randint(1, 3)
    tries = 0
    from ..common.constants import T
    while len(level.secrets) < secret_count and tries < 400:
        tries += 1
        x = rng.randint(2, level.w - 3)
        y = rng.randint(2, level.h - 3)
        if level.get(x, y) != T.WALL:
            continue
        horizontal = level.passable(x - 1, y) and level.passable(x + 1, y)
        vertical = level.passable(x, y - 1) and level.passable(x, y + 1)
        if horizontal or vertical:
            level.secrets[(x, y)] = {"found": False}


def search_here(world, level, player, rng):
    """Look at everything within reach. Returns a list of messages."""
    found = []
    skill = player.level + player.stat("intelligence")
    for dy in range(-1, 2):
        for dx in range(-1, 2):
            spot = (player.x + dx, player.y + dy)
            trap = getattr(level, "traps", {}).get(spot)
            if trap and not trap["found"] and rng.randint(1, 20) + skill >= 18:
                trap["found"] = True
                found.append(f"You spot {a_or_an(TRAPS[trap['kind']]['name'])}.")
            secret = getattr(level, "secrets", {}).get(spot)
            if secret and not secret["found"] and rng.randint(1, 20) + skill >= 20:
                secret["found"] = True
                from ..common.constants import T
                world.set_tile(level, spot[0], spot[1], T.DOOR)
                found.append("You find a hidden door!")
    return found


def disarm_at(world, level, player, spot, rng):
    """Try to take the teeth out of a trap you have found."""
    trap = getattr(level, "traps", {}).get(spot)
    if not trap or not trap["found"]:
        return False, "There is nothing there to disarm."
    if not trap["armed"]:
        return False, "That one is already dealt with."
    skill = player.level + player.stat("dexterity")
    roll = rng.randint(1, 20) + skill
    name = TRAPS[trap["kind"]]["name"]
    if roll >= 18:
        trap["armed"] = False
        del level.traps[spot]
        return True, f"You disarm the {name}."
    if roll <= 6:
        return True, f"You set the {name} off!"        # caller springs it
    return True, f"You cannot get the better of the {name}. Not yet."


def a_or_an(word):
    return ("an " if word[:1].lower() in "aeiou" else "a ") + word
