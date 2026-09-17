"""The keyboard the original documents, command by command.

CASTLE1.HLP prints a table of movement keys - "There are two different sets
of movement keys in Castle, the alphabetic set, and the numeric keypad set" -
and then a second table of commands: < > o c s d m i r R x v f g. That is
the whole interface for a player who is not using the mouse, and every row
here comes from one of those two tables.

This exists because eleven of them were missing or bound to something else,
and no test noticed: `s` walked south instead of searching, `f` fired an
arrow instead of freeing a hand, and `<` picked up off the floor instead of
climbing, because the Get branch matched the comma before the shift was
looked at.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame                                                    # noqa: E402

from stormhold.ui.app import PlayScene                            # noqa: E402
from stormhold.game.world import World                            # noqa: E402
from tests.test_ui import make_app                                # noqa: E402

SHIFT = pygame.KMOD_LSHIFT


class TestTheOriginalsKeyboard(unittest.TestCase):

    def setUp(self):
        pygame.display.init()
        self.app = make_app()
        self.app.screen = pygame.display.set_mode((1280, 800))
        self.world = World(seed=3)
        self.player = self.world.add_player("Typist")
        self.play = PlayScene(self.app)
        self.app.play = self.play
        self.app.inventory = self.world.inventory_view(self.player)
        self.app.replace(self.play)
        self.play.on_message(*self._level_packet())
        self.play.you = self.world.self_view(self.player)
        self.play.actors = [{"id": self.player.id, "k": "player",
                             "x": self.player.x, "y": self.player.y,
                             "n": self.player.name, "hp": self.player.hp,
                             "mhp": self.player.max_hp, "lv": self.player.level}]
        self.play.draw(self.app.screen)
        self.sent = []
        self.play.send_action = self.sent.append

    def _level_packet(self):
        from stormhold.net import protocol as P
        level = self.world.levels[self.player.depth]
        return P.S_LEVEL, {"w": level.w, "h": level.h, "depth": self.player.depth,
                           "name": "Aldershade", "town": True}

    def press(self, key, mod=0):
        self.sent.clear()
        self.play.handle(pygame.event.Event(pygame.KEYDOWN, key=key,
                                            unicode="", mod=mod))
        return self.sent

    # -- the movement table -------------------------------------------------
    ALPHABETIC = {"k": (0, -1), "u": (1, -1), "l": (1, 0), "n": (1, 1),
                  "j": (0, 1), "b": (-1, 1), "h": (-1, 0), "y": (-1, -1)}
    NUMERIC = {pygame.K_KP8: (0, -1), pygame.K_KP9: (1, -1),
               pygame.K_KP6: (1, 0), pygame.K_KP3: (1, 1),
               pygame.K_KP2: (0, 1), pygame.K_KP1: (-1, 1),
               pygame.K_KP4: (-1, 0), pygame.K_KP7: (-1, -1)}

    def test_the_alphabetic_set_moves_the_eight_ways(self):
        for letter, (dx, dy) in self.ALPHABETIC.items():
            with self.subTest(key=letter):
                sent = self.press(getattr(pygame, f"K_{letter}"))
                self.assertEqual(sent, [{"a": "move", "dx": dx, "dy": dy}])

    def test_the_numeric_set_moves_the_eight_ways(self):
        for key, (dx, dy) in self.NUMERIC.items():
            with self.subTest(key=pygame.key.name(key)):
                sent = self.press(key)
                self.assertEqual(sent, [{"a": "move", "dx": dx, "dy": dy}])

    def test_shift_and_a_direction_runs(self):
        self.assertEqual(self.press(pygame.K_l, SHIFT),
                         [{"a": "run", "dx": 1, "dy": 0}])

    def test_wasd_no_longer_shadows_search_and_disarm(self):
        """`s` and `d` are the original's commands; WASD used to eat them."""
        for key in (pygame.K_w, pygame.K_a, pygame.K_s, pygame.K_d):
            self.assertNotIn(key, PlayScene.MOVE_KEYS,
                             f"{pygame.key.name(key)} must not be a movement key")

    # -- the command table --------------------------------------------------
    COMMANDS = {
        "o": "open", "c": "close", "s": "search", "d": "disarm",
        "r": "rest", "f": "freehand", "g": "pickup",
    }

    def test_each_command_letter_sends_its_verb(self):
        for letter, verb in self.COMMANDS.items():
            with self.subTest(key=letter):
                sent = self.press(getattr(pygame, f"K_{letter}"))
                self.assertEqual(sent, [{"a": verb}])

    def test_shift_r_sleeps_for_mana_and_plain_r_rests(self):
        self.assertEqual(self.press(pygame.K_r), [{"a": "rest"}])
        self.assertEqual(self.press(pygame.K_r, SHIFT), [{"a": "sleep"}])

    def test_angle_brackets_climb_and_the_comma_still_gets(self):
        """`<` is shift plus comma, and the Get branch used to match first."""
        self.assertEqual(self.press(pygame.K_COMMA, SHIFT), [{"a": "stairs"}])
        self.assertEqual(self.press(pygame.K_PERIOD, SHIFT), [{"a": "stairs"}])
        self.assertEqual(self.press(pygame.K_COMMA), [{"a": "pickup"}])
        self.assertEqual(self.press(pygame.K_PERIOD), [{"a": "wait"}])

    def test_m_shows_the_whole_level_and_i_opens_the_pack(self):
        self.press(pygame.K_m)
        self.assertTrue(self.play.show_overview, "m did not open map mode")
        self.press(pygame.K_m)
        self.assertFalse(self.play.show_overview, "m did not close it again")
        self.press(pygame.K_i)
        self.assertEqual(type(self.app.scene).__name__, "PackScene")

    # -- "the cursor will change to cross hairs" ----------------------------
    def test_x_puts_up_crosshairs_that_the_movement_keys_drive(self):
        me = self.play.me()
        self.press(pygame.K_x)
        self.assertEqual(self.play.cursor, [me["x"], me["y"]],
                         "the crosshairs start on the player")
        self.press(pygame.K_l)
        self.press(pygame.K_j)
        self.assertEqual(self.play.cursor, [me["x"] + 1, me["y"] + 1])
        self.assertEqual(self.press(pygame.K_l), [],
                         "the player must not walk while aiming")
        sent = self.press(pygame.K_RETURN)
        self.assertEqual(sent, [{"a": "examine", "x": me["x"] + 2,
                                 "y": me["y"] + 1}])
        self.assertIsNone(self.play.cursor, "the crosshairs are put away")

    def test_escape_takes_the_crosshairs_down(self):
        self.press(pygame.K_x)
        self.press(pygame.K_ESCAPE)
        self.assertIsNone(self.play.target_mode)
        self.assertIsNone(self.play.cursor)

    def test_v_scrolls_the_window_and_return_puts_it_back(self):
        self.press(pygame.K_v)
        self.assertEqual(self.play.pan, [0, 0])
        self.assertEqual(self.press(pygame.K_l), [], "v must not walk you")
        self.assertEqual(self.play.pan, [1, 0])
        self.press(pygame.K_RETURN)
        self.assertIsNone(self.play.pan)

    def test_aiming_takes_the_window_back_from_the_view_command(self):
        """Both used the movement keys; whichever was up second lost them."""
        self.press(pygame.K_v)
        self.press(pygame.K_x)
        self.assertIsNone(self.play.pan)
        self.press(pygame.K_l)
        self.assertIsNotNone(self.play.cursor)
        self.assertNotEqual(self.play.cursor, [])


if __name__ == "__main__":
    unittest.main()
