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
                              MenuOverlay, HelpScene, OverlayScene,
                              PlayScene)
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
                                 pygame.Rect(cx - 210, CharGenScene.Y['actions'], 180, 32))

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
        self.targeted = []

    def add_message(self, *a, **k):
        pass

    def begin_target(self, name, spell):
        self.targeted.append(name)


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


class TestThePlayScreensOwnControls(unittest.TestCase):
    """The menu bar and the verb toolbar, exercised the way a player uses them.

    These are the controls that are on screen the whole time you are playing,
    and nothing tested them: the overlay tests never touched the screen
    underneath.
    """

    def setUp(self):
        self.app = make_app()
        self.app.screen = pygame.display.set_mode((1280, 800))
        self.world = World(seed=3)
        self.player = self.world.add_player("Pilot")
        self.play = PlayScene(self.app)
        self.play.you = self.world.self_view(self.player)
        self.app.play = self.play
        self.app.inventory = self.world.inventory_view(self.player)
        self.app.replace(self.play)
        self.play.draw(self.app.screen)
        self.commands = []
        self.play.menu_command = self.commands.append

    def test_every_menu_opens_and_every_item_fires(self):
        for index, (label, items) in enumerate(self.play.menubar.menus):
            with self.subTest(menu=label):
                self.commands.clear()
                self.play.menubar.open_index = None
                rect = self.play.menubar._rects[index]
                self.play.handle(pygame.event.Event(
                    pygame.MOUSEBUTTONDOWN, pos=rect.center, button=1))
                if not items:
                    # Character!, Inventory! and Map! are commands, not menus.
                    self.assertEqual(self.commands, [label])
                    continue
                self.assertEqual(self.play.menubar.open_index, index,
                                 f"{label} did not open")
                self.play.draw(self.app.screen)
                rows = list(self.play.menubar._item_rects)
                self.assertTrue(rows, f"{label} opened but drew no items")
                for row, action, enabled in rows:
                    self.commands.clear()
                    self.play.menubar.open_index = index
                    self.play.draw(self.app.screen)
                    self.play.handle(pygame.event.Event(
                        pygame.MOUSEBUTTONDOWN, pos=row.center, button=1))
                    if enabled:
                        self.assertEqual(self.commands, [action],
                                         f"{label} > {action} did nothing")

    def test_every_toolbar_verb_fires(self):
        self.play.draw(self.app.screen)
        for rect, action in list(self.play.toolbar.buttons):
            with self.subTest(verb=action):
                self.commands.clear()
                for kind in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
                    self.play.handle(pygame.event.Event(
                        kind, pos=rect.center, button=1))
                self.assertEqual(self.commands, [action],
                                 f"toolbar '{action}' did nothing")

    def test_an_open_menu_swallows_the_map_click_under_it(self):
        """Choosing a menu item must not also walk you into a wall."""
        self.play.menubar.open_index = 5
        self.play.draw(self.app.screen)
        walked = []
        self.play.click_map = lambda pos: walked.append(pos)
        row = self.play.menubar._item_rects[0][0]
        self.play.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN,
                                            pos=row.center, button=1))
        self.assertEqual(walked, [])


