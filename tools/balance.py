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

from stormhold.common.constants import DIFFICULTIES, mana_cost     # noqa: E402
from stormhold.game.actors import Player                           # noqa: E402
from stormhold.game import combat                                  # noqa: E402
from stormhold.game.items import Item                              # noqa: E402
from stormhold.game.monsters import spawn_table                    # noqa: E402
from stormhold.game.spells import SPELLS                           # noqa: E402
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


# --------------------------------------------------------------------------
#  The same fight, played properly
# --------------------------------------------------------------------------

def arena(world, depth, party, foes, spread=4):
    """Put everybody on a real floor, so spells have something to hit.

    Fighting with the actors floating off the level was how an earlier
    version of this file reported 0% for every spell: `cast` looks up what is
    standing on the target square, and nothing ever was.
    """
    level = world.levels[depth]
    spot = next((x, y) for y in range(2, level.h - 2)
                for x in range(2, level.w - spread - 2)
                if all(level.passable(x + dx, y + dy)
                       for dx in range(-1, spread + 1) for dy in (-1, 0, 1)))
    x, y = spot
    for n, p in enumerate(party):
        level.remove(p)
        p.x, p.y = x, y + (n % 3) - 1
        level.place(p)
    for n, m in enumerate(foes):
        m.x, m.y = x + 1 + n, y
        level.place(m)
    return level


def stock_belt(p, heal=0, mana=0):
    """A utility belt, because a potion in the pack cannot be drunk."""
    belt = Item("beltutil")
    belt.known = True
    p.equipment["waist"] = belt
    for key, count in (("potion_heal", heal), ("potion_mana", mana)):
        for _ in range(count):
            it = Item(key)
            it.known = True
            belt.contents.append(it)
    return belt


def a_potion_of(p, use):
    belt = p.equipment.get("waist")
    for it in getattr(belt, "contents", None) or []:
        if it.base.get("use") == use:
            return it
    return None


def best_attack_spell(p):
    """The hardest hit this caster can pay for right now."""
    best, best_dmg = None, 0
    for name in p.spells:
        spell = SPELLS.get(name)
        if not spell or not spell.get("dmg"):
            continue
        if mana_cost(spell["mana"], p.level, spell.get("level", 1)) > p.mana:
            continue
        n, sides, per = spell["dmg"]
        damage = n * (sides + 1) / 2 + per * p.level
        if damage > best_dmg:
            best, best_dmg = name, damage
    return best


def fight_well(world, depth, party, foes, limit=2000):
    """The same fight, played by somebody who is paying attention.

    Drinks when hurt, casts the hardest spell it can pay for, falls back on
    the weapon when the mana runs out. Every move goes through
    `do_player_action`, so this is the game's own rules and not a sketch of
    them.
    """
    level = arena(world, depth, party, foes)
    deaths = {p.id: p.deaths for p in party}
    for _ in range(limit):
        if all(m.dead for m in foes):
            return True
        if any(p.deaths != deaths[p.id] for p in party):
            return False
        for p in party:
            target = next((m for m in foes if not m.dead), None)
            if target is None:
                break
            if p.hp < p.max_hp * 0.45 and a_potion_of(p, "heal"):
                world.do_player_action(level, p, {
                    "a": "use", "id": a_potion_of(p, "heal").id})
                continue
            if p.mana < p.max_mana * 0.2 and a_potion_of(p, "mana"):
                world.do_player_action(level, p, {
                    "a": "use", "id": a_potion_of(p, "mana").id})
                continue
            spell = best_attack_spell(p)
            if spell:
                world.do_player_action(level, p, {"a": "cast", "spell": spell,
                                                  "x": target.x, "y": target.y})
                continue
            combat.melee(world, p, target)
        for m in foes:
            if m.dead:
                continue
            swings = 100.0 / max(1, m.speed)
            while swings > 0:
                if swings < 1 and world.rng.random() > swings:
                    break
                combat.melee(world, m, world.rng.choice(party))
                swings -= 1
    return False


def played_properly(setting, depth, foe, party_size=1, enchant=0, trials=50,
                    spells=(), heal=0, mana=0, pack=1):
    won = 0
    for trial in range(trials):
        w = World(seed=trial, difficulty=setting)
        party = []
        for n in range(party_size):
            hero = w.add_player(f"Hero{n}", spell="Spark")
            equip_like(hero, depth, enchant)
            hero.spells.update(spells)
            stock_belt(hero, heal, mana)
            hero.recalc()
            hero.hp, hero.mana = hero.max_hp, hero.max_mana
            party.append(hero)
        w.move_player_to(party[0], depth)
        foes = [w.spawn(foe, 0, 0, depth) for _ in range(pack)]
        won += fight_well(w, depth, party, foes)
    return won / trials


def main():
    ap = argparse.ArgumentParser()

    ap.add_argument("--difficulty", default=None,
                    help="one setting, or every setting if left out")
    ap.add_argument("--trials", type=int, default=300)
    ap.add_argument("--party", type=int, default=1,
                    help="how many of them there are")
    ap.add_argument("--enchant", type=int, default=0,
                    help="how good the gear is, as a plus on everything")
    ap.add_argument("--play", action="store_true",
                    help="fight it properly instead: spells, potions, and a "
                         "spell book the character could actually own")
    ap.add_argument("--spells", default="Spark,Fireball,Lightning Bolt",
                    help="what the character has learned, for --play")
    ap.add_argument("--heal", type=int, default=3,
                    help="healing potions on the belt, for --play")
    ap.add_argument("--mana", type=int, default=2,
                    help="mana potions on the belt, for --play")
    args = ap.parse_args()

    if args.play:
        spells = [n.strip() for n in args.spells.split(",") if n.strip() in SPELLS]
        for setting in ([args.difficulty] if args.difficulty
                        else [d[0] for d in DIFFICULTIES]):
            print(f"\n=== {setting}, played properly "
                  f"({args.trials} fights per row, +{args.enchant} gear, "
                  f"party of {args.party}, {args.heal} healing and "
                  f"{args.mana} mana potions, spells: {', '.join(spells)}) ===")
            print(f"{'floor':>5}  {'1 foe':>7} {'2 foes':>7} {'3 foes':>7}  "
                  f"typical resident")
            for depth in (1, 5, 11, 14, 17, 20, 23, 25):
                common = max(spawn_table(depth), key=lambda row: row[1])[0]
                rates = [played_properly(setting, depth, common, args.party,
                                         args.enchant, args.trials,
                                         spells, args.heal, args.mana, pack)
                         for pack in (1, 2, 3)]
                name = World(seed=1, difficulty=setting).spawn(
                    common, 0, 0, depth).name
                print(f"{depth:5d}  {rates[0]:6.0%} {rates[1]:6.0%} "
                      f"{rates[2]:6.0%}  {name}")
        return

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
