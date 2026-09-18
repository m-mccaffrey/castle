"""Play Stormhold headlessly and photograph it.

The click harness in tests/ proves geometry and plumbing. This proves the
game: it starts a real host-and-play session, drives the real App loop with
real events, and writes a PNG of every screen so the pictures can be looked
at rather than assumed. It is a tool, not a test - it is how you find the
things a test does not know to ask about.

    python3 tools/playtest.py            # runs the scripted playthrough
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame                                                   # noqa: E402

from stormhold.ui.app import App                                # noqa: E402

SHOTS = os.environ.get("SHOTS", "/tmp/claude-0/shots")


def free_port():
    """A port nobody is listening on.

    The tools used to hard-code one each. Two of them running at once - or
    one left over from a previous run - and the second client connects to
    the first one's game, lands on somebody else's menu, and fails with
    something that looks nothing like a port clash.
    """
    import socket
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class Session:
    def __init__(self, seed=4242, name="Tester", size=(1280, 800), port=7801):
        save = os.path.join(SHOTS, "party.json")
        os.makedirs(os.path.dirname(save), exist_ok=True)
        args = argparse.Namespace(serve=False, port=port, host="0.0.0.0",
                                  seed=seed, name=name, save=save,
                                  fullscreen=False)
        self.app = App(args)
        self.app.screen = pygame.display.set_mode(size)
        self.app.scene.layout(size)
        os.makedirs(SHOTS, exist_ok=True)
        self.n = 0

    # ---------------------------------------------------------------- loop --
    def step(self, frames=1):
        for _ in range(frames):
            self.app.pump_network()
            self.app.scene.update(1 / 30.0)
            self.app.scene.draw(self.app.screen)
            time.sleep(0.002)

    def settle(self, seconds=1.5, quiet=12):
        """Pump until the server stops talking, or until the time runs out.

        Sleeping for a fixed period was costing minutes across a suite; almost
        every wait here is really "wait for the server to finish answering",
        which is over as soon as the inbox has been empty for a few frames.
        """
        end = time.time() + seconds
        still = 0
        while time.time() < end:
            had = self.app.client.inbox.qsize()
            self.step()
            still = 0 if had else still + 1
            if still >= quiet:
                return

    def send(self, event):
        # Through App.dispatch, not straight at the scene: the app does some
        # tidying after each event, and a harness that skips it is testing a
        # game nobody plays.
        self.app.dispatch(event)
        self.step()

    def click(self, pos, button=1):
        for kind in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            self.send(pygame.event.Event(kind, pos=pos, button=button))

    def drag(self, src, dst):
        self.send(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=src, button=1))
        mid = ((src[0] + dst[0]) // 2, (src[1] + dst[1]) // 2)
        for p in (mid, dst):
            self.send(pygame.event.Event(pygame.MOUSEMOTION, pos=p, buttons=(1, 0, 0)))
        self.send(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=dst, button=1))

    def key(self, key, unicode="", mod=0):
        self.send(pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode, mod=mod))
        self.send(pygame.event.Event(pygame.KEYUP, key=key, mod=mod))

    def type(self, text):
        for ch in text:
            self.key(ord(ch) if len(ch) == 1 else 0, unicode=ch)

    def shot(self, label):
        self.n += 1
        path = os.path.join(SHOTS, f"{self.n:02d}-{label}.png")
        self.app.scene.draw(self.app.screen)
        pygame.image.save(self.app.screen, path)
        print(f"  shot {path}")
        return path

    # ------------------------------------------------------------- reading --
    def log(self, n=8):
        play = self.app.play
        if play is None:
            return []
        return [m[0] if isinstance(m, tuple) else m
                for m in getattr(play, "messages", [])[-n:]]

    def you(self):
        return getattr(self.app.play, "you", {}) or {}

    def scene_name(self):
        return type(self.app.scene).__name__

    def close(self):
        self.app.running = False
        self.app.client.close()
        if self.app.server:
            self.app.server.stop()

    # --------------------------------------------------------- the world ---
    @property
    def world(self):
        """The server's own world, for looking things up while driving.

        Only a test harness may do this; the client itself must never reach
        past the protocol.
        """
        return self.app.server.world

    def me(self):
        return next(iter(self.world.players.values()))

    def level(self):
        return self.world.levels[self.me().depth]

    def path_to(self, tx, ty):
        """Breadth-first over passable ground, ignoring what we remember."""
        from collections import deque
        lv, p = self.level(), self.me()
        start = (p.x, p.y)
        seen = {start: None}
        q = deque([start])
        while q:
            cur = q.popleft()
            if cur == (tx, ty):
                steps = []
                while cur != start:
                    prev = seen[cur]
                    steps.append((cur[0] - prev[0], cur[1] - prev[1]))
                    cur = prev
                return list(reversed(steps))
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    nxt = (cur[0] + dx, cur[1] + dy)
                    if nxt in seen or (dx == 0 and dy == 0):
                        continue
                    if not (0 <= nxt[0] < lv.w and 0 <= nxt[1] < lv.h):
                        continue
                    # A closed door is a step, not a wall: you walk into it
                    # and it opens.
                    from stormhold.game.level import can_walk_through
                    if not can_walk_through(lv, *nxt) and nxt != (tx, ty):
                        continue
                    seen[nxt] = cur
                    q.append(nxt)
        return None

    def walk_to(self, tx, ty, limit=400):
        steps = self.path_to(tx, ty)
        if steps is None:
            return False
        for dx, dy in steps[:limit]:
            self.app.client.send_action_move(dx, dy) if hasattr(
                self.app.client, "send_action_move") else self.app.play.send_action(
                    {"a": "move", "dx": dx, "dy": dy})
            self.step(2)
        self.settle(0.4)
        return (self.me().x, self.me().y) == (tx, ty)


class Guest(Session):
    """A second player joining a session that is already hosting.

    Multiplayer is the whole reason this remake exists, and until now it had
    never been driven: every test drove one client that happened to be its
    own host.
    """

    def __init__(self, port, name="Guest", seed=None, size=(1280, 800)):
        super().__init__(seed=seed, name=name, size=size, port=port)
        self.app.settings["host"] = "127.0.0.1"
        self.app.settings["port"] = port

    def join(self, stats=None, spell="Spark", colour=1):
        from stormhold.ui.app import MenuScene, CharGenScene
        self.app.replace(MenuScene(self.app))
        self.app.start_join()
        self.settle(2.0)
        scene = self.app.scene
        if isinstance(scene, CharGenScene):
            self.click([b for b in scene.buttons if b.action == "go"][0].rect.center)
            self.settle(2.5)
        return self.scene_name()

    @property
    def world(self):
        raise AttributeError("a guest has no world of its own; ask the host")

    def close(self):
        self.app.running = False
        self.app.client.close()