class TestChoosingAStartingSpell(unittest.TestCase):
    """The original's last step: "choose a starting spell" from a list of six."""

    def setUp(self):
        self.app = make_app()
        self.app.screen = pygame.display.set_mode((1024, 700))
        self.scene = CharGenScene(self.app)
        self.app.replace(self.scene)
        self.scene.draw(self.app.screen)

    def test_six_are_offered(self):
        from stormhold.game.spells import STARTING_SPELLS, SPELLS
        self.assertEqual(len(STARTING_SPELLS), 6)
        for name in STARTING_SPELLS:
            self.assertIn(name, SPELLS, f"{name} is not a spell")
        self.assertEqual([b.action[1] for b in self.scene.spell_buttons],
                         list(STARTING_SPELLS))

    def test_clicking_one_chooses_it_even_though_the_screen_redraws(self):
        """A redraw between the press and the release must not disarm it.

        It did: draw() set `pressed` to mark the chosen spell, which cleared
        the arming from the real mouse press, so at 30 frames a second the
        buttons could not be clicked at all.
        """
        button = [b for b in self.scene.spell_buttons if b.action[1] == "Spark"][0]
        self.scene.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN,
                                             pos=button.rect.center, button=1))
        self.scene.draw(self.app.screen)          # the frame in between
        self.scene.handle(pygame.event.Event(pygame.MOUSEBUTTONUP,
                                             pos=button.rect.center, button=1))
        self.assertEqual(self.scene.spell, "Spark")

    def test_the_choice_reaches_the_character(self):
        from stormhold.game.world import World
        world = World(seed=9)
        for name in ("Spark", "Shield", "Blink"):
            with self.subTest(spell=name):
                p = world.add_player(f"Caster{name}", spell=name)
                self.assertEqual(sorted(p.spells), [name])

    def test_a_nonsense_choice_still_leaves_you_able_to_cast(self):
        from stormhold.game.world import World
        from stormhold.game.spells import STARTING_SPELLS
        world = World(seed=9)
        p = world.add_player("Liar", spell="Wish For Everything")
        self.assertEqual(sorted(p.spells), [STARTING_SPELLS[0]])


class TestDifficulty(unittest.TestCase):
    """The original's four settings, and what they do to the keep."""

    def test_four_are_offered_with_the_originals_names(self):
        from stormhold.common.constants import DIFFICULTIES, DEFAULT_DIFFICULTY
        self.assertEqual([d[0] for d in DIFFICULTIES],
                         ["Easy", "Intermediate", "Difficult", "Experts Only"])
        self.assertEqual(DEFAULT_DIFFICULTY, "Intermediate")

    def test_harder_settings_make_tougher_creatures_worth_more(self):
        from stormhold.game.world import World
        last_hp = last_xp = 0
        for name in ("Easy", "Intermediate", "Difficult", "Experts Only"):
            with self.subTest(difficulty=name):
                world = World(seed=4, difficulty=name)
                kobold = world.spawn("kobold", 1, 1, 1)
                self.assertGreater(kobold.hp, last_hp)
                self.assertGreater(kobold.xp_value, last_xp)
                last_hp, last_xp = kobold.hp, kobold.xp_value

    def test_a_nonsense_setting_falls_back_to_the_default(self):
        from stormhold.net.server import valid_difficulty
        self.assertEqual(valid_difficulty("Impossible"), "Intermediate")
        self.assertEqual(valid_difficulty("Easy"), "Easy")

    def test_the_picker_chooses_and_survives_a_redraw(self):
        app = make_app()
        app.screen = pygame.display.set_mode((1024, 700))
        scene = CharGenScene(app)
        app.replace(scene)
        scene.draw(app.screen)
        button = [b for b in scene.difficulty_buttons
                  if b.action[1] == "Experts Only"][0]
        scene.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN,
                                        pos=button.rect.center, button=1))
        scene.draw(app.screen)
        scene.handle(pygame.event.Event(pygame.MOUSEBUTTONUP,
                                        pos=button.rect.center, button=1))
        self.assertEqual(scene.difficulty, "Experts Only")


