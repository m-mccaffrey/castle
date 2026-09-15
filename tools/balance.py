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

from stormhold.common.constants import (DIFFICULTIES, mana_cost,   # noqa: E402
                                        SHOP_BUY_MARKUP)
from stormhold.game.actors import Player                           # noqa: E402
from stormhold.game import combat                                  # noqa: E402
from stormhold.game.items import Item, BASES                       # noqa: E402
from stormhold.game.monsters import spawn_table                    # noqa: E402
from stormhold.game.spells import SPELLS                           # noqa: E402
from stormhold.game.world import World                             # noqa: E402

# How much copper the floors above this one actually contain, cumulatively,
# for one character. Measured off the level generator rather than guessed:
# see tools/campaign.py, which spends the real thing.
PURSE_BY_DEPTH = (0, 2100, 4600, 9800, 13000, 21700, 30200, 32800, 43100,
                  46900, 62300, 65300, 76000, 92100, 104200, 122500, 144200,
                  159800, 177100, 194900, 228900, 257900, 271900, 314900,
                  350900, 376900)

# Which things a character shops for, best first within each slot. A slot is
# filled with the best entry that is both affordable and wearable.
WARDROBE = (
    ("torso",  ("platemail", "scalemail", "chainmail", "ringmail", "studded",
                "leather", "robe")),
    ("weapon", ("halberd", "axe", "warhammer", "broadsword", "longsword",
                "sabre", "mace", "shortsword", "spear", "dagger")),
    ("shield", ("towershield", "shield", "buckler")),
    ("head",   ("helm", "cap")),
    ("legs",   ("leggings",)),
    ("arms",   ("gauntlets", "gloves")),
    ("feet",   ("boots",)),
    ("back",   ("cloak",)),
    ("bracers", ("bracers",)),
)


def purse_at(depth, share=0.7):
    """What a character arriving on this floor has had to spend.

    Half of what the floors above contained: the rest went on healing
    potions, on the temple, and on what you drop when you die. The share is
    the one judgement call in this file, and `--purse` moves it.
    """
    # The floors *above* this one, plus the 1500 copper the original starts
    # you with. Arriving on floor 1 you have spent nothing but your purse.
    above = PURSE_BY_DEPTH[min(max(0, depth - 1), len(PURSE_BY_DEPTH) - 1)]
    return int((1500 + above) * share)


