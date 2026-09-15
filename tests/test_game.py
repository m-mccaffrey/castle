"""Tests for the parts of Stormhold that are easy to get subtly wrong."""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stormhold.common.constants import (
    T, GRACE_TICKS, TOWN_DEPTH, MAX_DEPTH, encumbrance_for, CARRY_PER_STRENGTH, CARRY_BASE, SHOP_BUY_MARKUP, SHOP_SELL_RATE,
    xp_for_level, MAX_LEVEL, SLOTS,
)
from stormhold.common.fov import compute_fov, has_los
from stormhold.game.level import generate_dungeon, generate_town, reachable
from stormhold.game.ai import find_path
from stormhold.game.actors import Player, make_monster, stat_bonus
from stormhold.game.items import (Item, Appearances, generate_item, generate_gold,
                                   pluralise, BASES)
from stormhold.game.spells import SPELLS, can_learn
from stormhold.game.combat import attack_roll, apply_damage
from stormhold.game.world import World
from stormhold.net.protocol import encode, Decoder
import random


class TestLevels(unittest.TestCase):
    def test_every_floor_is_fully_connected(self):
        for depth in range(1, MAX_DEPTH + 1):
            level = generate_dungeon(depth, 555)
            # A closed door is walkable: you open it by walking into it.
            from stormhold.game.level import can_walk_through
            walkable = sum(1 for y in range(level.h) for x in range(level.w)
                           if can_walk_through(level, x, y))
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
                                  "junk",
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
        cap = 12 * CARRY_PER_STRENGTH + CARRY_BASE
        self.assertEqual(encumbrance_for(100, cap)[0], "Unencumbered")
        self.assertEqual(encumbrance_for(int(cap * 0.7), cap)[0], "Burdened")
        self.assertEqual(encumbrance_for(int(cap * 0.95), cap)[0], "Stressed")
        self.assertIsNone(encumbrance_for(cap * 3, cap)[1], "overloaded should be immobile")

    def test_gold_weighs_and_slows_movement_but_not_other_actions(self):
        """The manual is explicit that load touches movement alone."""
        p = Player("Miser", {"strength": 10, "dexterity": 10,
                             "intelligence": 10, "constitution": 10})
        light_move = p.action_cost(100, moving=True)
        light_cast = p.action_cost(100)
        p.copper = p.capacity                  # a coin weighs a gram, so this
                                               # is the rated maximum exactly
        self.assertGreater(p.action_cost(100, moving=True), light_move,
                           "a fortune in coin should slow you down")
        self.assertEqual(p.action_cost(100), light_cast,
                         "but you cast just as fast however laden you are")

    def test_heavy_armour_costs_time(self):
        p = Player("Knight", {"strength": 16, "dexterity": 10,
                              "intelligence": 8, "constitution": 12})
        bare = p.action_cost(100, moving=True)
        for key in ("platemail", "towershield", "helm"):
            it = Item(key)
            p.inventory.append(it)
            p.equip(it)
        self.assertGreaterEqual(p.action_cost(100, moving=True), bare)


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
    """Armour lowers the chance of a telling blow; it never soaks damage."""

    def test_armour_value_lowers_the_chance_of_a_hit(self):
        from stormhold.game.combat import hit_chance
        ladder = [hit_chance(8, av) for av in (0, 6, 12, 24, 42, 75)]
        self.assertEqual(ladder, sorted(ladder, reverse=True),
                         "every step up the ladder helps")
        self.assertLess(ladder[-1], ladder[0] / 2,
                        "a full kit should more than halve what lands")

    def test_the_ladder_matches_the_original(self):
        """Body armour in sixes, helmets and shields in threes."""
        from stormhold.game.items import BASES
        self.assertEqual(BASES["leather"]["ac"], 6)
        self.assertEqual(BASES["chainmail"]["ac"], 30)
        self.assertEqual(BASES["platemail"]["ac"], 42)
        self.assertEqual(BASES["buckler"]["ac"], 3)
        self.assertEqual(BASES["helm"]["ac"], 9)

    def test_nothing_is_untouchable_and_nothing_always_lands(self):
        from stormhold.game.combat import hit_chance, HIT_FLOOR, HIT_CEILING
        self.assertEqual(hit_chance(0, 10_000), HIT_FLOOR)
        self.assertEqual(hit_chance(10_000, 0), HIT_CEILING)

    def test_a_landed_blow_is_sometimes_critical(self):
        rng = random.Random(7)
        rolls = [attack_roll(rng, 12, 0) for _ in range(4000)]
        landed = [c for hit, c in rolls if hit]
        self.assertTrue(any(landed), "some blows tell double")
        self.assertLess(sum(landed) / len(landed), 0.15)


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
        p.copper = 1000
        p.add_item(Item("potion_heal", qty=2))
        carried = len(p.inventory)
        self.assertGreater(carried, 0)
        where = (p.x, p.y)
        apply_damage(world, p, 99999, None)
        self.assertEqual(p.depth, TOWN_DEPTH, "death should wake you at the temple")
        self.assertEqual(len(p.inventory), 0, "your pack should stay where you fell")
        self.assertEqual(p.copper, 800, "expected a fifth of your gold to be lost")
        self.assertGreater(p.hp, 0)
        self.assertTrue(world.levels[1].items_at(*where), "the pack is not on the floor")

    def test_buying_costs_gold_and_selling_pays(self):
        world = World(seed=3)
        p = world.add_player("Shopper")
        stock = world.stock_for("weaponsmith")
        item = min(stock, key=lambda i: i.value())
        # A shop charges above the item's worth and pays below it - the
        # markup and the discount both measured from the original.
        price = world.shop_price(item)
        self.assertEqual(price, int(item.value() * SHOP_BUY_MARKUP))
        p.copper = price
        world.submit(p, {"a": "buy", "shop": "weaponsmith", "id": item.id})
        self.assertEqual(p.copper, 0)
        self.assertTrue(any(i.id == item.id for i in p.inventory))
        world.submit(p, {"a": "sell", "shop": "weaponsmith", "id": item.id})
        self.assertEqual(p.copper, int(item.value() * SHOP_SELL_RATE))
        self.assertLess(p.copper, price, "you never sell back at cost")

    def test_the_strongroom_takes_the_weight_off_you(self):
        world = World(seed=3)
        p = world.add_player("Banker")
        p.copper = 5000
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


class TestVerbs(unittest.TestCase):
    """The verb set taken from the original's menu."""

    def descend(self, seed=31):
        world = World(seed=seed)
        p = world.add_player("Verb")
        town = world.levels[TOWN_DEPTH]
        town.move_actor(p, *town.down_at)
        world.update_fov(p, force=True)
        world.submit(p, {"a": "stairs"})
        return world, p, world.levels[1]

    def messages(self, world):
        return [e["text"] for e in world.events if e["t"] == "msg"]

    def test_open_and_close_a_door(self):
        world, p, level = self.descend()
        spot = level.find_floor(p.x + 2, p.y)
        level.set(spot[0], spot[1], T.DOOR)
        level.move_actor(p, *level.find_free(spot[0] + 1, spot[1]))
        world.events.clear()
        # Name the square: floors have their own doors now, and an
        # unqualified Open takes whichever one it finds first.
        world.submit(p, {"a": "open", "x": spot[0], "y": spot[1]})
        self.assertEqual(level.get(*spot), T.DOOR_OPEN)
        world.events.clear()
        world.submit(p, {"a": "close", "x": spot[0], "y": spot[1]})
        self.assertEqual(level.get(*spot), T.DOOR)

    def test_a_door_will_not_close_on_somebody(self):
        world, p, level = self.descend()
        spot = level.find_floor(p.x + 2, p.y)
        level.set(spot[0], spot[1], T.DOOR_OPEN)
        level.move_actor(p, *level.find_free(spot[0] + 1, spot[1]))
        m = make_monster("cave_rat", spot[0], spot[1], 1, random.Random(1))
        m.depth = 1
        level.place(m)
        world.events.clear()
        world.submit(p, {"a": "close"})
        self.assertEqual(level.get(*spot), T.DOOR_OPEN, "closed a door on a creature")

    def test_free_hand_puts_the_weapon_away(self):
        world, p, level = self.descend()
        self.assertIsNotNone(p.equipment.get("weapon"))
        world.submit(p, {"a": "freehand"})
        self.assertIsNone(p.equipment.get("weapon"))
        self.assertTrue(any(i.slot == "weapon" for i in p.inventory))

    def test_examine_costs_no_time(self):
        world, p, level = self.descend()
        before = level.clock
        world.submit(p, {"a": "examine", "x": p.x, "y": p.y})
        self.assertEqual(level.clock, before, "looking at something took a turn")

    def test_rest_runs_until_healed_then_stops(self):
        world, p, level = self.descend()
        for m in [a for a in level.actors.values() if a.kind == "monster"]:
            level.remove(m)
        p.hp, p.mana = 2, 0
        world.submit(p, {"a": "rest"})
        for _ in range(3000):
            if not p.resting:
                break
            world.run_level(p.depth)
        self.assertFalse(p.resting)
        self.assertEqual(p.hp, p.max_hp)
        self.assertEqual(p.mana, p.max_mana)

    def test_you_cannot_rest_with_company(self):
        world, p, level = self.descend()
        m = make_monster("cave_rat", p.x + 2, p.y, 1, random.Random(1))
        m.depth = 1
        level.place(m)
        world.events.clear()
        world.submit(p, {"a": "rest"})
        self.assertFalse(p.resting)

    def test_running_crosses_open_ground(self):
        """Running must not stop on every tile just because the floor is open."""
        world = World(seed=31)
        p = world.add_player("Runner")
        town = world.levels[TOWN_DEPTH]
        town.move_actor(p, town.down_at[0], town.down_at[1] + 20)
        world.update_fov(p, force=True)
        start_y = p.y
        world.submit(p, {"a": "run", "dx": 0, "dy": -1})
        self.assertGreater(start_y - p.y, 5,
                           "run stopped almost immediately on open ground")

    def test_running_stops_at_the_stairs(self):
        world = World(seed=31)
        p = world.add_player("Runner")
        town = world.levels[TOWN_DEPTH]
        town.move_actor(p, town.down_at[0], town.down_at[1] + 20)
        world.update_fov(p, force=True)
        world.submit(p, {"a": "run", "dx": 0, "dy": -1})
        self.assertEqual((p.x, p.y), town.down_at,
                         "run should have halted on the keep gate")


