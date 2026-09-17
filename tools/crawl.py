"""A bot that plays Stormhold, so the game gets played more than I can play it.

It makes a character, kits out in town, and dives: fighting what it meets,
picking up what it finds, resting when hurt, taking the stairs when the floor
is done. It reports what happened and every distinct message it saw, which is
where the parity problems show up - a message that never fires, a message that
fires wrongly, a fight that cannot be won or cannot be lost.

    python3 tools/crawl.py [--seed N] [--depth N] [--turns N] [--port N]
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame                                              # noqa: E402

from tools.playtest import Session                          # noqa: E402
from stormhold.game.spells import SPELLS                    # noqa: E402


def make_character(s, spread=(("strength", 6), ("dexterity", 4),
                              ("intelligence", 3), ("constitution", 3)),
                   spell="Spark", difficulty=None):
    s.click([b for b in s.app.scene.buttons if b.action == "host"][0].rect.center)
    # Hosting binds a socket and waits for our own client to connect, which
    # takes a variable moment. Clicking the stat buttons before the character
    # sheet is up sends the clicks to the menu, where they do nothing.
    for _ in range(40):
        s.settle(0.5)
        if hasattr(s.app.scene, "plus"):
            break
    sc = s.app.scene
    for stat, n in spread:
        for _ in range(n):
            s.click(sc.plus[stat].rect.center)
    if difficulty:
        s.click([b for b in sc.difficulty_buttons
                 if b.action[1] == difficulty][0].rect.center)
    s.click([b for b in sc.spell_buttons if b.action[1] == spell][0].rect.center)
    s.click([b for b in sc.buttons if b.action == "go"][0].rect.center)
    s.settle(2.5)


def kit_out(s, wants=(("general", "Two Slot Belt"),
                      ("armourer", "Leather Armour"),
                      ("weaponsmith", "Short Sword"))):
    town = s.level()
    for shop, want in wants:
        npc = [n for n in town.npcs if n["shop"] == shop][0]
        visit(s, npc)
        s.app.play.send_action({"a": "move",
                                "dx": (npc["x"] > s.me().x) - (npc["x"] < s.me().x),
                                "dy": (npc["y"] > s.me().y) - (npc["y"] < s.me().y)})
        s.settle(0.8)
        store = s.app.scene
        if hasattr(store, "store_cells"):
            store.draw(s.app.screen)
            hit = [(r, i) for r, i in store.store_cells if want in i["name"]]
            if hit:
                s.drag(hit[0][0].center, store.grid_rect.center)
                s.settle(0.4)
                if store.confirm:
                    s.click(store.confirm["yes"].center)
                    s.settle(0.6)
        back_to_the_map(s)

    s.key(pygame.K_i)
    s.settle(0.5)
    pack = s.app.scene
    for _ in range(8):
        pack.draw(s.app.screen)
        todo = [(r, i) for r, i in pack.cell_rects if i.get("slot")]
        if not todo:
            break
        rect, item = todo[0]
        s.drag(rect.center, pack.slot_rects[item["slot"]].center)
        s.settle(0.6)
    back_to_the_map(s)
    # Dragging pack items onto the doll in pack order can end with the
    # starting dagger back in hand over the sword we just paid for.
    wear_the_best_of_what_you_have(s)


def keep_the_belt_stocked(s):
    """Put healing on the belt, since nothing in the pack can be drunk."""
    p = s.me()
    belt = p.equipment.get("waist")
    if belt is None or belt.base.get("belt_slots") is None:
        return
    if len(belt.contents) >= belt.base["belt_slots"]:
        return
    for item in list(p.inventory):
        if item.base.get("use") in ("heal", "mana", "cure"):
            s.app.play.send_action({"a": "stow", "id": item.id, "slot": "waist"})
            s.step(3)
            return


def a_potion_of(s, use):
    belt = s.me().equipment.get("waist")
    for item in getattr(belt, "contents", None) or []:
        if item.base.get("use") == use:
            return item
    return None


def healing_on_the_belt(s):
    belt = s.me().equipment.get("waist")
    for item in getattr(belt, "contents", None) or []:
        if item.base.get("use") == "heal":
            return item
    return None


def go_home(s):
    """Climb back to town. The keep's own stairs, not a cheat."""
    for _ in range(40):
        p = s.me()
        if p.depth == 0:
            return True
        level = s.level()
        target = level.up_at
        if target is None:
            return False
        if (p.x, p.y) != tuple(target):
            if not s.walk_to(*target, limit=120):
                return False
        s.key(pygame.K_COMMA, mod=pygame.KMOD_SHIFT)
        s.settle(1.0)
    return s.me().depth == 0


