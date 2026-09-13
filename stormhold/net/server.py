"""The authoritative game server.

It can run on its own (``python -m stormhold --serve``) or inside the same
process as one player's game, which is how the "Host a game" button works.
Because Stormhold is turn-based there is no tick loop: the server sits idle
until somebody does something, then works out the consequences and tells
everyone who can see them. A Raspberry Pi hosting for three players spends
almost all of its time asleep.
"""

import json
import os
import socket
import threading
import time

from ..common.constants import PROTOCOL_VERSION, STATS, START_STAT, START_POINTS, TOWN_DEPTH, chebyshev
from ..game.world import World
from . import protocol as P

MAX_NAME = 14
HEAR_RADIUS = 14
TILE_CHUNK = 1500          # tile triples per packet


def clean_name(raw):
    text = "".join(ch for ch in str(raw or "") if ch.isprintable()).strip()
    return text[:MAX_NAME] or "Adventurer"


def valid_stats(raw):
    """Accept a character sheet only if it spends exactly the points allowed."""
    stats = {}
    for key in STATS:
        try:
            value = int(raw.get(key, START_STAT))
        except (TypeError, ValueError, AttributeError):
            value = START_STAT
        stats[key] = max(3, min(25, value))
    spent = sum(stats.values()) - START_STAT * len(STATS)
    if spent > START_POINTS:
        return {k: START_STAT for k in STATS}
    return stats


class Session:
    def __init__(self, sock, addr, sid):
        self.sock = sock
        self.addr = addr
        self.id = sid
        self.decoder = P.Decoder()
        self.player = None
        self.alive = True
        self.lock = threading.Lock()

    def send(self, kind, data=None):
        if not self.alive:
            return
        try:
            with self.lock:
                self.sock.sendall(P.encode(kind, data))
        except OSError:
            self.alive = False

    def close(self):
        self.alive = False
        try:
            self.sock.close()
        except OSError:
            pass


