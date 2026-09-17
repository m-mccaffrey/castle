"""Features that existed and could not be reached from the game.

Each of these was written, tested at the engine level, and unreachable: the
window sent an action the handler could not use, or nothing sent it at all.
The engine tests all passed the whole time, which is why these go through
the client's own path - the action the window actually sends, and the packet
the server actually sends back.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame                                                    # noqa: E402

from stormhold.game.items import Item                             # noqa: E402
from stormhold.game.world import World                            # noqa: E402


class TestNothingIsSpentBeforeYouHaveChosen(unittest.TestCase):
    """Revelation and the scrolls need an object named before they can act."""

    def setUp(self):
        self.world = World(seed=5)
        self.p = self.world.add_player("Picker")
        self.level = self.world.levels[self.p.depth]

    def picks(self):
        return [e for e in self.world.events if e["t"] == "pick"]

    def test_revelation_asks_first_and_charges_nothing(self):
        self.p.spells.add("Revelation")
        self.p.mana = 80
        self.world.do_player_action(self.level, self.p,
                                    {"a": "cast", "spell": "Revelation"})
        self.assertEqual(self.p.mana, 80, "the mana must still be there")
        asked = self.picks()
        self.assertTrue(asked, "nothing asked which object to look at")
        self.assertEqual(asked[0]["action"]["spell"], "Revelation",
                         "the request must carry the action to repeat")

    def test_revelation_with_a_target_identifies_and_charges(self):
        self.p.spells.add("Revelation")
        self.p.mana = 80
        ring = Item("ring_warding")
        ring.known = False
        self.p.add_item(ring)
        self.world.do_player_action(self.level, self.p,
                                    {"a": "cast", "spell": "Revelation",
                                     "target": ring.id})
        self.assertTrue(ring.known)
        self.assertLess(self.p.mana, 80)

    def test_a_scroll_of_revelation_survives_being_read_with_nothing_named(self):
        scroll = Item("scroll_ident")
        scroll.known = True
        self.p.add_item(scroll)
        belt = Item("belt3")
        self.p.equipment["waist"] = belt
        self.p.inventory.remove(scroll)
        belt.contents.append(scroll)
        self.world.do_player_action(self.level, self.p,
                                    {"a": "use", "id": scroll.id})
        self.assertIn(scroll, belt.contents, "the scroll must not be spent")
        self.assertTrue(self.picks(), "nothing asked what to identify")

    def test_the_enchant_scroll_asks_for_something_wearable(self):
        scroll = Item("scroll_enchant")
        scroll.known = True
        belt = Item("belt3")
        self.p.equipment["waist"] = belt
        belt.contents.append(scroll)
        self.world.do_player_action(self.level, self.p,
                                    {"a": "use", "id": scroll.id})
        asked = self.picks()
        self.assertTrue(asked)
        self.assertEqual(asked[0]["want"], "worn",
                         "only a weapon or armour can take an enchantment")


class TestOverdrawingManaCanBeAgreedTo(unittest.TestCase):

    def setUp(self):
        self.world = World(seed=5)
        self.p = self.world.add_player("Caster")
        self.level = self.world.levels[self.p.depth]
        self.p.spells.add("Spark")
        self.p.mana = 0

    def test_the_refusal_is_a_question_with_the_cast_attached(self):
        self.world.do_player_action(self.level, self.p,
                                    {"a": "cast", "spell": "Spark", "x": self.p.x,
                                     "y": self.p.y})
        asks = [e for e in self.world.events if e["t"] == "ask"]
        self.assertTrue(asks, "there was no way to say yes")
        self.assertEqual(asks[0]["key"], "confirm_overdraw")
        self.assertEqual(asks[0]["action"]["spell"], "Spark")

    def test_saying_yes_casts_it_and_takes_the_hit_points(self):
        before = self.p.hp
        self.world.do_player_action(self.level, self.p,
                                    {"a": "cast", "spell": "Spark",
                                     "x": self.p.x, "y": self.p.y,
                                     "confirm_overdraw": True})
        self.assertLess(self.p.hp, before)


class TestTheLightSpellChangesTheMap(unittest.TestCase):
    """It set the remembered bit and then asked for an event nobody handled.

    Worse than nothing: update_fov only sends a square whose bit is *not*
    set, so lighting one was the way to make sure it could never be sent.
    """

    def test_lighting_a_place_queues_it_for_the_client(self):
        world = World(seed=5)
        p = world.add_player("Lamp")
        world.move_player_to(p, 1)
        p.spells.add("Lantern")
        p.mana = 50
        # Light only sends a square it has *not* remembered, and the ground
        # you are standing on is remembered already, so forget this floor
        # first or the check proves nothing either way.
        level = world.levels[p.depth]
        mem = world.memory_for(p, level)
        for i in range(len(mem)):
            mem[i] = 0
        p.pending_tiles = []
        world.do_player_action(level, p, {"a": "cast", "spell": "Lantern",
                                          "x": p.x, "y": p.y})
        self.assertTrue(p.pending_tiles,
                        "the lit squares were never sent to the client")
        self.assertFalse([e for e in world.events if e["t"] == "map"],
                         "the map event type does not exist any more")


class TestTheCounterRefreshesWhileYouStandAtIt(unittest.TestCase):

    def setUp(self):
        self.world = World(seed=5)
        self.p = self.world.add_player("Saver")
        self.level = self.world.levels[self.p.depth]
        self.p.copper = 500

    def shops(self):
        return [e for e in self.world.events if e["t"] == "shop"]

    def test_a_deposit_redraws_the_strongroom(self):
        self.world.do_player_action(self.level, self.p,
                                    {"a": "service", "what": "deposit",
                                     "amount": 100, "shop": "bank"})
        self.assertEqual((self.p.copper, self.p.bank), (400, 100))
        self.assertTrue(self.shops(), "the panel was left showing the old figures")

    def test_an_identify_redraws_the_sage(self):
        ring = Item("ring_warding")
        ring.known = False
        self.p.add_item(ring)
        self.p.copper = 9000
        self.world.do_player_action(self.level, self.p,
                                    {"a": "service", "what": "identify",
                                     "shop": "sage", "id": ring.id})
        self.assertTrue(ring.known)
        self.assertTrue(self.shops(), "his window still called it unknown")


class TestTheSitesHaveAVerb(unittest.TestCase):
    """Fountains and thrones were generated, described, and unusable."""

    def test_the_verbs_menu_offers_both(self):
        from stormhold.ui.app import PlayScene
        from tests.test_ui import make_app
        pygame.display.init()
        app = make_app()
        app.screen = pygame.display.set_mode((1280, 800))
        play = PlayScene(app)
        play.build_chrome()
        verbs = dict(play.menubar.menus)["Verbs"]
        actions = [action for _, action, _ in verbs]
        self.assertIn("fountain", actions)
        self.assertIn("throne", actions)

    def test_the_handlers_answer_when_you_are_not_on_one(self):
        world = World(seed=5)
        p = world.add_player("Thirsty")
        said = []
        world.msg = lambda text, kind="info", **kw: said.append(text)
        for verb in ("fountain", "throne"):
            world.do_player_action(world.levels[p.depth], p, {"a": verb})
        self.assertEqual(len(said), 2, "both verbs must answer")


if __name__ == "__main__":
    unittest.main()
