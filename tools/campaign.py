"""Play the whole keep, floor by floor, through the game's own engine.

`tools/balance.py` measures one fight at a time, which tells you whether a
creature is too hard but not whether the game is finishable. This plays a
whole campaign: it makes a party, walks them down twenty-five floors,
fighting what is actually there, picking up what is actually on the ground,
levelling on the experience that is actually awarded, and going back to town
to spend what they actually found.

Every decision goes through `World.submit`, so the monster AI, the ranged
attacks, the boss specials, the traps, the wandering monsters and the shared
floor clock are all the real ones. Nothing here models the game; it plays it.

    python3 tools/campaign.py --party 1 --runs 3
    python3 tools/campaign.py --party 4 --difficulty Easy --verbose

What it is not: a good player. It does not use doorways, it does not lure,
it does not read a scroll of teleportation when things go wrong. Read its
results as what a competent, unimaginative person would get.
"""

import argparse
import os
import statistics
import sys
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stormhold.common.constants import (DIFFICULTIES, MAX_DEPTH,    # noqa: E402
                                        TOWN_DEPTH, mana_cost)
from stormhold.game import combat                                   # noqa: E402
from stormhold.game.items import Item                               # noqa: E402
from stormhold.game.level import can_walk_through                   # noqa: E402
from stormhold.game.spells import SPELLS                            # noqa: E402
from stormhold.game.world import World                              # noqa: E402


# --------------------------------------------------------------------------
#  Getting about
# --------------------------------------------------------------------------

def path(level, start, goal, mover=None):
    """Breadth-first to a square. A closed door is a step, not a wall."""
    if start == goal:
        return []
    seen = {start: None}
    q = deque([start])
    while q:
        cur = q.popleft()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if not (dx or dy):
                    continue
                nxt = (cur[0] + dx, cur[1] + dy)
                if nxt in seen or not level.in_bounds(*nxt):
                    continue
                if nxt != goal and not can_walk_through(level, *nxt):
                    continue
                seen[nxt] = cur
                if nxt == goal:
                    steps = []
                    node = nxt
                    while node != start:
                        prev = seen[node]
                        steps.append((node[0] - prev[0], node[1] - prev[1]))
                        node = prev
                    return list(reversed(steps))
                q.append(nxt)
    return None


def gap(a, b):
    return max(abs(a.x - b.x), abs(a.y - b.y))


def step_action(dx, dy):
    return {"a": "move", "dx": dx, "dy": dy}


# --------------------------------------------------------------------------
#  What the character knows how to do
# --------------------------------------------------------------------------

def belt_of(p):
    belt = p.equipment.get("waist")
    return belt if getattr(belt, "contents", None) is not None else None


def on_belt(p, use):
    belt = belt_of(p)
    for it in (belt.contents if belt else []):
        if it.base.get("use") == use:
            return it
    return None


def best_attack_spell(p, reach=None):
    """The hardest hit this character can pay for right now."""
    best, best_dmg = None, 0
    for name in p.spells:
        spell = SPELLS.get(name)
        if not spell or not spell.get("dmg"):
            continue
        if reach is not None and spell.get("rng", 0) and spell["rng"] < reach:
            continue
        if spell.get("rng", 0) == 0 and reach is not None and reach > 1:
            continue                  # a burst centred on you needs them close
        if mana_cost(spell["mana"], p.level, spell.get("level", 1)) > p.mana:
            continue
        n, sides, per = spell["dmg"]
        damage = n * (sides + 1) / 2 + per * p.level
        if damage > best_dmg:
            best, best_dmg = name, damage
    return best


def swing_of(item):
    if item is None:
        return 2.0
    n, sides = item.damage()
    return n * (sides + 1) / 2.0 + item.enchant


def better_than_worn(p, item):
    """Is this worth putting on? Armour by armour value, weapons by damage."""
    if not item.slot:
        return False
    if item.cursed and item.known:
        return False
    current = p.equipment.get(item.slot)
    if item.slot == "weapon":
        missile = item.base.get("missile")
        if missile and not any(i.base.get("ammo") == missile
                               for i in p.inventory):
            return False              # a bow with no arrows is a stick
        if item.base.get("str_req", 0) > p.stat("strength"):
            return False
        return swing_of(item) > swing_of(current)
    if item.base.get("str_req", 0) > p.stat("strength"):
        return False
    return item.ac() > (current.ac() if current else 0)


