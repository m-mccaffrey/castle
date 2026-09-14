"""Tests for the window itself.

These exist because of a real bug: the opening menu built its button rectangles
from a fixed constant while drawing them centred on the live window width, so
at any window size other than the default the buttons appeared in one place and
responded in another - which looks exactly like a game whose buttons do not
work.
"""

import argparse
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame                                            # noqa: E402

from stormhold.ui.app import App, MenuScene, CharGenScene  # noqa: E402

SIZES = [(1024, 700), (1280, 800), (1440, 900), (1920, 1080)]


def make_app():
    args = argparse.Namespace(serve=False, port=7777, host="0.0.0.0",
                              seed=5, name="Tester", save=None,
                              fullscreen=False)
    return App(args)


class TestWindowLayout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = make_app()

    def test_menu_buttons_are_clickable_at_every_window_size(self):
        for size in SIZES:
            with self.subTest(size=size):
                self.app.screen = pygame.display.set_mode(size)
                scene = MenuScene(self.app)
                self.app.replace(scene)
                scene.draw(self.app.screen)

                fired = []
                scene.act = lambda action: fired.append(action)
                cx = self.app.screen.get_width() // 2
                # where draw() puts "Host a game"
                drawn = pygame.Rect(cx - 200, 300, 190, 34)
                self.assertEqual(scene.buttons[0].rect, drawn,
                                 "hit target must match what is drawn")
                for kind in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
                    scene.handle(pygame.event.Event(kind, pos=drawn.center,
                                                    button=1))
                self.assertEqual(fired, ["host"], "the click must register")

    def test_resizing_moves_the_click_targets_with_the_buttons(self):
        self.app.screen = pygame.display.set_mode((1024, 700))
        scene = MenuScene(self.app)
        self.app.replace(scene)
        narrow = scene.buttons[0].rect.center
        self.app.screen = pygame.display.set_mode((1600, 900))
        scene.layout(self.app.screen.get_size())
        self.assertNotEqual(scene.buttons[0].rect.center, narrow,
                            "a wider window must move the buttons")

    def test_a_relayout_keeps_what_you_typed(self):
        self.app.screen = pygame.display.set_mode((1024, 700))
        scene = MenuScene(self.app)
        scene.name.value = "Brunhild"
        scene.layout((1400, 800))
        self.assertEqual(scene.name.value, "Brunhild")

    def test_chargen_buttons_are_clickable_at_every_window_size(self):
        for size in SIZES:
            with self.subTest(size=size):
                self.app.screen = pygame.display.set_mode(size)
                scene = CharGenScene(self.app)
                self.app.replace(scene)
                scene.draw(self.app.screen)
                cx = self.app.screen.get_width() // 2
                self.assertEqual(scene.buttons[0].rect,
                                 pygame.Rect(cx - 210, 470, 180, 34))

    def test_every_scene_survives_a_draw_at_each_size(self):
        """A smoke test: the window must not explode at any sensible size."""
        for size in SIZES:
            self.app.screen = pygame.display.set_mode(size)
            for scene in (MenuScene(self.app), CharGenScene(self.app)):
                self.app.replace(scene)
                scene.draw(self.app.screen)


if __name__ == "__main__":
    unittest.main()
