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


class TestTheGetCommandDoesWhatTheHelpSays(unittest.TestCase):
    """"This command generally puts everything on the floor into the
    player's pack. The special case is if the object is a pack, purse, or
    belt, and the player isn't wearing one, the object goes in the
    appropriate inventory slot."

    Ours took the top item of the pile and nothing else, and a found pack
    went into the pack you did not have.
    """

    def setUp(self):
        self.world = World(seed=5)
        self.p = self.world.add_player("Magpie")
        self.level = self.world.levels[self.p.depth]

    def test_one_press_lifts_the_whole_pile(self):
        for key in ("shortsword", "potion_heal", "leather"):
            self.level.add_ground_item(self.p.x, self.p.y, Item(key))
        held = len(self.p.inventory)
        self.world.do_player_action(self.level, self.p, {"a": "pickup"})
        self.assertEqual(len(self.p.inventory), held + 3)
        self.assertFalse(self.level.items_at(self.p.x, self.p.y))

    def test_a_pack_purse_or_belt_goes_on_rather_than_in(self):
        for key, slot in (("pack", "pack"), ("purse", "purse"), ("belt3", "waist")):
            with self.subTest(item=key):
                self.p.equipment[slot] = None
                thing = Item(key)
                self.level.add_ground_item(self.p.x, self.p.y, thing)
                self.world.do_player_action(self.level, self.p, {"a": "pickup"})
                self.assertIs(self.p.equipment.get(slot), thing)

    def test_but_a_second_one_goes_in_the_pack_as_usual(self):
        self.p.equipment["purse"] = Item("purse")
        spare = Item("purse")
        self.level.add_ground_item(self.p.x, self.p.y, spare)
        self.world.do_player_action(self.level, self.p, {"a": "pickup"})
        self.assertIn(spare, self.p.inventory)


class TestTheTwoRestCommandsAreTwoCommands(unittest.TestCase):
    """"Rest until player is fully healed" and "Rest until player's mana is
    restored" have different conditions and different interrupts: the first
    breaks "as soon as a monster comes in sight", the second "only ... when
    a monster attacks you, not when they come into view."
    """

    def setUp(self):
        self.world = World(seed=5)
        self.p = self.world.add_player("Sleeper")
        self.world.move_player_to(self.p, 1)
        self.level = self.world.levels[self.p.depth]
        for other in [a for a in list(self.level.actors.values())
                      if getattr(a, "kind", "") == "monster"]:
            self.level.remove(other)
        self.p.recalc()

    def test_rest_ends_when_the_wounds_are_closed_not_when_mana_is_back(self):
        self.p.hp = self.p.max_hp
        self.p.mana = 0
        self.world.do_player_action(self.level, self.p, {"a": "rest"})
        self.assertFalse(self.p.resting,
                         "r kept you sitting in the open waiting on mana")

    def test_sleep_still_waits_for_mana(self):
        self.p.hp = self.p.max_hp
        self.p.mana = 0
        self.world.do_player_action(self.level, self.p, {"a": "sleep"})
        self.assertEqual(self.p.resting, "mana")


class TestTheActivateMenuExists(unittest.TestCase):
    """The original's menu bar reads File, Character!, Inventory!, Map!,
    Spells, Activate, Verbs, Window - read off the running program. Ours had
    no Activate, so the only way to drink a potion was to open the pack.
    """

    def setUp(self):
        from stormhold.ui.app import PlayScene
        from tests.test_ui import make_app
        pygame.display.init()
        self.app = make_app()
        self.app.screen = pygame.display.set_mode((1280, 800))
        self.world = World(seed=5)
        self.player = self.world.add_player("Drinker")
        self.play = PlayScene(self.app)
        self.app.play = self.play

    def menu(self):
        self.play.menubar = None
        self.app.inventory = self.world.inventory_view(self.player)
        self.play.build_chrome()
        return dict(self.play.menubar.menus)["Activate"]

    def test_it_lists_what_is_to_hand_and_nothing_else(self):
        buried = Item("potion_heal")
        buried.known = True
        self.player.add_item(buried)
        self.assertEqual([row[0] for row in self.menu()], ["Nothing to hand"],
                         "a potion in the pack cannot be activated")

        belt = Item("belt3")
        self.player.equipment["waist"] = belt
        self.player.inventory.remove(buried)
        belt.contents.append(buried)
        rows = self.menu()
        self.assertEqual([row[0] for row in rows], ["Potion of Healing"])
        self.assertEqual(rows[0][1], f"use:{buried.id}")

    def test_choosing_one_sends_the_use_action(self):
        belt = Item("belt3")
        potion = Item("potion_heal")
        potion.known = True
        self.player.equipment["waist"] = belt
        belt.contents.append(potion)
        sent = []
        self.play.send_action = sent.append
        self.play.menu_command(self.menu()[0][1])
        self.assertEqual(sent, [{"a": "use", "id": potion.id}])