def kit_up(world, p):
    """Put on the best of what we are carrying, and read what we can."""
    level = world.levels[p.depth]
    for item in sorted(list(p.inventory), key=swing_of, reverse=True):
        if better_than_worn(p, item):
            world.do_player_action(level, p, {"a": "equip", "id": item.id,
                                              "slot": item.slot})
    belt = belt_of(p)
    for item in list(p.inventory):
        if item.spell and item.spell not in p.spells:
            # A book has to be to hand to be read, like anything else.
            if belt is not None and len(belt.contents) < belt.base["belt_slots"]:
                world.do_player_action(level, p, {"a": "stow", "id": item.id,
                                                  "slot": "waist"})
                world.do_player_action(level, p, {"a": "use", "id": item.id})
    stock_belt(world, p)


def stock_belt(world, p):
    """Healing to hand. Nothing in the pack can be drunk."""
    belt = belt_of(p)
    if belt is None:
        return
    room = belt.base.get("belt_slots", 0) - len(belt.contents)
    if room <= 0:
        return
    level = world.levels[p.depth]
    wanted = [i for i in p.inventory if i.base.get("use") == "heal"]
    wanted += [i for i in p.inventory if i.base.get("use") == "mana"]
    for item in wanted[:room]:
        world.do_player_action(level, p, {"a": "stow", "id": item.id,
                                          "slot": "waist"})


# --------------------------------------------------------------------------
#  Town
# --------------------------------------------------------------------------

SHOPS = ("weaponsmith", "armourer", "general", "magic", "junk")


def go_to_town(world, party, log=None):
    """Sell the haul, buy the best of what is on the shelves, read the books.

    Buying and selling are free actions with no adjacency check, so this does
    not walk the party round the square - it is the shopping, not the walking,
    that decides whether the party is equipped for the next floor.
    """
    for p in party:
        if p.depth != TOWN_DEPTH:
            world.move_player_to(p, TOWN_DEPTH)
    town = world.levels[TOWN_DEPTH]
    npcs = {n["shop"]: n for n in town.npcs}
    world.shop_stock.clear()

    for p in party:
        # --- sell what we will not use ------------------------------------
        for shop in SHOPS:
            if shop not in npcs:
                continue
            for item in list(p.inventory):
                if item.spell or item.base.get("use") in ("heal", "mana", "cure"):
                    continue
                if better_than_worn(p, item):
                    continue
                if world.shop_refusal(shop, item):
                    continue
                world.do_player_action(town, p, {"a": "sell", "shop": shop,
                                                 "id": item.id})
        # --- a belt first, then healing, then gear ------------------------
        for _ in range(40):
            pick = best_buy(world, p, npcs)
            if pick is None:
                break
            shop, item = pick
            world.do_player_action(town, p, {"a": "buy", "shop": shop,
                                             "id": item.id})
            kit_up(world, p)
        # --- and the temple, for drained stats and curses ------------------
        # Only when it is a quarter of the purse or less: the character who
        # spends everything on a rite has nothing left for armour.
        for row in world.temple_services(p):
            if not row["useful"] or not row["afford"]:
                continue
            if not (row["key"].startswith("restore_")
                    or row["key"] == "cure_poison"):
                continue
            if row["price"] > p.copper * 0.25:
                continue
            world.do_player_action(town, p, {"a": "service",
                                             "what": row["key"],
                                             "temple": True})
        kit_up(world, p)
        # A thousand copper weighs a kilo. The strongroom is in the game for
        # exactly this reason, and a party that never uses it walks into the
        # keep at a crawl.
        keep = 4000
        if p.copper > keep:
            world.do_player_action(town, p, {"a": "service", "what": "deposit",
                                             "amount": p.copper - keep})
        elif p.copper < 1500 and p.bank:
            world.do_player_action(town, p, {"a": "service", "what": "withdraw",
                                             "amount": min(p.bank, 4000)})
        p.__dict__.pop("_too_heavy", None)
        if log:
            log(f"    town: {p.name} cp {p.copper} "
                f"{[i.name(None) for i in belt_of(p).contents] if belt_of(p) else []}")


