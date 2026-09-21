"""If it changes what you carry, the client has to be told.

Reported from play: "I just picked up a bunch of items and there's nothing
in my inventory." The items were picked up. The window was showing the last
pack the server had described, and picking things up never described one -
so what you carried and what you could see drifted apart and stayed apart
until something unrelated, like walking into a shop, happened to refresh it.

That is not a bug in the Get command; it is a bug in a rule nobody had
written down. This file writes it down: perform each action, fingerprint
what the character carries before and after, and require an inventory event
whenever the fingerprint moves. Every handler that touches the pack is in
the list, so a new one that forgets goes red here rather than in the game.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from stormhold.game.items import Item                             # noqa: E402
from stormhold.game.world import World                            # noqa: E402


def fingerprint(p):
    """Everything about what this character is carrying, as one value."""
    def one(item):
        return (item.id, item.key, item.qty, getattr(item, "known", None),
                item.enchant,
                tuple((c.id, c.qty) for c in (getattr(item, "contents", None) or [])))
    return (tuple(one(i) for i in p.inventory),
            tuple((slot, one(i) if i else None)
                  for slot, i in sorted(p.equipment.items())),
            p.copper, p.bank)


def belt_with(p, key):
    belt = Item("belt3")
    thing = Item(key)
    thing.known = True
    p.equipment["waist"] = belt
    belt.contents.append(thing)
    return thing


# (name, set the scene, the action to perform)
CASES = [
    ("pickup", lambda w, p, l: l.add_ground_item(p.x, p.y, Item("shortsword")),
     lambda w, p, l: {"a": "pickup"}),
    ("pick up coins", lambda w, p, l: l.add_ground_item(p.x, p.y, w._gold_item(600, 1)),
     lambda w, p, l: {"a": "pickup"}),
    ("take one item off the floor",
     lambda w, p, l: l.add_ground_item(p.x, p.y, Item("shortsword")),
     lambda w, p, l: {"a": "take", "id": l.items_at(p.x, p.y)[-1].id}),
    ("drop", lambda w, p, l: p.add_item(Item("shortsword")),
     lambda w, p, l: {"a": "drop", "id": p.inventory[-1].id}),
    ("equip", lambda w, p, l: p.add_item(Item("helm")),
     lambda w, p, l: {"a": "equip", "id": p.inventory[-1].id, "slot": "head"}),
    ("unequip", lambda w, p, l: p.equipment.__setitem__("head", Item("helm")),
     lambda w, p, l: {"a": "unequip", "slot": "head"}),
    ("free hand", lambda w, p, l: l.add_ground_item(p.x, p.y, Item("potion_heal")),
     lambda w, p, l: {"a": "freehand"}),
    ("stow", lambda w, p, l: (p.equipment.__setitem__("waist", Item("belt3")),
                              p.add_item(Item("potion_heal"))),
     lambda w, p, l: {"a": "stow", "id": p.inventory[-1].id, "slot": "waist"}),
    ("unstow", lambda w, p, l: belt_with(p, "potion_heal"),
     lambda w, p, l: {"a": "unstow", "id": p.equipment["waist"].contents[0].id}),
    ("drink a potion", lambda w, p, l: (belt_with(p, "potion_heal"),
                                        setattr(p, "hp", 1)),
     lambda w, p, l: {"a": "use", "id": p.equipment["waist"].contents[0].id}),
    ("read a scroll", lambda w, p, l: belt_with(p, "scroll_map"),
     lambda w, p, l: {"a": "use", "id": p.equipment["waist"].contents[0].id}),
    ("sort the pack",
     lambda w, p, l: [p.add_item(Item(k)) for k in ("gem", "shortsword", "potion_heal")],
     lambda w, p, l: {"a": "sort"}),
    ("name an object", lambda w, p, l: p.add_item(Item("shortsword")),
     lambda w, p, l: {"a": "rename", "id": p.inventory[-1].id, "name": "Biter"}),
    ("buy", lambda w, p, l: setattr(p, "copper", 99999),
     lambda w, p, l: {"a": "buy", "shop": "general",
                      "id": w.stock_for("general")[0].id}),
    ("sell", lambda w, p, l: p.add_item(Item("longsword")),
     lambda w, p, l: {"a": "sell", "shop": "weaponsmith", "id": p.inventory[-1].id}),
    ("deposit", lambda w, p, l: setattr(p, "copper", 500),
     lambda w, p, l: {"a": "service", "what": "deposit", "amount": 100,
                      "shop": "bank"}),
    ("withdraw", lambda w, p, l: setattr(p, "bank", 500),
     lambda w, p, l: {"a": "service", "what": "withdraw", "amount": 100,
                      "shop": "bank"}),
]


class TestWhatYouCarryAndWhatYouSeeAgree(unittest.TestCase):

    def test_no_action_changes_the_pack_in_silence(self):
        for name, setup, action in CASES:
            with self.subTest(action=name):
                world = World(seed=5)
                p = world.add_player("Carrier")
                level = world.levels[p.depth]
                setup(world, p, level)
                world.events.clear()
                before = fingerprint(p)
                world.do_player_action(level, p, action(world, p, level))
                moved = fingerprint(p) != before
                told = any(e["t"] == "inv" for e in world.events)
                if moved:
                    self.assertTrue(
                        told, f"{name} changed what you carry and the window "
                              f"was never told, so it goes on showing the old pack")

    def test_the_list_covers_every_handler_that_touches_the_pack(self):
        """A new verb that moves things about must be added above.

        Without this the file rots quietly: the rule stays true of the twelve
        actions somebody thought of in 2026 and says nothing about the
        thirteenth.
        """
        import inspect
        from stormhold.game import world as world_module
        source = inspect.getsource(world_module)
        verbs = set()
        for line in source.splitlines():
            line = line.strip()
            if line.startswith("def _act_"):
                verbs.add(line[len("def _act_"):].split("(")[0])
        # Verbs that cannot change what you carry, and why.
        harmless = {
            "move", "run", "wait", "stairs", "examine", "search", "disarm",
            "open", "close", "rest", "sleep", "attack", "cast", "shoot",
            "callme", "fountain", "throne",
        }
        covered = {"pickup", "take", "drop", "equip", "unequip", "freehand",
                   "stow", "unstow", "use", "sort", "rename", "buy", "sell",
                   "service"}
        missing = verbs - harmless - covered
        self.assertFalse(
            missing,
            f"these verbs are neither covered here nor listed as harmless: "
            f"{sorted(missing)}")


if __name__ == "__main__":
    unittest.main()


class TestAShortGameStaysConsistent(unittest.TestCase):
    """A few dozen real actions, with the soak's checks after each one.

    The long version of this is `tools/soak.py`, which plays for hundreds of
    actions across several characters and is too slow to live here. This is
    the first minute of it, so that a change which makes the window and the
    game disagree fails on the way in rather than in somebody's evening.
    """

    def test_playing_for_a_while_never_breaks_the_invariants(self):
        from tools.soak import Soak
        soak = Soak(seed=3, actions=60, port=9899)
        try:
            faults = soak.run()
        finally:
            soak.close()
        self.assertEqual(
            [f[3] for f in faults], [],
            "playing the game made the window and the game disagree")


class TestTheFloorWindowKeepsUpWithYourFeet(unittest.TestCase):
    """"The floor window is always empty." Reported from play - and true for
    a different reason than the pack bug above: the Floor panel reads
    inventory_view()'s own "floor" field, which is only ever recomputed when
    an "inv" event fires. Picking something up fires one; simply walking
    onto (or off of) a tile with something on it never did, so the panel
    kept showing whatever it last saw - usually nothing, from before you had
    ever stood on anything - no matter what was actually underfoot.
    """

    def test_walking_onto_an_item_tells_the_window(self):
        world = World(seed=5)
        p = world.add_player("Walker")
        level = world.levels[p.depth]
        nx, ny = level.find_free(p.x + 1, p.y, 5)
        level.add_ground_item(nx, ny, Item("dagger"))

        world.events.clear()
        world.do_player_action(level, p, {"a": "move", "dx": 1 if nx > p.x else -1,
                                          "dy": 1 if ny > p.y else (-1 if ny < p.y else 0)})
        self.assertTrue(any(e["t"] == "inv" for e in world.events),
                        "moving onto an item tile never refreshed the Floor window")

    def test_walking_onto_bare_floor_still_tells_the_window(self):
        """Leaving a tile that had something on it has to clear the panel
        too, not just filling it in has to work. dx=dy=0 is Wait, not a
        step, so this needs an actual move onto an adjacent open tile."""
        world = World(seed=5)
        p = world.add_player("Walker")
        level = world.levels[p.depth]
        nx, ny = level.find_free(p.x + 1, p.y, 5)
        dx = 1 if nx > p.x else (-1 if nx < p.x else 0)
        dy = 1 if ny > p.y else (-1 if ny < p.y else 0)
        world.events.clear()
        world.do_player_action(level, p, {"a": "move", "dx": dx, "dy": dy})
        self.assertTrue(any(e["t"] == "inv" for e in world.events))

    def test_taking_the_stairs_tells_the_window_too(self):
        world = World(seed=5)
        p = world.add_player("Descender")
        world.events.clear()
        world.move_player_to(p, p.depth + 1)
        self.assertTrue(any(e["t"] == "inv" for e in world.events),
                        "landing on a new floor never refreshed the Floor window")

    def test_the_inventory_views_own_floor_field_matches_whats_underfoot(self):
        """Not just that an event fires - that inventory_view() itself, once
        recomputed, actually lists what is on the ground under the player."""
        world = World(seed=5)
        p = world.add_player("Walker")
        level = world.levels[p.depth]
        level.add_ground_item(p.x, p.y, Item("dagger"))
        floor = world.inventory_view(p)["floor"]
        self.assertEqual([f["key"] for f in floor], ["dagger"])
