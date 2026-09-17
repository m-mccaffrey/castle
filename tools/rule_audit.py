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

from stormhold.game.actors import Player, movement_speed          # noqa: E402
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
def check_heals():
    """"The greater of 8 hit points or 20% ... 16 or 40% ... 24 or 60%,
    but not exceeding the character's maximum."""
    for spell, flat, share in (("Heal Minor Wounds", 8, 0.20),
                               ("Heal Medium Wounds", 16, 0.40),
                               ("Heal Major Wounds", 24, 0.60)):
        for max_hp in (20, 200):
            w, p = fresh()
            p.max_hp = max_hp
            p.hp = 1
            p.mana = 99
            w.do_player_action(w.levels[p.depth], p, {"a": "cast", "spell": spell})
            want = min(max_hp, 1 + max(flat, int(max_hp * share)))
            note("heal", f"{spell} at {max_hp} max is the greater of "
                         f"{flat} and {int(share * 100)}%",
                 p.hp == want, f"gave {p.hp - 1}, wanted {want - 1}")
    w, p = fresh()
    p.max_hp, p.hp, p.mana = 30, 28, 99
    w.do_player_action(w.levels[p.depth], p, {"a": "cast", "spell": "Heal Major Wounds"})
    note("heal", "healing never goes past your maximum", p.hp == 30, f"hp {p.hp}/30")


# ---------------------------------------------------------- slow monster --
def check_slow():
    """"a monster will move at 1/2, then 1/3, then 1/4, then 1/5 ... of its
    normal speed"."""
    w, p = fresh()
    level = w.levels[p.depth]
    mon = next((m for m in level.actors if getattr(m, "kind", "") == "monster"), None)
    if mon is None:
        return note("slow", "a monster to slow", False, "none on the floor")
    base = mon.action_cost(100)
    seen = []
    for _ in range(4):
        mon.add_effect("slowed", 600)
        seen.append(round(mon.action_cost(100) / base, 3))
    note("slow", "slowing stacks 1/2, 1/3, 1/4, 1/5 - not 1/2 each time",
         seen == [2.0, 3.0, 4.0, 5.0], f"costs went {seen}")


# ----------------------------------------------------------- teleporting --
def check_teleports():
    """"a random location from 5 to 10 squares" and "at least 10 squares"."""
    for spell, lo, hi in (("Phase Door", 5, 10), ("Teleport", 10, 9999)):
        w, p = fresh(depth=2)
        level = w.levels[p.depth]
        spread = []
        for _ in range(40):
            x, y = p.x, p.y
            p.mana = 99
            w.do_player_action(level, p, {"a": "cast", "spell": spell})
            spread.append(max(abs(p.x - x), abs(p.y - y)))
        worst, best = min(spread), max(spread)
        note("teleport", f"{spell} lands {lo}..{'' if hi > 999 else hi} squares away",
             worst >= lo and best <= hi,
             f"{worst}..{best} over {len(spread)} casts")


# ------------------------------------------------------------ junk store --
def check_junk():
    """"It will buy anything, for market price (if it's less than 25 C.P.)
    or for 25 C.P. if it's cursed or worthless."""
    w, p = fresh()
    cheap = Item("arrow")
    dear = Item("platemail")
    cursed = Item("ring_burden")
    cursed.cursed = True
    got = {}
    for label, item in (("a cheap thing", cheap), ("a dear thing", dear),
                        ("a cursed thing", cursed)):
        got[label] = (w.junk_price(item), item.value())
    note("junk", "pays market for anything under 25 C.P.",
         got["a cheap thing"][0] == min(25, got["a cheap thing"][1]),
         f"paid {got['a cheap thing'][0]} for a {got['a cheap thing'][1]} item")
    note("junk", "pays a flat 25 for anything dearer",
         got["a dear thing"][0] == 25,
         f"paid {got['a dear thing'][0]} for a {got['a dear thing'][1]} item")
    note("junk", "pays 25 for a cursed thing",
         got["a cursed thing"][0] == 25, f"paid {got['a cursed thing'][0]}")


# ------------------------------------------------------------------ get --
def check_get():
    """"The special case is if the object is a pack, purse, or belt, and the
    player isn't wearing one, the object goes in the appropriate slot."""
    for key, slot in (("pack", "pack"), ("purse", "purse"), ("belt3", "waist")):
        w, p = fresh()
        level = w.levels[p.depth]
        p.equipment[slot] = None
        thing = Item(key)
        level.drop_item(thing, p.x, p.y)
        w.do_player_action(level, p, {"a": "pickup"})
        note("get", f"a {key} off the floor goes straight to the {slot} slot",
             p.equipment.get(slot) is thing,
             f"{slot} holds {getattr(p.equipment.get(slot), 'key', None)}")


# ----------------------------------------------------------------- sort --
def check_sort():
    """"all unknown objects of a type are at the end"."""
    w, p = fresh()
    known = Item("potion_heal")
    known.known = True
    unknown = Item("potion_mana")
    unknown.known = False
    second = Item("potion_speed")
    second.known = True
    for it in (unknown, second, known):
        p.add_item(it)
    w.do_player_action(w.levels[p.depth], p, {"a": "sort"})
    potions = [i for i in p.inventory if i.kind == "potion"]
    note("sort", "unknown things sort to the end of their own type",
         potions and potions[-1] is unknown,
         " then ".join(("?" if not i.known else i.key) for i in potions))


def main():
    random.seed(4)
    print("\n-- the original's arithmetic ------------------------------")
    for check in (check_load, check_heals, check_slow, check_teleports,
                  check_junk, check_get, check_sort):
        try:
            check()
        except Exception as exc:                      # noqa: BLE001
            note(check.__name__[6:], "the check itself ran", False, repr(exc))
    bad = [r for r in ROWS if not r[2]]
    print(f"\n{len(ROWS)} rules, {len(bad)} do not match the original")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