def dive_back(s, depth):
    """Down the stairs until we are back where we left off.

    Not before resting, though. Waking at the temple on a fraction of your
    hit points and walking straight back down the stairs is how one death
    turns into ten.
    """
    for _ in range(30):
        p = s.me()
        if p.hp >= p.max_hp * 0.9 or monsters_near(s, 3):
            break
        s.app.play.send_action({"a": "rest"})
        s.step(6)
    for _ in range(40):
        p = s.me()
        if p.depth >= depth:
            return True
        level = s.level()
        if level.down_at is None:
            return False
        if (p.x, p.y) != tuple(level.down_at):
            if not s.walk_to(*level.down_at, limit=200):
                return False
        s.key(pygame.K_PERIOD, mod=pygame.KMOD_SHIFT)
        s.settle(1.0)
    return s.me().depth >= depth


def open_sides(level, x, y):
    """How many ways something can reach this square."""
    return sum(1 for dx in (-1, 0, 1) for dy in (-1, 0, 1)
               if (dx or dy) and level.passable(x + dx, y + dy))


def a_place_to_make_a_stand(s, foes):
    """The nearest tight spot, away from the pack.

    A doorway or a corridor end lets a pack come at you one at a time, which
    is the difference between a fight and a mobbing.
    """
    level, p = s.level(), s.me()
    here = open_sides(level, p.x, p.y)
    if here <= 3:
        return None                     # already in a tight spot
    # Only the squares we could step to this turn. Hunting further afield
    # costs a pathfind for every candidate, and the pack is already on us.
    best, best_score = None, here
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if not (dx or dy):
                continue
            x, y = p.x + dx, p.y + dy
            if not level.walkable(x, y, p.id):
                continue
            ways = open_sides(level, x, y)
            if ways >= best_score:
                continue
            if min(max(abs(m.x - x), abs(m.y - y)) for m in foes) < 2:
                continue                # not towards them
            best, best_score = (x, y), ways
    return best


def monsters_near(s, reach=9):
    p = s.me()
    return [m for m in s.level().actors.values()
            if getattr(m, "kind", None) == "monster" and not m.dead
            and max(abs(m.x - p.x), abs(m.y - p.y)) <= reach]


def best_attack_spell(s, reach=None):
    """The hardest hit this character can pay for right now.

    It used to pick the spell with the largest listed mana cost and then
    compare that listed cost against the character's mana - but the real cost
    falls with caster level, so it turned down spells it could afford and
    tried ones it could not.
    """
    from stormhold.common.constants import mana_cost
    p = s.me()
    best, best_dmg = None, 0
    for name in p.spells:
        spell = SPELLS.get(name)
        if not spell or not spell.get("dmg"):
            continue
        if reach is not None and spell.get("rng", 0) < reach:
            continue
        if mana_cost(spell["mana"], p.level, spell.get("level", 1)) > p.mana:
            continue
        dice = spell["dmg"]
        damage = dice[0] * (dice[1] + 1) / 2 + dice[2] * p.level
        if damage > best_dmg:
            best, best_dmg = name, damage
    return best


# --------------------------------------------------------------------------
#  Playing properly: spend the loot, learn the spells, wear the better thing
# --------------------------------------------------------------------------

def worth_wearing(candidate, current, ammo=()):
    """Is this better than what is on? Armour by AV, weapons by average hit.

    `ammo` is vestigial: it used to keep the bot from wielding a bow it had
    no arrows for. There are no bows now.
    """
    if candidate.slot == "weapon":
        def swing(it):
            if it is None:
                return 2
            n, sides = it.damage()
            return n * (sides + 1) / 2 + it.enchant
        return swing(candidate) > swing(current)
    return candidate.ac() > (current.ac() if current else 0)


def ammunition(p):
    return {it.base["ammo"] for it in p.inventory if it.base.get("ammo")}


def wear_the_best_of_what_you_have(s):
    """Put on anything in the pack that beats what is already worn."""
    p = s.me()
    have = ammunition(p)
    for item in list(p.inventory):
        if not item.slot:
            continue
        if worth_wearing(item, p.equipment.get(item.slot), have):
            s.app.play.send_action({"a": "equip", "id": item.id,
                                    "slot": item.slot})
            s.step(3)


