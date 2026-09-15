"""Every spell, every item, every creature - exercised once each.

This file exists because of the throne. `_act_throne` used a name that was
never imported, so about one sitting in six raised a NameError, dropped that
player from the server and told nobody why. Thrones appear in roughly one
room in twenty, so it was waiting in nearly every game - and it survived
because no test, and no amount of playing, had ever happened to sit on one.

A sweep is cheap and it is the only thing that finds content nobody thought
to look at: a spell that heals in silence, a verb that raises, an item that
cannot be reached. It runs everything the game contains, once, and asks the
weakest question that still has teeth - did it run, and did it say anything?
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stormhold.common.constants import T, STATS               # noqa: E402
from stormhold.game import ai                                  # noqa: E402
from stormhold.game.items import BASES, Item                   # noqa: E402
from stormhold.game.monsters import MONSTERS                   # noqa: E402
from stormhold.game.spells import SPELLS                       # noqa: E402
from stormhold.game.traps import TRAPS                          # noqa: E402
from stormhold.game.world import World                          # noqa: E402


def archmage(depth=8, seed=77):
    """Somebody who can cast anything and survive the answer."""
    world = World(seed=seed)
    p = world.add_player("Subject", spell="Spark")
    p.stats = {k: 18 for k in p.stats}
    p.level = 25
    p.recalc()
    p.hp = p.max_hp
    p.spells = set(SPELLS)
    world.move_player_to(p, depth)
    p.mana = p.max_mana
    return world, p, world.levels[depth]


def said(world):
    return [e["text"] for e in world.events if e["t"] == "msg"]


class TestEverySpell(unittest.TestCase):
    def cast(self, name):
        spell = SPELLS[name]
        world, p, level = archmage()
        p.hp = max(1, p.max_hp // 3)          # so healing has work to do
        target = None
        for away in (1, 2, 3):
            spot = level.find_free(p.x + away, p.y, max_r=1, ignore_id=p.id)
            if spot:
                target = world.spawn("kobold", spot[0], spot[1], level.depth)
                target.max_hp = target.hp = 400
                level.place(target)
                break
        junk = Item("potion_heal")
        p.add_item(junk)
        action = {"a": "cast", "spell": name, "confirm_overdraw": True}
        if spell.get("rng", 0) and target is not None:
            action["x"], action["y"] = target.x, target.y
        if spell.get("identify"):
            action["target"] = junk.id
        if spell.get("passwall"):
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if level.get(p.x + dx, p.y + dy) == T.WALL:
                    action["x"], action["y"] = p.x + dx, p.y + dy
                    break
        world.events.clear()
        world.do_player_action(level, p, action)
        return world, p, target

    def test_every_spell_casts_without_raising(self):
        for name in SPELLS:
            with self.subTest(spell=name):
                self.cast(name)

    def test_every_spell_says_something(self):
        """A spell that answers in silence looks exactly like one that
        failed."""
        for name in SPELLS:
            with self.subTest(spell=name):
                world, _p, _target = self.cast(name)
                self.assertTrue(said(world), f"{name} said nothing at all")

    def test_no_spell_leaves_a_token_unsubstituted(self):
        for name in SPELLS:
            with self.subTest(spell=name):
                world, _p, _t = self.cast(name)
                for line in said(world):
                    self.assertNotIn("{", line, f"{name}: {line}")

    def test_every_attack_spell_actually_hurts_something(self):
        for name, spell in SPELLS.items():
            if not spell.get("dmg"):
                continue
            with self.subTest(spell=name):
                _world, _p, target = self.cast(name)
                self.assertIsNotNone(target, "nowhere to put a target")
                self.assertLess(target.hp, 400, f"{name} did no damage")

    def test_every_spell_is_one_a_character_could_reach(self):
        from stormhold.game.spells import can_learn
        for name, spell in SPELLS.items():
            with self.subTest(spell=name):
                ok, why = can_learn(name, 30, 25)
                self.assertTrue(ok, f"{name} can never be learned: {why}")


class TestEveryItem(unittest.TestCase):
    def setUp(self):
        self.world, self.p, self.level = archmage(depth=6, seed=91)
        for key, slot in (("beltutil", "waist"), ("quiver", "quiver")):
            holder = Item(key)
            holder.known = True
            self.p.equipment[slot] = holder

    def test_everything_wearable_can_be_worn(self):
        for key, base in BASES.items():
            if not base.get("slot"):
                continue
            with self.subTest(item=key):
                item = Item(key)
                item.known = True
                ok, message = self.p.equip(item)
                if not ok:
                    # The only fair refusals are the rules, not a broken item.
                    self.assertRegex(message, r"strong enough|Can't use both|"
                                             r"cannot let go|stuck fast", message)

    def test_everything_usable_does_something_and_says_so(self):
        for key, base in BASES.items():
            if base.get("kind") not in ("potion", "scroll"):
                continue
            with self.subTest(item=key):
                item = Item(key)
                item.known = True
                self.p.hp = max(1, self.p.max_hp // 3)
                self.p.add_item(item)
                self.world.do_player_action(
                    self.level, self.p,
                    {"a": "stow", "id": item.id, "slot": "waist"})
                self.world.events.clear()
                self.world.do_player_action(
                    self.level, self.p,
                    {"a": "use", "id": item.id, "x": self.p.x + 1,
                     "y": self.p.y, "target": item.id})
                lines = said(self.world)
                self.assertTrue(lines, f"{key} said nothing")
                for line in lines:
                    self.assertNotIn("buried in your pack", line,
                                     f"{key} could not be reached")

    def test_every_item_has_an_icon_that_exists(self):
        from stormhold.ui.art import SpriteSheet
        sheet = SpriteSheet(1).build()
        for key, base in BASES.items():
            with self.subTest(item=key):
                self.assertIn(base["icon"], sheet.items,
                              f"{key} asks for an icon nobody draws")

    def test_every_item_can_be_named_and_described(self):
        for key in BASES:
            with self.subTest(item=key):
                item = Item(key)
                for known in (False, True):
                    item.known = known
                    name = item.name(self.world.appearances)
                    self.assertTrue(name and "{" not in name, name)
                    self.assertTrue(item.describe(self.world.appearances))


class TestEveryCreature(unittest.TestCase):
    def bait(self, key):
        depth = max(1, MONSTERS[key]["min_d"])
        world = World(seed=64)
        p = world.add_player("Bait", spell="Spark")
        p.stats = {k: 18 for k in p.stats}
        p.level = 25
        p.recalc()
        p.max_hp = p.hp = 100000
        world.move_player_to(p, depth)
        level = world.levels[depth]
        spot = level.find_free(p.x, p.y, max_r=4, ignore_id=p.id)
        m = world.spawn(key, spot[0], spot[1], depth)
        level.place(m)
        m.target_id = p.id
        m.last_seen = (p.x, p.y)
        return world, p, level, m

    def test_every_creature_takes_its_turn_without_raising(self):
        for key in MONSTERS:
            with self.subTest(creature=key):
                world, p, level, m = self.bait(key)
                for _ in range(60):
                    if m.dead:
                        break
                    world.events.clear()
                    ai.take_turn(world, level, m)
                    p.hp = 100000
                    for line in said(world):
                        self.assertNotIn("{", line, f"{key}: {line}")

    def test_every_creature_has_an_icon_that_exists(self):
        from stormhold.ui.art import SpriteSheet
        sheet = SpriteSheet(1).build()
        for key, tpl in MONSTERS.items():
            with self.subTest(creature=key):
                self.assertIn(tpl["sprite"], sheet.creatures,
                              f"{key} asks for a sprite nobody draws")

    def test_everything_a_creature_can_hire_or_summon_exists(self):
        for key, tpl in MONSTERS.items():
            with self.subTest(creature=key):
                if tpl.get("hires"):
                    self.assertIn(tpl["hires"], MONSTERS)
                for summoned in tpl.get("summons", ()):
                    self.assertIn(summoned, MONSTERS)

    def test_every_floor_has_something_that_belongs_on_it(self):
        from stormhold.game.monsters import spawn_table
        for depth in range(1, 26):
            with self.subTest(depth=depth):
                table = spawn_table(depth)
                self.assertTrue(table, f"nothing lives on floor {depth}")


class TestEveryTrap(unittest.TestCase):
    def test_every_trap_springs_and_says_something(self):
        for kind in TRAPS:
            with self.subTest(trap=kind):
                world, p, level = archmage(depth=8, seed=5)
                p.max_hp = p.hp = 5000
                level.traps[(p.x, p.y)] = {"kind": kind, "found": False,
                                           "armed": True}
                world.events.clear()
                world.spring_trap(level, p)
                lines = said(world)
                self.assertTrue(lines, f"{kind} sprang in silence")
                for line in lines:
                    self.assertNotIn("{", line, f"{kind}: {line}")

    def test_every_trap_on_the_depth_tables_is_a_real_trap(self):
        from stormhold.game.traps import TRAP_BY_DEPTH, trap_kinds_for
        for _depth, kinds in TRAP_BY_DEPTH:
            for kind in kinds:
                self.assertIn(kind, TRAPS)
        for depth in range(1, 26):
            self.assertTrue(trap_kinds_for(depth), f"floor {depth} has no traps")


class TestEveryVerb(unittest.TestCase):
    """Every action the client can send, against a world that is not set up
    for it. None of them may raise."""

    VERBS = ("move", "wait", "search", "disarm", "freehand", "rest", "examine",
             "open", "close", "sleep", "run", "attack", "shoot", "pickup",
             "drop", "equip", "unequip", "use", "cast", "fountain", "throne",
             "stairs", "sort", "rename", "callme", "buy", "sell", "service",
             "stow", "unstow")

    def test_no_verb_raises_on_an_empty_hand(self):
        for verb in self.VERBS:
            with self.subTest(verb=verb):
                world, p, level = archmage(depth=4, seed=21)
                world.do_player_action(level, p, {"a": verb})

    def test_no_verb_raises_on_nonsense_arguments(self):
        rubbish = {"id": 999999, "slot": "nowhere", "x": -5, "y": 9999,
                   "dx": 7, "dy": -7, "spell": "Not A Spell", "amount": -100,
                   "what": "free money", "name": "", "qty": -3, "shop": "none"}
        for verb in self.VERBS:
            with self.subTest(verb=verb):
                world, p, level = archmage(depth=4, seed=22)
                world.do_player_action(level, p, dict(rubbish, a=verb))

    def test_an_unknown_verb_is_simply_ignored(self):
        world, p, level = archmage(depth=4, seed=23)
        world.do_player_action(level, p, {"a": "dance"})
        world.do_player_action(level, p, {})
