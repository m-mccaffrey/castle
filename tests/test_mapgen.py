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
