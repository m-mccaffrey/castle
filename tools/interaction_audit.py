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

    def give(self, *keys):
        p = self.s.me()
        made = []
        for key in keys:
            it = Item(key)
            it.known = True
            p.inventory.append(it)
            made.append(it)
        self.s.settle(0.3)
        return made