class TestAShopPaysWhatItOffered(unittest.TestCase):
    """The number in the box and the number in your purse are the same one.

    They were two: the window quoted four fifths of an item's value for
    every shop alike, while the sale paid Nan's flat twenty-five. She
    offered 129 copper for a sword and handed over twenty-five. The
    armourer was worse - it quoted 960 for a sword it would not take at
    all, and paid nothing.
    """

    def setUp(self):
        self.world = World(seed=5)
        self.p = self.world.add_player("Hawker")
        self.level = self.world.levels[self.p.depth]

    def offer_and_sell(self, shop, key):
        item = Item(key)
        item.known = True
        self.p.inventory = [item]
        view = self.world.shop_view(self.p, shop, 1, shop)
        row = next(r for r in view["sell"] if r["id"] == item.id)
        before = self.p.copper
        self.world.do_player_action(self.level, self.p,
                                    {"a": "sell", "shop": shop, "id": item.id})
        return row, self.p.copper - before

    def test_every_shop_pays_exactly_what_its_window_said(self):
        for shop in ("weaponsmith", "armourer", "general", "magic", "junk"):
            for key in ("longsword", "platemail", "potion_heal", "dagger", "gem"):
                with self.subTest(shop=shop, item=key):
                    row, paid = self.offer_and_sell(shop, key)
                    self.assertEqual(paid, row["price"],
                                     f"{shop} offered {row['price']} and paid {paid}")

    def test_a_shop_that_will_not_buy_offers_nothing_and_says_why(self):
        row, paid = self.offer_and_sell("armourer", "longsword")
        self.assertEqual(row["price"], 0, "it quoted a price it would not honour")
        self.assertTrue(row["refusal"], "and gave the window no reason to show")
        self.assertEqual(paid, 0)

    def test_nan_still_takes_anything(self):
        for key in ("longsword", "platemail", "potion_heal", "gem"):
            with self.subTest(item=key):
                row, paid = self.offer_and_sell("junk", key)
                self.assertIsNone(row["refusal"])
                self.assertEqual(paid, self.world.JUNK_FLAT)


class TestDropWorksFromWhereverTheThingIs(unittest.TestCase):
    """Reported from play. The Drop button is offered, and enabled, for
    anything you can select - but the handler insisted the thing was loose
    in the pack, so dropping a potion off your belt or the sword in your
    hand did nothing at all and said nothing at all.
    """

    def setUp(self):
        self.world = World(seed=5)
        self.p = self.world.add_player("Dropper")
        self.level = self.world.levels[self.p.depth]
        self.said = []
        self.world.msg = lambda text, kind="info", **kw: self.said.append(text)

    def floor(self):
        return [i.key for i in self.level.items_at(self.p.x, self.p.y)]

    def test_dropping_out_of_the_pack(self):
        sword = Item("shortsword")
        self.p.add_item(sword)
        self.world.do_player_action(self.level, self.p,
                                    {"a": "drop", "id": sword.id})
        self.assertIn("shortsword", self.floor())
        self.assertNotIn(sword, self.p.inventory)

    def test_dropping_off_the_belt(self):
        belt = Item("belt3")
        potion = Item("potion_heal")
        self.p.equipment["waist"] = belt
        belt.contents.append(potion)
        self.world.do_player_action(self.level, self.p,
                                    {"a": "drop", "id": potion.id})
        self.assertIn("potion_heal", self.floor())
        self.assertEqual(belt.contents, [])

    def test_dropping_what_you_are_wearing(self):
        helm = Item("helm")
        self.p.equipment["head"] = helm
        self.world.do_player_action(self.level, self.p,
                                    {"a": "drop", "id": helm.id})
        self.assertIn("helm", self.floor())
        self.assertIsNone(self.p.equipment["head"])
        self.assertNotIn(helm, self.p.inventory, "it must not also be in the pack")

    def test_a_cursed_thing_stays_on_and_says_why(self):
        ring = Item("ring_burden")
        ring.cursed = True
        self.p.equipment["ring_left"] = ring
        self.world.do_player_action(self.level, self.p,
                                    {"a": "drop", "id": ring.id})
        self.assertIs(self.p.equipment["ring_left"], ring)
        self.assertNotIn("ring_burden", self.floor())
        self.assertTrue(self.said, "it refused in silence")

    def test_dropping_something_you_do_not_have_says_so(self):
        self.world.do_player_action(self.level, self.p,
                                    {"a": "drop", "id": 999999})
        self.assertTrue(self.said, "a drop that cannot happen must say so")