class TestHazards(unittest.TestCase):
    def test_every_floor_gets_traps_and_hidden_doors(self):
        for depth in (1, 10, 25):
            level = generate_dungeon(depth, 4242)
            self.assertGreater(len(level.traps), 0, f"floor {depth} has no traps")
            self.assertGreater(len(level.secrets), 0, f"floor {depth} has no secret doors")
            for (x, y) in level.traps:
                self.assertTrue(level.passable(x, y), "a trap was placed inside a wall")

    def test_traps_start_hidden_and_searching_finds_them(self):
        world = World(seed=777)
        p = world.add_player("Seeker")
        town = world.levels[TOWN_DEPTH]
        town.move_actor(p, *town.down_at)
        world.update_fov(p, force=True)
        world.submit(p, {"a": "stairs"})
        level = world.levels[1]
        spot = next(iter(level.traps))
        self.assertFalse(level.traps[spot]["found"], "traps should start hidden")

        p.stats["intelligence"] = 20
        level.move_actor(p, *level.find_free(spot[0] + 1, spot[1]))
        for _ in range(40):
            world.submit(p, {"a": "search"})
            if spot not in level.traps or level.traps[spot]["found"]:
                break
        self.assertTrue(spot not in level.traps or level.traps[spot]["found"],
                        "searching next to a trap never revealed it")

    def test_walking_onto_a_hidden_trap_springs_it(self):
        world = World(seed=777)
        p = world.add_player("Unlucky")
        town = world.levels[TOWN_DEPTH]
        town.move_actor(p, *town.down_at)
        world.update_fov(p, force=True)
        world.submit(p, {"a": "stairs"})
        level = world.levels[1]
        spot = next(s for s, t in level.traps.items() if t["kind"] != "alarm")
        level.traps[spot]["kind"] = "dart"
        level.move_actor(p, *spot)
        before = p.hp
        world.spring_trap(level, p)
        self.assertLess(p.hp, before, "the trap did nothing")
        self.assertNotIn(spot, level.traps, "a sprung trap should be spent")


class TestStatusReadouts(unittest.TestCase):
    def test_condition_reads_in_words_not_numbers(self):
        from stormhold.common.constants import condition_for
        self.assertEqual(condition_for(1.0), "Uninjured")
        self.assertEqual(condition_for(0.9), "Barely scratched")
        self.assertEqual(condition_for(0.5), "Injured")
        self.assertEqual(condition_for(0.0), "Critically injured")
        # never falls off the end, however battered
        self.assertEqual(condition_for(-0.5), "Critically injured")

    def test_the_clock_reads_in_days_and_hours(self):
        from stormhold.common.constants import format_clock
        from stormhold.common.constants import TICKS_PER_SECOND
        self.assertEqual(format_clock(0), "0d,00:00:00")
        self.assertEqual(format_clock(1061 * TICKS_PER_SECOND), "0d,00:17:41")
        self.assertEqual(format_clock(86400 * 7 * TICKS_PER_SECOND),
                         "7d,00:00:00")

    def test_overall_speed_is_a_hundred_until_magic_says_otherwise(self):
        """The original reads "100% / 200%" for every fresh character.

        Dexterity does not enter it, and neither does the weapon in your hand:
        we used to scale every action by both, and a nimble character with a
        dagger read 125%.
        """
        quick = Player("Q", {"strength": 12, "dexterity": 16,
                             "intelligence": 8, "constitution": 8})
        slow = Player("S", {"strength": 12, "dexterity": 8,
                            "intelligence": 8, "constitution": 12})
        self.assertEqual(quick.speed_percent(), 100)
        self.assertEqual(slow.speed_percent(), 100)

        quick.add_effect("haste", 10 ** 9)
        self.assertEqual(quick.speed_percent(), 200)
        slow.add_effect("slowed", 10 ** 9)
        self.assertEqual(slow.speed_percent(), 50)

    def test_a_heavy_weapon_slows_the_swing_and_nothing_else(self):
        from stormhold.common.constants import ATTACK_COST, REST_COST
        from stormhold.game.items import Item
        p = Player("W", {"strength": 14, "dexterity": 10,
                         "intelligence": 8, "constitution": 10})
        bare = p.action_cost(ATTACK_COST, attacking=True)
        rest = p.action_cost(REST_COST)
        p.equipment["weapon"] = Item("crossbow")      # speed 140
        self.assertGreater(p.action_cost(ATTACK_COST, attacking=True), bare)
        self.assertEqual(p.action_cost(REST_COST), rest)

        laden = Player("L", {"strength": 10, "dexterity": 12,
                             "intelligence": 8, "constitution": 8})
        before = laden.move_speed_percent()
        # Copper weighs a hundredth of a pound a piece, so the pile has to be
        # sized against capacity rather than hardcoded - capacity moved when
        # the carry law was corrected against the original.
        laden.copper = laden.capacity
        self.assertLess(laden.move_speed_percent(), before,
                        "a purse full of copper should slow you down")

    def test_an_immobile_character_reports_zero_rather_than_lying(self):
        stuck = Player("Stuck", {"strength": 8, "dexterity": 10,
                                 "intelligence": 8, "constitution": 8})
        stuck.copper = 200000
        self.assertIsNone(stuck.move_speed_percent())
        self.assertIsNone(stuck.action_cost(100, moving=True))
        self.assertIsNotNone(stuck.action_cost(100),
                             "pinned by your own loot, you can still cast")


class TestStartingKit(unittest.TestCase):
    def test_you_start_light_with_a_purse_worth_spending(self):
        """The original's opening: a dagger, a pack, and a real decision."""
        world = World(seed=3)
        p = world.add_player("Newcomer")
        self.assertEqual(p.move_speed_percent(), 200,
                         "a fresh character should be lightly loaded")
        worn = {i.base["name"] for i in p.equipment.values() if i}
        self.assertNotIn("Leather Armour", worn, "armour is bought, not given")
        self.assertEqual(p.copper, 1500)

    def test_item_figures_match_the_original(self):
        """Grams and cubic centimetres, straight off the Object Directory."""
        from stormhold.game.items import Item
        self.assertEqual((Item("leather").base["wt"], Item("leather").base["bulk"]),
                         (5000, 24000))
        self.assertEqual((Item("dagger").base["wt"], Item("dagger").base["bulk"]),
                         (500, 500))
        pack = Item("pack").base
        self.assertEqual((pack["wt"], pack["bulk"]), (1000, 1000))
        self.assertEqual((pack["capacity"], pack["bulk_capacity"]), (12000, 50000))


class TestSpellRules(unittest.TestCase):
    """Rules taken verbatim from the original's Spell Directory."""

    def test_healing_is_a_floor_or_a_fraction_whichever_is_greater(self):
        from stormhold.game.spells import SPELLS
        minor = SPELLS["Mend Wounds"]
        self.assertEqual(minor["heal_flat"], 8)
        self.assertAlmostEqual(minor["heal_frac"], 0.20)
        # a big character gets the percentage, a small one the flat floor
        self.assertEqual(max(8, int(0.20 * 200)), 40)
        self.assertEqual(max(8, int(0.20 * 20)), 8)

    def test_elements_resist_themselves_and_fear_their_opposite(self):
        from stormhold.game.spells import elemental_factor
        self.assertEqual(elemental_factor("fire", {"element": "fire"}), 0.5)
        self.assertEqual(elemental_factor("fire", {"element": "cold"}), 1.5)
        self.assertEqual(elemental_factor("fire", {}), 1.0)
        self.assertEqual(elemental_factor(None, {"element": "fire"}), 1.0)

    def test_slowing_stacks_with_diminishing_returns(self):
        """1/2, then 1/3, then 1/4 - never a second halving."""
        import random as _r
        from stormhold.game.actors import make_monster
        from stormhold.game.monsters import MONSTERS
        world = World(seed=4)
        m = make_monster(sorted(MONSTERS)[0], 1, 1, 1, _r.Random(1))
        base = m.action_cost(100)
        world.apply_slow(m, 0)
        first = m.action_cost(100)
        world.apply_slow(m, 0)
        second = m.action_cost(100)
        self.assertEqual(first, base * 2)
        self.assertEqual(second, base * 3)

    def test_a_pack_of_holding_reports_a_fixed_weight(self):
        from stormhold.game.items import Item
        bag = Item("holdpack")
        empty = bag.weight
        for _ in range(3):
            bag.contents.append(Item("platemail"))
        self.assertEqual(bag.weight, empty, "a pack of holding never gets heavier")
        plain = Item("pack")
        before = plain.weight
        plain.contents.append(Item("platemail"))
        self.assertGreater(plain.weight, before)

    def test_coins_come_in_four_metals(self):
        from stormhold.common.constants import coin_purse
        self.assertEqual(coin_purse(1000), [("platinum", 1)])
        self.assertEqual(coin_purse(111), [("gold", 1), ("silver", 1), ("copper", 1)])

    def test_every_coin_weighs_a_gram_whatever_it_is_worth(self):
        """Why platinum matters: value per gram, not value per coin."""
        p = Player("Rich", {"strength": 10, "dexterity": 10,
                            "intelligence": 10, "constitution": 10})
        p.copper = 0
        p.gain_coins("copper", 1000)
        heavy_value, heavy_weight = p.copper, p.coin_count
        p.copper = 0
        p.gain_coins("platinum", 1)
        self.assertEqual(p.copper, heavy_value, "same value")
        self.assertEqual(p.coin_count, 1)
        self.assertEqual(heavy_weight, 1000, "a thousand copper is a kilogram")

    def test_a_purse_is_not_silently_consolidated(self):
        """Measured in the original: 1500 copper weighed 1500, not 12."""
        p = Player("Hoarder", {"strength": 10, "dexterity": 10,
                               "intelligence": 10, "constitution": 10})
        p.copper = 1500
        self.assertEqual(p.coin_count, 1500)

    def test_spending_makes_change_from_larger_coins(self):
        p = Player("Buyer", {"strength": 10, "dexterity": 10,
                             "intelligence": 10, "constitution": 10})
        p.copper = 0
        p.gain_coins("gold", 2)
        self.assertTrue(p.spend(150))
        self.assertEqual(p.copper, 50)
        self.assertFalse(p.spend(999), "you cannot spend what you have not got")

    def test_deep_finds_come_in_better_metal(self):
        import random as _r
        from stormhold.game.items import coin_metal
        rng = _r.Random(7)
        self.assertEqual(coin_metal(1, rng), "copper")
        self.assertIn(coin_metal(22, rng), ("platinum",))


