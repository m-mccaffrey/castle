"""Two people on one keep, which is what this remake exists for.

The shared per-floor clock is our own invention - the original is one player
- so it is the part with no prior art to be right by accident. These drive
two real clients over a real socket: one hosts, one joins, and both windows
are asked whether they agree with the server and with each other.
"""

import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame                                                    # noqa: E402

from tools.playtest import Session, Guest                         # noqa: E402
from tools import crawl as C                                      # noqa: E402

MOVES = (pygame.K_h, pygame.K_j, pygame.K_k, pygame.K_l)


class TestTwoPlayers(unittest.TestCase):
    PORT = 9861

    @classmethod
    def setUpClass(cls):
        cls.host = Session(seed=5, port=cls.PORT, size=(1280, 800))
        C.make_character(cls.host, spell="Spark", difficulty="Intermediate")
        cls.guest = Guest(cls.PORT, name="Kid", seed=5)
        cls.joined = cls.guest.join()
        cls.world = cls.host.app.server.world
        cls.H = next(p for p in cls.world.players.values() if p.name == "Tester")
        cls.G = next(p for p in cls.world.players.values() if p.name == "Kid")
        cls.rng = random.Random(1)

    @classmethod
    def tearDownClass(cls):
        cls.guest.close()
        cls.host.close()

    def both(self, seconds=0.3):
        self.host.settle(seconds)
        self.guest.settle(seconds)

    def wander(self, n=6):
        for _ in range(n):
            for who in (self.host, self.guest):
                who.key(self.rng.choice(MOVES))
            self.both(0.25)

    def test_a_guest_can_join_and_lands_in_the_game(self):
        self.assertEqual(self.joined, "PlayScene")
        self.assertEqual(len(self.world.players), 2)

    def test_each_window_shows_the_other_player_where_they_are(self):
        self.wander()
        for viewer, label in ((self.host, "host"), (self.guest, "guest")):
            with self.subTest(window=label):
                depth = viewer.app.play.map.depth
                seen = {a["id"]: (a["x"], a["y"]) for a in viewer.app.play.actors
                        if a.get("k") == "player"}
                truth = {p.id: (p.x, p.y) for p in self.world.players.values()
                         if p.depth == depth}
                self.assertEqual(seen, truth)

    def test_the_party_panel_matches_the_party(self):
        self.world.move_player_to(self.H, 1)
        self.world.move_player_to(self.G, 1)
        self.both(0.8)
        self.wander(3)
        for viewer, label in ((self.host, "host"), (self.guest, "guest")):
            with self.subTest(window=label):
                panel = {m["id"]: (m["hp"], m["d"]) for m in viewer.app.play.party}
                truth = {p.id: (max(0, int(p.hp)), p.depth)
                         for p in self.world.players.values()}
                self.assertEqual(panel, truth)

    def test_one_player_in_a_window_does_not_freeze_the_other(self):
        """The floor waits for whoever is due to act. Opening the pack must
        not be a way to stop everybody else playing."""
        self.host.key(pygame.K_i)
        self.host.settle(0.4)
        try:
            before = self.G.elapsed
            for _ in range(6):
                self.guest.key(pygame.K_l)
                self.guest.settle(0.3)
            self.assertGreater(self.G.elapsed, before,
                               "the guest could not act while the host had a "
                               "window open")
        finally:
            self.host.key(pygame.K_ESCAPE)
            self.host.settle(0.3)

    def test_the_party_can_be_on_different_floors_and_both_keep_playing(self):
        self.world.move_player_to(self.H, 1)
        self.world.move_player_to(self.G, 2)
        self.both(0.8)
        self.assertNotEqual(self.H.depth, self.G.depth)
        before = (self.H.elapsed, self.G.elapsed)
        self.wander(6)
        self.assertGreater(self.H.elapsed, before[0], "the host's floor stalled")
        self.assertGreater(self.G.elapsed, before[1], "the guest's floor stalled")

    def test_a_death_does_not_leave_the_floor_waiting_on_a_corpse(self):
        from stormhold.game import combat
        self.world.move_player_to(self.H, 1)
        self.world.move_player_to(self.G, 1)
        self.both(0.8)
        combat.apply_damage(self.world, self.G, 99999, None)
        self.both(1.0)
        before = self.H.elapsed
        for _ in range(6):
            self.host.key(pygame.K_l)
            self.host.settle(0.3)
        self.assertGreater(self.H.elapsed, before,
                           "the survivor was stuck after the other died")
        level = self.world.levels[self.H.depth]
        self.assertIn(level.waiting_on, (None, self.H.id),
                      "the floor is waiting on somebody who is not there")


if __name__ == "__main__":
    unittest.main()


class TestAWindowThatFallsBehindCatchesUp(unittest.TestCase):
    """A client drops any state packet for a floor it has no map of, which
    is right for the moment between taking the stairs and the map arriving -
    and fatal if the map never arrives, because every packet after it is
    dropped for the same reason and the window freezes while the game plays
    on behind it. It asks for the floor now instead of waiting forever.
    """

    PORT = 9863

    def test_it_asks_for_the_floor_and_recovers(self):
        host = Session(seed=5, port=self.PORT, size=(1280, 800))
        try:
            C.make_character(host, spell="Spark", difficulty="Intermediate")
            guest = Guest(self.PORT, name="Kid", seed=5)
            guest.join()
            try:
                world = host.app.server.world
                G = next(p for p in world.players.values() if p.name == "Kid")
                # Move them with the client none the wiser: what a lost level
                # packet looks like from the window's side.
                world.move_player_to(G, 2)
                world.events.clear()
                host.settle(0.5)
                guest.settle(0.5)
                self.assertNotEqual(guest.app.play.map.depth, G.depth,
                                    "the window should be behind at this point")
                for _ in range(8):
                    guest.key(pygame.K_l)
                    guest.settle(0.4)
                self.assertEqual(guest.app.play.map.depth, G.depth,
                                 "the window never caught up")
                panel = {m["n"]: m["d"] for m in guest.app.play.party}
                self.assertEqual(panel.get("Kid"), G.depth)
            finally:
                guest.close()
        finally:
            host.close()
