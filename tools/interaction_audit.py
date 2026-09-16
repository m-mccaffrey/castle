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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=("trade", "drag"))
    args = ap.parse_args()
    b = Bench()
    if args.only in (None, "trade"):
        b.check_trade()
    bad = [r for r in b.rows if r[2] != "ok"]
    print(f"\n{len(b.rows)} checks, {len(bad)} failed")
    b.s.close()
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