def best_buy(world, p, npcs):
    """The one thing most worth buying in the whole town, or nothing.

    Shop by shop was wrong: the weaponsmith is the first door on the square,
    so a character walked out with a spear and no belt - and with no belt
    there is nowhere to put a healing potion, which is most of what kills a
    character who can otherwise win the fight.
    """
    best = None
    for shop in SHOPS:
        if shop not in npcs:
            continue
        found = shelf_pick(world, p, shop)
        if found and (best is None or found[1] < best[2]):
            best = (shop, found[0], found[1])
    return (best[0], best[1]) if best else None


def shelf_pick(world, p, shop):
    """The one thing most worth buying here, as (item, rank), or nothing.

    The order is the order a person buys in, and getting it wrong is not a
    detail: with everything wearable ranked alike, a character spent its
    whole starting purse on a spear and walked down the stairs with no
    armour, no belt and nothing to drink.
    """
    belt = belt_of(p)
    slots = belt.base.get("belt_slots", 0) if belt else 0
    room = belt is not None and len(belt.contents) < slots
    healing = sum(1 for i in (belt.contents if belt else [])
                  if i.base.get("use") == "heal")
    armoured = p.equipment.get("torso") is not None
    weapon = p.equipment.get("weapon")
    stick = weapon is None or weapon.key == "dagger"

    best, best_rank = None, 99
    for item in world.stock_for(shop):
        if world.shop_price(item) > p.copper:
            continue
        ok, _why = p.room_for(item)
        if not ok:
            continue
        use = item.base.get("use")
        if item.slot == "torso" and better_than_worn(p, item):
            rank = 0 if not armoured else 3
        elif belt is None and item.base.get("belt_slots"):
            rank = 1
        elif use == "heal" and room and healing < 2:
            rank = 2
        elif item.slot == "weapon" and better_than_worn(p, item) and stick:
            rank = 3          # anything beats the dagger you started with
        elif item.slot and item.slot != "weapon" and better_than_worn(p, item):
            rank = 4
        elif item.spell and item.spell not in p.spells and can_read(p, item.spell):
            rank = 5
        elif item.slot == "weapon" and better_than_worn(p, item):
            rank = 6
        elif use in ("heal", "mana") and room:
            rank = 7
        else:
            continue
        if rank < best_rank:
            best, best_rank = item, rank
    return (best, best_rank) if best else None


def can_read(p, spell):
    s = SPELLS.get(spell)
    return bool(s) and p.level >= s["level"] and p.stat("intelligence") >= s["int_req"]


# --------------------------------------------------------------------------
#  A floor
# --------------------------------------------------------------------------

def open_sides(level, x, y):
    """How many ways something can reach this square."""
    return sum(1 for dx in (-1, 0, 1) for dy in (-1, 0, 1)
               if (dx or dy) and level.passable(x + dx, y + dy))


def a_doorway(level, p, foes):
    """The nearest tighter square, on the far side from the pack.

    "When found in numbers can be much more deadly" - the manual's own words,
    and the answer to it is a doorway. Standing in the open against four dire
    wolves is not a hard fight, it is arithmetic: they get four swings a turn
    and you get one.
    """
    here = open_sides(level, p.x, p.y)
    if here <= 3:
        return None
    near = min(gap(m, p) for m in foes)
    best, best_ways = None, here
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if not (dx or dy):
                continue
            x, y = p.x + dx, p.y + dy
            if not level.walkable(x, y, p.id):
                continue
            if min(max(abs(m.x - x), abs(m.y - y)) for m in foes) < near:
                continue                      # not away from them
            ways = open_sides(level, x, y)
            if ways < best_ways:
                best, best_ways = (x, y), ways
    return best


