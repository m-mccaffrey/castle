"""What a floor plan must never look like.

Reported from play: "there will be two doors one after the other, or next to
each other leading to the same place". Both came from the same thing - doors
were rolled for each room's edge ring separately, so two rooms back to back
each put one on their own side of the same stub of corridor, and a two-wide
gap got a door in each square.

These are shape checks over many generated floors rather than one, because a
bad plan is a thing you notice while playing and never while reading.
"""

import collections
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from stormhold.common.constants import T                          # noqa: E402
from stormhold.game.level import generate_dungeon                 # noqa: E402

DOORS = (T.DOOR, T.DOOR_OPEN)
SOLID = (T.WALL, T.VOID)
FLOORS = [(seed, depth) for seed in range(8) for depth in (1, 4, 9)]


def doors_on(level):
    return {(x, y) for y in range(level.h) for x in range(level.w)
            if level.get(x, y) in DOORS}


class TestTheFloorPlansAreSane(unittest.TestCase):

    def test_no_two_doors_stand_shoulder_to_shoulder(self):
        for seed, depth in FLOORS:
            level = generate_dungeon(depth, seed)
            doors = doors_on(level)
            for x, y in doors:
                for dx, dy in ((1, 0), (0, 1)):
                    self.assertNotIn(
                        (x + dx, y + dy), doors,
                        f"seed {seed} depth {depth}: doors at {(x, y)} and "
                        f"{(x + dx, y + dy)} open on the same place")

    def test_no_door_two_along_the_corridor_from_another(self):
        """An airlock: through one door, one pace, through the next."""
        for seed, depth in FLOORS:
            level = generate_dungeon(depth, seed)
            doors = doors_on(level)
            for x, y in doors:
                for dx, dy in ((1, 0), (0, 1)):
                    if level.get(x + dx, y + dy) != T.FLOOR:
                        continue
                    self.assertNotIn(
                        (x + 2 * dx, y + 2 * dy), doors,
                        f"seed {seed} depth {depth}: doors at {(x, y)} and "
                        f"{(x + 2 * dx, y + 2 * dy)} with one pace between")

    def test_a_door_is_always_a_gap_in_a_wall(self):
        for seed, depth in FLOORS:
            level = generate_dungeon(depth, seed)
            for x, y in doors_on(level):
                horiz = (level.get(x - 1, y) == T.WALL
                         and level.get(x + 1, y) == T.WALL)
                vert = (level.get(x, y - 1) == T.WALL
                        and level.get(x, y + 1) == T.WALL)
                self.assertTrue(horiz or vert,
                                f"seed {seed} depth {depth}: the door at "
                                f"{(x, y)} is not set in a wall")

    def test_every_floor_is_walkable_end_to_end(self):
        """Thinning the doors must not cut a room off."""
        for seed, depth in FLOORS:
            level = generate_dungeon(depth, seed)
            start = next(((x, y) for y in range(level.h) for x in range(level.w)
                          if level.get(x, y) == T.STAIRS_UP), tuple(level.spawn_point))
            seen, queue = {start}, collections.deque([start])
            while queue:
                x, y = queue.popleft()
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    spot = (x + dx, y + dy)
                    if (spot in seen or not level.in_bounds(*spot)
                            or level.get(*spot) in SOLID):
                        continue
                    seen.add(spot)
                    queue.append(spot)
            walkable = {(x, y) for y in range(level.h) for x in range(level.w)
                        if level.get(x, y) not in SOLID}
            self.assertEqual(walkable - seen, set(),
                             f"seed {seed} depth {depth}: squares cut off")

    def test_there_are_still_plenty_of_doors(self):
        """The cheap way to pass the checks above is to stop making doors."""
        counts = [len(doors_on(generate_dungeon(depth, seed)))
                  for seed, depth in FLOORS]
        average = sum(counts) / len(counts)
        self.assertGreater(average, 8, f"only {average:.1f} doors a floor")


if __name__ == "__main__":
    unittest.main()


class TestEverySpellHasAGlyph(unittest.TestCase):
    """The quick-cast slots used to draw the numbers 1 to 10, which told you
    how many spells you knew and nothing about which was which."""

    def test_no_spell_is_left_without_one(self):
        from stormhold.ui import art
        from stormhold.game.spells import SPELLS
        missing = [name for name in SPELLS if name not in art.SPELL_BUILDERS]
        self.assertEqual(missing, [], f"no icon for {missing}")

    def test_no_glyph_is_left_without_a_spell(self):
        from stormhold.ui import art
        from stormhold.game.spells import SPELLS
        extra = [name for name in art.SPELL_BUILDERS if name not in SPELLS]
        self.assertEqual(extra, [], f"icons for spells that do not exist: {extra}")

    def test_each_one_draws_something_at_the_size_the_slot_expects(self):
        from stormhold.ui import art
        from stormhold.game.spells import SPELLS
        for name in SPELLS:
            with self.subTest(spell=name):
                icon = art.spell_icon(name)
                self.assertEqual((icon.w, icon.h),
                                 (art.SPELL_ICON, art.SPELL_ICON))
                painted = sum(1 for row in icon.px for cell in row if cell is not None)
                self.assertGreater(painted, 24,
                                   f"{name} is nearly blank at {painted} pixels")
                self.assertLess(painted, art.SPELL_ICON * art.SPELL_ICON - 8,
                                f"{name} fills the whole square, so it has no silhouette")


class TestHowThicklyAFloorIsStocked(unittest.TestCase):
    """The first floors have to be quiet.

    Every floor used to be filled to 85% of however many spawn points the
    map generator happened to lay down: thirteen creatures on floor one
    against a character with twenty-two hit points and a dagger, and then
    twenty-six on floor three because that particular map had more room. One
    at a time none of the early creatures can beat a fresh character - that
    is measured - so what killed people was arithmetic, and a floor that
    doubles because of its shape is a difficulty cliff nobody chose.
    """

    def counts(self, seed):
        from stormhold.game.world import World
        world = World(seed=seed)
        world.add_player("Counter")
        return {depth: sum(1 for a in world.get_level(depth).actors.values()
                           if getattr(a, "kind", "") == "monster")
                for depth in (1, 2, 3, 5, 8, 12, 20)}

    def test_the_first_floor_is_quiet(self):
        for seed in range(4):
            with self.subTest(seed=seed):
                self.assertLessEqual(self.counts(seed)[1], 12)

    def test_it_gets_busier_as_you_go_down(self):
        for seed in range(4):
            with self.subTest(seed=seed):
                counts = self.counts(seed)
                self.assertGreater(counts[12], counts[1] + 6)

    def test_no_floor_is_a_crowd(self):
        """The cap is what stops a big map becoming a massacre."""
        for seed in range(4):
            with self.subTest(seed=seed):
                for depth, n in self.counts(seed).items():
                    self.assertLessEqual(n, 40, f"floor {depth} holds {n}")
