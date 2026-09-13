"""Tests for the parts of Stormhold that are easy to get subtly wrong."""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stormhold.common.constants import (
    T, GRACE_TICKS, TOWN_DEPTH, MAX_DEPTH, encumbrance_for, CARRY_PER_STRENGTH,
    xp_for_level, MAX_LEVEL, SLOTS,
)
from stormhold.common.fov import compute_fov, has_los
from stormhold.game.level import generate_dungeon, generate_town, reachable
from stormhold.game.ai import find_path
from stormhold.game.actors import Player, make_monster, stat_bonus
from stormhold.game.items import Item, Appearances, generate_item, pluralise, BASES
from stormhold.game.spells import SPELLS, can_learn
from stormhold.game.combat import attack_roll, apply_damage
from stormhold.game.world import World
from stormhold.net.protocol import encode, Decoder
import random


class TestLevels(unittest.TestCase):
    def test_every_floor_is_fully_connected(self):
        for depth in range(1, MAX_DEPTH + 1):
            level = generate_dungeon(depth, 555)
            walkable = sum(1 for y in range(level.h) for x in range(level.w)
                           if level.passable(x, y))
            reach = reachable(level, *level.up_at)
            self.assertEqual(len(reach), walkable,
                             f"floor {depth} has tiles nothing can reach")
            if depth < MAX_DEPTH:
                self.assertIsNotNone(level.down_at, f"floor {depth} has no way down")
                self.assertIn(level.idx(*level.down_at), reach,
                              f"floor {depth} down stairs walled off")

    def test_room_centres_stay_clear(self):
        """Stairs, altars and bosses all sit on a room centre."""
        for seed in range(12):
            for depth in (1, 12, 25):
                level = generate_dungeon(depth, seed * 977)
                for room in level.rooms:
                    self.assertTrue(level.passable(room["cx"], room["cy"]))

    def test_town_is_walkable_and_has_every_trade(self):
        town = generate_town(7)
        reach = reachable(town, *town.spawn_point)
        self.assertIn(town.idx(*town.down_at), reach, "keep gate unreachable")
        trades = {n["shop"] for n in town.npcs}
        self.assertEqual(trades, {"weaponsmith", "armourer", "general", "magic",
                                  "sage", "temple", "bank"})
        for npc in town.npcs:
            self.assertTrue(town.passable(npc["x"], npc["y"]), f"{npc['name']} is in a wall")

    def test_pathfinding_reaches_every_room(self):
        level = generate_dungeon(6, 99)
        start = level.rooms[0]
        for room in level.rooms:
            self.assertIsNotNone(
                find_path(level, start["cx"], start["cy"], room["cx"], room["cy"]),
                f"no path to the room at {room['cx']},{room['cy']}")

    def test_sight_is_blocked_by_walls(self):
        level = generate_dungeon(2, 31)
        room = level.rooms[0]
        seen = compute_fov(level, room["cx"], room["cy"], 8)
        self.assertIn(level.idx(room["cx"], room["cy"]), seen)
        for i in seen:
            x, y = i % level.w, i // level.w
            self.assertLessEqual(max(abs(x - room["cx"]), abs(y - room["cy"])), 8)


class TestEncumbrance(unittest.TestCase):
    def test_tiers(self):
        cap = 12 * CARRY_PER_STRENGTH
        self.assertEqual(encumbrance_for(100, cap)[0], "Unencumbered")
        self.assertEqual(encumbrance_for(int(cap * 0.7), cap)[0], "Burdened")
        self.assertEqual(encumbrance_for(int(cap * 0.95), cap)[0], "Stressed")
        self.assertIsNone(encumbrance_for(cap * 3, cap)[1], "overloaded should be immobile")

    def test_gold_has_weight_and_slows_you(self):
        p = Player("Miser", {"strength": 10, "dexterity": 10,
                             "intelligence": 10, "constitution": 10})
        light = p.action_cost(100)
        p.gold = 12000                       # 120 lb of coins
        heavy = p.action_cost(100)
        self.assertGreater(heavy, light, "a fortune in coin should slow you down")

    def test_heavy_armour_costs_time(self):
        p = Player("Knight", {"strength": 16, "dexterity": 10,
                              "intelligence": 8, "constitution": 12})
        bare = p.action_cost(100)
        for key in ("platemail", "towershield", "helm"):
            it = Item(key)
            p.inventory.append(it)
            p.equip(it)
        self.assertGreaterEqual(p.action_cost(100), bare)