def way_out(world, level, p):
    """Back to the stairs we came in by, and up them.

    Leaving a floor you cannot take is not giving up, it is the game: you
    come back with a better sword. A character who never leaves has only one
    way for a bad fight to end.
    """
    if level.up_at is None:
        return None
    if (p.x, p.y) == tuple(level.up_at):
        return {"a": "stairs", "dir": "up"}
    steps = path(level, (p.x, p.y), tuple(level.up_at))
    return step_action(*steps[0]) if steps else None


def visible_foes(world, level, p, reach=9):
    return [a for a in level.actors.values()
            if a.kind == "monster" and not a.dead and gap(a, p) <= reach]


def decide(world, level, p, looting=True):
    """One action for one character. None means "nothing left to do here"."""
    foes = visible_foes(world, level, p)
    close = [m for m in foes if gap(m, p) <= 3]

    # --- staying alive ----------------------------------------------------
    if p.hp < p.max_hp * 0.5:
        potion = on_belt(p, "heal")
        if potion is not None:
            return {"a": "use", "id": potion.id}
    # The engine refuses to rest with anything in sight within eight squares,
    # so asking on any looser test just burns the turn on a refusal.
    if not combat.enemies_in_sight(world, level, p, 8):
        if p.hp < p.max_hp * 0.95 or p.mana < p.max_mana * 0.7:
            return {"a": "rest"}

    # --- getting out of a fight we are losing ------------------------------
    if foes and p.hp < p.max_hp * 0.35 and on_belt(p, "heal") is None:
        out = way_out(world, level, p)
        if out is not None:
            return out

    # --- fighting ---------------------------------------------------------
    if foes:
        # Back into a doorway before they surround us.
        if len(close) >= 2:
            spot = a_doorway(level, p, close)
            if spot:
                return step_action(spot[0] - p.x, spot[1] - p.y)
        target = min(foes, key=lambda m: gap(m, p))
        reach = gap(target, p)
        spell = best_attack_spell(p, reach=reach)
        # Cast whenever the spell hits harder than the weapon does. Spell
        # damage is the only damage that grows with level.
        if spell:
            n, sides, per = SPELLS[spell]["dmg"]
            magic = n * (sides + 1) / 2 + per * p.level
            if reach > 1 or magic > swing_of(p.equipment.get("weapon")) * 1.2:
                return {"a": "cast", "spell": spell, "x": target.x, "y": target.y}
        steps = path(level, (p.x, p.y), (target.x, target.y))
        if steps:
            return step_action(*steps[0])
        return {"a": "wait"}

    # --- picking things up ------------------------------------------------
    # A pile we could not lift is a pile we must stop walking back to, or the
    # character spends the rest of the floor saying "there is no more room in
    # your pack for that weight".
    skip = p.__dict__.setdefault("_too_heavy", set())
    if looting:
        if level.items_at(p.x, p.y) and (p.x, p.y) not in skip:
            carried = len(p.inventory)
            before = len(level.items_at(p.x, p.y))
            world.do_player_action(level, p, {"a": "pickup"})
            if len(p.inventory) == carried and len(level.items_at(p.x, p.y)) >= before:
                skip.add((p.x, p.y))
            return {"a": "wait"}
        piles = [xy for xy, pile in level.ground.items()
                 if pile and xy not in skip]
        piles.sort(key=lambda q: max(abs(q[0] - p.x), abs(q[1] - p.y)))
        for spot in piles[:12]:
            steps = path(level, (p.x, p.y), spot)
            if steps:
                return step_action(*steps[0])

    # --- down ---------------------------------------------------------------
    if level.down_at:
        if (p.x, p.y) == tuple(level.down_at):
            return {"a": "stairs", "dir": "down"}
        steps = path(level, (p.x, p.y), tuple(level.down_at))
        if steps:
            return step_action(*steps[0])
    return None


def clear_floor(world, party, depth, budget=6000, log=None):
    """Play one floor until it is cleared and looted, or the budget runs out."""
    level = world.levels[depth]
    spent = 0
    stuck = 0
    while spent < budget:
        acted = False
        for p in party:
            if p.depth != depth:
                continue
            action = decide(world, level, p)
            if action is None:
                continue
            if action.get("a") == "stairs":
                if action.get("dir") == "up":
                    world.submit(p, action)
                    spent += 1
                    return "withdrew", spent
                return "descended", spent
            world.submit(p, action)
            spent += 1
            acted = True
        if not acted:
            stuck += 1
            if stuck > 3:
                return "stuck", spent
        else:
            stuck = 0
        if all(p.depth != depth for p in party):
            return "left", spent
    return "budget", spent


