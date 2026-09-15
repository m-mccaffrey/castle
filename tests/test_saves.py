"""Carrying a character from one evening to the next.

Saving had never been driven end to end, and the only time anything was
written was when a player disconnected or the server stopped - so a power cut
mid-game cost the whole session.
"""

import json
import os
import sys
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame                                                  # noqa: E402

from tools.playtest import Session, SHOTS                       # noqa: E402
from tools.crawl import make_character, kit_out                 # noqa: E402

_port = [7960]


def next_port():
    _port[0] += 1
    return _port[0]


def snapshot(p):
    return dict(name=p.name, level=p.level, xp=p.xp, copper=p.copper,
                bank=p.bank, deepest=p.deepest, spells=sorted(p.spells),
                worn=sorted(v.key for v in p.equipment.values() if v),
                pack=sorted(i.key for i in p.inventory),
                stats=dict(p.stats))


class TestSaveAndResume(unittest.TestCase):
    def setUp(self):
        self.path = os.path.join(SHOTS, "party.json")
        self.clean()

    def clean(self):
        for name in os.listdir(SHOTS) if os.path.isdir(SHOTS) else []:
            if name == "party.json" or name.endswith(".tmp"):
                try:
                    os.remove(os.path.join(SHOTS, name))
                except OSError:
                    pass

    def tearDown(self):
        self.clean()

    def play_a_bit(self, name="Keeper"):
        s = Session(seed=55, name=name, port=next_port())
        make_character(s, spell="Shield", difficulty="Difficult")
        kit_out(s)
        p = s.me()
        p.xp, p.level, p.bank = 140, 3, 777
        p.recalc()
        s.walk_to(*s.level().down_at)
        s.key(pygame.K_PERIOD, mod=pygame.KMOD_SHIFT)
        s.settle(1.5)
        return s, p

    def test_a_character_comes_back_exactly_as_they_left(self):
        s, p = self.play_a_bit()
        before = snapshot(p)
        s.app.server.save_everyone()
        s.close()

        again = Session(seed=55, name="Keeper", port=next_port())
        again.click([b for b in again.app.scene.buttons
                     if b.action == "host"][0].rect.center)
        again.settle(2)
        scene = again.app.scene
        self.assertTrue(scene.resume_buttons, "nothing offered to carry on as")
        self.assertIn("Keeper", scene.resume_buttons[0].label)
        again.click(scene.resume_buttons[0].rect.center)
        again.settle(2.5)
        try:
            self.assertEqual(snapshot(again.me()), before)
        finally:
            again.close()

    def test_the_file_menu_saves_on_demand(self):
        s, p = self.play_a_bit("Scribe")
        p.xp = 99
        play = s.app.play
        play.draw(s.app.screen)
        index = [i for i, (label, _items) in enumerate(play.menubar.menus)
                 if label == "File"][0]
        s.click(play.menubar._rects[index].center)
        s.step()
        play.draw(s.app.screen)
        row = [r for r, a, _e in play.menubar._item_rects if a == "save"][0]
        s.click(row.center)
        s.settle(1.0)
        try:
            self.assertTrue(os.path.exists(self.path), "Save wrote nothing")
            written = json.load(open(self.path))["players"]["scribe"]
            self.assertEqual(written["xp"], 99)
            self.assertTrue(any("book" in m for m in s.log(4)),
                            "Save said nothing back")
        finally:
            s.close()

    def test_saving_twice_at_once_does_not_lose_the_file(self):
        """Two threads used to race on one shared party.json.tmp."""
        import threading
        s, p = self.play_a_bit("Racer")
        server = s.app.server
        server.store_save(p)
        threads = [threading.Thread(target=server.flush_saves) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        try:
            self.assertTrue(os.path.exists(self.path))
            json.load(open(self.path))          # not half-written
            leftovers = [f for f in os.listdir(SHOTS) if f.endswith(".tmp")]
            self.assertEqual(leftovers, [], "temporary files left behind")
        finally:
            s.close()

    def test_the_keep_saves_itself_as_you_play(self):
        """Not only when somebody disconnects."""
        s, p = self.play_a_bit("Autosaver")
        p.xp = 1234
        try:
            s.app.server.save_everyone()
            self.assertTrue(os.path.exists(self.path))
            written = json.load(open(self.path))["players"]["autosaver"]
            self.assertEqual(written["xp"], 1234)
            self.assertLessEqual(s.app.server.AUTOSAVE_SECONDS, 120,
                                 "an autosave that rare is not a safety net")
        finally:
            s.close()