class TestBuyingStraightOntoTheBody(unittest.TestCase):
    """Reported from play: "the stores force you to put something in the
    pack before you put it on your person". Dragging out of the shop onto
    the paper doll now buys and wears in one motion.
    """

    def setUp(self):
        self.world = World(seed=5)
        self.p = self.world.add_player("Shopper")
        self.level = self.world.levels[self.p.depth]
        self.p.copper = 9000

    def buy(self, shop, item, **extra):
        return self.world.do_player_action(
            self.level, self.p,
            dict({"a": "buy", "shop": shop, "id": item.id}, **extra))

    def first_stock(self, shop, slot=None):
        return next(i for i in self.world.stock_for(shop)
                    if (slot is None and i.slot) or i.slot == slot)

    def test_dropping_a_helmet_on_the_head_slot_wears_it(self):
        item = self.first_stock("general")
        self.buy("general", item, wear=item.slot)
        self.assertIs(self.p.equipment.get(item.slot), item)

    def test_without_a_slot_it_still_lands_in_the_pack(self):
        item = self.first_stock("general")
        self.buy("general", item)
        self.assertIn(item, self.p.inventory)
        self.assertIsNot(self.p.equipment.get(item.slot), item,
                         "without a slot named it must stay in the pack")

    def test_a_slot_it_does_not_fit_leaves_it_in_the_pack_and_says_so(self):
        item = self.first_stock("general")
        said = []
        self.world.msg = lambda text, kind="info", **kw: said.append(text)
        self.buy("general", item, wear="head" if item.slot != "head" else "feet")
        self.assertIn(item, self.p.inventory)
        self.assertTrue(said)


class TestAMagicalPackActuallyLightensTheLoad(unittest.TestCase):
    """The original: "If non-zero, the Wt. Fx and Bulk Fx columns are used
    instead of the sum of the contents (plus whatever intrinsic weight and
    bulk the container has)". Instead of, not as well as.

    What is "in the pack" is the character's inventory list; the pack item
    does not hold it. So the fixed figure was applied to the pack and the
    contents were then counted in full anyway - which made a Pack of Holding,
    the reward for getting deep, *heavier* than the ordinary pack it
    replaced. The parity table called this done.
    """

    def setUp(self):
        self.world = World(seed=5)
        self.p = self.world.add_player("Mule")

    def load(self, pack_key, suits):
        self.p.equipment["pack"] = Item(pack_key)
        self.p.inventory = [Item("platemail") for _ in range(suits)]
        self.p.recalc()
        return self.p.carried_weight, self.p.carried_bulk

    def test_a_pack_of_holding_weighs_the_same_full_as_empty(self):
        empty = self.load("holdpack", 0)
        full = self.load("holdpack", 8)
        self.assertEqual(empty, full)

    def test_an_ordinary_pack_does_not(self):
        empty = self.load("pack", 0)
        full = self.load("pack", 8)
        self.assertGreater(full[0], empty[0])
        self.assertGreater(full[1], empty[1])

    def test_it_is_worth_carrying(self):
        """It cost 900 and lives nine floors down; it has to beat a backpack."""
        plain = self.load("pack", 4)
        magic = self.load("holdpack", 4)
        self.assertLess(magic[0], plain[0],
                        "a Pack of Holding must be lighter than a backpack "
                        "with the same load in it")

    def test_you_can_still_be_stopped_by_what_you_wear(self):
        """The fixed figure covers the pack's contents, not your armour."""
        self.load("holdpack", 2)
        light = self.p.carried_weight
        self.p.equipment["torso"] = Item("platemail")
        self.p.recalc()
        self.assertGreater(self.p.carried_weight, light)


