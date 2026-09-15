"""How hard is the keep, floor by floor?

Not a test - a measuring instrument. It puts a character of the level you
would plausibly be, in the gear you could plausibly afford, against the
creatures that live on each floor, and reports how often they walk away.

    python3 tools/balance.py [--difficulty Intermediate] [--trials 400]

The model is deliberately simple and deliberately pessimistic: toe to toe,
no retreating, no potions, no spells, no corridor to fight in. Read it as
"how bad is the worst case", not "how hard is the game".
"""

import argparse
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stormhold.common.constants import DIFFICULTIES                # noqa: E402
from stormhold.game.actors import Player                           # noqa: E402
from stormhold.game import combat                                  # noqa: E402
from stormhold.game.items import Item                              # noqa: E402
from stormhold.game.monsters import spawn_table                    # noqa: E402
from stormhold.game.world import World                             # noqa: E402

# What a character who has been spending their loot is plausibly wearing at
# each depth: (from this floor down, torso, shield, head, weapon).
KIT = (
    (1,  "leather",   None,          None,   "shortsword"),
    (4,  "studded",   "buckler",     "cap",  "sabre"),
    (7,  "ringmail",  "shield",      "cap",  "longsword"),
    (10, "chainmail", "shield",      "helm", "broadsword"),
    (14, "scalemail", "towershield", "helm", "warhammer"),
    (18, "platemail", "towershield", "helm", "axe"),
)


def kit_for(depth):
    best = KIT[0]
    for row in KIT:
        if depth >= row[0]:
            best = row
    return best


def equip_like(p, depth, enchant=0, level=None):
    """Dress a character the way somebody who got this deep would be."""
    p.stats = {"strength": 12 + min(6, depth // 4),
               "dexterity": 11 + min(5, depth // 5),
               "intelligence": 10,
               "constitution": 11 + min(5, depth // 5)}
    p.level = level or max(1, min(25, depth + 1))
    _from, torso, shield, head, weapon = kit_for(depth)
    for key, slot in ((torso, "torso"), (shield, "shield"),
                      (head, "head"), (weapon, "weapon")):
        if key:
            item = Item(key, enchant=enchant)
            item.known = True
            p.equipment[slot] = item
    p.recalc()
    p.hp = p.max_hp
    p.mana = p.max_mana
    return p


def champion(depth, level=None, enchant=0):
    """Somebody who has been down this far and lived."""
    return equip_like(Player("Hero", {}), depth, enchant, level)


def fight(world, party, foes, limit=4000):
    """The real combat code, not a model of it.

    A model of the fight is a model of my own assumptions; this calls the
    same `melee` the game calls. A death counts as a loss even though the
    temple hands the character back, because in the middle of a fight it is
    one.
    """
    deaths = {p.id: p.deaths for p in party}
    rounds = 0
    while rounds < limit:
        rounds += 1
        if all(m.dead for m in foes):
            return True, rounds
        if any(p.deaths != deaths[p.id] for p in party):
            return False, rounds
        for p in party:
            target = next((m for m in foes if not m.dead), None)
            if target is None:
                break
            combat.melee(world, p, target)
        for m in foes:
            if m.dead:
                continue
            # Speed decides how often it swings: 70 is faster than 130.
            swings = 100.0 / max(1, m.speed)
            while swings > 0:
                if swings < 1 and world.rng.random() > swings:
                    break
                victim = world.rng.choice([p for p in party])
                combat.melee(world, m, victim)
                swings -= 1
    return False, rounds


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--difficulty", default=None,
                    help="one setting, or every setting if left out")
    ap.add_argument("--trials", type=int, default=300)
    ap.add_argument("--party", type=int, default=1,
                    help="how many of them there are")
    ap.add_argument("--enchant", type=int, default=0,
                    help="how good the gear is, as a plus on everything")
    args = ap.parse_args()

    settings = ([args.difficulty] if args.difficulty
                else [d[0] for d in DIFFICULTIES])
    for setting in settings:
        world = World(seed=1, difficulty=setting)
        print(f"\n=== {setting} "
              f"({args.trials} fights per row, no potions, no spells, "
              f"no retreat, +{args.enchant} gear, party of {args.party}) ===")
        print(f"{'floor':>5} {'lvl':>4} {'hp':>4} {'AV':>4}  "
              f"{'1 foe':>7} {'2 foes':>7} {'3 foes':>7}  typical resident")
        for depth in (1, 2, 3, 5, 8, 11, 14, 17, 20, 23, 25):
            p = champion(depth, enchant=args.enchant)
            table = spawn_table(depth)
            common = max(table, key=lambda row: row[1])[0]
            wins = []
            for pack in (1, 2, 3):
                won = 0
                for trial in range(args.trials):
                    w = World(seed=trial, difficulty=setting)
                    party = []
                    for n in range(args.party):
                        hero = w.add_player(f"Hero{n}", spell="Spark")
                        equip_like(hero, depth, args.enchant)
                        party.append(hero)
                    w.move_player_to(party[0], depth)
                    level = w.levels[depth]
                    foes = [w.spawn(common, 0, 0, depth) for _ in range(pack)]
                    ok, _rounds = fight(w, party, foes)
                    won += ok
                wins.append(won / args.trials)
            name = world.spawn(common, 0, 0, depth).name
            print(f"{depth:5d} {p.level:4d} {p.max_hp:4d} {p.armour_class:4d}  "
                  f"{wins[0]:6.0%} {wins[1]:6.0%} {wins[2]:6.0%}  {name}")


if __name__ == "__main__":
    main()