# --------------------------------------------------------------------------
#  The whole thing
# --------------------------------------------------------------------------

def make_party(world, size, spread=None):
    spread = spread or {"strength": 14, "dexterity": 12,
                        "intelligence": 12, "constitution": 14}
    party = []
    for n in range(size):
        p = world.add_player(f"Hero{n + 1}", dict(spread), spell="Spark")
        party.append(p)
    return party


def run(seed=1, size=1, difficulty="Intermediate", to_depth=MAX_DEPTH,
        budget=6000, tries=3, log=None):
    world = World(seed=seed, difficulty=difficulty)
    party = make_party(world, size)
    go_to_town(world, party, log=log)

    rows = []
    for depth in range(1, to_depth + 1):
        # A person who dies on a floor does not shrug and walk down to the
        # next one. They come back to the same floor, better equipped, and
        # try again - and if they cannot take it after several goes, that is
        # where their run ends. Pushing the party deeper after every death
        # was measuring a death spiral, not the game.
        outcome, spent, died = "stalled", 0, 0
        for attempt in range(tries):
            for p in party:
                world.move_player_to(p, depth)
                p.hp, p.mana = p.max_hp, p.max_mana
            before = {q.id: q.deaths for q in party}
            outcome, spent = clear_floor(world, party, depth, budget, log=log)
            died += sum(q.deaths - before[q.id] for q in party)
            go_to_town(world, party, log=log)
            if outcome == "descended":
                break
        lead = party[0]
        rows.append(dict(depth=depth, outcome=outcome, actions=spent,
                         deaths=died, level=lead.level,
                         hp=lead.max_hp, av=lead.armour_class,
                         copper=sum(p.copper for p in party),
                         spells=len(lead.spells),
                         weapon=(lead.equipment.get("weapon").name(None)
                                 if lead.equipment.get("weapon") else "-")))
        if log:
            r = rows[-1]
            log(f"  floor {depth:2d}: {outcome:9s} {spent:5d} actions, "
                f"{died} deaths, level {r['level']}, {r['hp']} hp, "
                f"AV {r['av']}, {r['spells']} spells, {r['copper']} cp, "
                f"{r['weapon']}")
        if outcome != "descended":
            break
    return world, party, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--party", type=int, default=1)
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--difficulty", default="Intermediate")
    ap.add_argument("--depth", type=int, default=MAX_DEPTH)
    ap.add_argument("--budget", type=int, default=6000)
    ap.add_argument("--tries", type=int, default=3,
                    help="how many goes at a floor before the run is over")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--all-parties", action="store_true",
                    help="one run each for parties of 1, 2, 3 and 4")
    args = ap.parse_args()

    sizes = (1, 2, 3, 4) if args.all_parties else (args.party,)
    for size in sizes:
        deepest, total_deaths = [], []
        for n in range(args.runs):
            log = print if args.verbose else None
            if log:
                print(f"=== party of {size}, seed {args.seed + n} ===")
            _w, party, rows = run(seed=args.seed + n, size=size,
                                  difficulty=args.difficulty,
                                  to_depth=args.depth, budget=args.budget,
                                  tries=args.tries, log=log)
            reached = max((r["depth"] for r in rows
                           if r["outcome"] == "descended"), default=0)
            deepest.append(reached)
            total_deaths.append(sum(r["deaths"] for r in rows))
            print(f"party {size}, seed {args.seed + n}: reached floor "
                  f"{reached}, {total_deaths[-1]} deaths, "
                  f"level {party[0].level}, {len(party[0].spells)} spells")
        print(f"--- party of {size}: median floor "
              f"{statistics.median(deepest):.0f}, "
              f"median deaths {statistics.median(total_deaths):.0f}")


if __name__ == "__main__":
    main()