class TestAHeavyWeaponIsSlowToSwing(unittest.TestCase):
    """Taking the bows out left this true of nothing: the crossbow was the
    only weapon slower than the base swing. The heavy end of the rack now
    carries a penalty scaled to what the thing weighs, and the label says so.
    """

    def setUp(self):
        from stormhold.game.actors import Player
        self.p = Player("Swinger", {"strength": 14, "dexterity": 10,
                                    "intelligence": 8, "constitution": 10})

    def swing(self, key):
        from stormhold.common.constants import ATTACK_COST
        self.p.equipment["weapon"] = Item(key) if key else None
        return self.p.action_cost(ATTACK_COST, attacking=True)

    def test_the_heavier_the_weapon_the_slower_the_swing(self):
        from stormhold.game.items import BASES
        weapons = sorted(((v["wt"], k) for k, v in BASES.items()
                          if v.get("slot") == "weapon" and v.get("dmg")))
        speeds = [(BASES[k].get("speed", 100), k, wt) for wt, k in weapons]
        # Not a strict ordering - a mace is compact for its weight - but the
        # lightest must be quicker than the heaviest by a clear margin.
        self.assertLess(speeds[0][0], speeds[-1][0] - 30,
                        f"{speeds[0][1]} and {speeds[-1][1]} swing alike")

    def test_something_is_actually_slower_than_bare_hands(self):
        bare = self.swing(None)
        self.assertGreater(self.swing("halberd"), bare)
        self.assertGreater(self.swing("axe"), bare)

    def test_a_dagger_is_still_quicker(self):
        self.assertLess(self.swing("dagger"), self.swing(None))

    def test_it_changes_the_swing_and_nothing_else(self):
        from stormhold.common.constants import REST_COST, MOVE_COST
        self.p.equipment["weapon"] = None
        rest, walk = (self.p.action_cost(REST_COST),
                      self.p.action_cost(MOVE_COST, moving=True))
        self.p.equipment["weapon"] = Item("halberd")
        self.p.recalc()
        self.assertEqual(self.p.action_cost(REST_COST), rest)
        self.assertEqual(self.p.action_cost(MOVE_COST, moving=True), walk)

    def test_the_label_says_which_way_it_cuts(self):
        self.assertIn("slow to swing", Item("halberd").describe())
        self.assertIn("quick to swing", Item("dagger").describe())
        self.assertNotIn("to swing", Item("longsword").describe())


class TestNanSaysWhatSheWillPay(unittest.TestCase):
    """The junk store pays a flat rate above 25 copper, which is the
    original's rule and looks like a bug unless the window admits it.
    """

    def test_the_window_explains_the_flat_rate(self):
        from stormhold.ui.app import StoreScene
        from tests.test_ui import make_app
        from stormhold.common.constants import JUNK_FLAT
        pygame.display.init()
        app = make_app()
        app.screen = pygame.display.set_mode((1280, 800))
        world = World(seed=5)
        player = world.add_player("Tipper")
        app.inventory = world.inventory_view(player)

        class _Play:
            you = {"name": "Tipper"}

            def add_message(self, *a, **k):
                pass
        app.play = _Play()
        drawn = []
        import stormhold.ui.widgets as W
        real = W.text
        W.text = lambda surf, value, *a, **k: (drawn.append(str(value)),
                                               real(surf, value, *a, **k))[1]
        try:
            scene = StoreScene(app, world.shop_view(player, "junk", 1, "Nan"))
            app.push(scene)
            scene.draw(app.screen)
        finally:
            W.text = real
        said = " ".join(drawn)
        self.assertIn(str(JUNK_FLAT), said)
        self.assertIn("anything", said.lower())

    def test_and_pays_exactly_that(self):
        world = World(seed=5)
        p = world.add_player("Tipper")
        sword = Item("longsword")
        p.inventory = [sword]
        row = next(r for r in world.shop_view(p, "junk", 1, "Nan")["sell"]
                   if r["id"] == sword.id)
        before = p.copper
        world.do_player_action(world.levels[p.depth], p,
                               {"a": "sell", "shop": "junk", "id": sword.id})
        self.assertEqual(p.copper - before, row["price"])


