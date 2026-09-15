"""Two people in one keep.

Multiplayer is the reason this remake exists - it is meant to be played with
children on a LAN - and it had no tests at all. These drive two real clients
over real sockets against a real server, because the things that go wrong in
multiplayer (one player's turn blocking another, a floor's clock stalling
when someone wanders off to make a sandwich) do not show up in a unit test of
the world.
"""

import os
import sys
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame                                                  # noqa: E402

from tools.playtest import Session, Guest                       # noqa: E402
from tools.crawl import make_character                          # noqa: E402
from stormhold.net import protocol as P                         # noqa: E402

_port = [7930]


def next_port():
    _port[0] += 1
    return _port[0]


class TwoPlayers(unittest.TestCase):
    """A host and a guest, both really connected."""

    difficulty = "Intermediate"

    def setUp(self):
        port = next_port()
        self.host = Session(seed=99, name="Host", port=port)
        make_character(self.host, spell="Spark", difficulty=self.difficulty)
        self.guest = Guest(port=port, name="Guest")
        self.guest.join()
        self.pump(30)

    def tearDown(self):
        try:
            self.guest.close()
        finally:
            self.host.close()

    def pump(self, n=10):
        for _ in range(n):
            self.host.step()
            self.guest.step()

    @property
    def world(self):
        return self.host.world

    def player(self, name):
        return next(p for p in self.world.players.values() if p.name == name)

    def send(self, session, action, pumps=10):
        session.app.play.send_action(action)
        self.pump(pumps)


class TestJoining(TwoPlayers):
    def test_both_are_in_the_same_world(self):
        self.assertEqual(sorted(p.name for p in self.world.players.values()),
                         ["Guest", "Host"])

    def test_each_sees_the_other_in_the_party_panel(self):
        for view in (self.host.app.play.party, self.guest.app.play.party):
            self.assertEqual(sorted(p["n"] for p in view), ["Guest", "Host"])

    def test_the_guest_is_told_where_they_are(self):
        self.assertTrue(any("Aldershade" in m for m in self.guest.log(6)))

    def test_the_host_hears_that_someone_arrived(self):
        self.assertIn("Guest joins the party.", self.host.log(8))


class TestPlayingTogether(TwoPlayers):
    def test_one_players_movement_is_visible_to_the_other(self):
        guest = self.player("Guest")
        seen = lambda: [(a["x"], a["y"]) for a in self.host.app.play.actors
                        if a.get("n") == "Guest"]
        before = seen()
        self.assertTrue(before, "the host cannot see the guest at all")
        for _ in range(3):
            self.send(self.guest, {"a": "move", "dx": 0, "dy": 1})
        self.assertNotEqual(seen(), before, "the host never saw the guest move")
        self.assertEqual(seen()[0], (guest.x, guest.y))

    def test_chat_reaches_the_other_player(self):
        self.host.app.client.send(P.C_CHAT, {"text": "down the stairs"})
        self.pump(15)
        self.assertTrue(any("down the stairs" in m for m in self.guest.log(8)),
                        self.guest.log(8))

    def test_an_idle_player_does_not_freeze_the_other(self):
        """Someone wandering off must not stop the game for everyone else.

        This is the failure that would end a game with children: one player
        puts the controller down and the floor's clock stops for the rest.
        """
        guest = self.player("Guest")
        start = (guest.x, guest.y)
        moved = 0
        for _ in range(10):
            where = (guest.x, guest.y)
            self.send(self.guest, {"a": "move", "dx": -1, "dy": 0})
            if (guest.x, guest.y) != where:
                moved += 1
        self.assertGreaterEqual(moved, 4,
                                f"the guest only moved {moved} times from {start} "
                                f"while the host stood still")

    def test_the_hosts_difficulty_is_the_one_in_force(self):
        self.assertEqual(self.world.difficulty, "Intermediate")

    def test_a_guest_cannot_change_the_difficulty_after_the_fact(self):
        before = self.world.difficulty
        self.guest.app.client.send(P.C_HELLO, {"name": "Interloper",
                                               "difficulty": "Easy",
                                               "version": 0})
        self.pump(10)
        self.assertEqual(self.world.difficulty, before)


