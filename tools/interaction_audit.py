"""Drag things about and buy things, and check what actually happened.

The control audit presses buttons. The bugs that survive that live one level
down, in what a drag or a trade *does*: whether a helmet dragged to the boots
slot is refused, whether a potion lands on the belt, whether the copper that
leaves your purse matches the price you were quoted.

Everything here goes through the real windows - synthesised presses, motions
and releases handed to `App.dispatch` - because every UI bug found in this
project so far has been in the wiring between the widget and the game, and a
test that calls the engine directly cannot see any of them.

    python3 tools/interaction_audit.py            # both halves
    python3 tools/interaction_audit.py --only trade
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame                                                    # noqa: E402

from stormhold.common.constants import (SHOP_BUY_MARKUP,         # noqa: E402
                                        SHOP_SELL_RATE)
from stormhold.game.items import Item                             # noqa: E402
from tools.playtest import Session                                # noqa: E402
from tools import crawl as C                                      # noqa: E402


class Bench:
    def __init__(self, seed=5, port=9300):
        self.s = Session(seed=seed, port=port, size=(1280, 800))
        C.make_character(self.s, spell="Spark", difficulty="Intermediate")
        self.rows = []

    # ---- the mouse, the way the game receives it -------------------------
    def drag(self, src, dst):
        if src is None or dst is None:
            raise AssertionError("nothing to drag from - the window is not "
                                 "showing what the check expected")
        app = self.s.app
        pygame.mouse.set_pos(src)
        app.dispatch(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=src, button=1))
        self.s.step(2)
        for t in (0.34, 0.67, 1.0):
            mid = (int(src[0] + (dst[0] - src[0]) * t),
                   int(src[1] + (dst[1] - src[1]) * t))
            pygame.mouse.set_pos(mid)
            app.dispatch(pygame.event.Event(pygame.MOUSEMOTION, pos=mid,
                                            rel=(1, 1), buttons=(1, 0, 0)))
            self.s.step(1)
        app.dispatch(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=dst, button=1))
        self.s.settle(0.4)

    def say_yes(self):
        """Answer a shop's confirm box, if one is up. Returns its wording."""
        sc = self.s.app.scene
        sc.draw(self.s.app.screen)
        box = getattr(sc, "confirm", None)
        if not box:
            return None
        text = box.get("text", "")
        pos = box["yes"].center
        self.s.app.dispatch(pygame.event.Event(pygame.MOUSEBUTTONDOWN,
                                               pos=pos, button=1))
        self.s.app.dispatch(pygame.event.Event(pygame.MOUSEBUTTONUP,
                                               pos=pos, button=1))
        self.s.settle(0.8)
        return text

    def note(self, area, what, ok, detail=""):
        self.rows.append((area, what, "ok" if ok else "FAIL", detail))
        print(f"   {'  ' if ok else '**'}{area:<10} {what:<46} "
              f"{'ok' if ok else 'FAIL'}  {detail}", flush=True)

    # ---- getting places ---------------------------------------------------
    def home(self):
        for _ in range(8):
            if self.s.app.scene.__class__.__name__ == "PlayScene":
                return
            self.s.key(pygame.K_ESCAPE)
            self.s.settle(0.2)

    def open_shop(self, shop):
        self.home()
        town = self.s.level()
        npc = next((n for n in town.npcs if n["shop"] == shop), None)
        if npc is None:
            return None
        self.s.walk_to(npc["x"], npc["y"], limit=200)
        self.s.settle(0.6)
        sc = self.s.app.scene
        if sc.__class__.__name__ != "StoreScene":
            return None
        sc.draw(self.s.app.screen)
        return sc

    def open_pack(self):
        self.home()
        self.s.key(pygame.K_i)
        self.s.settle(0.6)
        sc = self.s.app.scene
        sc.draw(self.s.app.screen)
        return sc if sc.__class__.__name__ == "PackScene" else None

    def give(self, *keys, known=True):
        """Put things in the pack the way the server would, and tell the
        client about it. Appending to the inventory alone is not enough: the
        window draws what the last S_INV packet said, and the server clears
        its event list on every action, so a hand-made "inv" event never
        arrives. That is why the pack looked empty here for three checks.
        """
        srv, p = self.s.app.server, self.s.me()
        made = []
        with srv.lock:
            for key in keys:
                it = Item(key)
                it.known = known
                if not p.add_item(it):
                    # A full pack here means the checks that follow are
                    # measuring nothing, so make room rather than fail
                    # mysteriously three functions later.
                    p.inventory = [x for x in p.inventory if x.key != key]
                    p.add_item(it)
                made.append(it)
            session = srv.session_for(p.id)
            if session:
                srv.send_inventory(session)
        self.s.settle(0.3)
        return made


    def messages(self, n=6):
        return self.s.log(n)

    def said(self, text, n=6):
        return any(text in m for m in self.messages(n))

    def cell_for(self, scene, item_id, where="pack"):
        """Where the window is currently drawing a given item."""
        scene.draw(self.s.app.screen)
        cells = scene.store_cells if where == "store" else scene.cell_rects
        for rect, item in cells:
            if item["id"] == item_id:
                return rect.center
        return None

    # ---- half one: buying and selling ------------------------------------
    def check_trade(self):
        print("\n-- trade ------------------------------------------------")
        self.check_prices()
        self.check_buy()
        self.check_poor()
        self.check_sell()
        self.check_every_shop_quotes_what_it_pays()
        self.check_refusal()
        self.check_identify()

    def check_prices(self):
        """The reference's rule: buy at 1.4x base, sell at 0.8x."""
        for shop in ("general", "weaponsmith", "armourer", "magic"):
            sc = self.open_shop(shop)
            if sc is None:
                self.note("price", f"{shop}: no such shop in town", False)
                continue
            bad = [(i["name"], i["price"], max(1, int(i["value"] * SHOP_BUY_MARKUP)))
                   for i in sc.stock()
                   if i["price"] != max(1, int(i["value"] * SHOP_BUY_MARKUP))]
            self.note("price", f"{shop}: {len(sc.stock())} prices are 1.4x base",
                      not bad, "" if not bad else str(bad[:3]))
            bad = [(r["name"], r["price"]) for r in sc.data.get("sell", [])
                   if r["price"] != max(1, int(r["value"] * SHOP_SELL_RATE))]
            self.note("price", f"{shop}: offers are 0.8x base",
                      not bad, "" if not bad else str(bad[:3]))

    def check_buy(self):
        sc = self.open_shop("general")
        if sc is None or not sc.stock():
            return self.note("buy", "general store has stock", False)
        p = self.s.me()
        p.copper = 5000
        sc = self.open_shop("general")
        item = min(sc.stock(), key=lambda i: i["price"])
        before, held = p.copper, len(p.inventory)
        src = self.cell_for(sc, item["id"], "store")
        self.drag(src, self.s.app.scene.grid_rect.center)
        text = self.say_yes()
        want = f"It'll cost you {item['price']} C.P. for that. Take it?"
        self.note("buy", "dragging out of the store quotes a price",
                  text == want, f"said {text!r}" if text != want else "")
        self.note("buy", f"buying {item['name']} costs exactly {item['price']}",
                  before - p.copper == item["price"],
                  f"purse went {before} -> {p.copper}")
        self.note("buy", "the thing bought arrives in the pack",
                  len(p.inventory) > held, f"{held} -> {len(p.inventory)} items")

    def check_poor(self):
        sc = self.open_shop("general")
        if sc is None or not sc.stock():
            return
        item = min(sc.stock(), key=lambda i: i["price"])
        p = self.s.me()
        p.copper = max(0, item["price"] - 1)
        sc = self.open_shop("general")
        src = self.cell_for(sc, item["id"], "store")
        self.drag(src, self.s.app.scene.grid_rect.center)
        self.say_yes()
        self.note("buy", "a short purse is told so, and is not charged",
                  self.said("You don't have enough money!") and p.copper == item["price"] - 1,
                  str(self.messages(3)))

    def check_sell(self):
        p = self.s.me()
        p.copper = 500
        (blade,) = self.give("longsword")
        sc = self.open_shop("weaponsmith")
        if sc is None:
            return self.note("sell", "weaponsmith is in town", False)
        want_price = max(1, int(blade.value() * SHOP_SELL_RATE))
        before = p.copper
        src = self.cell_for(sc, blade.id)
        if src is None:
            return self.note("sell", "the sword shows in the pack half", False)
        self.drag(src, self.s.app.scene.store_rect.center)
        text = self.say_yes()
        want = f"I'll give you {want_price} C.P. for that. Take it?"
        self.note("sell", "dragging into the store offers a price",
                  text == want, f"said {text!r}" if text != want else "")
        self.note("sell", f"selling pays exactly {want_price}",
                  p.copper - before == want_price,
                  f"purse went {before} -> {p.copper}")
        self.note("sell", "the thing sold leaves the pack",
                  blade not in p.inventory)

    def check_every_shop_quotes_what_it_pays(self):
        """The number in the box, against the number in your purse.

        This audit used to sell one sword to one weaponsmith, which is how
        the junk store went on quoting four fifths of an item's value and
        paying a flat twenty-five: two functions, one for the window and one
        for the till, and nothing that compared them.
        """
        town = self.s.level()
        shops = sorted({n["shop"] for n in town.npcs}
                       - {"bank", "temple", "sage"})
        for shop in shops:
            (thing,) = self.give("longsword")
            sc = self.open_shop(shop)
            if sc is None:
                self.note("quote", f"{shop}: open", False, "no such shop")
                continue
            p = self.s.me()
            before = p.copper
            src = self.cell_for(sc, thing.id)
            if src is None:
                self.note("quote", f"{shop}: the sword shows in the pack", False)
                continue
            self.drag(src, self.s.app.scene.store_rect.center)
            text = self.say_yes()
            paid = self.s.me().copper - before
            if text is None:
                # No box came up, so this shop does not deal in swords. Then
                # it must say so and nothing may move: an offer it will not
                # honour is the bug this check exists for.
                self.note("quote", f"{shop} turns a sword down out loud",
                          paid == 0 and thing in self.s.me().inventory
                          and self.said("We don't buy"),
                          f"paid {paid}, said {self.messages(2)}")
                continue
            quoted = next((int(w) for w in text.replace(".", " ").split()
                           if w.isdigit()), None)
            self.note("quote", f"{shop} pays what it offered for a sword",
                      quoted is not None and paid == quoted,
                      f"offered {quoted}, paid {paid}")

    def check_refusal(self):
        (potion,) = self.give("potion_heal")
        sc = self.open_shop("weaponsmith")
        if sc is None:
            return
        p = self.s.me()
        before = p.copper
        src = self.cell_for(sc, potion.id)
        if src is None:
            return self.note("sell", "the potion shows in the pack half", False)
        self.drag(src, self.s.app.scene.store_rect.center)
        self.say_yes()
        self.note("sell", "a weaponsmith refuses a potion, and says why",
                  potion in p.inventory and p.copper == before
                  and self.said("We don't buy those"),
                  str(self.messages(3)))

    def check_identify(self):
        p = self.s.me()
        p.copper = 9000
        (ring,) = self.give("ring_warding", known=False)
        sc = self.open_shop("sage")
        if sc is None:
            return self.note("sage", "sage is in town", False)
        price = sc.data.get("identify_price", 0)
        before = p.copper
        src = self.cell_for(sc, ring.id)
        if src is None:
            return self.note("sage", "the unknown ring shows in the pack half", False)
        self.drag(src, self.s.app.scene.store_rect.center)
        text = self.say_yes()
        want = f"I can tell you what that is for {price} C.P. Well?"
        self.note("sage", "the sage quotes for identifying, not for buying",
                  text == want, f"said {text!r}" if text != want else "")
        self.note("sage", f"identifying costs {price} and names the thing",
                  ring.known and before - p.copper == price,
                  f"known={ring.known} purse {before} -> {p.copper}")


    # ---- half two: dressing yourself ------------------------------------
    WEARS = [("helm", "head"), ("chainmail", "torso"), ("shield", "shield"),
             ("boots", "feet"), ("leggings", "legs"), ("cloak", "back"),
             ("gauntlets", "arms"), ("amulet_ward", "neck"),
             ("ring_might", "ring_left"), ("longsword", "weapon"),
             ("bracers", "bracers")]

    def empty_the_pack(self):
        """Start the dressing half with room to put things.

        The trade half leaves a pack full of swords, and a `give` that
        quietly fails to fit makes every check after it report on an item
        that is not there.
        """
        srv, p = self.s.app.server, self.s.me()
        with srv.lock:
            p.inventory = []
            srv.send_inventory(srv.session_for(p.id))
        self.s.settle(0.3)

    def check_drag(self):
        print("\n-- dressing ---------------------------------------------")
        self.empty_the_pack()
        self.check_equip()
        self.check_wrong_slot()
        self.check_unequip()
        self.check_belt()
        self.check_cursed()

    def worn(self, slot):
        p = self.s.me()
        return p.equipment.get(slot)

    def check_equip(self):
        """Every wearable dragged onto the slot it belongs in."""
        for key, slot in self.WEARS:
            (thing,) = self.give(key)
            sc = self.open_pack()
            src = self.cell_for(sc, thing.id)
            if src is None:
                self.note("equip", f"{key} shows in the pack", False)
                continue
            self.drag(src, sc.slot_rects[slot].center)
            self.note("equip", f"{key} dragged to {slot} is worn",
                      self.worn(slot) is thing,
                      f"{slot} holds {getattr(self.worn(slot), 'key', None)}")

    def check_wrong_slot(self):
        """A helmet is not a boot, and the window should say so."""
        (helm,) = self.give("cap")
        sc = self.open_pack()
        src = self.cell_for(sc, helm.id)
        if src is None:
            return self.note("equip", "the spare cap shows in the pack", False)
        before = self.worn("feet")
        self.drag(src, sc.slot_rects["feet"].center)
        self.home()
        self.note("equip", "a cap dragged to the boots slot is refused, with a reason",
                  self.worn("feet") is before and self.said("does not go there"),
                  str(self.messages(3)))

    def check_unequip(self):
        sc = self.open_pack()
        helm = self.worn("head")
        if helm is None:
            return self.note("equip", "something is on the head to take off", False)
        self.drag(sc.slot_rects["head"].center, sc.grid_rect.center)
        p = self.s.me()
        self.note("equip", "dragging a worn thing to the pack takes it off",
                  self.worn("head") is None and helm in p.inventory,
                  f"head holds {getattr(self.worn('head'), 'key', None)}")

    def check_belt(self):
        """A belt's squares are drop targets, and a potion lands on one."""
        (belt,) = self.give("belt3")
        sc = self.open_pack()
        src = self.cell_for(sc, belt.id)
        if src is None:
            return self.note("belt", "the belt shows in the pack", False,
                             "it never arrived")
        self.drag(src, sc.slot_rects["waist"].center)
        self.note("belt", "a belt dragged to the waist is worn",
                  self.worn("waist") is belt)
        (potion,) = self.give("potion_heal")
        sc = self.open_pack()
        sc.draw(self.s.app.screen)
        cells = list(sc.empty_stow_rects)
        self.note("belt", "an empty belt draws its squares as drop targets",
                  bool(cells), f"{len(cells)} empty squares")
        if not cells:
            return
        src = self.cell_for(sc, potion.id)
        self.drag(src, cells[0][0].center)
        stowed = self.worn("waist").contents or []
        self.note("belt", "a potion dropped on a belt square is stowed there",
                  potion in stowed, f"belt holds {[i.key for i in stowed]}")

    def check_cursed(self):
        (ring,) = self.give("ring_burden")
        ring.cursed = True
        sc = self.open_pack()
        src = self.cell_for(sc, ring.id)
        if src is None:
            return self.note("curse", "the cursed ring shows in the pack", False)
        self.drag(src, sc.slot_rects["ring_right"].center)
        if self.worn("ring_right") is not ring:
            return self.note("curse", "a cursed ring goes on like any other",
                             False, "it would not even go on")
        sc = self.open_pack()
        self.drag(sc.slot_rects["ring_right"].center, sc.grid_rect.center)
        self.home()
        self.note("curse", "a cursed ring will not come off, and says why",
                  self.worn("ring_right") is ring, str(self.messages(3)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=("trade", "drag"))
    args = ap.parse_args()
    b = Bench()
    if args.only in (None, "trade"):
        b.check_trade()
    if args.only in (None, "drag"):
        b.check_drag()
    bad = [r for r in b.rows if r[2] != "ok"]
    print(f"\n{len(b.rows)} checks, {len(bad)} failed")
    b.s.close()
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