class TestBestiaryBehaviour(unittest.TestCase):
    """Behaviours the original's bestiary describes in prose."""

    def test_some_creatures_arrive_in_packs(self):
        from stormhold.game.monsters import MONSTERS
        packed = [k for k, v in MONSTERS.items() if v.get("pack")]
        self.assertTrue(packed, "rats, wolves and goblins come in numbers")
        for k in packed:
            lo, hi = MONSTERS[k]["pack"]
            self.assertGreaterEqual(lo, 1)
            self.assertLessEqual(lo, hi)

    def test_fearless_things_never_break_off(self):
        import random as _r
        from stormhold.game.ai import _will_flee
        from stormhold.game.actors import make_monster
        from stormhold.game.monsters import MONSTERS
        brave = next(k for k, v in MONSTERS.items() if v.get("fearless"))
        timid = next(k for k, v in MONSTERS.items() if not v.get("fearless"))
        for key, expect in ((brave, False), (timid, True)):
            m = make_monster(key, 1, 1, 1, _r.Random(2))
            m.hp = 1
            self.assertEqual(_will_flee(m), expect, key)

    def test_immunity_beats_mere_resistance(self):
        from stormhold.game.spells import elemental_factor
        self.assertEqual(elemental_factor("fire", {"immune": ("fire",)}), 0.0)
        self.assertEqual(elemental_factor("fire", {"element": "fire"}), 0.5)

    def test_the_undead_take_different_things_from_you(self):
        world = World(seed=8)
        p = world.add_player("Victim")
        p.mana = 10
        world.drain_player(p, "mana")
        self.assertLess(p.mana, 10, "a wraith takes your magic first")
        p.mana = 0
        before = p.stat("intelligence")
        world.drain_player(p, "mana")
        self.assertLess(p.stat("intelligence"), before,
                        "and your wits when there is no magic left")

    def test_resistances_stack_against_breath(self):
        world = World(seed=5)
        p = world.add_player("Warded")
        p.spells.add("Ward Fire")
        p.max_mana = 99
        self.assertEqual(world.resisted(p, "fire", 100), 100)
        for expect in (50, 25):
            p.mana = 99
            world.submit(p, {"a": "cast", "spell": "Ward Fire",
                             "x": p.x, "y": p.y})
            self.assertEqual(world.resisted(p, "fire", 100), expect)
        self.assertEqual(world.resisted(p, "cold", 100), 100,
                         "warding fire does nothing about cold")


class TestReachAndUpkeep(unittest.TestCase):
    def test_only_worn_things_and_the_belt_can_be_activated(self):
        from stormhold.game.items import Item
        world = World(seed=13)
        p = world.add_player("Belted")
        pot = Item("potion_heal")
        p.inventory.append(pot)
        p.hp = 1
        world.submit(p, {"a": "use", "id": pot.id})
        self.assertEqual(p.hp, 1, "a potion in the pack cannot be reached")
        belt = Item("belt")
        p.equipment["waist"] = belt
        p.inventory.remove(pot)
        belt.contents.append(pot)
        world.submit(p, {"a": "use", "id": pot.id})
        self.assertGreater(p.hp, 1, "on the belt it is to hand")

    def test_belts_hold_a_fixed_number_of_things(self):
        from stormhold.game.items import Item
        p = Player("B", {"strength": 12, "dexterity": 10,
                         "intelligence": 10, "constitution": 10})
        belt = Item("belt")
        p.equipment["waist"] = belt
        self.assertTrue(p.belt_has_room())
        for _ in range(belt.base["belt_slots"]):
            belt.contents.append(Item("potion_heal"))
        self.assertFalse(p.belt_has_room(), "two slots means two things")
        self.assertEqual(Item("beltutil").base["belt_slots"], 10)

    def test_levelling_fills_your_mana(self):
        p = Player("Caster", {"strength": 10, "dexterity": 10,
                              "intelligence": 14, "constitution": 10})
        p.mana = 0
        p.add_xp(10_000)
        self.assertEqual(p.mana, p.max_mana,
                         "mana is restored on gaining a level, not topped up")

    def test_a_spell_gets_cheaper_as_you_outgrow_it(self):
        from stormhold.common.constants import mana_cost
        self.assertEqual(mana_cost(6, 1, 1), 6)
        self.assertLess(mana_cost(6, 10, 1), 6)
        self.assertGreater(mana_cost(6, 5, 15), 6,
                           "reaching beyond your level costs extra")

    def test_the_junk_store_pays_a_flat_pittance(self):
        from stormhold.game.items import Item
        world = World(seed=12)
        rich = Item("platemail")
        self.assertEqual(world.junk_price(rich), world.JUNK_FLAT)
        cursed = Item("leather")
        cursed.cursed = True
        self.assertEqual(world.junk_price(cursed), world.JUNK_FLAT)

    def test_remove_curse_is_always_offered(self):
        """Greying it out would leak whether your gear is cursed."""
        world = World(seed=3)
        p = world.add_player("Clean")
        services = {s["key"]: s for s in world.temple_services(p)}
        self.assertTrue(services["uncurse"]["useful"])

    def test_wielding_identifies(self):
        from stormhold.game.items import Item
        world = World(seed=11)
        p = world.add_player("Wielder")
        it = Item("leather")
        it.known = False
        it.enchant = 2
        p.inventory.append(it)
        world.submit(p, {"a": "equip", "id": it.id})
        self.assertTrue(it.known, "you learn what it is by putting it on")