class TestBuyingOneOutOfALot(unittest.TestCase):
    """The magic shop stocks potions in twos. One drag buys one potion, so
    one potion is what the window must quote and what the till must charge -
    and what the shop must decide affordability on.

    All three disagreed: the shelf said 425 for the pair, the till took 212,
    and a customer with 300 copper was turned away from a potion they could
    afford. That last one is why a new character went down the stairs with
    nothing to drink.
    """

    def setUp(self):
        self.world = World(seed=8)
        self.p = self.world.add_player("Buyer")
        self.level = self.world.levels[self.p.depth]

    def lot(self):
        stock = self.world.stock_for("magic")
        return next(i for i in stock if i.stackable and i.qty > 1)

    def test_the_window_quotes_the_price_of_one(self):
        lot = self.lot()
        row = next(r for r in self.world.shop_view(self.p, "magic", 1, "M")["stock"]
                   if r["id"] == lot.id)
        self.assertEqual(row["price"], self.world.shop_price(Item(lot.key, qty=1)))

    def test_you_are_charged_what_you_were_quoted(self):
        lot = self.lot()
        row = next(r for r in self.world.shop_view(self.p, "magic", 1, "M")["stock"]
                   if r["id"] == lot.id)
        self.p.copper = row["price"] + 5
        before = self.p.copper
        self.world.do_player_action(self.level, self.p,
                                    {"a": "buy", "shop": "magic", "id": lot.id})
        self.assertEqual(before - self.p.copper, row["price"])

    def test_one_is_what_arrives_and_the_shelf_keeps_the_rest(self):
        lot = self.lot()
        was = lot.qty
        self.p.copper = 9999
        self.world.do_player_action(self.level, self.p,
                                    {"a": "buy", "shop": "magic", "id": lot.id})
        self.assertEqual(lot.qty, was - 1)
        self.assertEqual(sum(i.qty for i in self.p.inventory if i.key == lot.key), 1)

    def test_enough_for_one_is_enough(self):
        lot = self.lot()
        row = next(r for r in self.world.shop_view(self.p, "magic", 1, "M")["stock"]
                   if r["id"] == lot.id)
        self.p.copper = row["price"]
        self.world.do_player_action(self.level, self.p,
                                    {"a": "buy", "shop": "magic", "id": lot.id})
        self.assertTrue([i for i in self.p.inventory if i.key == lot.key],
                        "turned away from something they could afford")


class TestAStackCanBeReachedForOneAtATime(unittest.TestCase):
    """A belt slot takes one potion. Weighing the whole armful against it
    meant a stack of six could not be put on a belt at all, so a character
    carrying plenty had none of it to hand.
    """

    def test_a_stack_fills_the_belt_one_slot_at_a_time(self):
        world = World(seed=5)
        p = world.add_player("Drinker")
        belt = Item("belt3")
        p.equipment["waist"] = belt
        for _ in range(6):
            potion = Item("potion_mana")
            potion.known = True
            p.add_item(potion)
        for _ in range(6):
            stack = next((i for i in p.inventory if i.key == "potion_mana"), None)
            if stack is None:
                break
            world.do_player_action(world.levels[p.depth], p,
                                   {"a": "stow", "id": stack.id, "slot": "waist"})
        self.assertEqual(len(belt.contents), belt.base["belt_slots"])
        self.assertTrue(all(i.qty == 1 for i in belt.contents))
