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
    s.settle(2)
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
        s.walk_to(npc["x"], npc["y"])
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
        s.key(pygame.K_ESCAPE)
        s.settle(0.4)

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
    s.key(pygame.K_ESCAPE)
    s.settle(0.4)


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


def healing_on_the_belt(s):
    belt = s.me().equipment.get("waist")
    for item in getattr(belt, "contents", None) or []:
        if item.base.get("use") == "heal":
            return item
    return None


def monsters_near(s, reach=9):
    p = s.me()
    return [m for m in s.level().actors.values()
            if getattr(m, "kind", None) == "monster" and not m.dead
            and max(abs(m.x - p.x), abs(m.y - p.y)) <= reach]


def best_attack_spell(s):
    from stormhold.game.spells import SPELLS
    known = [n for n in s.me().spells if SPELLS[n].get("dmg")]
    return max(known, key=lambda n: SPELLS[n]["mana"], default=None)


def crawl(s, to_depth=5, turns=3000, log=print):
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
    floor = s.me().depth
    while took < turns and s.me().depth < to_depth and not s.me().dead:
        took += 1
        p, lv = s.me(), s.level()
        if p.depth != floor:
            floor, on_this_floor = p.depth, 0
        on_this_floor += 1
        # Killing things drops more things, so a bot that always walks to the
        # nearest pile never leaves the first floor. After a while, go down.
        greedy = on_this_floor < 60
        near = monsters_near(s)
        keep_the_belt_stocked(s)
        if p.hp < p.max_hp * 0.5:
            potion = healing_on_the_belt(s)
            if potion is not None:
                s.app.play.send_action({"a": "use", "id": potion.id})
                s.step(4); note(); continue
        if p.hp < p.max_hp * 0.35 and not near:
            s.app.play.send_action({"a": "rest"})
            s.step(6); note(); continue
        if near:
            m = min(near, key=lambda m: max(abs(m.x - p.x), abs(m.y - p.y)))
            gap = max(abs(m.x - p.x), abs(m.y - p.y))
            spell = best_attack_spell(s)
            reach = SPELLS[spell]["rng"] if spell else 0
            if (spell and 1 < gap <= reach
                    and p.mana >= SPELLS[spell]["mana"]):
                s.app.play.send_action({"a": "cast", "spell": spell,
                                        "x": m.x, "y": m.y})
                s.step(4); note(); continue
            step_toward(m.x, m.y); note(); continue
        if lv.ground.get((p.x, p.y)):
            s.app.play.send_action({"a": "pickup"})
            s.step(4); note(); continue
        piles = [xy for xy, pile in lv.ground.items() if pile] if greedy else []
        if piles:
            t = min(piles, key=lambda q: max(abs(q[0] - p.x), abs(q[1] - p.y)))
            if s.path_to(*t):
                step_toward(*t); note(); continue
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
