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
                              StoreScene, ServiceScene, PackScene,
                              SpellScene, SheetScene, AttributesScene,
                              MenuOverlay, HelpScene, OverlayScene)
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


class TestEveryScene(unittest.TestCase):
    """Every screen, at every sensible size, drawn and clicked.

    Two of the first three screens tested this way had real bugs - buttons that
    were drawn in one place and hit-tested in another, and an overlay stack that
    recursed until Python gave up. The rest deserve the same treatment rather
    than an assumption.
    """

    def setUp(self):
        self.app = make_app()
        self.world = World(seed=7)
        self.player = self.world.add_player("Subject")
        self.app.inventory = self.world.inventory_view(self.player)
        self.app.play = _PlayStub(self.world.self_view(self.player))
        self.app.play.spells = sorted(self.player.spells)
        self.acted = []
        self.app.act = self.acted.append

    def overlays(self):
        play = self.app.play
        return [PackScene(self.app),
                SpellScene(self.app, play),
                SheetScene(self.app),
                AttributesScene(self.app),
                MenuOverlay(self.app),
                StoreScene(self.app, self.world.shop_view(
                    self.player, "general", 1, "Pell's General Store")),
                ServiceScene(self.app, self.world.shop_view(
                    self.player, "temple", 2, "Temple"))]

    def test_every_scene_draws_at_every_size(self):
        for size in SIZES:
            self.app.screen = pygame.display.set_mode(size)
            for scene in [MenuScene(self.app), CharGenScene(self.app),
                          HelpScene(self.app)] + self.overlays():
                with self.subTest(scene=type(scene).__name__, size=size):
                    self.app.scenes = [MenuScene(self.app)]
                    self.app.push(scene)
                    scene.draw(self.app.screen)

    def test_no_overlay_leaves_a_placeholder_hit_target(self):
        """A rect of 10x10 at the origin means draw() never positioned it."""
        self.app.screen = pygame.display.set_mode((1280, 800))
        stale = pygame.Rect(0, 0, 10, 10)
        for scene in self.overlays():
            with self.subTest(scene=type(scene).__name__):
                self.app.scenes = [MenuScene(self.app)]
                self.app.push(scene)
                scene.draw(self.app.screen)
                for name in dir(scene):
                    if name.startswith("_"):
                        continue
                    value = getattr(scene, name, None)
                    if isinstance(value, pygame.Rect):
                        self.assertNotEqual(value, stale,
                                            f"{type(scene).__name__}.{name}")

    def test_clicking_anywhere_on_any_scene_never_raises(self):
        """A stray click must not take the game down."""
        self.app.screen = pygame.display.set_mode((1280, 800))
        w, h = self.app.screen.get_size()
        spots = [(5, 5), (w // 2, h // 2), (w - 5, h - 5),
                 (w // 4, h // 3), (w - 40, 40)]
        for scene in self.overlays():
            self.app.scenes = [MenuScene(self.app)]
            self.app.push(scene)
            scene.draw(self.app.screen)
            for pos in spots:
                with self.subTest(scene=type(scene).__name__, pos=pos):
                    for kind in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
                        scene.handle(pygame.event.Event(kind, pos=pos, button=1))
                    scene.draw(self.app.screen)

    def test_keyboard_on_every_scene_never_raises(self):
        self.app.screen = pygame.display.set_mode((1280, 800))
        keys = [pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_TAB, pygame.K_UP,
                pygame.K_DOWN, pygame.K_a, pygame.K_1]
        for scene in self.overlays():
            self.app.scenes = [MenuScene(self.app)]
            self.app.push(scene)
            scene.draw(self.app.screen)
            for key in keys:
                with self.subTest(scene=type(scene).__name__, key=key):
                    scene.handle(pygame.event.Event(pygame.KEYDOWN, key=key,
                                                    unicode="a", mod=0))
                    scene.draw(self.app.screen)


if __name__ == "__main__":
    unittest.main()


class TestEveryButtonActuallyFires(unittest.TestCase):
    """Press every button on every window and watch for the action.

    The earlier harness only proved that clicking did not crash, which is a
    much weaker claim than it sounds: the inventory and every store swallowed
    the mouse press before the buttons saw it, so they never armed, and the
    release did nothing. Close, Drop, Use, Sort Pack and Name Object were all
    dead, and the only way out of a shop was Escape. Crashing is not the only
    way a button can be broken.
    """

    def setUp(self):
        self.app = make_app()
        self.app.screen = pygame.display.set_mode((1280, 800))
        self.world = World(seed=11)
        self.player = self.world.add_player("Subject")
        self.app.inventory = self.world.inventory_view(self.player)
        self.app.play = _PlayStub(self.world.self_view(self.player))
        self.app.play.spells = sorted(self.player.spells)
        self.app.act = lambda action: None

    def scenes(self):
        return {
            "PackScene": lambda: PackScene(self.app),
            "SpellScene": lambda: SpellScene(self.app, self.app.play),
            "SheetScene": lambda: SheetScene(self.app),
            "AttributesScene": lambda: AttributesScene(self.app),
            "MenuOverlay": lambda: MenuOverlay(self.app),
            "StoreScene": lambda: StoreScene(self.app, self.world.shop_view(
                self.player, "general", 1, "Pell's General Store")),
            "ServiceScene": lambda: ServiceScene(self.app, self.world.shop_view(
                self.player, "temple", 2, "Temple")),
        }

    def test_every_button_reaches_on_action(self):
        for name, build in self.scenes().items():
            probe = build()
            self.app.scenes = [MenuScene(self.app)]
            self.app.push(probe)
            probe.draw(self.app.screen)
            labels = [(b.label, b.rect.center) for b in probe.buttons if b.enabled]
            self.assertTrue(labels, f"{name} draws no buttons at all")

            for label, pos in labels:
                with self.subTest(scene=name, button=label):
                    scene = build()
                    self.app.scenes = [MenuScene(self.app)]
                    self.app.push(scene)
                    scene.draw(self.app.screen)
                    seen = []
                    scene.on_action = seen.append
                    for kind in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
                        scene.handle(pygame.event.Event(kind, pos=pos, button=1))
                    self.assertTrue(seen, f"{name}: '{label}' did nothing")

    def test_close_really_closes_every_overlay(self):
        """Escape is a shortcut, not the only door."""
        for name, build in self.scenes().items():
            with self.subTest(scene=name):
                scene = build()
                self.app.scenes = [MenuScene(self.app)]
                self.app.push(scene)
                scene.draw(self.app.screen)
                closer = [b for b in scene.buttons
                          if b.action == "close" and b.enabled]
                self.assertTrue(closer, f"{name} offers no way out but Escape")
                for kind in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
                    scene.handle(pygame.event.Event(kind, pos=closer[0].rect.center,
                                                    button=1))
                self.assertNotIn(scene, self.app.scenes,
                                 f"{name} stayed open after Close")