class TestCharacters(unittest.TestCase):
    def test_levelling_stops_at_the_cap(self):
        p = Player("Hero")
        p.add_xp(10 ** 9)
        self.assertEqual(p.level, MAX_LEVEL)

    def test_equipment_changes_derived_stats(self):
        p = Player("Guard", {"strength": 14, "dexterity": 12,
                             "intelligence": 8, "constitution": 12})
        before = p.armour_class
        mail = Item("chainmail")
        p.inventory.append(mail)
        ok, _ = p.equip(mail)
        self.assertTrue(ok)
        self.assertGreater(p.armour_class, before)

    def test_cursed_gear_will_not_come_off(self):
        p = Player("Unlucky")
        ring = Item("ring_burden", enchant=-2, cursed=True)
        p.inventory.append(ring)
        p.equip(ring)
        slot = "ring_left" if p.equipment["ring_left"] else "ring_right"
        ok, message = p.unequip(slot)
        self.assertFalse(ok)
        self.assertIn("not come off", message)

    def test_strength_requirement_is_enforced(self):
        weak = Player("Scholar", {"strength": 8, "dexterity": 10,
                                  "intelligence": 16, "constitution": 9})
        plate = Item("platemail")
        weak.inventory.append(plate)
        ok, message = weak.equip(plate)
        self.assertFalse(ok)
        self.assertIn("not strong enough", message)


class TestItems(unittest.TestCase):
    def test_unidentified_things_hide_their_name(self):
        app = Appearances(1234)
        potion = Item("potion_heal")
        hidden = potion.name(app)
        self.assertNotIn("Healing", hidden)
        app.identify("potion_heal")
        self.assertIn("Healing", potion.name(app))

    def test_appearances_differ_between_worlds(self):
        a, b = Appearances(1), Appearances(2)
        self.assertNotEqual(a.look, b.look, "potion colours should be reshuffled each game")

    def test_plurals(self):
        self.assertEqual(pluralise("Torch", 5), "Torches")
        self.assertEqual(pluralise("Potion of Healing", 2), "Potions of Healing")
        self.assertEqual(pluralise("Ration", 3), "Rations")

    def test_generated_items_are_sane(self):
        rng = random.Random(4)
        for depth in range(1, MAX_DEPTH + 1):
            for _ in range(40):
                it = generate_item(depth, rng)
                self.assertTrue(it.name(None))
                self.assertGreater(it.value(), 0)
                self.assertGreaterEqual(it.weight, 0)


class TestSpells(unittest.TestCase):
    def test_learning_is_gated_by_level_and_wits(self):
        ok, _ = can_learn("Fireball", 3, 10)
        self.assertFalse(ok)
        ok, _ = can_learn("Fireball", 20, 9)
        self.assertFalse(ok)
        ok, _ = can_learn("Fireball", 20, 18)
        self.assertTrue(ok)

    def test_every_spell_is_well_formed(self):
        for name, spell in SPELLS.items():
            self.assertIn("school", spell)
            self.assertGreater(spell["mana"], 0, name)
            self.assertGreaterEqual(spell["level"], 1, name)


class TestCombat(unittest.TestCase):
    def test_armour_makes_you_harder_to_hit(self):
        rng = random.Random(7)
        lightly = sum(attack_roll(rng, 3, 3)[0] for _ in range(3000))
        heavily = sum(attack_roll(rng, 3, 16)[0] for _ in range(3000))
        self.assertGreater(lightly, heavily * 3)

    def test_natural_one_and_twenty(self):
        class Fixed:
            def __init__(self, value):
                self.value = value

            def randint(self, a, b):
                return self.value
        self.assertFalse(attack_roll(Fixed(1), 99, 0)[0], "a 1 always misses")
        self.assertTrue(attack_roll(Fixed(20), -99, 99)[0], "a 20 always hits")


class TestTurnEngine(unittest.TestCase):
    def make_world(self):
        world = World(seed=20260913)
        dad = world.add_player("Dad")
        mia = world.add_player("Mia")
        town = world.levels[TOWN_DEPTH]
        for who in (dad, mia):
            town.move_actor(who, *town.down_at)
            world.update_fov(who, force=True)
            world.submit(who, {"a": "stairs"})
        return world, dad, mia, world.levels[1]

    def test_nothing_happens_until_somebody_acts(self):
        world, dad, mia, level = self.make_world()
        before = level.clock
        time.sleep(0.25)
        self.assertEqual(level.clock, before,
                         "the world moved on its own; this is meant to be turn-based")

    def test_an_action_advances_the_clock(self):
        world, dad, mia, level = self.make_world()
        before = level.clock
        world.submit(dad, {"a": "wait"})
        self.assertGreater(level.clock, before)

    def test_the_floor_waits_for_a_player_who_has_not_acted(self):
        world, dad, mia, level = self.make_world()
        base = level.clock
        for _ in range(20):
            world.submit(dad, {"a": "wait"})
        ran = level.clock - base
        self.assertLessEqual(ran, GRACE_TICKS * 3,
                             "the floor ran far ahead of a player who had not acted")
        self.assertEqual(level.waiting_on, mia.id,
                         "the floor should say who it is waiting for")

    def test_taking_the_stairs_does_not_corrupt_the_clock(self):
        """A character who changes floor is timed against the new floor."""
        world, dad, mia, level = self.make_world()
        for _ in range(6):
            world.submit(dad, {"a": "wait"})
            world.submit(mia, {"a": "wait"})
        level.move_actor(dad, *level.up_at)
        world.update_fov(dad, force=True)
        world.submit(dad, {"a": "stairs"})
        self.assertEqual(dad.depth, TOWN_DEPTH)
        town = world.levels[TOWN_DEPTH]
        self.assertGreaterEqual(dad.next_at, town.clock,
                                "arriving on a floor must not leave you owing turns")

    def test_nobody_blocks_anybody_in_a_safe_place(self):
        """In town there is nothing to be fair about, so nobody waits."""
        world = World(seed=4242)
        a = world.add_player("A")
        b = world.add_player("B")
        town = world.levels[TOWN_DEPTH]
        before = town.clock
        for _ in range(10):
            world.submit(a, {"a": "wait"})
        self.assertGreater(town.clock, before, "an idle companion froze the town")

    def test_an_absent_player_does_not_strand_the_party(self):
        world, dad, mia, level = self.make_world()
        for _ in range(20):
            world.submit(dad, {"a": "wait"})
        self.assertEqual(level.waiting_on, mia.id)
        self.assertEqual(world.nudge_idle(idle_seconds=45.0), [],
                         "should not nudge somebody who has only just paused")
        level.waiting_since -= 120
        self.assertIn(mia.id, world.nudge_idle(idle_seconds=45.0))
        before = level.clock
        for _ in range(4):
            world.submit(dad, {"a": "wait"})
        self.assertGreater(level.clock, before, "the party is still stuck")