class TestOnDifferentFloors(TwoPlayers):
    def take_the_stairs(self, session, actor):
        target = self.world.levels[actor.depth].down_at
        for _ in range(200):
            if (actor.x, actor.y) == tuple(target):
                break
            dx = (target[0] > actor.x) - (target[0] < actor.x)
            dy = (target[1] > actor.y) - (target[1] < actor.y)
            level = self.world.levels[actor.depth]
            if not level.passable(actor.x + dx, actor.y + dy):
                for alt in ((dx, 0), (0, dy), (0, 1), (1, 0), (-1, 0), (0, -1)):
                    if level.passable(actor.x + alt[0], actor.y + alt[1]):
                        dx, dy = alt
                        break
            self.send(session, {"a": "move", "dx": dx, "dy": dy}, pumps=6)
        session.key(pygame.K_PERIOD, mod=pygame.KMOD_SHIFT)
        self.pump(20)

    def test_a_player_can_go_down_alone(self):
        guest = self.player("Guest")
        self.take_the_stairs(self.guest, guest)
        self.assertEqual(guest.depth, 1)
        self.assertEqual(self.player("Host").depth, 0)

    def test_the_party_panel_shows_where_everyone_is(self):
        guest = self.player("Guest")
        self.take_the_stairs(self.guest, guest)
        depths = {p["n"]: p["d"] for p in self.host.app.play.party}
        self.assertEqual(depths, {"Host": 0, "Guest": 1})

    def test_you_do_not_see_someone_on_another_floor(self):
        guest = self.player("Guest")
        self.take_the_stairs(self.guest, guest)
        self.assertFalse(any(a.get("n") == "Host"
                             for a in self.guest.app.play.actors))

    def test_each_floor_keeps_its_own_clock(self):
        guest = self.player("Guest")
        self.take_the_stairs(self.guest, guest)
        for _ in range(6):
            self.send(self.guest, {"a": "move", "dx": 0, "dy": -1}, pumps=6)
        town, below = self.world.levels[0].clock, self.world.levels[1].clock
        self.assertNotEqual(town, below,
                            "the floors are sharing one clock")


if __name__ == "__main__":
    unittest.main()


class TestAMisbehavingActionDoesNotEndYourGame(TwoPlayers):
    """A crash inside one action used to raise out of the client's thread.

    The `finally` dropped that player from the game, so a bug in a verb read
    as "the connection was lost" - with no message, and no sign to anyone
    else that anything had happened. Sitting on a throne did exactly this:
    `_act_throne` referred to a name that was never imported.
    """

    def test_a_verb_that_raises_leaves_you_playing(self):
        world = self.world
        guest = self.player("Guest")

        def explode(level, p, action):
            raise RuntimeError("a deliberate bug")

        world._act_wait = explode
        try:
            self.send(self.guest, {"a": "wait"}, pumps=15)
        finally:
            del world._act_wait

        self.assertIn(guest.id, world.players, "the player was dropped")
        self.assertTrue(self.guest.app.client.connected,
                        "the client was disconnected")
        self.assertTrue(any("went wrong" in m for m in self.guest.log(6)),
                        self.guest.log(6))

    def test_and_you_can_carry_on_afterwards(self):
        world = self.world
        guest = self.player("Guest")

        def explode(level, p, action):
            raise RuntimeError("a deliberate bug")

        world._act_wait = explode
        try:
            self.send(self.guest, {"a": "wait"}, pumps=15)
        finally:
            del world._act_wait

        moved = 0
        for _ in range(6):
            where = (guest.x, guest.y)
            self.send(self.guest, {"a": "move", "dx": 0, "dy": 1})
            if (guest.x, guest.y) != where:
                moved += 1
        self.assertGreater(moved, 0, "the game was stuck after the error")
