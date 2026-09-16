"""Click every control on every screen and report what happened.

Written because the same bug - "the buttons in the shops do nothing" - was
reported, fixed, and reported again. Reading the code said it should work,
which is exactly when you stop reading and start driving.

For each screen it can reach, this enumerates the buttons the screen itself
says it has, and for each one: opens the screen fresh, synthesises a real
press and release on the button's centre, and records what came of it - an
action sent to the server, a scene change, a message, an exception, or
nothing at all. "Nothing at all" is the interesting answer.

    python3 tools/ui_audit.py
    python3 tools/ui_audit.py --only store
"""

import argparse
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame                                                   # noqa: E402

from tools.playtest import Session                               # noqa: E402
from tools import crawl as C                                     # noqa: E402


class Audit:
    def __init__(self, seed=5, port=8920):
        self.s = Session(seed=seed, port=port, size=(1280, 800))
        C.make_character(self.s, spell="Spark", difficulty="Intermediate")
        self.s.me().copper = 50000
        self.acts = []
        real = self.s.app.act

        def spy(action):
            self.acts.append(action)
            return real(action)
        self.s.app.act = spy

    # ---- getting to each screen -----------------------------------------
    def to_play(self):
        while self.s.app.scene.__class__.__name__ != "PlayScene":
            self.s.key(pygame.K_ESCAPE)
            self.s.settle(0.3)

    def open(self, where):
        self.to_play()
        if where == "play":
            pass
        elif where == "pack":
            self.s.key(pygame.K_i)
        elif where == "spells":
            self.s.key(pygame.K_z)
        elif where == "sheet":
            self.s.key(pygame.K_c)
        elif where.startswith("shop:"):
            shop = where.split(":", 1)[1]
            town = self.s.level()
            npc = next((n for n in town.npcs if n["shop"] == shop), None)
            if npc is None:
                return False
            if not self.s.walk_to(npc["x"], npc["y"], limit=200):
                # walking onto the counter is what opens it
                p = self.s.me()
                self.s.app.play.send_action(
                    {"a": "move", "dx": (npc["x"] > p.x) - (npc["x"] < p.x),
                     "dy": (npc["y"] > p.y) - (npc["y"] < p.y)})
        self.s.settle(1.0)
        return True

    # ---- the click itself -------------------------------------------------
    def press(self, rect):
        """A real press and release, with the mouse actually over it."""
        pos = rect.center
        pygame.mouse.set_pos(pos)
        for ev in (pygame.event.Event(pygame.MOUSEMOTION, pos=pos, rel=(0, 0),
                                      buttons=(0, 0, 0)),
                   pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1),
                   pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=1)):
            self.s.app.dispatch(ev)
            self.s.step(2)
        self.s.settle(0.5)

    def controls(self):
        sc = self.s.app.scene
        sc.draw(self.s.app.screen)          # laying out is what fills the rects
        return list(getattr(sc, "buttons", []))

    def check(self, where):
        rows = []
        if not self.open(where):
            return [(where, "-", "SKIP", "no such place")]
        n = len(self.controls())
        if n == 0:
            return [(where, "-", "none", f"{self.s.app.scene.__class__.__name__}"
                                          " exposes no buttons")]
        for i in range(n):
            self.open(where)
            buttons = self.controls()
            if i >= len(buttons):
                break
            b = buttons[i]
            before_scene = self.s.app.scene.__class__.__name__
            before_acts = len(self.acts)
            before_log = len(self.s.log(200))
            label = f"{b.label!r}({b.action})"
            try:
                self.press(b.rect)
            except Exception as exc:
                rows.append((where, label, "CRASH",
                             traceback.format_exception_only(type(exc), exc)[-1].strip()))
                continue
            after_scene = self.s.app.scene.__class__.__name__
            acts = self.acts[before_acts:]
            grew = len(self.s.log(200)) - before_log
            if acts:
                rows.append((where, label, "ok", f"sent {acts[0].get('a')}"))
            elif after_scene != before_scene:
                rows.append((where, label, "ok", f"-> {after_scene}"))
            elif grew > 0:
                rows.append((where, label, "ok", "message"))
            elif not b.enabled:
                rows.append((where, label, "off", "disabled"))
            else:
                rows.append((where, label, "DEAD", "nothing happened"))
        return rows


PLACES = ["play", "pack", "sheet", "spells",
          "shop:weaponsmith", "shop:armourer", "shop:general",
          "shop:magic", "shop:junk", "shop:temple", "shop:sage",
          "shop:bank"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None)
    ap.add_argument("--port", type=int, default=8920)
    args = ap.parse_args()

    a = Audit(port=args.port)
    places = [p for p in PLACES if not args.only or args.only in p]
    rows = []
    for place in places:
        rows += a.check(place)
    print(f"\n{'screen':<20} {'control':<34} {'':<6} what happened")
    bad = 0
    for place, label, verdict, note in rows:
        mark = {"ok": "  ", "off": "  ", "none": "  "}.get(verdict, "**")
        if verdict in ("DEAD", "CRASH"):
            bad += 1
        print(f"{mark}{place:<18} {label:<34} {verdict:<6} {note}")
    print(f"\n{bad} broken of {len(rows)} controls")
    a.s.close()


if __name__ == "__main__":
    main()