def study_anything_readable(s):
    """Read every tome carried. Spells are the only damage that scales."""
    p = s.me()
    for item in list(p.inventory):
        if item.spell and item.spell not in p.spells:
            belt = p.equipment.get("waist")
            if belt is not None and belt.contents is not None:
                s.app.play.send_action({"a": "stow", "id": item.id,
                                        "slot": "waist"})
                s.step(2)
            s.app.play.send_action({"a": "use", "id": item.id})
            s.step(3)


def back_to_the_map(s):
    """Close whatever window is open, and nothing else.

    Pressing Escape when no window is open *opens* the game menu, and the
    menu then swallows every keystroke after it - which is how the bot came
    to stand in the town square for four hundred turns, unable to press the
    key for "go down the stairs".
    """
    for _ in range(4):
        if s.app.scene.__class__.__name__ == "PlayScene":
            return True
        s.key(pygame.K_ESCAPE)
        s.settle(0.3)
    return s.app.scene.__class__.__name__ == "PlayScene"


def visit(s, npc):
    """Stand next to a shopkeeper.

    You cannot stand *on* one, so walking to the counter's own square always
    reports failure - which is how the bot came to walk to all four shops and
    then buy nothing at any of them.
    """
    p, level = s.me(), s.level()
    if max(abs(p.x - npc["x"]), abs(p.y - npc["y"])) <= 1:
        return True
    spots = [(npc["x"] + dx, npc["y"] + dy)
             for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy]
    spots.sort(key=lambda q: max(abs(q[0] - p.x), abs(q[1] - p.y)))
    for x, y in spots:
        if level.passable(x, y) and s.walk_to(x, y, limit=200):
            return True
    return False


def go_shopping(s, log=None):
    """Sell what the trades will take, then buy the best of what is left.

    A bot that never goes back to town fights the whole keep in starting
    leather, which is not what the game is like and not what its difficulty
    should be judged on.
    """
    world, p = s.world, s.me()
    town = world.levels[0]
    npcs = {n["shop"]: n for n in town.npcs}
    # Only loot we walked into town with is for sale. Without this the junk
    # dealer at the end of the round buys back, at a loss, the sword and
    # armour we bought two shops earlier - which is where five thousand
    # copper went in the last run.
    for_sale = {it.id for it in p.inventory}

    for shop in ("weaponsmith", "armourer", "magic", "junk"):
        npc = npcs.get(shop)
        if not npc:
            continue
        if not visit(s, npc):
            continue
        s.settle(0.4)
        # Sell everything this trade will take that we are not wearing.
        have = ammunition(p)
        for item in list(p.inventory):
            if item.id not in for_sale:
                continue
            if item.spell or item.base.get("use") in ("heal", "mana", "cure"):
                continue
            if item.slot and worth_wearing(item, p.equipment.get(item.slot), have):
                continue                # it is better than what we have on
            if world.shop_refusal(shop, item):
                continue
            s.app.play.send_action({"a": "sell", "shop": shop, "id": item.id,
                                    "npc": npc["x"]})
            s.step(3)
        # Buy the best thing on the shelf we can afford and would wear.
        for _ in range(6):
            view = world.shop_view(p, shop, 0, npc["name"])
            wanted = None
            # Healing first. Everything else is worth nothing to a corpse,
            # and an empty belt is what most of the bot's deaths were.
            def ranked(row_item):
                _row, item = row_item
                if item.base.get("use") == "heal":
                    return 0
                if item.spell and item.spell not in p.spells:
                    return 1
                if item.base.get("use") == "mana":
                    return 2
                return 3

            have = ammunition(p)
            belt = p.equipment.get("waist")
            slots = (belt.base.get("belt_slots", 0) if belt else 0)
            room_on_belt = belt is not None and len(belt.contents) < slots
            shelf = []
            for row in view["stock"]:
                item = next((i for i in world.stock_for(shop)
                             if i.id == row["id"]), None)
                if item is None or row["price"] > p.copper:
                    continue
                if item.spell and item.spell not in p.spells:
                    shelf.append((row, item))
                elif item.slot and worth_wearing(
                        item, p.equipment.get(item.slot), have):
                    shelf.append((row, item))
                elif item.base.get("use") in ("heal", "mana") and room_on_belt:
                    shelf.append((row, item))
            # Keep enough back for a healing potion until there is one on
            # the belt. Five weapons and no healing is how the bot used to
            # come out of town.
            if room_on_belt and p.copper < 2000:
                shelf = [row_item for row_item in shelf
                         if row_item[1].base.get("use") == "heal"]
            if shelf:
                wanted = min(shelf, key=ranked)
            if wanted is None:
                break
            s.app.play.send_action({"a": "buy", "shop": shop,
                                    "id": wanted[0]["id"], "npc": npc["x"]})
            s.step(3)
            # Put it on before deciding what else to buy, or every weapon on
            # the rack looks like an upgrade on the dagger still in hand.
            wear_the_best_of_what_you_have(s)
            keep_the_belt_stocked(s)
        back_to_the_map(s)

    # A belt is the only thing that makes a potion usable at all.
    if p.equipment.get("waist") is None:
        npc = npcs.get("general")
        if npc and visit(s, npc):
            s.settle(0.4)
            view = world.shop_view(p, "general", 0, npc["name"])
            for row in view["stock"]:
                if "Belt" in row["name"] and row["price"] <= p.copper:
                    s.app.play.send_action({"a": "buy", "shop": "general",
                                            "id": row["id"], "npc": npc["x"]})
                    s.step(3)
                    break
            back_to_the_map(s)

    wear_the_best_of_what_you_have(s)
    study_anything_readable(s)
    for _ in range(8):
        keep_the_belt_stocked(s)