def equip_like(p, depth, enchant=0, level=None, share=0.7):
    """Dress a character the way somebody who got this deep would be.

    Not from a table of what seems right - from what the floors above this
    one actually contain, spent at the shop's actual prices on the best
    thing in each slot that a character of this Strength can wear. A hand
    written kit table was the weakest thing in this file: set it low and the
    early floors look impossible, set it high and the whole keep looks like
    a walk. Both happened.
    """
    p.stats = {"strength": 12 + min(6, depth // 4),
               "dexterity": 11 + min(5, depth // 5),
               "intelligence": 10 + min(8, depth // 3),
               "constitution": 11 + min(5, depth // 5)}
    p.level = level or max(1, min(30, depth + 1))
    budget = purse_at(depth, share)

    def affordable(choices, spent_on_slot):
        """The best of these we can pay for, and what it would cost."""
        for key in choices:
            if BASES[key].get("str_req", 0) > p.stats["strength"]:
                continue
            item = Item(key, enchant=enchant)
            price = int(item.value() * SHOP_BUY_MARKUP)
            if price - spent_on_slot <= budget:
                return item, price
        return None, 0

    # Nobody buys a halberd and then walks down the stairs in a shirt. Cover
    # every slot with the cheapest thing that fills it, then spend what is
    # left upgrading, armour first.
    paid = {}
    for slot, choices in WARDROBE:
        item, price = affordable(list(reversed(choices)), 0)
        if item is not None:
            item.known = True
            p.equipment[slot] = item
            paid[slot] = price
            budget -= price
    for _round in range(3):
        for slot, choices in WARDROBE:
            item, price = affordable(choices, paid.get(slot, 0))
            if item is None or item.key == getattr(p.equipment.get(slot), "key", None):
                continue
            item.known = True
            budget -= price - paid.get(slot, 0)
            p.equipment[slot] = item
            paid[slot] = price
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


# What level a character actually is when they arrive on each floor, having
# cleared the ones above. Measured, not assumed: sum the experience the floor
# generator actually puts on floors 1..d-1 and share it the way `kill` does.
# The old assumption here was level = depth + 1, which is four to five levels
# short by the bottom of the keep and made spells look weaker than they are.
LEVEL_AT_DEPTH = {
    1: (1, 1, 1, 1), 2: (2, 2, 2, 2), 3: (4, 4, 3, 3), 4: (5, 5, 4, 4),
    5: (6, 6, 5, 5), 6: (7, 6, 6, 5), 7: (8, 7, 7, 6), 8: (9, 8, 7, 7),
    9: (10, 9, 8, 8), 10: (11, 10, 9, 8), 11: (12, 12, 10, 10),
    12: (13, 12, 11, 10), 13: (15, 14, 13, 12), 14: (16, 15, 14, 13),
    15: (18, 17, 15, 14), 16: (19, 18, 16, 15), 17: (21, 19, 17, 16),
    18: (23, 21, 19, 18), 19: (24, 23, 21, 20), 20: (26, 25, 22, 21),
    21: (28, 27, 24, 23), 22: (30, 29, 26, 25), 23: (30, 30, 28, 26),
    24: (30, 30, 30, 29), 25: (30, 30, 30, 30),
}


def level_at(depth, party=1):
    return LEVEL_AT_DEPTH.get(depth, (1, 1, 1, 1))[min(party, 4) - 1]


def spells_by(level):
    """Every attack spell a character of this level could have learned."""
    return [n for n, s in SPELLS.items()
            if s.get("dmg") and s["level"] <= level and s["int_req"] <= 18]


def fight_well(world, depth, party, foes, limit=2000, frontage=None):
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
        # In a doorway only so many of them can reach you at once. This is
        # the single biggest thing a person does that a number does not.
        attacking = [m for m in foes if not m.dead]
        if frontage is not None:
            attacking = attacking[:frontage * len(party)]
        for m in attacking:
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


def worst_cluster(setting, depth, party_size, seeds=15):
    """A bad fight you will actually meet on this floor.

    Not the typical resident - the typical resident is not what kills you,
    the four dire wolves standing together are. But not the worst knot on
    any floor ever generated either: that is a tail event, and tuning to it
    would make the game a walk. This takes the worst knot on each of fifteen
    floors and returns the median one.
    """
    per_floor = []
    for seed in range(seeds):
        w = World(seed=seed, difficulty=setting)
        players = [w.add_player(f"H{n}", spell="Spark") for n in range(party_size)]
        w.move_player_to(players[0], depth)
        level = w.levels[depth]
        mobs = [m for m in level.actors.values()
                if m.kind == "monster" and not m.dead]
        best, best_hp = [], 0
        for m in mobs:
            knot = [o for o in mobs
                    if max(abs(o.x - m.x), abs(o.y - m.y)) <= 2]
            hp = sum(o.max_hp for o in knot)
            if hp > best_hp:
                best, best_hp = [o.key for o in knot], hp
        per_floor.append((best_hp, best))
    per_floor.sort(key=lambda row: row[0])
    return per_floor[len(per_floor) // 2][1]


def floors_report(setting, party_size, trials, enchant, share=0.7):
    print(f"\n=== {setting}, party of {party_size}: the worst knot on each "
          f"floor, at the level you would be ({trials} fights per row, "
          f"+{enchant} gear) ===")
    print(f"{'floor':>5} {'lvl':>4} {'hp':>5} {'AV':>4} {'open':>6} "
          f"{'doorway':>8}  what is standing there")
    for depth in (1, 2, 3, 4, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23, 25):
        knot = worst_cluster(setting, depth, party_size)
        level = level_at(depth, party_size)
        spells = spells_by(level)
        rates = {}
        for frontage in (None, 1):
            won = 0
            for trial in range(trials):
                w = World(seed=1000 + trial, difficulty=setting)
                party = []
                for n in range(party_size):
                    hero = w.add_player(f"Hero{n}", spell="Spark")
                    equip_like(hero, depth, enchant, level=level, share=share)
                    hero.spells.update(spells)
                    stock_belt(hero, heal=3, mana=2)
                    hero.recalc()
                    hero.hp, hero.mana = hero.max_hp, hero.max_mana
                    party.append(hero)
                w.move_player_to(party[0], depth)
                foes = []
                for key in knot:
                    m = w.spawn(key, 0, 0, depth)
                    # `World.populate` makes every creature tougher for a
                    # bigger party. Re-spawning the knot without that was
                    # quietly fighting a solo player's monsters with four
                    # people, and reported 100% everywhere.
                    m.max_hp = int(m.max_hp * (1 + (party_size - 1) * 0.45))
                    m.hp = m.max_hp
                    foes.append(m)
                won += fight_well(w, depth, party, foes, frontage=frontage)
            rates[frontage] = won / trials
        p = party[0]
        names = ", ".join(sorted(set(knot)))
        print(f"{depth:5d} {level:4d} {p.max_hp:5d} {p.armour_class:4d} "
              f"{rates[None]:6.0%} {rates[1]:8.0%}  {len(knot)}x {names[:44]}")


def bosses_report(setting, trials, enchant, share=0.7):
    """Can each party size take the two bosses, at the level they would be?

    The boss scales with the party in `populate` - half again as much health
    per extra person - so this is the real fight, not a single-player fight
    with more swords pointed at it.
    """
    print(f"\n=== {setting}: the bosses, at the level and gear you would "
          f"have ({trials} fights per row, +{enchant}) ===")
    print(f"{'boss':<26} " + " ".join(f"{'party ' + str(n):>9}" for n in (1, 2, 3, 4)))
    for key, depth in (("warden_of_ash", 12), ("vaelrik", 25)):
        rates = []
        for size in (1, 2, 3, 4):
            level = level_at(depth, size)
            spells = spells_by(level)
            won = 0
            for trial in range(trials):
                w = World(seed=2000 + trial, difficulty=setting)
                party = []
                for n in range(size):
                    hero = w.add_player(f"Hero{n}", spell="Spark")
                    equip_like(hero, depth, enchant, level=level, share=share)
                    hero.spells.update(spells)
                    stock_belt(hero, heal=4, mana=3)
                    hero.recalc()
                    hero.hp, hero.mana = hero.max_hp, hero.max_mana
                    party.append(hero)
                w.move_player_to(party[0], depth)
                # The same scaling `World.populate` applies for real.
                crowd = size - 1
                boss = w.spawn(key, 0, 0, depth)
                boss.max_hp = int(boss.max_hp * (1 + crowd * 0.9))
                boss.hp = boss.max_hp
                boss.dmg_bonus = getattr(boss, "dmg_bonus", 0) + crowd * 2
                boss.speed = max(40, int(boss.speed / (1 + crowd * 0.2)))
                won += fight_well(w, depth, party, [boss])
            rates.append(won / trials)
        name = World(seed=1, difficulty=setting).spawn(key, 0, 0, depth).name
        print(f"{name:<26} " + " ".join(f"{r:8.0%} " for r in rates))


def main():
    ap = argparse.ArgumentParser()

    ap.add_argument("--difficulty", default=None,
                    help="one setting, or every setting if left out")
    ap.add_argument("--trials", type=int, default=300)
    ap.add_argument("--party", type=int, default=1,
                    help="how many of them there are")
    ap.add_argument("--enchant", type=int, default=0,
                    help="how good the gear is, as a plus on everything")
    ap.add_argument("--bosses", action="store_true",
                    help="the two bosses, for parties of one to four")
    ap.add_argument("--purse", type=float, default=0.7,
                    help="what share of the copper on the floors above a "
                         "character still has to spend on gear")
    ap.add_argument("--floors", action="store_true",
                    help="the worst knot of creatures on each floor, fought "
                         "in the open and fought in a doorway")
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

    if args.bosses:
        bosses_report(args.difficulty or "Intermediate", args.trials,
                      args.enchant, args.purse)
        return

    if args.floors:
        for size in ((1, 2, 3, 4) if args.party == 0 else (args.party,)):
            floors_report(args.difficulty or "Intermediate", size,
                          args.trials, args.enchant, args.purse)
        return

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
