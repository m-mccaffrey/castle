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

    # Menu entries that end the session rather than doing something in it.
    # "Leave the keep" disconnects, and after that nothing gets back to the
    # play screen - so an unbounded walk home sat pressing Escape at a
    # disconnected menu forever, which is what hung this audit.
    DESTRUCTIVE = {"File > Leave the keep"}

    def to_play(self, tries=8):
        for _ in range(tries):
            if self.s.app.scene.__class__.__name__ == "PlayScene":
                return True
            self.s.key(pygame.K_ESCAPE)
            self.s.settle(0.2)
        return self.s.app.scene.__class__.__name__ == "PlayScene"

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

    # ---- the play screen's own chrome ------------------------------------
    def menu_items(self):
        """Every drop-down entry, as (menu index, item index, label)."""
        self.to_play()
        sc = self.s.app.scene
        sc.draw(self.s.app.screen)
        bar = getattr(sc, "menubar", None)
        if bar is None:
            return []
        out = []
        for mi, (label, items) in enumerate(bar.menus):
            if not items:
                out.append((mi, None, f"{label} (button)"))
                continue
            for ii, (ilabel, action, _on) in enumerate(items):
                if ilabel != "-":
                    out.append((mi, ii, f"{label} > {ilabel}"))
        return out

    def check_menus(self):
        rows = []
        for mi, ii, label in self.menu_items():
            if label in self.DESTRUCTIVE:
                rows.append(("menu", label, "skip", "ends the session"))
                print("   ", rows[-1], flush=True)
                continue
            # Only walk home if something took us away: most menu items leave
            # the play screen up, and going the whole way back between each of
            # twenty-odd items is most of the running time.
            if self.s.app.scene.__class__.__name__ != "PlayScene":
                self.to_play()
            sc = self.s.app.scene
            sc.draw(self.s.app.screen)
            bar = sc.menubar
            before_scene = sc.__class__.__name__
            before_acts = len(self.acts)
            before_log = len(self.s.log(200))
            before_state = self.snapshot(sc)
            try:
                self.press(bar._rects[mi])           # open the menu
                if ii is not None:
                    self.s.app.scene.draw(self.s.app.screen)
                    bar = self.s.app.scene.menubar
                    # _item_rects skips separators and holds
                    # (rect, action, enabled), so line it up against the
                    # non-separator items rather than indexing by position.
                    wanted = bar.menus[mi][1][ii]
                    real = [it for it in bar.menus[mi][1] if it[0] != "-"]
                    try:
                        at = real.index(wanted)
                    except ValueError:
                        rows.append(("menu", label, "SKIP", "no such item"))
                        continue
                    if at >= len(bar._item_rects):
                        rows.append(("menu", label, "SKIP", "item not drawn"))
                        continue
                    self.press(bar._item_rects[at][0])
            except Exception as exc:
                rows.append(("menu", label, "CRASH", repr(exc)[:70]))
                continue
            after = self.s.app.scene.__class__.__name__
            acts = self.acts[before_acts:]
            grew = len(self.s.log(200)) - before_log
            if acts:
                rows.append(("menu", label, "ok", f"sent {acts[0].get('a')}"))
            elif after != before_scene:
                rows.append(("menu", label, "ok", f"-> {after}"))
            elif grew:
                # What it said, not just that it said something: a verb that
                # answers "there is nothing here to get" is working, but a
                # verb that only ever answers that is not.
                said = self.s.log(200)[-1][:52]
                rows.append(("menu", label, "ok", f'said "{said}"'))
            elif self.snapshot(self.s.app.scene) != before_state:
                rows.append(("menu", label, "ok", "toggled"))
            else:
                rows.append(("menu", label, "DEAD", "nothing happened"))
            print("   ", rows[-1], flush=True)
        return rows

    def check_toolbar(self):
        rows = []
        self.to_play()
        sc = self.s.app.scene
        sc.draw(self.s.app.screen)
        tools = list(getattr(getattr(sc, "toolbar", None), "buttons", []))
        for i in range(len(tools)):
            if self.s.app.scene.__class__.__name__ != "PlayScene":
                self.to_play()
            sc = self.s.app.scene
            sc.draw(self.s.app.screen)
            rect, action = sc.toolbar.buttons[i]     # (rect, action) pairs
            label = f"{sc.toolbar.verbs[i][0]!r}({action})"
            before_acts = len(self.acts)
            before_log = len(self.s.log(200))
            before_scene = sc.__class__.__name__
            try:
                self.press(rect)
            except Exception as exc:
                rows.append(("toolbar", label, "CRASH", repr(exc)[:70]))
                continue
            acts = self.acts[before_acts:]
            grew = len(self.s.log(200)) - before_log
            after = self.s.app.scene.__class__.__name__
            if acts:
                rows.append(("toolbar", label, "ok", f"sent {acts[0].get('a')}"))
            elif after != before_scene:
                rows.append(("toolbar", label, "ok", f"-> {after}"))
            elif grew:
                # What it said, not just that it said something: a verb that
                # answers "there is nothing here to get" is working, but a
                # verb that only ever answers that is not.
                said = self.s.log(200)[-1][:52]
                rows.append(("toolbar", label, "ok", f'said "{said}"'))
            elif self.snapshot(self.s.app.scene) != before_state:
                rows.append(("toolbar", label, "ok", "toggled"))
            else:
                rows.append(("toolbar", label, "DEAD", "nothing happened"))
            print("   ", rows[-1], flush=True)
        return rows

    @staticmethod
    def snapshot(scene):
        """The scene's own switches, so a toggle is not mistaken for a dud.

        Map! turns the overview on and off and Examine arms a click: neither
        sends anything to the server or opens a window, so without this they
        both report as doing nothing.
        """
        return {k: getattr(scene, k, None) for k in
                ("show_overview", "target_mode", "run_mode", "show_help")}

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
                said = self.s.log(200)[-1][:52]
                rows.append((where, label, "ok", f'said "{said}"'))
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
    if not args.only or args.only in ("menu", "chrome"):
        rows += a.check_menus()
    if not args.only or args.only in ("toolbar", "chrome"):
        rows += a.check_toolbar()
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