def crawl(s, to_depth=5, turns=3000, log=print, shopping=True):
    seen, order = set(), []

    def note():
        for m in s.log(30):
            if m not in seen:
                seen.add(m)
                order.append(m)

    def step_toward(tx, ty):
        p = s.me()
        s.app.play.send_action({"a": "move",
                                "dx": (tx > p.x) - (tx < p.x),
                                "dy": (ty > p.y) - (ty < p.y)})
        s.step(3)

    took = 0
    on_this_floor = 0
    shopped = False
    floor = s.me().depth
    deepest = [s.me().depth]
    while took < turns and s.me().depth < to_depth and not s.me().dead:
        took += 1
        p, lv = s.me(), s.level()
        if p.depth != floor:
            floor, on_this_floor, shopped = p.depth, 0, False
            deepest[0] = max(deepest[0], p.depth)
            wear_the_best_of_what_you_have(s)
            study_anything_readable(s)
        on_this_floor += 1
        # Killing things drops more things, so a bot that always walks to the
        # nearest pile never leaves the first floor. After a while, go down.
        greedy = on_this_floor < 60
        near = monsters_near(s)
        # "Near" for fighting is everything in sight; "near" for resting has
        # to be much tighter. Nine squares is almost always occupied by
        # something, so the bot never rested, never healed between fights,
        # and ground itself down to nothing over a floor.
        close = monsters_near(s, 3)
        keep_the_belt_stocked(s)

        # --- staying alive --------------------------------------------------
        if p.hp < p.max_hp * 0.5:
            potion = a_potion_of(s, "heal")
            if potion is not None:
                s.app.play.send_action({"a": "use", "id": potion.id})
                s.step(4); note(); continue
        # Rest up to nearly full, not to a third: walking into the next room
        # on eight hit points is how the last one died.
        if p.hp < p.max_hp * 0.85 and not close:
            s.app.play.send_action({"a": "rest"})
            s.step(6); note(); continue
        if not close and p.mana < p.max_mana * 0.3:
            potion = a_potion_of(s, "mana")
            if potion is not None:
                s.app.play.send_action({"a": "use", "id": potion.id})
                s.step(4); note(); continue
            # Sleep restores mana at twice the waking rate, and spells are the
            # only damage that grows with level - so they are worth waiting for.
            s.app.play.send_action({"a": "sleep"})
            s.step(6); note(); continue

        # --- knowing when to run --------------------------------------------
        # Nothing in the pack heals, no mana left, and a quarter of the hit
        # points gone: this fight is already lost. Back away. The temple
        # hands you back, but it takes your gear and some of what you knew,
        # which is a worse outcome than a lost floor.
        if near and p.hp < p.max_hp * 0.3 and a_potion_of(s, "heal") is None:
            away = None
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if not (dx or dy):
                        continue
                    x, y = p.x + dx, p.y + dy
                    if not lv.walkable(x, y, p.id):
                        continue
                    gap = min(max(abs(m.x - x), abs(m.y - y)) for m in near)
                    if away is None or gap > away[0]:
                        away = (gap, (x, y))
            here = min(max(abs(m.x - p.x), abs(m.y - p.y)) for m in near)
            if away and away[0] > here:
                step_toward(*away[1]); note(); continue

        # --- fighting -------------------------------------------------------
        if near:
            # "When found in numbers can be much more deadly." Standing in the
            # open against a pack is how a starting character dies; standing
            # in a doorway means fighting them one at a time.
            if len(near) >= 2 and p.hp < p.max_hp * 0.9:
                spot = a_place_to_make_a_stand(s, near)
                if spot and spot != (p.x, p.y):
                    step_toward(*spot); note(); continue
            m = min(near, key=lambda m: max(abs(m.x - p.x), abs(m.y - p.y)))
            gap = max(abs(m.x - p.x), abs(m.y - p.y))
            spell = best_attack_spell(s, reach=gap)
            if spell and gap > 1:
                s.app.play.send_action({"a": "cast", "spell": spell,
                                        "x": m.x, "y": m.y})
                s.step(4); note(); continue
            if gap <= 1:
                spell = best_attack_spell(s, reach=1)
                if spell and p.hp < p.max_hp * 0.7:
                    s.app.play.send_action({"a": "cast", "spell": spell,
                                            "x": m.x, "y": m.y})
                    s.step(4); note(); continue
            step_toward(m.x, m.y); note(); continue

        # --- picking things up ----------------------------------------------
        if lv.ground.get((p.x, p.y)):
            s.app.play.send_action({"a": "pickup"})
            s.step(4)
            wear_the_best_of_what_you_have(s)
            study_anything_readable(s)
            note(); continue
        piles = [xy for xy, pile in lv.ground.items() if pile] if greedy else []
        if piles:
            t = min(piles, key=lambda q: max(abs(q[0] - p.x), abs(q[1] - p.y)))
            if s.path_to(*t):
                step_toward(*t); note(); continue

        # --- spending it ----------------------------------------------------
        # Whenever we are in town with money to spend - which includes every
        # time we are killed and wake at the temple - turn it into equipment
        # before going back down. A bot that never shops fights the whole
        # keep in starting leather with an empty belt.
        if shopping and p.depth == 0 and p.copper > 400 and not shopped:
            shopped = True          # one trip round the square per visit
            go_shopping(s)
            dive_back(s, max(1, deepest[0]))
            note(); continue
        if shopping and p.depth > 0 and on_this_floor > 220 and p.copper > 2500:
            # A full purse is no use down here.
            if go_home(s):
                go_shopping(s)
                dive_back(s, floor)
                note(); continue

        if lv.down_at:
            if (p.x, p.y) == tuple(lv.down_at):
                s.key(pygame.K_PERIOD, mod=pygame.KMOD_SHIFT)
                s.settle(1.2); note(); continue
            # Walking one greedy step at a time gets stuck against the first
            # wall between here and the stairs; go by the actual path.
            if not s.walk_to(*lv.down_at, limit=60):
                step_toward(*lv.down_at)
            note(); continue
        break

    note()
    return took, order


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=4242)
    ap.add_argument("--depth", type=int, default=5)
    ap.add_argument("--turns", type=int, default=3000)
    ap.add_argument("--port", type=int, default=7801)
    ap.add_argument("--difficulty", default=None)
    ap.add_argument("--spell", default="Spark")
    ap.add_argument("--mighty", action="store_true",
                    help="make the character absurdly strong, to test the "
                         "deep floors and the bosses rather than the balance")
    a = ap.parse_args()

    s = Session(seed=a.seed, port=a.port)
    make_character(s, spell=a.spell, difficulty=a.difficulty)
    kit_out(s)
    if a.mighty:
        p = s.me()
        p.stats = {k: 18 for k in p.stats}
        p.level = 25
        p.recalc()
        p.max_hp = p.hp = 4000
        p.max_mana = p.mana = 900
        from stormhold.game.items import Item
        for key, slot in (("platemail", "torso"), ("towershield", "shield"),
                          ("helm", "head"), ("halberd", "weapon")):
            it = Item(key, enchant=5)
            it.known = True
            p.equipment[slot] = it
        p.spells = set(SPELLS)

    s.walk_to(*s.level().down_at)
    s.key(pygame.K_PERIOD, mod=pygame.KMOD_SHIFT)
    s.settle(1.5)

    took, messages = crawl(s, a.depth, a.turns)
    p = s.me()
    print(f"=== seed {a.seed} ({s.world.difficulty}): {took} turns, depth {p.depth}, level {p.level}, "
          f"xp {p.xp}, hp {p.hp}/{p.max_hp}, kills {p.kills}, deaths {p.deaths}")
    s.shot(f"crawl-{a.seed}")
    print("=== every distinct message:")
    for m in messages:
        print("   ", m)
    s.close()


if __name__ == "__main__":
    main()