class TestSitesAndThieves(unittest.TestCase):
    def test_a_thief_takes_coin_and_leaves(self):
        import random as _r
        from stormhold.game.actors import make_monster
        from stormhold.game import combat
        world = World(seed=22)
        p = world.add_player("Mark")
        level = world.levels[p.depth]
        spot = level.find_free(p.x, p.y, max_r=4)
        thief = make_monster("cutpurse", spot[0], spot[1], 1, _r.Random(5))
        level.place(thief)
        before, where = p.copper, (thief.x, thief.y)
        for _ in range(12):
            combat.melee(world, thief, p)
            if p.copper < before:
                break
        self.assertLess(p.copper, before, "it goes for the purse")
        self.assertNotEqual((thief.x, thief.y), where, "and then it is gone")

    def test_banked_money_cannot_be_stolen(self):
        """Half the reason the bank exists."""
        import random as _r
        from stormhold.game.actors import make_monster
        from stormhold.game import combat
        world = World(seed=22)
        p = world.add_player("Prudent")
        level = world.levels[p.depth]
        p.bank = 5000
        spot = level.find_free(p.x, p.y, max_r=4)
        thief = make_monster("cutpurse", spot[0], spot[1], 1, _r.Random(5))
        level.place(thief)
        for _ in range(12):
            combat.melee(world, thief, p)
        self.assertEqual(p.bank, 5000, "the strongroom is out of its reach")

    def test_fountains_and_thrones_can_help_or_harm(self):
        from stormhold.common.constants import T
        world = World(seed=31)
        p = world.add_player("Sipper")
        level = world.levels[p.depth]
        level.set(p.x, p.y, T.FOUNTAIN)
        outcomes = set()
        for _ in range(60):
            p.hp = max(1, p.max_hp // 2)
            p.mana = 0
            world.submit(p, {"a": "fountain"})
            outcomes.add("good" if p.hp > p.max_hp // 2 or p.mana > 0 else "other")
        self.assertEqual(outcomes, {"good", "other"},
                         "a fountain is a gamble, not a free heal")

    def test_reshaping_keeps_how_hurt_it_was(self):
        import random as _r
        from stormhold.game.actors import make_monster
        from stormhold.game.monsters import MONSTERS
        world = World(seed=21)
        p = world.add_player("Mage")
        level = world.levels[p.depth]
        spot = level.find_free(p.x, p.y, max_r=6)
        m = make_monster(sorted(MONSTERS)[0], spot[0], spot[1], 1, _r.Random(3))
        level.place(m)
        m.hp = max(1, m.max_hp // 2)
        share = m.hp / m.max_hp
        fresh = world.transmogrify(level, m)
        self.assertAlmostEqual(fresh.hp / fresh.max_hp, share, delta=0.08)


class TestCasting(unittest.TestCase):
    def test_casting_time_varies_by_what_the_spell_does(self):
        """Attack spells are fast, divination slow - the original's rule."""
        from stormhold.game.spells import SPELLS
        attack = next(v for v in SPELLS.values() if v["school"] == "Attack")
        divine = next(v for v in SPELLS.values() if v["school"] == "Divination")
        self.assertEqual(attack["cast_seconds"], 5)
        self.assertEqual(divine["cast_seconds"], 30)
        self.assertFalse(attack["interruptible"])
        self.assertTrue(divine["interruptible"], "slow spells can be broken off")
        self.assertEqual(SPELLS["Revelation"]["cast_seconds"], 60)

    def test_you_may_overdraw_mana_and_pay_in_blood(self):
        from stormhold.game.spells import SPELLS
        world = World(seed=9)
        p = world.add_player("Mage")
        name = next(n for n, v in SPELLS.items() if v["school"] == "Attack")
        p.spells.add(name)
        p.mana = 0
        hp = p.hp
        shot = {"a": "cast", "spell": name, "x": p.x, "y": p.y}
        world.submit(p, dict(shot))
        self.assertEqual(p.hp, hp, "an unconfirmed overdraw costs nothing")
        world.submit(p, dict(shot, confirm_overdraw=True))
        self.assertEqual(p.hp, hp - SPELLS[name]["mana"],
                         "the shortfall comes out of hit points")


class TestSpellClasses(unittest.TestCase):
    def test_six_classes_and_every_spell_belongs_to_one(self):
        from stormhold.game.spells import SCHOOLS
        self.assertEqual(len(SCHOOLS), 6)
        for name, spell in SPELLS.items():
            self.assertIn(spell["school"], SCHOOLS, name)

    def test_every_class_has_at_least_one_spell(self):
        from stormhold.game.spells import SCHOOLS
        for school in SCHOOLS:
            self.assertTrue(any(s["school"] == school for s in SPELLS.values()),
                            f"{school} has no spells in it")


class TestDrainAndTemple(unittest.TestCase):
    """Draining, and the only thing in the world that undoes it."""

    def test_draining_an_attribute_lowers_what_depends_on_it(self):
        p = Player("Sapped", {"strength": 14, "dexterity": 11,
                              "intelligence": 10, "constitution": 12})
        capacity = p.capacity
        p.drain_stat("strength", 3)
        self.assertEqual(p.stat("strength"), 11)
        self.assertLess(p.capacity, capacity, "drained strength should carry less")
        self.assertTrue(p.is_drained)

    def test_draining_hit_points_lowers_the_maximum(self):
        p = Player("Sapped", {"strength": 10, "dexterity": 10,
                              "intelligence": 10, "constitution": 14})
        before = p.max_hp
        p.drain_hp(8)
        self.assertEqual(p.max_hp, before - 8)
        self.assertLessEqual(p.hp, p.max_hp, "current hp must not exceed a drained maximum")

    def test_drain_never_takes_an_attribute_below_three(self):
        p = Player("Husk", {"strength": 8, "dexterity": 8,
                            "intelligence": 8, "constitution": 8})
        p.drain_stat("strength", 99)
        self.assertGreaterEqual(p.stat("strength"), 3)

    def test_drain_survives_a_save_and_reload(self):
        p = Player("Sapped", {"strength": 14, "dexterity": 11,
                              "intelligence": 10, "constitution": 12})
        p.drain_stat("intelligence", 2)
        p.drain_hp(6)
        data = p.to_save()
        back = Player("Sapped")
        back.load_save(data)
        self.assertEqual(back.drained["intelligence"], 2)
        self.assertEqual(back.drained_hp, 6)

    def test_the_temple_restores_what_was_taken(self):
        world = World(seed=9)
        p = world.add_player("Pilgrim")
        p.drain_stat("strength", 2)
        p.drain_hp(7)
        p.copper = 10000
        before_hp, before_str = p.max_hp, p.stat("strength")

        world.buy_service(p, "restore_strength")
        self.assertGreater(p.stat("strength"), before_str)
        self.assertEqual(p.copper, 7000)

        world.buy_service(p, "restore_hp")
        self.assertGreater(p.max_hp, before_hp)
        self.assertFalse(p.is_drained)

    def test_you_cannot_buy_what_you_cannot_afford(self):
        world = World(seed=9)
        p = world.add_player("Pauper")
        p.drain_stat("dexterity", 1)
        p.copper = 10
        world.buy_service(p, "restore_dexterity")
        self.assertEqual(p.copper, 10, "was charged despite being unable to pay")
        self.assertTrue(p.is_drained, "was restored without paying")

    def test_the_temple_only_offers_what_is_useful(self):
        world = World(seed=9)
        p = world.add_player("Hale")
        p.copper = 99999
        useful = {s["key"] for s in world.temple_services(p) if s["useful"]}
        self.assertNotIn("restore_strength", useful, "offered to fix an undrained stat")
        self.assertNotIn("heal_full", useful, "offered to heal an unwounded character")

        p.drain_stat("strength", 1)
        p.hp = 1
        useful = {s["key"] for s in world.temple_services(p) if s["useful"]}
        self.assertIn("restore_strength", useful)
        self.assertIn("heal_full", useful)

    def test_healing_tiers_restore_different_amounts(self):
        world = World(seed=9)
        p = world.add_player("Hurt")
        p.copper = 99999
        p.add_xp(40000)                 # a big enough pool for the tiers to differ
        self.assertGreater(p.max_hp, 40)

        p.hp = 1
        world.buy_service(p, "heal_minor")
        minor = p.hp
        p.hp = 1
        world.buy_service(p, "heal_major")
        major = p.hp
        p.hp = 1
        world.buy_service(p, "heal_full")

        self.assertGreater(major, minor, "a major heal should beat a minor one")
        self.assertGreater(p.hp, major, "a full heal should beat a major one")
        self.assertEqual(p.hp, p.max_hp)


class TestEconomy(unittest.TestCase):
    def test_an_early_find_is_worth_a_few_hundred_copper(self):
        rng = random.Random(4)
        haul = [generate_gold(1, rng) for _ in range(400)]
        mean = sum(haul) / len(haul)
        self.assertGreater(mean, 250, "early copper finds are too small to matter")
        self.assertLess(mean, 900, "early copper finds are absurdly large")

    def test_copper_still_weighs_enough_to_matter(self):
        p = Player("Hauler", {"strength": 12, "dexterity": 10,
                              "intelligence": 10, "constitution": 10})
        light = p.move_speed_percent()
        p.copper = 40000
        self.assertLess(p.move_speed_percent(), light,
                        "a fortune in copper should still slow you down")

    def test_temple_prices_are_reachable_but_not_trivial(self):
        rng = random.Random(11)
        typical = sum(generate_gold(6, rng) for _ in range(8)) / 8
        self.assertLess(typical, 3000, "a single find should not cover a restoration")
        self.assertGreater(typical * 12, 3000, "restoration should be reachable at depth")


class TestBlowMessages(unittest.TestCase):
    """The original builds a sentence per blow and never prints a number.

    The reference calls this "the single most copyable thing in the game for
    feel, and it costs nothing but a message table", so it is worth holding
    to: the right verb for the weapon, a place on the body, an escalation
    with the size of the wound, and a shield block of its own.
    """

    def setUp(self):
        import random
        from stormhold.game.actors import Player, make_monster
        self.rng = random.Random(4)
        self.p = Player("Striker", {"strength": 14, "dexterity": 12,
                                    "intelligence": 10, "constitution": 11})
        self.m = make_monster("kobold", 0, 0, 1, self.rng)

    def graze(self):
        return max(1, int(self.m.max_hp * 0.05))

    def glancing(self):
        return max(2, int(self.m.max_hp * 0.15))

    def blows(self, key, dmg=6, killed=False, n=40):
        from stormhold.game.combat import blow_message
        from stormhold.game.items import Item
        self.p.equipment["weapon"] = Item(key) if key else None
        return {blow_message(self.rng, self.p, self.m, dmg, killed)
                for _ in range(n)}

    def test_the_verb_follows_the_weapon(self):
        self.assertTrue(any("slash" in t for t in self.blows("shortsword", self.graze())))
        self.assertTrue(any("chop" in t for t in self.blows("axe", self.graze())))
        self.assertTrue(any("crush" in t or "smash" in t or "clip" in t
                            for t in self.blows("mace", self.graze())))
        self.assertTrue(any("stab" in t or "point" in t or "prick" in t
                            for t in self.blows("dagger", self.graze())))

    def test_a_blow_can_land_somewhere(self):
        places = ("arm", "chest", "head", "leg", "flank")
        texts = self.blows("shortsword", self.glancing())
        self.assertTrue(any(any(p in t for p in places) for t in texts))

    def test_a_worse_wound_reads_worse(self):
        from stormhold.game.combat import blow_message
        from stormhold.game.items import Item
        self.p.equipment["weapon"] = Item("mace")
        graze = blow_message(self.rng, self.p, self.m, 1, False)
        mortal = blow_message(self.rng, self.p, self.m, self.m.max_hp, False)
        self.assertNotEqual(graze, mortal)
        self.assertIn("crushing", mortal)

    def test_no_damage_number_appears_in_the_sentence(self):
        from stormhold.game.combat import blow_message, miss_message
        for dmg in (1, 5, 17, 99):
            text = blow_message(self.rng, self.p, self.m, dmg, False)
            self.assertNotIn(str(dmg), text, text)
        self.assertNotIn("0", miss_message(self.rng, self.p, self.m))

    def test_a_kill_gets_its_own_line(self):
        ordinary = self.blows("shortsword", 6, killed=False)
        final = self.blows("shortsword", 6, killed=True)
        self.assertFalse(ordinary & final, "a kill must not read like a hit")

    def test_the_shield_block_is_its_own_message(self):
        from stormhold.game.combat import blow_message
        from stormhold.game.items import Item
        self.p.equipment["shield"] = Item("buckler")
        text = blow_message(self.rng, self.m, self.p, 0, False, blocked=True)
        self.assertIn("shield", text)
        self.assertIn("your", text, "it is your shield, not you's")

    def test_your_blows_read_in_the_second_person_and_theirs_do_not(self):
        from stormhold.game.combat import blow_message
        from stormhold.game.items import Item
        self.p.equipment["weapon"] = Item("shortsword")
        yours = blow_message(self.rng, self.p, self.m, 5, False)
        theirs = blow_message(self.rng, self.m, self.p, 5, False)
        self.assertTrue(yours.startswith("You "), yours)
        self.assertTrue(theirs.startswith("The Kobold "), theirs)
        for text in (yours, theirs):
            self.assertNotIn("{", text, "an unsubstituted token escaped")


class TestSortPack(unittest.TestCase):
    """"Sort Pack sorts by type, and within type, unknowns last."""

    def setUp(self):
        from stormhold.game.world import World
        from stormhold.game.items import Item
        self.world = World(seed=12)
        self.p = self.world.add_player("Tidy")
        self.p.inventory = []
        for key, known in (("scroll_map", False), ("potion_mana", False),
                           ("axe", False), ("potion_heal", True),
                           ("leather", True), ("shortsword", True)):
            item = Item(key)
            item.known = known
            self.p.add_item(item)
        self.world.appearances.identify("potion_heal")
        self.p.sort_pack(self.world.appearances)
        self.kinds = [i.base.get("kind") or i.slot for i in self.p.inventory]

    def test_weapons_come_before_armour_before_potions_before_scrolls(self):
        self.assertEqual(self.kinds[:2], ["weapon", "weapon"])
        self.assertEqual(self.kinds[2], "torso")
        self.assertEqual(self.kinds[-1], "scroll")

    def test_within_a_type_the_unidentified_fall_to_the_end(self):
        potions = [i for i in self.p.inventory if i.base.get("kind") == "potion"]
        self.assertTrue(self.world.appearances.is_known(potions[0].key))
        self.assertFalse(self.world.appearances.is_known(potions[-1].key))


class TestArticles(unittest.TestCase):
    """Small words, but they are in every line of the log."""

    def names(self, *pairs):
        from stormhold.game.items import Item, with_article
        return [with_article(Item(k).name(None)) for k in pairs]

    def test_singular_things_get_one(self):
        a, b = self.names("dagger", "axe")
        self.assertTrue(a.startswith("a "), a)
        self.assertTrue(b.startswith("a "), b)

    def test_plural_things_do_not(self):
        for text in self.names("bracers", "gauntlets", "boots", "leggings"):
            self.assertFalse(text.startswith(("a ", "an ")), text)

    def test_a_counted_stack_does_not(self):
        from stormhold.game.items import Item, with_article
        text = with_article(Item("arrow", qty=12).name(None))
        self.assertTrue(text.startswith("12 "), text)


class TestTheKeepCanBeFinished(unittest.TestCase):
    """Every floor generates, both bosses are placed, and the last one wins it.

    Nothing tested that the game had an ending - only that its parts worked.
    """

    def setUp(self):
        from stormhold.game.world import World
        from stormhold.game.items import Item
        self.world = World(seed=31)
        self.p = self.world.add_player("Champion", spell="Spark")
        self.p.stats = {k: 18 for k in self.p.stats}
        self.p.level = 25
        self.p.recalc()
        self.p.max_hp = self.p.hp = 6000
        for key, slot in (("platemail", "torso"), ("halberd", "weapon")):
            item = Item(key, enchant=5)
            item.known = True
            self.p.equipment[slot] = item

    def test_every_floor_generates_with_a_way_down(self):
        for depth in range(1, 26):
            with self.subTest(depth=depth):
                level = self.world.get_level(depth)
                self.assertTrue(level.w and level.h)
                self.assertTrue(level.spawns, "a floor with nothing living on it")
                if depth < 25:
                    self.assertIsNotNone(level.down_at, "no way down")

    def test_both_bosses_are_placed(self):
        self.assertEqual(self.world.get_level(12).boss_key, "warden_of_ash")
        self.assertEqual(self.world.get_level(25).boss_key, "vaelrik")

    def test_killing_the_last_one_wins_the_game(self):
        from stormhold.game import combat
        level = self.world.get_level(25)
        self.world.move_player_to(self.p, 25)
        self.world.populate(level)
        boss = level.boss
        self.assertIsNotNone(boss)
        self.world.events.clear()
        for _ in range(5000):
            if boss.dead:
                break
            combat.melee(self.world, self.p, boss)
        self.assertTrue(boss.dead, "the final boss could not be killed")
        self.assertTrue(getattr(self.p, "won", False))
        said = [e.get("text") for e in self.world.events if e.get("t") == "msg"]
        self.assertIn("The storm over Aldershade breaks. The keep is yours.", said)

    def test_a_boss_is_named_not_described(self):
        from stormhold.game import combat
        level = self.world.get_level(25)
        self.world.move_player_to(self.p, 25)
        self.world.populate(level)
        text = combat.blow_message(self.world.rng, self.p, level.boss, 5, False)
        self.assertNotIn("the Vaelrik", text)
        self.assertIn("Vaelrik", text)

    def test_the_blow_is_narrated_before_the_death_it_causes(self):
        from stormhold.game import combat
        level = self.world.get_level(25)
        self.world.move_player_to(self.p, 25)
        self.world.populate(level)
        boss = level.boss
        boss.hp = 1
        self.world.events.clear()
        combat.melee(self.world, self.p, boss)
        said = [e.get("text") for e in self.world.events if e.get("t") == "msg"]
        falls = said.index("Vaelrik, the Storm-Bound falls!")
        self.assertGreater(falls, 0, "the killing blow was never described")


class TestDoorsExist(unittest.TestCase):
    """The keep had no doors at all - on any floor, on any seed.

    _add_doors places a door where a floor square has wall on both sides, and
    it ran before the pass that builds the walls, so it never found one. The
    Open and Close verbs, the blocked-door message and the door-opening
    behaviour in the monster AI were all dead code.
    """

    def levels(self, seeds=(1, 2, 3), depths=(1, 5, 12, 20)):
        from stormhold.game.level import generate_dungeon
        for seed in seeds:
            for depth in depths:
                yield seed, depth, generate_dungeon(depth, seed)

    def test_every_floor_has_doors(self):
        for seed, depth, level in self.levels():
            with self.subTest(seed=seed, depth=depth):
                doors = sum(1 for t in level.tiles if t == T.DOOR)
                self.assertGreater(doors, 0, "a floor with no doors")

    def test_doors_never_wall_off_the_stairs(self):
        """A closed door is a step, not a wall, and the sealing pass must
        agree - it used to wall off everything behind the first door."""
        from stormhold.game.level import reachable
        for seed, depth, level in self.levels(depths=(1, 3, 7, 11, 17, 24)):
            with self.subTest(seed=seed, depth=depth):
                reach = reachable(level, *level.up_at)
                self.assertIn(level.idx(*level.down_at), reach)
                self.assertGreater(len(reach), 200,
                                   "most of the floor has been sealed off")

    def test_walking_into_a_closed_door_opens_it(self):
        from stormhold.game.world import World
        world = World(seed=1)
        p = world.add_player("Opener", spell="Spark")
        world.move_player_to(p, 1)
        level = world.levels[1]
        spot = next((i, j) for j in range(level.h) for i in range(level.w)
                    if level.get(i, j) == T.DOOR)
        beside = next((spot[0] + dx, spot[1] + dy)
                      for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))
                      if level.passable(spot[0] + dx, spot[1] + dy))
        level.move_actor(p, *beside)
        world.events.clear()
        world.do_player_action(level, p, {"a": "move",
                                          "dx": spot[0] - p.x,
                                          "dy": spot[1] - p.y})
        self.assertEqual(level.get(*spot), T.DOOR_OPEN)
        said = [e["text"] for e in world.events if e["t"] == "msg"]
        self.assertIn("You open the door.", said)

    def test_a_closed_door_blocks_the_view(self):
        """Which is what makes them worth having: a room is a sealed box
        until you open it."""
        from stormhold.common.constants import OPAQUE
        self.assertIn(T.DOOR, OPAQUE)
        self.assertNotIn(T.DOOR_OPEN, OPAQUE)


class TestNobodyIsCalledIt(unittest.TestCase):
    """Pronouns in the lines that describe your own death.

    A bot's log read "The Goblin beats you down, and it does not get up",
    and "You pick up an a pale gold potion".
    """

    def setUp(self):
        import random
        from stormhold.game.actors import Player, make_monster
        self.rng = random.Random(3)
        self.p = Player("Subject", {"strength": 12, "dexterity": 12,
                                    "intelligence": 10, "constitution": 10})
        self.m = make_monster("goblin", 0, 0, 2, self.rng)

    def every_line(self, n=250):
        from stormhold.game.combat import blow_message, miss_message
        from stormhold.game.items import Item
        lines = set()
        for _ in range(n):
            for key in (None, "dagger", "longbow", "mace", "axe", "shortsword"):
                self.p.equipment["weapon"] = Item(key) if key else None
                for dmg, killed in ((1, False), (8, False), (99, True)):
                    lines.add(blow_message(self.rng, self.p, self.m, dmg, killed))
                    lines.add(blow_message(self.rng, self.m, self.p, dmg, killed))
                lines.add(miss_message(self.rng, self.m, self.p))
                lines.add(miss_message(self.rng, self.p, self.m))
        return lines

    def test_a_line_about_you_never_calls_you_it(self):
        for line in self.every_line():
            if line.startswith("The Goblin") and " you" in line:
                self.assertNotIn(" it ", line, line)

    def test_the_verbs_agree_with_whoever_they_are_about(self):
        for line in self.every_line():
            for wrong in ("you does", "it do not", "dos ", "you dances",
                          "it dance ", "you folds", "you stands"):
                self.assertNotIn(wrong, line, line)

    def test_nothing_is_left_unsubstituted(self):
        for line in self.every_line():
            self.assertNotIn("{", line, line)

    def test_a_name_that_already_has_an_article_does_not_get_another(self):
        from stormhold.game.items import with_article
        for name in ("a pale gold potion", "an oily black scroll", "the Rune"):
            self.assertEqual(with_article(name), name)


class TestTheTwoMissingTraps(unittest.TestCase):
    """The original's list has fourteen; we had twelve.

    "a trap door" drops you a level rather than hurting you, and "an
    animation trap" raises the dead. Both are in the reference's trap list
    and neither existed.
    """

    def setUp(self):
        from stormhold.game.world import World
        self.world = World(seed=5)
        self.p = self.world.add_player("Unlucky", spell="Spark")
        self.world.move_player_to(self.p, 8)
        self.level = self.world.levels[8]

    def spring(self, kind):
        self.level.traps[(self.p.x, self.p.y)] = {"kind": kind, "found": False,
                                                  "armed": True}
        self.world.events.clear()
        self.world.spring_trap(self.level, self.p)
        return [e["text"] for e in self.world.events if e["t"] == "msg"]

    def test_both_are_in_the_table(self):
        from stormhold.game.traps import TRAPS
        names = {t["name"] for t in TRAPS.values()}
        self.assertIn("trap door", names)
        self.assertIn("animation trap", names)

    def test_a_trap_door_drops_you_a_floor_and_does_no_damage(self):
        hp = self.p.hp
        said = self.spring("trapdoor")
        self.assertEqual(self.p.depth, 9)
        self.assertEqual(self.p.hp, hp, "a trap door is not supposed to hurt")
        self.assertTrue(any("floor further down" in m for m in said), said)

    def test_an_animation_trap_raises_things(self):
        before = sum(1 for a in self.level.actors.values()
                     if getattr(a, "kind", None) == "monster")
        said = self.spring("animate")
        after = sum(1 for a in self.level.actors.values()
                    if getattr(a, "kind", None) == "monster")
        self.assertGreater(after, before, said)

    def test_levitation_carries_you_over_anything_that_works_by_falling(self):
        """"Levitation ... will prevent you from falling into pits and trap
        doors."""
        from stormhold.game.items import Item
        for kind in ("pit", "trapdoor", "deadfall"):
            with self.subTest(trap=kind):
                self.world.move_player_to(self.p, 8)
                self.level = self.world.levels[8]
                self.p.add_effect("levitating", self.level.clock + 10 ** 6)
                hp, depth = self.p.hp, self.p.depth
                said = self.spring(kind)
                self.assertEqual(self.p.hp, hp)
                self.assertEqual(self.p.depth, depth)
                self.assertTrue(any("drift" in m for m in said), said)

    def test_a_potion_of_levitation_exists_and_does_it(self):
        from stormhold.game.items import Item, BASES
        self.assertIn("potion_float", BASES)
        belt = Item("belt3")
        belt.known = True
        self.p.equipment["waist"] = belt
        potion = Item("potion_float")
        potion.known = True
        belt.contents.append(potion)
        self.world.events.clear()
        self.world.do_player_action(self.level, self.p,
                                    {"a": "use", "id": potion.id})
        self.assertTrue(self.p.has("levitating"),
                        [e.get("text") for e in self.world.events])


class TestTheMonsterBehavioursWeLacked(unittest.TestCase):
    """Four of the original's creature habits that the audit had as open.

    We keep our own bestiary, so these are attached to our creatures: what is
    being reproduced is the behaviour, not the beast.
    """

    def setUp(self):
        from stormhold.game.world import World
        self.world = World(seed=9)
        self.p = self.world.add_player("Quarry", spell="Spark")
        self.world.move_player_to(self.p, 14)
        self.level = self.world.levels[14]

    def test_something_can_pass_through_rock(self):
        from stormhold.game import ai
        wall = next((i, j) for j in range(self.level.h)
                    for i in range(self.level.w)
                    if self.level.get(i, j) == T.WALL)
        through = ai.find_path(self.level, wall[0], wall[1], self.p.x, self.p.y,
                               through_rock=True)
        self.assertTrue(through, "nothing can path out of solid stone")
        golem = self.world.spawn("stone_golem", self.p.x, self.p.y, 14)
        self.assertTrue(golem.tpl.get("through_rock"))

    def test_something_breaks_doors_rather_than_opening_them(self):
        from stormhold.game import ai
        from stormhold.game.monsters import MONSTERS
        breakers = [k for k, t in MONSTERS.items() if t.get("breaks_doors")]
        self.assertTrue(breakers, "nothing in the keep breaks a door")
        golem = self.world.spawn(breakers[0], self.p.x + 2, self.p.y, 14)
        self.level.place(golem)
        spot = (self.p.x + 1, self.p.y)
        self.level.set(spot[0], spot[1], T.DOOR)
        golem.target_id = self.p.id
        golem.path = [spot]
        golem.path_goal = (self.p.x, self.p.y)   # so the prepared step is used
        self.world.events.clear()
        # The door is the next square on its way to us, which is the case
        # that matters; take_turn would re-path through the rock instead.
        ai._step_toward(self.world, self.level, golem, self.p.x, self.p.y)
        said = [e["text"] for e in self.world.events if e["t"] == "msg"]
        self.assertEqual(self.level.get(*spot), T.DOOR_OPEN)
        self.assertTrue(any("blasts open the door" in m for m in said), said)

    def test_something_taunts_you_while_it_fights(self):
        from stormhold.game import ai
        from stormhold.game.monsters import MONSTERS
        talkers = [k for k, t in MONSTERS.items() if t.get("taunts")]
        self.assertTrue(talkers, "nothing in the keep says anything")
        thief = self.world.spawn(talkers[0], self.p.x + 1, self.p.y, 14)
        self.level.place(thief)
        thief.target_id = self.p.id
        heard = []
        for _ in range(200):
            self.world.events.clear()
            ai.take_turn(self.world, self.level, thief)
            heard += [e["text"] for e in self.world.events
                      if e["t"] == "msg" and "says:" in e["text"]]
            self.p.hp = self.p.max_hp
            if heard:
                break
        self.assertTrue(heard, "it never said a word in two hundred blows")

    def test_a_slow_poison_takes_hold_later(self):
        from stormhold.game import combat
        from stormhold.game.monsters import MONSTERS
        slow = [k for k, t in MONSTERS.items() if t.get("poison_delay")]
        self.assertTrue(slow, "no creature has a slow poison")
        ghoul = self.world.spawn(slow[0], self.p.x + 1, self.p.y, 14)
        self.level.place(ghoul)
        self.p.max_hp = self.p.hp = 5000
        for _ in range(200):
            combat.melee(self.world, ghoul, self.p)
            if self.p.has("poison_later"):
                break
        self.assertTrue(self.p.has("poison_later"), "the bite never told")
        self.assertFalse(self.p.has("poisoned"), "it took hold at once")

        # ...and then it does.
        self.level.clock += 10 ** 6
        self.world.events.clear()
        self.world.after_action(self.level, self.p)
        self.assertTrue(self.p.has("poisoned"))
        said = [e["text"] for e in self.world.events if e["t"] == "msg"]
        self.assertTrue(any("taken hold" in m for m in said), said)

    def test_a_tribe_can_hire_something_worse(self):
        from stormhold.game.monsters import MONSTERS
        employers = [k for k, t in MONSTERS.items() if t.get("hires")]
        self.assertTrue(employers, "no tribe hires anybody")
        for key in employers:
            self.assertIn(MONSTERS[key]["hires"], MONSTERS,
                          "hired something that does not exist")


class TestNamingYourself(unittest.TestCase):
    """"You may rename your character during the game, adding such
    descriptions as you feel you deserve (the bold, the mighty)."

    The character sheet had a box that looked like a text field and was a
    drawn rectangle.
    """

    def setUp(self):
        from stormhold.game.world import World
        self.world = World(seed=3)
        self.p = self.world.add_player("Hild", spell="Spark")
        self.level = self.world.levels[0]

    def rename(self, name):
        self.world.events.clear()
        self.world.do_player_action(self.level, self.p,
                                    {"a": "callme", "name": name})
        return [e["text"] for e in self.world.events if e["t"] == "msg"]

    def test_you_can_add_a_description_to_your_name(self):
        said = self.rename("Hild the Bold")
        self.assertEqual(self.p.name, "Hild the Bold")
        self.assertTrue(any("known as Hild the Bold" in m for m in said), said)

    def test_it_tells_the_rest_of_the_party(self):
        self.world.events.clear()
        self.world.do_player_action(self.level, self.p,
                                    {"a": "callme", "name": "Hild the Bold"})
        told = [e for e in self.world.events
                if e["t"] == "msg" and e.get("depth") is not None]
        self.assertTrue(told, "nobody else was told")

    def test_you_cannot_take_a_name_somebody_else_is_using(self):
        other = self.world.add_player("Bjorn", spell="Spark")
        said = self.rename("Bjorn")
        self.assertEqual(self.p.name, "Hild")
        self.assertTrue(any("already called" in m for m in said), said)

    def test_an_empty_name_changes_nothing(self):
        self.rename("   ")
        self.assertEqual(self.p.name, "Hild")


class TestQualityPrefixes(unittest.TestCase):
    """"Broken, Ripped, Rusty, Normal, Enchanted, Cursed" - we had three."""

    def named(self, key, enchant=0, cursed=False, known=True):
        from stormhold.game.items import Item
        item = Item(key, enchant=enchant, cursed=cursed)
        item.known = known
        return item.name(None)

    def test_plain_gear_is_normal(self):
        self.assertTrue(self.named("dagger").startswith("Normal"))

    def test_a_battered_thing_is_named_for_what_it_is_made_of(self):
        self.assertTrue(self.named("leather", -2).startswith("Ripped"))
        self.assertTrue(self.named("chainmail", -1).startswith("Rusty"))
        self.assertTrue(self.named("shortbow", -1).startswith("Broken"))
        self.assertTrue(self.named("dagger", -1).startswith("Rusty"))

    def test_a_good_thing_keeps_its_plus(self):
        self.assertTrue(self.named("dagger", 2).startswith("+2"))

    def test_a_cursed_thing_says_so(self):
        self.assertTrue(self.named("leather", -1, cursed=True).startswith("Cursed"))

    def test_before_you_know_it_it_is_only_enchanted_or_normal(self):
        self.assertTrue(self.named("dagger", 2, known=False).startswith("Enchanted"))
        self.assertTrue(self.named("dagger", -2, known=False).startswith("Enchanted"))
        self.assertTrue(self.named("dagger", 0, known=False).startswith("Normal"))


class TestTwoHandedWeapons(unittest.TestCase):
    """"Two-handed weapons conflict with shields, and the game says so rather
    than silently refusing." We had no two-handed weapons at all.
    """

    def player(self, pack=True):
        from stormhold.game.actors import Player
        from stormhold.game.items import Item
        p = Player("Wielder", {"strength": 16, "dexterity": 12,
                               "intelligence": 10, "constitution": 12})
        if pack:
            p.equipment["pack"] = Item("pack")
        return p

    def thing(self, key, cursed=False):
        from stormhold.game.items import Item
        item = Item(key, cursed=cursed)
        item.known = True
        return item

    def test_some_weapons_are_two_handed(self):
        from stormhold.game.items import BASES
        two = [k for k, b in BASES.items() if b.get("two_handed")]
        self.assertTrue(two, "nothing needs both hands")

    def test_taking_one_up_puts_the_shield_away(self):
        p = self.player()
        shield = self.thing("shield")
        p.equipment["shield"] = shield
        halberd = self.thing("halberd")
        p.add_item(halberd)
        ok, said = p.equip(halberd)
        self.assertTrue(ok, said)
        self.assertIsNone(p.equipment["shield"])
        self.assertIn(shield, p.inventory)
        self.assertIn("both hands", said)

    def test_you_cannot_raise_a_shield_while_holding_one(self):
        p = self.player()
        halberd = self.thing("halberd")
        p.equipment["weapon"] = halberd
        shield = self.thing("shield")
        p.add_item(shield)
        ok, said = p.equip(shield)
        self.assertFalse(ok)
        self.assertIn("Can't use both", said)
        self.assertIsNone(p.equipment["shield"])

    def test_with_nowhere_to_put_the_shield_it_is_refused_and_says_why(self):
        p = self.player(pack=False)
        shield = self.thing("towershield")
        p.equipment["shield"] = shield
        halberd = self.thing("halberd")
        ok, said = p.equip(halberd)
        self.assertFalse(ok)
        self.assertIn("Can't use both", said)
        self.assertIs(p.equipment["shield"], shield, "it lost the shield anyway")
        self.assertIsNone(p.equipment.get("weapon"), "it took the weapon anyway")

    def test_a_cursed_shield_cannot_be_let_go_of(self):
        p = self.player()
        shield = self.thing("shield", cursed=True)
        p.equipment["shield"] = shield
        halberd = self.thing("halberd")
        p.add_item(halberd)
        ok, said = p.equip(halberd)
        self.assertFalse(ok)
        self.assertIn("cannot let go", said)


class TestThingsCanActuallyBeUsed(unittest.TestCase):
    """The belt was unreachable, so nothing consumable could ever be used.

    "Objects in your pack cannot be activated" was enforced, and nothing in
    the game ever put anything on a belt - so every potion, scroll and wand
    answered "That is buried in your pack" for the whole game. `belt_has_room`
    was dead code and belt contents were always empty.
    """

    def setUp(self):
        from stormhold.game.world import World
        from stormhold.game.items import Item
        self.world = World(seed=3)
        self.p = self.world.add_player("Drinker", spell="Spark")
        self.level = self.world.levels[0]
        belt = Item("belt3")
        belt.known = True
        self.p.equipment["waist"] = belt
        self.belt = belt
        self.potion = Item("potion_heal")
        self.potion.known = True
        self.p.add_item(self.potion)

    def act(self, action):
        self.world.events.clear()
        self.world.do_player_action(self.level, self.p, action)
        return [e["text"] for e in self.world.events if e["t"] == "msg"]

    def test_a_potion_in_the_pack_cannot_be_drunk(self):
        said = self.act({"a": "use", "id": self.potion.id})
        self.assertTrue(any("buried in your pack" in m for m in said), said)

    def test_you_can_put_it_on_your_belt(self):
        said = self.act({"a": "stow", "id": self.potion.id, "slot": "waist"})
        self.assertIn(self.potion, self.belt.contents)
        self.assertNotIn(self.potion, self.p.inventory)
        self.assertTrue(any("on your" in m for m in said), said)

    def test_and_then_it_can_be_drunk(self):
        self.p.hp = 1
        self.act({"a": "stow", "id": self.potion.id, "slot": "waist"})
        said = self.act({"a": "use", "id": self.potion.id})
        self.assertGreater(self.p.hp, 1, said)

    def test_and_then_it_is_gone(self):
        self.p.hp = 1
        self.act({"a": "stow", "id": self.potion.id, "slot": "waist"})
        self.act({"a": "use", "id": self.potion.id})
        self.assertNotIn(self.potion, self.belt.contents,
                         "the potion survived being drunk")
        self.assertNotIn(self.potion, self.p.inventory)

    def test_a_belt_holds_only_as_many_things_as_it_has_slots(self):
        from stormhold.game.items import Item
        extras = []
        for _ in range(5):
            item = Item("potion_mana")
            item.known = True
            self.p.add_item(item)
            extras.append(item)
        for item in [self.potion] + extras:
            self.act({"a": "stow", "id": item.id, "slot": "waist"})
        self.assertEqual(len(self.belt.contents),
                         self.belt.base["belt_slots"])

    def test_you_can_take_it_back_off(self):
        self.act({"a": "stow", "id": self.potion.id, "slot": "waist"})
        said = self.act({"a": "unstow", "id": self.potion.id})
        self.assertIn(self.potion, self.p.inventory)
        self.assertNotIn(self.potion, self.belt.contents)
        self.assertTrue(any("back in your pack" in m for m in said), said)

    def test_a_wand_quiver_takes_wands_and_nothing_else(self):
        from stormhold.game.items import Item
        quiver = Item("quiver")
        quiver.known = True
        self.p.equipment["quiver"] = quiver
        said = self.act({"a": "stow", "id": self.potion.id, "slot": "quiver"})
        self.assertTrue(any("is for wands" in m for m in said), said)
        wand = Item("wand", charges=3)
        wand.known = True
        self.p.add_item(wand)
        self.act({"a": "stow", "id": wand.id, "slot": "quiver"})
        self.assertIn(wand, quiver.contents)

    def test_a_wand_in_the_quiver_is_within_reach(self):
        from stormhold.game.items import Item
        quiver = Item("quiver")
        quiver.known = True
        self.p.equipment["quiver"] = quiver
        wand = Item("wand", charges=3)
        wand.known = True
        self.p.add_item(wand)
        self.act({"a": "stow", "id": wand.id, "slot": "quiver"})
        self.assertTrue(self.world.within_reach(self.p, wand))

    def test_a_spent_wand_says_it_is_dead(self):
        from stormhold.game.items import Item
        wand = Item("wand", charges=0)
        wand.known = True
        self.assertIn("Dead", wand.name(None))

    def test_a_chest_keeps_its_bulk_whatever_is_in_it(self):
        """"Bags' bulk varies with contents, chests' is fixed."""
        from stormhold.game.items import Item
        chest, sack = Item("chest"), Item("sack")
        empty_chest, empty_sack = chest.bulk, sack.bulk
        for holder in (chest, sack):
            for _ in range(3):
                holder.contents.append(Item("potion_heal"))
        self.assertEqual(chest.bulk, empty_chest, "the chest swelled")
        self.assertGreater(sack.bulk, empty_sack, "the sack did not")


class TestTheTwoMissingDivinations(unittest.TestCase):
    """Clairvoyance and Detect Traps, both open rows in the audit."""

    def setUp(self):
        from stormhold.game.world import World
        self.world = World(seed=5)
        self.p = self.world.add_player("Seer", spell="Spark")
        self.p.level = 12
        self.p.stats = {k: 16 for k in self.p.stats}
        self.p.recalc()
        self.p.mana = self.p.max_mana
        self.p.spells |= {"Clairvoyance", "Detect Traps"}
        self.world.move_player_to(self.p, 6)
        self.level = self.world.levels[6]

    def cast(self, name):
        self.p.mana = self.p.max_mana
        self.world.events.clear()
        self.world.do_player_action(self.level, self.p,
                                    {"a": "cast", "spell": name})
        return [e["text"] for e in self.world.events if e["t"] == "msg"]

    def test_both_are_in_the_book(self):
        from stormhold.game.spells import SPELLS
        for name in ("Clairvoyance", "Detect Traps"):
            self.assertIn(name, SPELLS)
            self.assertEqual(SPELLS[name]["school"], "Divination")

    def test_detect_traps_is_certain_close_by(self):
        """"Detect Traps is certain within ten squares."""
        close = [(xy, t) for xy, t in self.level.traps.items()
                 if max(abs(xy[0] - self.p.x), abs(xy[1] - self.p.y)) <= 10]
        if not close:
            # put one where we can be sure of the answer
            spot = (self.p.x + 2, self.p.y)
            self.level.traps[spot] = {"kind": "pit", "found": False,
                                      "armed": True}
            close = [(spot, self.level.traps[spot])]
        self.cast("Detect Traps")
        for xy, _ in close:
            self.assertTrue(self.level.traps[xy]["found"],
                            f"missed a trap {xy} within ten squares")

    def test_clairvoyance_shows_the_ground_around_you(self):
        memory = self.world.memory_for(self.p, self.level)
        before = sum(1 for b in memory if b)
        self.cast("Clairvoyance")
        after = sum(1 for b in self.world.memory_for(self.p, self.level) if b)
        self.assertGreater(after, before, "it revealed nothing")

    def test_clairvoyance_finds_what_is_hidden_in_it(self):
        """"...and shows secret doors and traps in it."""
        spot = (self.p.x + 1, self.p.y + 1)
        self.level.secrets[spot] = {"found": False}
        self.level.traps[(self.p.x - 1, self.p.y)] = {"kind": "pit",
                                                      "found": False,
                                                      "armed": True}
        self.cast("Clairvoyance")
        self.assertTrue(self.level.secrets[spot]["found"])
        self.assertTrue(self.level.traps[(self.p.x - 1, self.p.y)]["found"])

    def test_clairvoyance_does_not_show_the_whole_floor(self):
        """That is Cartography's job, and it costs more."""
        self.cast("Clairvoyance")
        memory = self.world.memory_for(self.p, self.level)
        floor = sum(1 for t in self.level.tiles if t != T.VOID)
        self.assertLess(sum(1 for b in memory if b), floor)


class TestEveryBlowIsNarrated(unittest.TestCase):
    """Melee read well and nothing else did.

    Arrows, bolts and spells all had their own older messages that printed a
    damage number, so the log switched register the moment you picked up a
    bow or learned a spell.
    """

    def setUp(self):
        from stormhold.game.world import World
        from stormhold.game.spells import SPELLS
        self.world = World(seed=64)
        self.p = self.world.add_player("Shooter", spell="Spark")
        self.p.stats = {k: 18 for k in self.p.stats}
        self.p.level = 20
        self.p.recalc()
        self.p.spells = set(SPELLS)
        self.p.mana = 999
        self.world.move_player_to(self.p, 5)
        self.level = self.world.levels[5]

    def a_target(self, away=1, hp=300):
        spot = self.level.find_free(self.p.x + away, self.p.y, max_r=2,
                                    ignore_id=self.p.id)
        m = self.world.spawn("kobold", spot[0], spot[1], 5)
        m.max_hp = m.hp = hp
        self.level.place(m)
        return m

    def said(self):
        return [e["text"] for e in self.world.events if e["t"] == "msg"]

    def test_your_own_shot_does_not_print_a_number(self):
        from stormhold.game.items import Item
        target = self.a_target()
        bow = Item("longbow")
        bow.known = True
        self.p.equipment["weapon"] = bow
        self.p.add_item(Item("arrow", qty=40))
        for _ in range(12):
            self.world.events.clear()
            self.world.do_player_action(self.level, self.p,
                                        {"a": "shoot", "x": target.x,
                                         "y": target.y})
            for line in self.said():
                self.assertNotRegex(line, r"for \d+\.", line)

    def test_a_creatures_shot_does_not_either(self):
        from stormhold.game import ai
        self.p.max_hp = self.p.hp = 100000
        spot = None
        for d in range(2, 7):
            candidate = (self.p.x + d, self.p.y)
            if (self.level.walkable(*candidate, self.p.id)
                    and all(self.level.passable(self.p.x + i, self.p.y)
                            for i in range(1, d + 1))):
                spot = candidate
        if spot is None:
            self.skipTest("no clear line on this floor")
        archer = self.world.spawn("goblin_archer", spot[0], spot[1], 5)
        self.level.place(archer)
        archer.target_id = self.p.id
        archer.last_seen = (self.p.x, self.p.y)
        for _ in range(20):
            self.world.events.clear()
            ai.take_turn(self.world, self.level, archer)
            for line in self.said():
                self.assertNotRegex(line, r"for \d+\.", line)
            self.p.hp = 100000

    def test_a_spell_says_what_it_did(self):
        target = self.a_target()
        self.world.events.clear()
        self.world.do_player_action(self.level, self.p,
                                    {"a": "cast", "spell": "Fire Bolt",
                                     "x": target.x, "y": target.y,
                                     "confirm_overdraw": True})
        said = self.said()
        self.assertTrue(said)
        self.assertNotIn("You cast Fire Bolt.", said,
                         "it still only names the spell")
        self.assertIn("Kobold", " ".join(said))

    def test_the_words_follow_the_element(self):
        wording = {}
        for spell in ("Fire Bolt", "Frost Shard", "Spark"):
            target = self.a_target(away=1)
            self.world.events.clear()
            self.world.do_player_action(self.level, self.p,
                                        {"a": "cast", "spell": spell,
                                         "x": target.x, "y": target.y,
                                         "confirm_overdraw": True})
            wording[spell] = " ".join(self.said())
            target.hp = 0
            target.dead = True
            self.level.remove(target)
        self.assertRegex(wording["Fire Bolt"], r"scorch|sear|alight|fire")
        self.assertRegex(wording["Frost Shard"], r"chill|rime|freeze|ice")
        self.assertRegex(wording["Spark"], r"spark|jolt|arc|blast")

    def test_a_spell_that_catches_a_crowd_does_not_fill_the_log(self):
        for away in (1, 2, -1, -2):
            self.a_target(away=away, hp=500)
        self.world.events.clear()
        self.world.do_player_action(self.level, self.p,
                                    {"a": "cast", "spell": "Ice Storm",
                                     "confirm_overdraw": True})
        said = self.said()
        self.assertLessEqual(len(said), 4, said)
        if len(said) == 4:
            self.assertIn("other", said[-1])


class TestSitesAndServices(unittest.TestCase):
    """Fountains, thrones, and the temple putting back what was drained.

    All three were built and none had ever been run. Sitting on a throne
    raised a NameError - `STATS` was used in world.py and never imported -
    which in a real game dropped that player from the server without a word.
    """

    def world_at(self, depth=8, seed=13):
        from stormhold.game.world import World
        world = World(seed=seed)
        p = world.add_player("Pilgrim", spell="Spark")
        p.stats = {k: 14 for k in p.stats}
        p.level = 10
        p.recalc()
        p.hp = p.max_hp
        world.move_player_to(p, depth)
        return world, p, world.levels[depth]

    def use(self, site, verb, seed):
        world, p, level = self.world_at(seed=seed)
        level.set(p.x, p.y, site)
        world.events.clear()
        world.do_player_action(level, p, {"a": verb})
        return [e["text"] for e in world.events if e["t"] == "msg"]

    def test_a_throne_never_raises_and_always_says_something(self):
        outcomes = set()
        for seed in range(200, 260):
            said = self.use(T.THRONE, "throne", seed)
            self.assertTrue(said, "sitting on a throne said nothing")
            outcomes.add(said[0])
        self.assertGreater(len(outcomes), 3,
                           "a throne should not always do the same thing")

    def test_a_fountain_never_raises_and_always_says_something(self):
        outcomes = set()
        for seed in range(300, 360):
            said = self.use(T.FOUNTAIN, "fountain", seed)
            self.assertTrue(said, "drinking said nothing")
            outcomes.add(said[0])
        self.assertGreater(len(outcomes), 3,
                           "a fountain should not always do the same thing")

    def test_both_can_help_and_both_can_hurt(self):
        """"Can have beneficial or harmful effects, or may do nothing at
        all", which is the point of them."""
        for site, verb, seeds in ((T.THRONE, "throne", range(200, 280)),
                                  (T.FOUNTAIN, "fountain", range(300, 380))):
            said = " ".join(t for seed in seeds for t in self.use(site, verb, seed))
            with self.subTest(site=verb):
                self.assertRegex(said, r"ebbing away|foul|It comes")
                self.assertRegex(said, r"improves|better|magic returns|compartment")
                self.assertRegex(said, r"[Nn]othing")

    def test_the_temple_gives_back_what_was_drained(self):
        world, p, _level = self.world_at(depth=10)
        for kind in ("body", "mana", "mind", "hp"):
            world.drain_player(p, kind)
        self.assertTrue(any(p.drained.values()) or p.drained_hp,
                        "nothing was drained, so this proves nothing")
        world.move_player_to(p, 0)
        town = world.levels[0]
        p.copper = 99999
        for what in ("restore_strength", "restore_intelligence",
                     "restore_constitution", "restore_dexterity",
                     "restore_hp"):
            world.do_player_action(town, p, {"a": "service", "what": what,
                                             "temple": True})
        self.assertEqual({k: v for k, v in p.drained.items() if v}, {})
        self.assertEqual(p.drained_hp, 0)

    def test_drain_never_raises_for_any_kind_it_is_asked_for(self):
        world, p, _level = self.world_at(depth=10)
        for kind in ("body", "mana", "mind", "hp", "maxhp", "anything else"):
            with self.subTest(kind=kind):
                world.drain_player(p, kind)