class TestTheMessageLogScrollsBack(unittest.TestCase):
    """"The message log keeps a scrollback with its own scrollbar, oldest at
    top." Ours drew the scrollbar and ignored the wheel."""

    def setUp(self):
        self.app = make_app()
        self.app.screen = pygame.display.set_mode((1280, 800))
        self.world = World(seed=6)
        self.player = self.world.add_player("Talker")
        self.play = PlayScene(self.app)
        self.play.you = self.world.self_view(self.player)
        self.app.play = self.play
        self.app.replace(self.play)
        for i in range(120):
            self.play.add_message(f"Line {i}", "info")
        self.play.draw(self.app.screen)

    def wheel(self, y):
        self.play.handle(pygame.event.Event(pygame.MOUSEWHEEL, y=y, x=0))
        self.play.draw(self.app.screen)

    def shown(self):
        """Which of our numbered lines are on screen, by reading the state."""
        end = self.play.log_lines - self.play.log_scroll
        return max(0, end - self.play.log_visible), end

    def test_the_newest_line_is_on_screen_to_begin_with(self):
        self.assertEqual(self.play.log_scroll, 0)
        _, end = self.shown()
        self.assertEqual(end, self.play.log_lines)

    def test_the_wheel_scrolls_back_and_forward(self):
        import pygame as pg
        pg.mouse.set_pos(self.play.log_rect(self.app.screen).center)
        self.wheel(1)
        self.assertGreater(self.play.log_scroll, 0, "the wheel did nothing")
        back = self.play.log_scroll
        self.wheel(-1)
        self.assertLess(self.play.log_scroll, back)

    def test_it_cannot_scroll_past_either_end(self):
        import pygame as pg
        pg.mouse.set_pos(self.play.log_rect(self.app.screen).center)
        for _ in range(200):
            self.wheel(1)
        self.assertEqual(self.play.log_scroll,
                         self.play.log_lines - self.play.log_visible)
        for _ in range(400):
            self.wheel(-1)
        self.assertEqual(self.play.log_scroll, 0)

    def test_a_new_message_brings_you_back_to_the_bottom(self):
        import pygame as pg
        pg.mouse.set_pos(self.play.log_rect(self.app.screen).center)
        self.wheel(1)
        self.assertGreater(self.play.log_scroll, 0)
        self.play.add_message("Something happens.", "info")
        self.assertEqual(self.play.log_scroll, 0)


class TestTheFastMap(unittest.TestCase):
    """Map! toggled a flag that nothing read, so the menu item did nothing."""

    def setUp(self):
        self.app = make_app()
        self.app.screen = pygame.display.set_mode((1280, 800))
        self.world = World(seed=3)
        self.player = self.world.add_player("Cartographer")
        self.world.move_player_to(self.player, 1)
        self.world.update_fov(self.player, force=True)
        self.play = PlayScene(self.app)
        self.app.play = self.play
        self.app.replace(self.play)
        self.play.on_message(
            __import__("stormhold.net.protocol", fromlist=["x"]).S_LEVEL,
            {"w": self.world.levels[1].w, "h": self.world.levels[1].h,
             "depth": 1, "name": self.world.levels[1].name, "town": False})
        view = self.world.snapshot_for(self.player)
        self.play.you = view["you"]
        self.play.actors = view["actors"]
        self.play.items = view["items"]
        self.play.party = view["party"]
        self.world.resend_level(self.player)
        self.play.map.apply(self.player.pending_tiles)

    def test_the_menu_item_turns_it_on_and_off(self):
        self.assertFalse(getattr(self.play, "show_overview", False))
        self.play.menu_command("Map!")
        self.assertTrue(self.play.show_overview)
        self.play.menu_command("Map!")
        self.assertFalse(self.play.show_overview)

    def test_it_draws_something_different_from_the_ordinary_map(self):
        surface = pygame.Surface((1280, 800))
        self.play.draw(surface)
        ordinary = pygame.image.tobytes(surface, "RGB")
        self.play.menu_command("Map!")
        self.play.draw(surface)
        overview = pygame.image.tobytes(surface, "RGB")
        self.assertNotEqual(ordinary, overview, "Map! changed nothing on screen")

    def test_it_shows_only_what_you_have_seen(self):
        """A floor plan you have not walked is not a floor plan you have."""
        self.play.menu_command("Map!")
        surface = pygame.Surface((1280, 800))
        self.play.draw(surface)
        seen = sum(1 for b in self.play.map.known if b)
        self.assertGreater(seen, 0)
        self.assertLess(seen, self.play.map.w * self.play.map.h,
                        "the whole floor is already known, so this proves nothing")

    def test_it_survives_every_window_size(self):
        self.play.menu_command("Map!")
        for size in SIZES:
            with self.subTest(size=size):
                self.app.screen = pygame.display.set_mode(size)
                self.play.draw(self.app.screen)