class TestWorld(unittest.TestCase):
    def test_death_drops_the_pack_and_wakes_you_in_town(self):
        world = World(seed=11)
        p = world.add_player("Doomed")
        world.submit(p, {"a": "wait"})
        town = world.levels[TOWN_DEPTH]
        town.move_actor(p, *town.down_at)
        world.submit(p, {"a": "stairs"})
        self.assertEqual(p.depth, 1)
        p.gold = 1000
        p.add_item(Item("potion_heal", qty=2))
        carried = len(p.inventory)
        self.assertGreater(carried, 0)
        where = (p.x, p.y)
        apply_damage(world, p, 99999, None)
        self.assertEqual(p.depth, TOWN_DEPTH, "death should wake you at the temple")
        self.assertEqual(len(p.inventory), 0, "your pack should stay where you fell")
        self.assertEqual(p.gold, 800, "expected a fifth of your gold to be lost")
        self.assertGreater(p.hp, 0)
        self.assertTrue(world.levels[1].items_at(*where), "the pack is not on the floor")

    def test_buying_costs_gold_and_selling_pays(self):
        world = World(seed=3)
        p = world.add_player("Shopper")
        stock = world.stock_for("weaponsmith")
        item = min(stock, key=lambda i: i.value())
        p.gold = item.value()
        world.submit(p, {"a": "buy", "shop": "weaponsmith", "id": item.id})
        self.assertEqual(p.gold, 0)
        self.assertTrue(any(i.id == item.id for i in p.inventory))
        world.submit(p, {"a": "sell", "shop": "weaponsmith", "id": item.id})
        self.assertGreater(p.gold, 0)

    def test_the_strongroom_takes_the_weight_off_you(self):
        world = World(seed=3)
        p = world.add_player("Banker")
        p.gold = 5000
        heavy = p.carried_weight
        world.submit(p, {"a": "service", "what": "deposit", "amount": 5000})
        self.assertEqual(p.bank, 5000)
        self.assertLess(p.carried_weight, heavy)

    def test_a_snapshot_only_shows_what_you_can_see(self):
        world = World(seed=8)
        p = world.add_player("Watcher")
        town = world.levels[TOWN_DEPTH]
        town.move_actor(p, *town.down_at)
        world.submit(p, {"a": "stairs"})
        world.update_fov(p, force=True)
        snap = world.snapshot_for(p)
        level = world.levels[p.depth]
        for actor in snap["actors"]:
            if actor["k"] == "player":
                continue
            self.assertIn(actor["y"] * level.w + actor["x"], p.fov,
                          f"leaked a hidden {actor['n']}")


class TestProtocol(unittest.TestCase):
    def test_messages_survive_fragmented_reads(self):
        blob = encode("hello", {"name": "Dad"}) + encode("act", {"a": "move"})
        decoder = Decoder()
        out = []
        for i in range(0, len(blob), 3):
            out.extend(decoder.feed(blob[i:i + 3]))
        self.assertEqual([m for m, _ in out], ["hello", "act"])

    def test_large_messages_round_trip(self):
        payload = {"d": list(range(30000))}
        out = Decoder().feed(encode("tiles", payload))
        self.assertEqual(out[0][1]["d"], payload["d"])

    def test_rubbish_is_ignored_not_fatal(self):
        decoder = Decoder()
        self.assertEqual(decoder.feed(b"\x00\x00\x00\x04junk"), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