class GameServer:
    def __init__(self, host="0.0.0.0", port=7777, seed=None, save_path=None,
                 idle_seconds=45.0):
        self.idle_seconds = idle_seconds
        self.host = host
        self.port = port
        self.world = World(seed)
        self.sessions = {}
        self.next_sid = 1
        self.lock = threading.RLock()
        self.running = False
        self.sock = None
        self.save_path = save_path
        self.saves = {}
        self.load_saves()

    # ------------------------------------------------------------ saves ----
    def load_saves(self):
        if not self.save_path or not os.path.exists(self.save_path):
            return
        try:
            with open(self.save_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self.saves = data.get("players", {})
        except (OSError, ValueError) as exc:
            print(f"[stormhold] could not read saves: {exc}")

    def store_save(self, player):
        self.saves[player.name.lower()] = player.to_save()

    def flush_saves(self):
        if not self.save_path:
            return
        try:
            os.makedirs(os.path.dirname(self.save_path) or ".", exist_ok=True)
            tmp = self.save_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump({"version": 1, "seed": self.world.seed,
                           "players": self.saves}, fh, indent=1)
            os.replace(tmp, self.save_path)
        except OSError as exc:
            print(f"[stormhold] save failed: {exc}")

    # ----------------------------------------------------------- serving ---
    def start(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))
        self.sock.listen(8)
        self.running = True
        threading.Thread(target=self._accept_loop, daemon=True, name="accept").start()
        threading.Thread(target=self._watchdog_loop, daemon=True, name="watchdog").start()
        return self

    def _watchdog_loop(self):
        """Once a second, check whether a floor is stuck on somebody who has
        walked away from the keyboard, and let the others carry on."""
        while self.running:
            time.sleep(1.0)
            with self.lock:
                if not any(s.player for s in self.sessions.values()):
                    continue
                self.world.events.clear()
                if self.world.nudge_idle(self.idle_seconds):
                    self.dispatch()

    def stop(self):
        self.running = False
        with self.lock:
            for s in list(self.sessions.values()):
                s.close()
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
        self.flush_saves()

    def _accept_loop(self):
        while self.running:
            try:
                conn, addr = self.sock.accept()
            except OSError:
                break
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            with self.lock:
                sid = self.next_sid
                self.next_sid += 1
                session = Session(conn, addr, sid)
                self.sessions[sid] = session
            threading.Thread(target=self._client_loop, args=(session,),
                             daemon=True, name=f"client-{sid}").start()

    def _client_loop(self, session):
        session.send(P.S_ROSTER, {
            "version": PROTOCOL_VERSION,
            "saves": [{"name": s.get("name"), "level": s.get("level"),
                       "deepest": s.get("deepest", 0)} for s in self.saves.values()],
            "online": [s.player.name for s in self.sessions.values() if s.player],
            "seed": self.world.seed,
        })
        try:
            while self.running and session.alive:
                chunk = session.sock.recv(8192)
                if not chunk:
                    break
                for kind, data in session.decoder.feed(chunk):
                    self.handle(session, kind, data)
        except (OSError, ValueError):
            pass
        finally:
            self.drop(session)

    def drop(self, session):
        with self.lock:
            self.sessions.pop(session.id, None)
            if session.player:
                name = session.player.name
                self.store_save(session.player)
                self.flush_saves()
                self.world.remove_player(session.player.id)
                self.broadcast_msg(f"{name} has left the party.", "info")
        session.close()

    # ---------------------------------------------------------- handling ---
    def handle(self, session, kind, data):
        if kind == P.C_PING:
            session.send(P.S_PONG, {"t": data.get("t", 0)})
            return
        if kind == P.C_HELLO:
            self.handle_hello(session, data)
            return

        with self.lock:
            player = session.player
            if player is None:
                return
            if kind == P.C_ACTION:
                self.world.events.clear()
                self.world.submit(player, data)
                self.dispatch()
            elif kind == P.C_CHAT:
                text = "".join(c for c in str(data.get("text", "")) if c.isprintable())[:160].strip()
                if text:
                    for s in self.sessions.values():
                        if s.player:
                            s.send(P.S_CHAT, {"from": player.name, "text": text})

    def handle_hello(self, session, data):
        with self.lock:
            if session.player is not None:
                return
            if int(data.get("version", 0)) != PROTOCOL_VERSION:
                session.send(P.S_ERROR, {"msg": "This copy of Stormhold is a different "
                                                "version from the server's. Update both."})
                return
            name = clean_name(data.get("name"))
            for s in self.sessions.values():
                if s.player and s.player.name.lower() == name.lower():
                    session.send(P.S_ERROR, {"msg": f"{name} is already in the keep."})
                    return

            save = self.saves.get(name.lower()) if data.get("resume") else None
            stats = valid_stats(data.get("stats") or {})
            colour = int(data.get("colour", 0)) % 6
            player = self.world.add_player(name, stats, colour, save)
            session.player = player

            session.send(P.S_WELCOME, {
                "id": player.id,
                "resumed": bool(save),
                "motd": (f"Welcome back, {name}." if save else
                         f"Welcome to Aldershade, {name}. The keep gate is north of the square."),
            })
            self.send_level(session)
            self.send_inventory(session)
            self.broadcast_msg(f"{name} joins the party.", "good")
            self.push_state()

    # --------------------------------------------------------- dispatching -
    def dispatch(self):
        """Turn the world's event list into per-player packets."""
        world = self.world
        for event in world.events:
            etype = event["t"]
            if etype == "msg":
                for s in self.sessions.values():
                    p = s.player
                    if not p:
                        continue
                    if event["to"] is not None and p.id != event["to"]:
                        continue
                    if event["to"] is None and event["depth"] is not None and p.depth != event["depth"]:
                        continue
                    s.send(P.S_MSG, {"text": event["text"], "kind": event["kind"]})
            elif etype in ("float", "fx", "snd"):
                for s in self.sessions.values():
                    p = s.player
                    if not p or p.depth != event.get("depth"):
                        continue
                    visible = (event["y"] * world.levels[p.depth].w + event["x"]) in p.fov
                    if etype == "snd":
                        if not visible and chebyshev(p.x, p.y, event["x"], event["y"]) > HEAR_RADIUS:
                            continue
                        s.send(P.S_SOUND, {"name": event["name"], "x": event["x"], "y": event["y"]})
                    elif visible:
                        s.send(P.S_FX, {"kind": event.get("kind"), "x": event["x"],
                                        "y": event["y"], "text": event.get("text")})
            elif etype == "inv":
                s = self.session_for(event["to"])
                if s:
                    self.send_inventory(s)
            elif etype == "shop":
                s = self.session_for(event["to"])
                if s and s.player:
                    s.send(P.S_SHOP, world.shop_view(s.player, event["shop"],
                                                     event["npc"], event["name"]))
            elif etype == "level":
                s = self.session_for(event["to"])
                if s:
                    self.send_level(s)
            elif etype == "died":
                s = self.session_for(event["to"])
                if s:
                    s.send(P.S_DIED, {})
        world.events.clear()
        self.push_state()

    def session_for(self, player_id):
        for s in self.sessions.values():
            if s.player and s.player.id == player_id:
                return s
        return None

    def send_level(self, session):
        p = session.player
        level = self.world.levels.get(p.depth)
        if not level:
            return
        session.send(P.S_LEVEL, {"depth": level.depth, "w": level.w, "h": level.h,
                                 "name": level.name, "town": level.is_town})
        self.world.resend_level(p)
        self.flush_tiles(session)

    def flush_tiles(self, session):
        p = session.player
        while p.pending_tiles:
            chunk = p.pending_tiles[:TILE_CHUNK * 3]
            del p.pending_tiles[:TILE_CHUNK * 3]
            session.send(P.S_TILES, {"d": chunk})

    def send_inventory(self, session):
        session.send(P.S_INV, self.world.inventory_view(session.player))

    def push_state(self):
        for s in list(self.sessions.values()):
            if not s.player:
                continue
            self.flush_tiles(s)
            snap = self.world.snapshot_for(s.player)
            if snap:
                s.send(P.S_STATE, snap)

    def broadcast_msg(self, text, kind="info"):
        for s in self.sessions.values():
            if s.player:
                s.send(P.S_MSG, {"text": text, "kind": kind})


def lan_addresses():
    """Best guess at the addresses other machines should type in."""
    found = []
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("8.8.8.8", 80))          # no packets are actually sent
        found.append(probe.getsockname()[0])
        probe.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            addr = info[4][0]
            if not addr.startswith("127.") and addr not in found:
                found.append(addr)
    except OSError:
        pass
    return found
