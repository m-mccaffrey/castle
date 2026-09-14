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

from stormhold.ui.app import (App, MenuScene, CharGenScene,      # noqa: E402
                              StoreScene, ServiceScene)
from stormhold.game.world import World                            # noqa: E402

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


class _PlayStub:
    def __init__(self, view):
        self.you = view

    def add_message(self, *a, **k):
        pass


class TestStoreIsTheInventory(unittest.TestCase):
    """The original: "Stores operate as an extension of the inventory."""

    def setUp(self):
        self.app = make_app()
        self.app.screen = pygame.display.set_mode((1280, 800))
        self.world = World(seed=5)
        self.player = self.world.add_player("Shopper")
        self.app.inventory = self.world.inventory_view(self.player)
        self.app.play = _PlayStub(self.world.self_view(self.player))
        self.acted = []
        self.app.act = self.acted.append

    def store(self, shop="weaponsmith"):
        data = self.world.shop_view(self.player, shop, 1, "Bolgar")
        scene = StoreScene(self.app, data)
        self.app.push(scene)
        scene.draw(self.app.screen)
        return scene

    def drag(self, scene, src, dst):
        scene.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=src, button=1))
        scene.handle(pygame.event.Event(pygame.MOUSEMOTION,
                                        pos=(src[0] + 30, src[1] + 30),
                                        buttons=(1, 0, 0)))
        scene.handle(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=dst, button=1))

    def test_the_shop_shows_the_doll_and_the_pack_not_a_list(self):
        scene = self.store()
        self.assertTrue(scene.store_cells, "stock is shown as icons")
        self.assertTrue(scene.slot_rects, "the paper doll is still there")

    def test_dragging_out_of_the_store_offers_to_buy(self):
        scene = self.store()
        self.drag(scene, scene.store_cells[0][0].center, scene.grid_rect.center)
        self.assertIsNotNone(scene.confirm, "a price must be quoted first")
        self.assertIn("cost you", scene.confirm["text"])
        scene.draw(self.app.screen)
        scene.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN,
                                        pos=scene.confirm["yes"].center, button=1))
        self.assertEqual(self.acted[-1]["a"], "buy")

    def test_saying_no_buys_nothing(self):
        scene = self.store()
        self.drag(scene, scene.store_cells[0][0].center, scene.grid_rect.center)
        scene.draw(self.app.screen)
        scene.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN,
                                        pos=scene.confirm["no"].center, button=1))
        self.assertEqual(self.acted, [], "declining must not spend anything")

    def test_dragging_into_the_store_offers_to_sell(self):
        scene = self.store()
        if not scene.cell_rects:
            self.skipTest("nothing in the pack to sell")
        self.drag(scene, scene.cell_rects[0][0].center, scene.store_rect.center)
        self.assertIsNotNone(scene.confirm)
        self.assertIn("give you", scene.confirm["text"])

    def test_the_sage_identifies_rather_than_buys(self):
        scene = self.store("sage")
        if not scene.cell_rects:
            self.skipTest("nothing in the pack")
        self.drag(scene, scene.cell_rects[0][0].center, scene.store_rect.center)
        self.assertIn("what that is", scene.confirm["text"])

    def test_the_temple_stays_a_counter(self):
        data = self.world.shop_view(self.player, "temple", 3, "Temple")
        scene = ServiceScene(self.app, data)
        self.app.push(scene)
        scene.draw(self.app.screen)
        self.assertIsInstance(scene, ServiceScene)

    def test_overlays_can_stack_without_drawing_themselves(self):
        """scene_under used to hand the lower overlay itself, forever."""
        first = self.store()
        second = self.store("magic")
        second.draw(self.app.screen)
        self.assertIsNot(self.app.under(first), first)
        self.assertIs(self.app.under(second), first)


if __name__ == "__main__":
    unittest.main()
