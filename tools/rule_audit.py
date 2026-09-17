"""Check the original's stated numbers against ours, one rule per row.

CASTLE1.HLP and CASTLE2.HLP state a lot of arithmetic outright: how far a
Phase Door throws you, how much a Heal restores, what happens to a monster's
speed when you slow it twice, what the junk store pays. Those are the rules
easiest to get subtly wrong, because nothing about the game looks broken
when a heal gives 20% and the original gives the greater of 20% and 8.

Each row quotes the help file and then measures ours. Where the rule is
about chance or a random spread, it is sampled rather than reasoned about.

    python3 tools/rule_audit.py
"""

import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import random                                                     # noqa: E402

from stormhold.game.actors import make_monster, movement_speed     # noqa: E402
from stormhold.game.items import Item                             # noqa: E402
from stormhold.game.world import World                            # noqa: E402

ROWS = []


def note(area, rule, ok, detail=""):
    ROWS.append((area, rule, ok, detail))
    print(f"   {'  ' if ok else '**'}{area:<9} {rule:<52} "
          f"{'ok' if ok else 'FAIL'}  {detail}", flush=True)


def fresh(depth=1, name="Rule"):
    w = World(seed=7)
    p = w.add_player(name)
    level = w.get_level(depth)
    w.levels[p.depth].remove(p)
    p.depth = depth
    p.x, p.y = level.find_free(*level.spawn_point)
    level.place(p)
    return w, p


# ---------------------------------------------------------------- load ----
def check_load():
    """"lightly loaded (less than 1/2 rated) ... 200% ... at your rated
    maximum ... 100% ... at twice your rated maximum (the real limit on what
    you can carry) ... 50%"."""
    cap = 10000
    note("load", "under half the rating moves at 200%",
         movement_speed(cap // 4, cap) == 200, f"{movement_speed(cap // 4, cap)}%")
    note("load", "at the rating exactly, 100%",
         movement_speed(cap, cap) == 100, f"{movement_speed(cap, cap)}%")
    note("load", "at twice the rating, 50%",
         movement_speed(2 * cap, cap) == 50, f"{movement_speed(2 * cap, cap)}%")
    note("load", "past twice the rating you cannot move at all",
         movement_speed(int(2.05 * cap), cap) is None,
         str(movement_speed(int(2.05 * cap), cap)))

    w, p = fresh()
    light = p.action_cost(100)
    p.inventory.append(Item("platemail"))
    p.inventory.append(Item("platemail"))
    heavy = p.action_cost(100)
    note("load", "load slows walking but nothing else",
         light == heavy, f"a turn costs {light} empty, {heavy} loaded")


# --------------------------------------------------------------- heals ----
# Our spells have their own names - the remake's prose is its own - so the
# rule is matched to the spell that does the original's job.
HEALS = (("Mend Wounds", 8, 0.20),         # Heal Minor Wounds
         ("Greater Mending", 16, 0.40),    # Heal Medium Wounds
         ("Circle of Mending", 24, 0.60))  # Heal Major Wounds


def check_heals():
    """"The greater of 8 hit points or 20% ... 16 or 40% ... 24 or 60%,
    but not exceeding the character's maximum."""
    for spell, flat, share in HEALS:
        for con, lvl in ((8, 1), (30, 12)):
            w, p = fresh()
            p.spells.add(spell)
            # max_hp is rebuilt from constitution and level whenever the
            # character is recalculated, including during a cast, so it is
            # raised the way the game raises it and then read back.
            p.stats["constitution"] = con
            p.level = lvl
            p.recalc()
            p.hp, p.mana = 1, 999
            max_hp = p.max_hp
            w.do_player_action(w.levels[p.depth], p,
                               {"a": "cast", "spell": spell, "x": p.x, "y": p.y})
            want = min(max_hp, 1 + max(flat, int(max_hp * share)))
            note("heal", f"{spell} at {max_hp} max: the greater of "
                         f"{flat} and {int(share * 100)}%",
                 p.hp == want, f"gave {p.hp - 1}, wanted {want - 1}")
    w, p = fresh()
    p.spells.add("Circle of Mending")
    p.recalc()
    p.hp, p.mana = p.max_hp - 2, 999
    w.do_player_action(w.levels[p.depth], p,
                       {"a": "cast", "spell": "Circle of Mending",
                        "x": p.x, "y": p.y})
    note("heal", "healing never goes past your maximum", p.hp == p.max_hp,
         f"hp {p.hp}/{p.max_hp}")


# ---------------------------------------------------------- slow monster --
def check_slow():
    """"a monster will move at 1/2, then 1/3, then 1/4, then 1/5 ... of its
    normal speed"."""
    w, p = fresh()
    level = w.levels[p.depth]
    from stormhold.game.monsters import MONSTERS
    key = next(iter(MONSTERS))
    mon = make_monster(key, p.x + 1, p.y, p.depth, w.rng)
    level.place(mon)
    base = mon.action_cost(100)
    seen = []
    for _ in range(4):
        # Through the world's own path: add_effect alone sets the flag
        # without the step count, which is a way of measuring nothing.
        w.apply_slow(mon, level.clock)
        seen.append(round(mon.action_cost(100) / base, 3))
    note("slow", "slowing stacks 1/2, 1/3, 1/4, 1/5 - not 1/2 each time",
         seen == [2.0, 3.0, 4.0, 5.0], f"costs went {seen}")


# ----------------------------------------------------------- teleporting --
def check_teleports():
    """"a random location from 5 to 10 squares" and "at least 10 squares".

    Ours are Blink and Farstep; the spread is sampled rather than reasoned
    about, because both pick a square and then fall back to the nearest one
    that is safe to stand on.
    """
    for spell, lo, hi in (("Blink", 5, 10), ("Farstep", 10, 9999)):
        w, p = fresh(depth=2)
        level = w.levels[p.depth]
        spread = []
        for _ in range(40):
            x, y = p.x, p.y
            p.spells.add(spell)
            p.mana = 999
            w.do_player_action(level, p, {"a": "cast", "spell": spell})
            gap = max(abs(p.x - x), abs(p.y - y))
            if gap:
                spread.append(gap)
        if not spread:
            note("teleport", f"{spell} moves you at all", False, "never moved")
            continue
        worst, best = min(spread), max(spread)
        note("teleport", f"{spell} lands {lo}..{'' if hi > 999 else hi} squares off",
             worst >= lo and best <= hi,
             f"{worst}..{best} over {len(spread)} casts")


# ------------------------------------------------------------ junk store --
def check_junk():
    """"It will buy anything, for market price (if it's less than 25 C.P.)
    or for 25 C.P. if it's cursed or worthless."""
    w, _ = fresh()
    cheap, dear = Item("arrow"), Item("platemail")
    cursed = Item("ring_burden")
    cursed.cursed = True
    note("junk", "market price while that is under 25",
         w.junk_price(cheap) == cheap.value() and cheap.value() < 25,
         f"paid {w.junk_price(cheap)} for a {cheap.value()} thing")
    note("junk", "a flat 25 for anything dearer",
         w.junk_price(dear) == 25, f"paid {w.junk_price(dear)} for a {dear.value()} thing")
    note("junk", "a flat 25 for a cursed thing",
         w.junk_price(cursed) == 25, f"paid {w.junk_price(cursed)}")


# ------------------------------------------------------------------ get --
def check_get():
    """"The special case is if the object is a pack, purse, or belt, and the
    player isn't wearing one, the object goes in the appropriate slot."""
    w, p = fresh()
    level = w.levels[p.depth]
    for key in ("shortsword", "potion_heal", "leather"):
        level.add_ground_item(p.x, p.y, Item(key))
    held = len(p.inventory)
    w.do_player_action(level, p, {"a": "pickup"})
    note("get", "Get takes everything on the floor, not one thing",
         len(p.inventory) == held + 3 and not level.items_at(p.x, p.y),
         f"{len(p.inventory) - held} of 3 taken, "
         f"{len(level.items_at(p.x, p.y))} left lying there")

    for key, slot in (("pack", "pack"), ("purse", "purse"), ("belt3", "waist")):
        w, p = fresh()
        level = w.levels[p.depth]
        p.equipment[slot] = None
        thing = Item(key)
        level.add_ground_item(p.x, p.y, thing)
        w.do_player_action(level, p, {"a": "pickup"})
        note("get", f"a {key} off the floor goes straight to the {slot} slot",
             p.equipment.get(slot) is thing,
             f"{slot} holds {getattr(p.equipment.get(slot), 'key', None)}")


# ----------------------------------------------------------------- sort --
def check_sort():
    """"all unknown objects of a type are at the end".

    A potion is unknown by its *appearance*, which is a fact about the world
    and not about the bottle, so the check has to find a kind this character
    has not met rather than just clearing a flag on one item.
    """
    w, p = fresh()
    unknown_key = next((k for k in ("potion_mana", "potion_speed", "potion_might")
                        if not w.appearances.is_known(k)), None)
    if unknown_key is None:
        return note("sort", "a potion this character has not met", False,
                    "everything was already identified")
    known = Item("potion_heal")
    w.appearances.identify("potion_heal")
    unknown = Item(unknown_key)
    for it in (unknown, known):
        p.add_item(it)
    w.do_player_action(w.levels[p.depth], p, {"a": "sort"})
    potions = [i for i in p.inventory if i.kind == "potion"]
    note("sort", "unknown things sort to the end of their own type",
         bool(potions) and potions[-1] is unknown,
         " then ".join(("?" if not w.appearances.is_known(i.key) else i.key)
                       for i in potions))


# ------------------------------------------------------- resting & rites --
def check_resting():
    """Two commands, two conditions, two ways of being interrupted.

    "[r] is interrupted as soon as a monster comes in sight" ... "[R] is
    only interrupted when a monster attacks you, not when they come into
    view", and during it "you regenerate mana at twice the normal rate".
    """
    from stormhold.game.monsters import MONSTERS
    w, p = fresh(depth=2)
    level = w.levels[p.depth]
    p.recalc()
    p.hp = p.max_hp
    p.mana = 0
    w.do_player_action(level, p, {"a": "rest"})
    note("rest", "r stops once you are healed, without waiting on mana",
         not p.resting, f"resting={p.resting!r} at {p.hp}/{p.max_hp} hp, "
                        f"{p.mana}/{p.max_mana} mana")

    w, p = fresh(depth=2)
    level = w.levels[p.depth]
    for other in [a for a in list(level.actors.values()) if getattr(a, "kind", "") == "monster"]:
        level.remove(other)          # rest refuses outright with one in sight
    p.recalc()
    p.hp = 1
    w.do_player_action(level, p, {"a": "rest"})
    resting_was = bool(p.resting)
    mon = make_monster(next(iter(MONSTERS)), p.x + 1, p.y, p.depth, w.rng)
    level.place(mon)
    w.act(level, p)
    note("rest", "a monster coming into view breaks a rest",
         resting_was and not p.resting, f"was {resting_was}, now {bool(p.resting)}")

    w, p = fresh(depth=2)
    level = w.levels[p.depth]
    for other in [a for a in list(level.actors.values()) if getattr(a, "kind", "") == "monster"]:
        level.remove(other)
    p.recalc()
    p.mana = 0
    w.do_player_action(level, p, {"a": "sleep"})
    sleeping_was = bool(p.resting)
    mon = make_monster(next(iter(MONSTERS)), p.x + 1, p.y, p.depth, w.rng)
    level.place(mon)
    w.act(level, p)
    note("rest", "a monster merely in view does not break a sleep",
         sleeping_was and bool(p.resting),
         f"was {sleeping_was}, now {bool(p.resting)}")


def check_temple():
    """"Remove Curse ... is always available since it would give the player
    hints about unidentified objects to gray it."""
    w, p = fresh()
    p.copper = 999999
    rows = {r["key"]: r for r in w.temple_services(p)}
    row = rows.get("uncurse")
    note("temple", "Remove Curse is offered whether or not you are cursed",
         bool(row and row["useful"]), str(row))


def main():
    random.seed(4)
    print("\n-- the original's arithmetic ------------------------------")
    for check in (check_load, check_heals, check_slow, check_teleports,
                  check_junk, check_get, check_sort, check_resting,
                  check_temple):
        try:
            check()
        except Exception as exc:                      # noqa: BLE001
            note(check.__name__[6:], "the check itself ran", False, repr(exc))
    bad = [r for r in ROWS if not r[2]]
    print(f"\n{len(ROWS)} rules, {len(bad)} do not match the original")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
