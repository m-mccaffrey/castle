"""The game window: menus, character creation, and the play screen.

Drawing is deliberately lazy. Stormhold is turn-based, so the screen only needs
redrawing when something actually changed. On a Raspberry Pi the window sits at
a few percent of one core while you think about your next move.
"""

import os
import sys
import time

import pygame

from ..common.constants import (
    DIRS, STATS, STAT_ABBR, START_STAT, START_POINTS, PROTOCOL_VERSION,
    TILE_NAMES, T, SIGHT_DUNGEON, SIGHT_TOWN, chebyshev, xp_for_level,
)
from ..common.fov import compute_fov
from ..net import protocol as P
from ..net.client import GameClient
from . import widgets as W
from .art import SpriteSheet, TILE
from .palette import (BLACK, WHITE, SILVER, GRAY, NAVY, MAROON, GREEN, RED,
                      YELLOW, LIME, AQUA, TEAL, OLIVE, PURPLE, FUCHSIA, BLUE)

SIDEBAR_W = 268
LOG_H = 150
MIN_SIZE = (1024, 700)

MSG_COLOURS = {
    "info": (30, 30, 30), "good": (0, 96, 0), "bad": (150, 0, 0),
    "warn": (140, 90, 0), "combat": (0, 0, 120), "hurt": (170, 0, 0),
    "loot": (0, 90, 120), "kill": (90, 0, 120),
}

FLOAT_COLOURS = {
    "damage": YELLOW, "crit": (255, 160, 0), "hurt": RED,
    "heal": LIME, "miss": SILVER,
}


class Scene:
    def __init__(self, app):
        self.app = app

    def handle(self, event):
        pass

    def update(self, dt):
        pass

    def draw(self, surf):
        pass


# ===========================================================================
#  Opening screen: host a game, or join one.
# ===========================================================================

class MenuScene(Scene):
    def __init__(self, app, message=""):
        super().__init__(app)
        self.message = message
        cx = MIN_SIZE[0] // 2
        self.name = W.TextField((cx - 90, 250, 220, 28), app.settings.get("name", ""), 14)
        self.host = W.TextField((cx - 90, 380, 220, 28), app.settings.get("host", "127.0.0.1"), 24)
        self.port = W.TextField((cx + 140, 380, 70, 28), str(app.settings.get("port", 7777)), 5, numeric=True)
        self.buttons = [
            W.Button((cx - 200, 300, 190, 34), "Host a game", "host"),
            W.Button((cx + 10, 300, 190, 34), "Join a game", "join"),
            W.Button((cx - 200, 430, 190, 34), "How to play", "help"),
            W.Button((cx + 10, 430, 190, 34), "Quit", "quit"),
        ]
        self.name.focused = not self.name.value

    def handle(self, event):
        self.name.handle(event)
        self.host.handle(event)
        self.port.handle(event)
        for b in self.buttons:
            action = b.handle(event)
            if action:
                self.act(action)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            if not any(f.focused for f in (self.name, self.host, self.port)):
                self.act("host")

    def act(self, action):
        name = self.name.value.strip() or "Adventurer"
        self.app.settings["name"] = name
        self.app.settings["host"] = self.host.value.strip()
        self.app.settings["port"] = int(self.port.value or 7777)
        self.app.save_settings()

        if action == "quit":
            self.app.running = False
        elif action == "help":
            self.app.push(HelpScene(self.app))
        elif action == "host":
            self.app.start_host()
        elif action == "join":
            self.app.start_join()

    def draw(self, surf):
        surf.fill((18, 24, 40))
        w, h = surf.get_size()
        cx = w // 2

        title = W.font(46, bold=True).render("STORMHOLD", True, SILVER)
        shadow = W.font(46, bold=True).render("STORMHOLD", True, BLACK)
        surf.blit(shadow, (cx - title.get_width() // 2 + 3, 63))
        surf.blit(title, (cx - title.get_width() // 2, 60))
        sub = W.font(16).render("a co-operative dungeon crawl for the family", True, SILVER)
        surf.blit(sub, (cx - sub.get_width() // 2, 112))

        # A row of the bestiary, as a sign of what is downstairs.
        sheet = self.app.sheet
        show = ["kobold", "goblin", "skeleton", "orc", "dire_wolf", "pale_wraith", "vaelrik"]
        total = len(show) * (TILE + 10)
        x = cx - total // 2
        for key in show:
            img = sheet.creatures.get(key)
            if img:
                surf.blit(img, (x, 150))
            x += TILE + 10

        box = pygame.Rect(cx - 260, 210, 520, 290)
        W.panel(surf, box, raised=True)
        W.text(surf, "Your name", (box.x + 24, 256), 14, bold=True)
        self.name.draw(surf)
        W.text(surf, "Server address", (box.x + 24, 386), 14, bold=True)
        self.host.draw(surf)
        self.port.draw(surf)
        for b in self.buttons:
            b.draw(surf)

        if self.message:
            for i, line in enumerate(W.wrap(self.message, 500, 13)):
                img = W.font(13, bold=True).render(line, True, (150, 0, 0))
                surf.blit(img, (cx - img.get_width() // 2, 512 + i * 17))

        foot = W.font(12).render(
            "Host on one computer, then everyone else picks Join and types that machine's address.",
            True, SILVER)
        surf.blit(foot, (cx - foot.get_width() // 2, h - 34))


# ===========================================================================
#  Character creation. No classes: four numbers and what you do with them.
# ===========================================================================

class CharGenScene(Scene):
    def __init__(self, app, saves=None):
        super().__init__(app)
        self.saves = saves or []
        self.stats = {k: START_STAT for k in STATS}
        self.points = START_POINTS
        self.colour = 0
        self.error = ""
        cx = MIN_SIZE[0] // 2
        self.plus = {}
        self.minus = {}
        for i, stat in enumerate(STATS):
            y = 210 + i * 42
            self.minus[stat] = W.Button((cx - 30, y, 28, 26), "-", ("dec", stat))
            self.plus[stat] = W.Button((cx + 88, y, 28, 26), "+", ("inc", stat))
        self.buttons = [
            W.Button((cx - 210, 470, 180, 34), "Enter the keep", "go"),
            W.Button((cx + 30, 470, 180, 34), "Back", "back"),
        ]
        self.resume_buttons = []
        for i, s in enumerate(self.saves[:6]):
            self.resume_buttons.append(
                W.Button((cx - 210, 530 + i * 30, 420, 26),
                         f"Carry on as {s['name']} (level {s['level']}, reached {s.get('deepest', 0)})",
                         ("resume", s["name"])))

    def handle(self, event):
        for b in list(self.plus.values()) + list(self.minus.values()) + self.buttons + self.resume_buttons:
            action = b.handle(event)
            if not action:
                continue
            if isinstance(action, tuple):
                op, value = action
                if op == "inc" and self.points > 0 and self.stats[value] < 18:
                    self.stats[value] += 1
                    self.points -= 1
                elif op == "dec" and self.stats[value] > START_STAT:
                    self.stats[value] -= 1
                    self.points += 1
                elif op == "resume":
                    self.app.join_as(value, self.stats, self.colour, resume=True)
            elif action == "go":
                self.app.join_as(self.app.settings.get("name", "Adventurer"),
                                 self.stats, self.colour, resume=False)
            elif action == "back":
                self.app.disconnect("")
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                self.app.join_as(self.app.settings.get("name", "Adventurer"),
                                 self.stats, self.colour, resume=False)
            elif event.key == pygame.K_LEFT:
                self.colour = (self.colour - 1) % 6
            elif event.key == pygame.K_RIGHT:
                self.colour = (self.colour + 1) % 6

    def draw(self, surf):
        surf.fill((18, 24, 40))
        w = surf.get_width()
        cx = w // 2
        box = pygame.Rect(cx - 260, 60, 520, 620)
        client = W.window(surf, box, "Create a character")

        W.text(surf, "Stormhold has no character classes.", (client.x + 8, 100), 14, bold=True)
        for i, line in enumerate(W.wrap(
                "Spend your points however you like. Strength carries armour and swings "
                "it hard, Dexterity hits and dodges, Intelligence powers spells, "
                "Constitution keeps you alive. You learn magic from books you find or buy.",
                client.width - 16, 13)):
            W.text(surf, line, (client.x + 8, 122 + i * 17), 13)

        W.text(surf, f"Points left: {self.points}", (cx - 210, 182), 15, bold=True,
               colour=(0, 96, 0) if self.points else (120, 0, 0))

        for i, stat in enumerate(STATS):
            y = 210 + i * 42
            W.text(surf, STAT_ABBR[stat] + "  " + stat.title(), (cx - 210, y + 5), 14, bold=True)
            W.panel(surf, (cx + 2, y, 82, 26), raised=False, fill=WHITE)
            value = str(self.stats[stat])
            img = W.font(15, bold=True, mono=True).render(value, True, BLACK)
            surf.blit(img, (cx + 43 - img.get_width() // 2, y + 5))
            self.minus[stat].enabled = self.stats[stat] > START_STAT
            self.plus[stat].enabled = self.points > 0 and self.stats[stat] < 18
            self.minus[stat].draw(surf)
            self.plus[stat].draw(surf)
            W.text(surf, self.hint(stat), (cx + 124, y + 6), 12, colour=(70, 70, 70))

        W.text(surf, "Colour on the map (left/right arrows)", (cx - 210, 392), 13, bold=True)
        for i in range(6):
            img = self.app.sheet.player(i, "sword", False, False, False)[0]
            spot = pygame.Rect(cx - 210 + i * 44, 412, 40, 40)
            W.panel(surf, spot, raised=i != self.colour)
            surf.blit(img, (spot.x + 4, spot.y + 4))

        for b in self.buttons:
            b.draw(surf)
        if self.resume_buttons:
            W.text(surf, "Or carry on with a character already saved here:",
                   (cx - 210, 512), 13, bold=True)
            for b in self.resume_buttons:
                b.draw(surf)
        if self.error:
            W.text(surf, self.error, (cx - 210, 690), 13, colour=(150, 0, 0), bold=True)

    @staticmethod
    def hint(stat):
        return {
            "strength": "carry more, hit harder",
            "dexterity": "hit more often, harder to hit",
            "intelligence": "more mana, better spells",
            "constitution": "more health, heal faster",
        }[stat]


class HelpScene(Scene):
    KEYS = [
        ("Arrows / numpad / W A S D", "Move. Walk into something to attack it."),
        ("Numpad 1-9", "Move in all eight directions (7 9 1 3 are the diagonals)."),
        ("5 or  .", "Wait one turn."),
        ("G or comma", "Pick up what is under you."),
        ("I", "Open your pack: wear, wield, drink, read, drop."),
        ("Z", "Cast a spell from your book."),
        ("F", "Fire a bow or crossbow at the nearest enemy."),
        ("> and <", "Go down or up a staircase you are standing on."),
        ("C", "Character sheet."),
        ("Enter", "Talk to the rest of the party."),
        ("Click the map", "Step that way, or attack what you clicked."),
        ("Esc", "Close a window, or open the menu."),
    ]

    def handle(self, event):
        if event.type == pygame.KEYDOWN or event.type == pygame.MOUSEBUTTONDOWN:
            self.app.pop()

    def draw(self, surf):
        surf.fill((18, 24, 40))
        w, h = surf.get_size()
        box = pygame.Rect(w // 2 - 340, 40, 680, h - 80)
        client = W.window(surf, box, "How to play Stormhold")
        y = client.y + 6
        for line in W.wrap(
                "Stormhold is turn-based. Nothing in the dungeon moves until you do, so "
                "there is never any hurry. When several of you are playing, the floor's "
                "clock waits for whoever is thinking - it will run on about two turns "
                "without you, then stop and say who it is waiting for.",
                client.width - 12, 14):
            W.text(surf, line, (client.x + 6, y), 14)
            y += 19
        y += 10
        for key, what in self.KEYS:
            W.text(surf, key, (client.x + 10, y), 13, bold=True, mono=True)
            W.text(surf, what, (client.x + 250, y), 13)
            y += 22
        y += 10
        for line in W.wrap(
                "Weight matters. Armour and loot slow you down, and a hundred gold coins "
                "weigh a pound - which is why there is a strongroom in town. If you die "
                "you drop your pack where you fell and wake at the temple, so the party "
                "can go back for it.",
                client.width - 12, 14):
            W.text(surf, line, (client.x + 6, y), 14)
            y += 19
        W.text(surf, "Press any key to go back.", (client.x + 6, client.bottom - 24), 13, bold=True)


# ===========================================================================
#  The play screen.
# ===========================================================================

class MapView:
    """The client's own copy of what it has been told about a floor."""

    def __init__(self, w, h, depth, name, town):
        self.w = w
        self.h = h
        self.depth = depth
        self.name = name
        self.town = town
        self.tiles = bytearray(w * h)
        self.known = bytearray(w * h)

    def apply(self, flat):
        for i in range(0, len(flat) - 2, 3):
            x, y, t = flat[i], flat[i + 1], flat[i + 2]
            if 0 <= x < self.w and 0 <= y < self.h:
                idx = y * self.w + x
                self.tiles[idx] = t
                self.known[idx] = 1


class PlayScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.map = None
        self.actors = []
        self.items = []
        self.you = {}
        self.party = []
        self.waiting_on = None
        self.messages = []
        self.floats = []
        self.effects = []
        self.fov = set()
        self._fov_key = None
        self.terrain_cache = None
        self.terrain_key = None
        self.camera = (0, 0)
        self.target_mode = None       # ("spell", name) while choosing a target
        self.chatting = False
        self.chat_text = ""
        self.dirty = True

    # ------------------------------------------------------------ network --
    def on_message(self, kind, data):
        self.dirty = True
        if kind == P.S_LEVEL:
            self.map = MapView(data["w"], data["h"], data["depth"], data["name"], data["town"])
            self.terrain_cache = None
            self._fov_key = None
            self.add_message(f"You enter {data['name']}." if not data["town"]
                             else "You are back in Aldershade.", "good")
        elif kind == P.S_TILES:
            if self.map:
                self.map.apply(data["d"])
                self.terrain_cache = None
        elif kind == P.S_STATE:
            if self.map is not None and data.get("depth") != self.map.depth:
                # We have changed floor but the new map has not arrived yet.
                # Drawing this against the old map would mix two levels together.
                return
            self.actors = data["actors"]
            self.items = data["items"]
            self.you = data["you"]
            self.party = data["party"]
            self.waiting_on = data.get("waiting")
            self.update_fov()
        elif kind == P.S_MSG:
            self.add_message(data["text"], data.get("kind", "info"))
        elif kind == P.S_FX:
            if data.get("text"):
                self.floats.append({"x": data["x"], "y": data["y"], "text": data["text"],
                                    "kind": data["kind"], "born": time.time()})
            else:
                self.effects.append({"x": data["x"], "y": data["y"],
                                     "kind": data["kind"], "born": time.time()})
        elif kind == P.S_SOUND:
            pass
        elif kind == P.S_INV:
            self.app.inventory = data
        elif kind == P.S_SHOP:
            self.app.push(ShopScene(self.app, data))
        elif kind == P.S_CHAT:
            self.add_message(f"{data['from']}: {data['text']}", "chat")
        elif kind == P.S_DIED:
            self.add_message("You have died. You wake on the temple floor.", "bad")

    def add_message(self, text, kind="info"):
        self.messages.append((text, kind))
        if len(self.messages) > 200:
            del self.messages[:80]

    # -------------------------------------------------------------- vision --
    def update_fov(self):
        if not self.map or not self.you:
            return
        me = self.me()
        if not me:
            return
        radius = SIGHT_TOWN if self.map.town else SIGHT_DUNGEON
        key = (me["x"], me["y"], self.map.depth, radius)
        if key == self._fov_key:
            return
        self._fov_key = key
        compute_fov(self.map, me["x"], me["y"], radius, self.fov)

    def me(self):
        my_id = self.you.get("id")
        for a in self.actors:
            if a["id"] == my_id:
                return a
        return None

    # --------------------------------------------------------------- input --
    MOVE_KEYS = {
        pygame.K_UP: (0, -1), pygame.K_DOWN: (0, 1),
        pygame.K_LEFT: (-1, 0), pygame.K_RIGHT: (1, 0),
        pygame.K_w: (0, -1), pygame.K_s: (0, 1),
        pygame.K_a: (-1, 0), pygame.K_d: (1, 0),
        pygame.K_KP8: (0, -1), pygame.K_KP2: (0, 1),
        pygame.K_KP4: (-1, 0), pygame.K_KP6: (1, 0),
        pygame.K_KP7: (-1, -1), pygame.K_KP9: (1, -1),
        pygame.K_KP1: (-1, 1), pygame.K_KP3: (1, 1),
    }

    def handle(self, event):
        if self.chatting:
            self.handle_chat(event)
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.click_map(event.pos)
            return
        if event.type != pygame.KEYDOWN:
            return

        key = event.key
        self.dirty = True

        if self.target_mode and key == pygame.K_ESCAPE:
            self.target_mode = None
            self.add_message("Never mind.", "info")
            return

        if key in self.MOVE_KEYS:
            dx, dy = self.MOVE_KEYS[key]
            self.send_action({"a": "move", "dx": dx, "dy": dy})
        elif key in (pygame.K_KP5, pygame.K_PERIOD) and not (event.mod & pygame.KMOD_SHIFT):
            self.send_action({"a": "wait"})
        elif key in (pygame.K_g, pygame.K_COMMA):
            self.send_action({"a": "pickup"})
        elif key == pygame.K_i:
            self.app.push(PackScene(self.app))
        elif key == pygame.K_z:
            self.app.push(SpellScene(self.app, self))
        elif key == pygame.K_c:
            self.app.push(SheetScene(self.app))
        elif key == pygame.K_f:
            self.fire_at_nearest()
        elif key == pygame.K_PERIOD and (event.mod & pygame.KMOD_SHIFT):
            self.send_action({"a": "stairs"})
        elif key == pygame.K_COMMA and (event.mod & pygame.KMOD_SHIFT):
            self.send_action({"a": "stairs"})
        elif key == pygame.K_RETURN:
            self.chatting = True
            self.chat_text = ""
        elif key == pygame.K_ESCAPE:
            self.app.push(MenuOverlay(self.app))
        elif key == pygame.K_F1:
            self.app.push(HelpScene(self.app))

    def handle_chat(self, event):
        if event.type != pygame.KEYDOWN:
            return
        self.dirty = True
        if event.key == pygame.K_RETURN:
            if self.chat_text.strip():
                self.app.client.send(P.C_CHAT, {"text": self.chat_text.strip()})
            self.chatting = False
            self.chat_text = ""
        elif event.key == pygame.K_ESCAPE:
            self.chatting = False
            self.chat_text = ""
        elif event.key == pygame.K_BACKSPACE:
            self.chat_text = self.chat_text[:-1]
        elif event.unicode and event.unicode.isprintable() and len(self.chat_text) < 120:
            self.chat_text += event.unicode

    def send_action(self, action):
        self.app.client.send(P.C_ACTION, action)

    def fire_at_nearest(self):
        me = self.me()
        if not me:
            return
        best, best_d = None, 99
        for a in self.actors:
            if a["k"] != "monster":
                continue
            d = chebyshev(a["x"], a["y"], me["x"], me["y"])
            if d < best_d:
                best, best_d = a, d
        if best is None:
            self.add_message("Nothing in sight to shoot at.", "info")
            return
        self.send_action({"a": "shoot", "x": best["x"], "y": best["y"]})

    def click_map(self, pos):
        cell = self.screen_to_tile(pos)
        if cell is None:
            return
        tx, ty = cell
        me = self.me()
        if not me:
            return
        if self.target_mode:
            kind, name = self.target_mode
            self.target_mode = None
            self.send_action({"a": "cast", "spell": name, "x": tx, "y": ty})
            return
        dx = (tx > me["x"]) - (tx < me["x"])
        dy = (ty > me["y"]) - (ty < me["y"])
        if dx or dy:
            self.send_action({"a": "move", "dx": dx, "dy": dy})

    def begin_target(self, spell_name, spell):
        if spell.get("rng", 0) == 0:
            self.send_action({"a": "cast", "spell": spell_name})
            return
        self.target_mode = ("spell", spell_name)
        self.add_message(f"Click a target for {spell_name}, or press Esc.", "info")

    # ------------------------------------------------------------- drawing --
    def viewport(self, surf):
        return pygame.Rect(0, 0, surf.get_width() - SIDEBAR_W, surf.get_height() - LOG_H)

    def screen_to_tile(self, pos):
        surf = pygame.display.get_surface()
        view = self.viewport(surf)
        if not view.collidepoint(pos):
            return None
        cx, cy = self.camera
        tx = (pos[0] - view.x) // TILE + cx
        ty = (pos[1] - view.y) // TILE + cy
        if self.map and 0 <= tx < self.map.w and 0 <= ty < self.map.h:
            return int(tx), int(ty)
        return None

    def draw(self, surf):
        surf.fill(W.FACE)
        view = self.viewport(surf)
        self.draw_map(surf, view)
        self.draw_sidebar(surf)
        self.draw_log(surf)

    def draw_map(self, surf, view):
        pygame.draw.rect(surf, BLACK, view)
        if not self.map or not self.you:
            return
        me = self.me()
        cols = view.width // TILE
        rows = view.height // TILE
        if me:
            cx = max(0, min(self.map.w - cols, me["x"] - cols // 2))
            cy = max(0, min(self.map.h - rows, me["y"] - rows // 2))
        else:
            cx = cy = 0
        if self.map.w <= cols:
            cx = -(cols - self.map.w) // 2
        if self.map.h <= rows:
            cy = -(rows - self.map.h) // 2
        self.camera = (cx, cy)

        sheet = self.app.sheet
        clip = surf.get_clip()
        surf.set_clip(view)

        for ry in range(rows + 1):
            for rx in range(cols + 1):
                mx, my = cx + rx, cy + ry
                if not (0 <= mx < self.map.w and 0 <= my < self.map.h):
                    continue
                idx = my * self.map.w + mx
                if not self.map.known[idx]:
                    continue
                tile = self.map.tiles[idx]
                if tile == T.VOID:
                    continue
                img = sheet.terrain.get(TILE_NAMES.get(tile, "floor"))
                if img is None:
                    continue
                px = view.x + rx * TILE
                py = view.y + ry * TILE
                surf.blit(img, (px, py))
                if idx not in self.fov:
                    shade = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
                    shade.fill((0, 0, 24, 150))
                    surf.blit(shade, (px, py))

        for it in self.items:
            if not (cx <= it["x"] < cx + cols + 1 and cy <= it["y"] < cy + rows + 1):
                continue
            img = sheet.item(it["icon"])
            if img:
                surf.blit(img, (view.x + (it["x"] - cx) * TILE, view.y + (it["y"] - cy) * TILE))

        my_id = self.you.get("id")
        for a in sorted(self.actors, key=lambda a: a["y"]):
            px = view.x + (a["x"] - cx) * TILE
            py = view.y + (a["y"] - cy) * TILE
            if not view.collidepoint(px + 2, py + 2):
                continue
            if a["k"] == "player":
                img, flipped = sheet.player(a.get("c", 0), a.get("w"), a.get("sh"),
                                            a.get("hm"), a.get("rb"))
                if a.get("f", 4) in (5, 6, 7):
                    img = flipped
            else:
                key = a.get("s", "kobold")
                img = (sheet.creatures_flipped if a.get("f", 4) in (5, 6, 7)
                       else sheet.creatures).get(key)
            if img:
                surf.blit(img, (px, py))

            if a["k"] == "monster" and a["hp"] < a["mhp"]:
                frac = a["hp"] / max(1, a["mhp"])
                pygame.draw.rect(surf, BLACK, (px + 2, py - 5, TILE - 4, 5))
                pygame.draw.rect(surf, RED if frac < 0.5 else (200, 60, 60),
                                 (px + 3, py - 4, int((TILE - 6) * frac), 3))
            if a["k"] == "player":
                name = a["n"] + (" (you)" if a["id"] == my_id else "")
                img2 = W.font(11, bold=True).render(name, True, WHITE)
                sh = W.font(11, bold=True).render(name, True, BLACK)
                nx = px + TILE // 2 - img2.get_width() // 2
                surf.blit(sh, (nx + 1, py - 14))
                surf.blit(img2, (nx, py - 15))

        now = time.time()
        self.effects = [e for e in self.effects if now - e["born"] < 0.35]
        for e in self.effects:
            px = view.x + (e["x"] - cx) * TILE + TILE // 2
            py = view.y + (e["y"] - cy) * TILE + TILE // 2
            k = e["kind"]
            colour = {"hit": YELLOW, "miss": SILVER, "bolt": AQUA, "blast": (255, 140, 0),
                      "death": RED, "heal": LIME, "burning": (255, 120, 0),
                      "poisoned": LIME}.get(k, WHITE)
            radius = int(TILE * 0.55 * (1 - (now - e["born"]) / 0.35)) + 4
            pygame.draw.circle(surf, colour, (px, py), radius, 3)

        self.floats = [f for f in self.floats if now - f["born"] < 1.1]
        for f in self.floats:
            age = now - f["born"]
            px = view.x + (f["x"] - cx) * TILE + TILE // 2
            py = view.y + (f["y"] - cy) * TILE - int(age * 26)
            colour = FLOAT_COLOURS.get(f["kind"], WHITE)
            img = W.font(15, bold=True, mono=True).render(f["text"], True, colour)
            sh = W.font(15, bold=True, mono=True).render(f["text"], True, BLACK)
            surf.blit(sh, (px - img.get_width() // 2 + 1, py + 1))
            surf.blit(img, (px - img.get_width() // 2, py))

        surf.set_clip(clip)

        if self.target_mode:
            label = W.font(15, bold=True).render(
                f"Click a target for {self.target_mode[1]}  (Esc to cancel)", True, YELLOW)
            box = pygame.Rect(view.centerx - label.get_width() // 2 - 8, view.y + 8,
                              label.get_width() + 16, 26)
            pygame.draw.rect(surf, (20, 20, 30), box)
            pygame.draw.rect(surf, YELLOW, box, 1)
            surf.blit(label, (box.x + 8, box.y + 5))

        if self.waiting_on and self.waiting_on != self.you.get("id"):
            who = next((p["n"] for p in self.party if p["id"] == self.waiting_on), "someone")
            label = W.font(15, bold=True).render(f"Waiting for {who}...", True, WHITE)
            box = pygame.Rect(view.centerx - label.get_width() // 2 - 10, view.bottom - 40,
                              label.get_width() + 20, 28)
            pygame.draw.rect(surf, (30, 30, 60), box)
            W.bevel(surf, box, raised=True, width=1)
            surf.blit(label, (box.x + 10, box.y + 6))

    def draw_sidebar(self, surf):
        x = surf.get_width() - SIDEBAR_W
        rect = pygame.Rect(x, 0, SIDEBAR_W, surf.get_height())
        W.panel(surf, rect, raised=True)
        you = self.you
        if not you:
            return
        pad = x + 10
        width = SIDEBAR_W - 20
        y = 10

        W.text(surf, you.get("name", ""), (pad, y), 17, bold=True)
        W.text_right(surf, f"Level {you.get('level', 1)}", x + SIDEBAR_W - 10, y + 3, 13)
        y += 26

        hp, mhp = you.get("hp", 0), max(1, you.get("max_hp", 1))
        W.bar(surf, (pad, y, width, 18), hp / mhp, (176, 32, 32), f"{hp} / {mhp}   health")
        y += 22
        mana, mmana = you.get("mana", 0), max(1, you.get("max_mana", 1))
        W.bar(surf, (pad, y, width, 18), mana / mmana, (40, 72, 176), f"{mana} / {mmana}   mana")
        y += 22
        level = you.get("level", 1)
        need = xp_for_level(level)
        prev = xp_for_level(level - 1) if level > 1 else 0
        span = max(1, need - prev)
        W.bar(surf, (pad, y, width, 13), (you.get("xp", 0) - prev) / span,
              (110, 60, 150), f"{you.get('xp', 0)} xp")
        y += 22

        stats = you.get("stats", {})
        base = you.get("base_stats", {})
        for i, stat in enumerate(STATS):
            col = pad + (i % 2) * (width // 2)
            row = y + (i // 2) * 18
            value = stats.get(stat, 10)
            colour = (0, 96, 0) if value > base.get(stat, value) else (
                (150, 0, 0) if value < base.get(stat, value) else BLACK)
            W.text(surf, f"{STAT_ABBR[stat]} {value:2d}", (col, row), 13, bold=True, colour=colour, mono=True)
        y += 44

        W.text(surf, f"Armour {you.get('ac', 0)}", (pad, y), 13, mono=True)
        W.text(surf, f"To hit {you.get('to_hit', 0):+d}", (pad + width // 2, y), 13, mono=True)
        y += 20

        weight, capacity = you.get("weight", 0), max(1, you.get("capacity", 1))
        enc = you.get("encumbrance", "Unencumbered")
        enc_colour = {"Unencumbered": (0, 96, 0), "Burdened": (110, 90, 0),
                      "Stressed": (150, 80, 0)}.get(enc, (150, 0, 0))
        W.bar(surf, (pad, y, width, 15), weight / capacity, enc_colour,
              f"{weight/10:.1f} / {capacity/10:.0f} lb")
        y += 18
        W.text(surf, enc, (pad, y), 12, bold=True, colour=enc_colour)
        W.text_right(surf, f"{you.get('gold', 0)} gold", x + SIDEBAR_W - 10, y, 12, bold=True)
        y += 22

        depth = you.get("depth", 0)
        W.text(surf, "Aldershade" if depth == 0 else f"Keep, level {depth}",
               (pad, y), 13, bold=True)
        y += 22

        effects = you.get("effects", {})
        if effects:
            W.text(surf, "  ".join(sorted(effects.keys())), (pad, y), 11, colour=(90, 0, 120))
            y += 18

        y += 4
        pygame.draw.line(surf, W.FACE_SHADOW, (pad, y), (pad + width, y))
        y += 6
        W.text(surf, "PARTY", (pad, y), 11, bold=True)
        y += 16
        for p in self.party:
            here = p["d"] == depth
            name = p["n"]
            colour = BLACK if here else GRAY
            W.text(surf, name[:12], (pad, y), 12, bold=True, colour=colour)
            frac = p["hp"] / max(1, p["mhp"])
            W.bar(surf, (pad + 96, y + 2, width - 96, 10), frac,
                  (176, 32, 32) if here else GRAY)
            if not here:
                W.text(surf, "town" if p["d"] == 0 else f"lv{p['d']}",
                       (pad + 96, y + 13), 10, colour=GRAY)
                y += 12
            y += 18

        hint_y = surf.get_height() - LOG_H - 78
        pygame.draw.line(surf, W.FACE_SHADOW, (pad, hint_y - 6), (pad + width, hint_y - 6))
        for i, line in enumerate(["I pack    Z spells    C sheet",
                                  "G pick up    F fire    > stairs",
                                  "Enter chat    F1 help    Esc menu"]):
            W.text(surf, line, (pad, hint_y + i * 15), 11, mono=True, colour=(70, 70, 70))

    def draw_log(self, surf):
        rect = pygame.Rect(0, surf.get_height() - LOG_H, surf.get_width() - SIDEBAR_W, LOG_H)
        W.panel(surf, rect, raised=True)
        inner = rect.inflate(-10, -10)
        W.panel(surf, inner, raised=False, fill=(240, 240, 236))

        lines = []
        for text, kind in self.messages[-40:]:
            for i, part in enumerate(W.wrap(text, inner.width - 14, 13)):
                lines.append((part, kind))
        visible = (inner.height - 8) // 17
        for i, (text, kind) in enumerate(lines[-visible:]):
            W.text(surf, text, (inner.x + 6, inner.y + 4 + i * 17), 13,
                   colour=MSG_COLOURS.get(kind, BLACK))

        if self.chatting:
            box = pygame.Rect(inner.x, inner.bottom - 24, inner.width, 24)
            W.panel(surf, box, raised=False, fill=WHITE)
            W.text(surf, "Say: " + self.chat_text + "_", (box.x + 6, box.y + 4), 13, mono=True)


# ===========================================================================
#  Overlay windows
# ===========================================================================

class OverlayScene(Scene):
    """A modal window drawn on top of the play screen."""

    title = "Window"
    size = (700, 520)

    def __init__(self, app):
        super().__init__(app)
        self.buttons = []

    def close(self):
        self.app.pop()

    def handle(self, event):
        for b in self.buttons:
            action = b.handle(event)
            if action:
                self.on_action(action)
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE,):
            self.close()

    def on_action(self, action):
        if action == "close":
            self.close()

    def frame(self, surf):
        w, h = surf.get_size()
        rect = pygame.Rect(w // 2 - self.size[0] // 2, h // 2 - self.size[1] // 2, *self.size)
        dim = pygame.Surface((w, h), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 110))
        surf.blit(dim, (0, 0))
        return W.window(surf, rect, self.title), rect


class PackScene(OverlayScene):
    title = "Pack and equipment"
    size = (760, 560)

    def __init__(self, app):
        super().__init__(app)
        self.list = W.ListBox((0, 0, 10, 10), row_height=36)
        self.slot_rects = []
        self.selected_item = None
        self.buttons = []

    def rows(self):
        return self.app.inventory.get("items", [])

    def handle(self, event):
        index = self.list.handle(event)
        if index is not None:
            self.selected_item = self.rows()[index]
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for rect, slot, item in self.slot_rects:
                if rect.collidepoint(event.pos) and item:
                    self.selected_item = item
                    self.app.act({"a": "unequip", "slot": slot})
                    return
        super().handle(event)

    def on_action(self, action):
        item = self.selected_item
        if action == "close":
            self.close()
        elif item and action in ("use", "drop"):
            self.app.act({"a": action, "id": item["id"]})
            if action == "drop":
                self.selected_item = None

    def draw(self, surf):
        self.app.scene_under.draw(surf)
        client, _ = self.frame(surf)

        left = pygame.Rect(client.x, client.y, 300, client.height - 46)
        W.text(surf, "Worn", (left.x, left.y), 13, bold=True)
        self.slot_rects = []
        equipment = self.app.inventory.get("equipment", {})
        y = left.y + 20
        from ..common.constants import SLOTS, SLOT_LABELS
        for slot in SLOTS:
            item = equipment.get(slot)
            rect = pygame.Rect(left.x, y, left.width, 26)
            W.panel(surf, rect, raised=bool(item), fill=W.FACE if item else (200, 200, 196))
            W.text(surf, SLOT_LABELS[slot], (rect.x + 6, rect.y + 6), 12, colour=(80, 80, 80))
            if item:
                img = self.app.sheet.item(item["icon"])
                if img:
                    surf.blit(pygame.transform.smoothscale(img, (20, 20)), (rect.x + 88, rect.y + 3))
                name = item["name"]
                colour = (150, 0, 0) if item.get("cursed") else BLACK
                W.text(surf, name[:26], (rect.x + 112, rect.y + 6), 12, colour=colour)
            self.slot_rects.append((rect, slot, item))
            y += 27

        right = pygame.Rect(client.x + 316, client.y, client.width - 316, client.height - 150)
        inv = self.app.inventory
        W.text(surf, f"Carried  ({inv.get('weight', 0)/10:.1f} lb of "
                     f"{inv.get('capacity', 1)/10:.0f} lb)", (right.x, right.y), 13, bold=True)
        self.list.rect = pygame.Rect(right.x, right.y + 20, right.width, right.height - 20)
        sheet = self.app.sheet

        def draw_row(target, item, rect, selected):
            img = sheet.item(item["icon"])
            if img:
                target.blit(pygame.transform.smoothscale(img, (26, 26)), (rect.x + 3, rect.y + 4))
            colour = WHITE if selected else ((150, 0, 0) if item.get("cursed") else BLACK)
            W.text(target, item["name"][:40], (rect.x + 34, rect.y + 3), 13, colour=colour, bold=True)
            W.text(target, item["desc"][:52], (rect.x + 34, rect.y + 19), 11,
                   colour=SILVER if selected else (90, 90, 90))

        self.list.draw(surf, self.rows(), draw_row)

        detail = pygame.Rect(right.x, client.bottom - 126, right.width, 78)
        W.panel(surf, detail, raised=False, fill=(240, 240, 236))
        item = self.selected_item
        if item:
            W.text(surf, item["name"], (detail.x + 8, detail.y + 6), 14, bold=True)
            for i, line in enumerate(W.wrap(item["desc"], detail.width - 16, 12)):
                W.text(surf, line, (detail.x + 8, detail.y + 26 + i * 15), 12)
            W.text(surf, f"worth about {max(1, item['value'] // 2)} gold in town",
                   (detail.x + 8, detail.bottom - 18), 11, colour=(90, 90, 90))
        else:
            W.text(surf, "Pick something up to see what it is.",
                   (detail.x + 8, detail.y + 8), 13, colour=(90, 90, 90))

        by = client.bottom - 36
        label = "Use"
        if item:
            if item.get("slot"):
                label = "Wear / wield"
            elif item.get("spell"):
                label = "Study"
            elif item.get("kind") == "potion":
                label = "Drink"
            elif item.get("kind") == "scroll":
                label = "Read"
        self.buttons = [
            W.Button((client.x + 316, by, 150, 30), label, "use", enabled=bool(item)),
            W.Button((client.x + 476, by, 110, 30), "Drop", "drop", enabled=bool(item)),
            W.Button((client.right - 110, by, 100, 30), "Close", "close"),
        ]
        for b in self.buttons:
            b.draw(surf)
        W.text(surf, "Click a worn item to take it off.", (client.x, by + 8), 11, colour=(90, 90, 90))


class SpellScene(OverlayScene):
    title = "Spell book"
    size = (620, 500)

    def __init__(self, app, play):
        super().__init__(app)
        self.play = play
        self.list = W.ListBox((0, 0, 10, 10), row_height=34)
        self.selected = None

    def rows(self):
        from ..game.spells import SPELLS
        known = self.app.play.you.get("spells", [])
        return [(name, SPELLS[name]) for name in known if name in SPELLS]

    def handle(self, event):
        index = self.list.handle(event)
        if index is not None:
            self.selected = self.rows()[index]
        if event.type == pygame.KEYDOWN and pygame.K_1 <= event.key <= pygame.K_9:
            i = event.key - pygame.K_1
            rows = self.rows()
            if i < len(rows):
                self.selected = rows[i]
                self.cast()
                return
        super().handle(event)

    def on_action(self, action):
        if action == "cast":
            self.cast()
        else:
            super().on_action(action)

    def cast(self):
        if not self.selected:
            return
        name, spell = self.selected
        if self.app.play.you.get("mana", 0) < spell["mana"]:
            self.app.play.add_message("You have not the mana for that.", "warn")
            return
        self.close()
        self.play.begin_target(name, spell)

    def draw(self, surf):
        self.app.scene_under.draw(surf)
        client, _ = self.frame(surf)
        rows = self.rows()
        you = self.app.play.you

        if not rows:
            W.text(surf, "You know no spells yet.", (client.x + 8, client.y + 10), 15, bold=True)
            for i, line in enumerate(W.wrap(
                    "Magic comes from books. The Gilded Retort in Aldershade sells tomes, "
                    "and they turn up in the keep. Read one and the spell is yours for good, "
                    "provided you are experienced and clever enough for it.",
                    client.width - 16, 13)):
                W.text(surf, line, (client.x + 8, client.y + 36 + i * 17), 13)
        else:
            W.text(surf, f"Mana {you.get('mana', 0)} of {you.get('max_mana', 0)}",
                   (client.x + 8, client.y + 4), 13, bold=True)
            self.list.rect = pygame.Rect(client.x, client.y + 24, client.width, client.height - 110)

            def draw_row(target, row, rect, selected):
                name, spell = row
                affordable = you.get("mana", 0) >= spell["mana"]
                colour = WHITE if selected else (BLACK if affordable else GRAY)
                W.text(target, name, (rect.x + 6, rect.y + 3), 14, bold=True, colour=colour)
                W.text(target, spell["school"], (rect.x + 190, rect.y + 4), 12,
                       colour=SILVER if selected else (90, 90, 90))
                W.text(target, f"{spell['mana']} mana", (rect.x + 280, rect.y + 4), 12,
                       colour=SILVER if selected else (0, 0, 140))
                W.text(target, spell["desc"][:46], (rect.x + 6, rect.y + 19), 11,
                       colour=SILVER if selected else (90, 90, 90))

            self.list.draw(surf, rows, draw_row)

        self.buttons = [
            W.Button((client.x, client.bottom - 36, 170, 30), "Cast", "cast",
                     enabled=bool(self.selected)),
            W.Button((client.right - 110, client.bottom - 36, 100, 30), "Close", "close"),
        ]
        for b in self.buttons:
            b.draw(surf)
        W.text(surf, "Press 1-9 to cast straight from this list.",
               (client.x + 186, client.bottom - 28), 11, colour=(90, 90, 90))


class SheetScene(OverlayScene):
    title = "Character"
    size = (520, 480)

    def draw(self, surf):
        self.app.scene_under.draw(surf)
        client, _ = self.frame(surf)
        you = self.app.play.you
        y = client.y + 6
        W.text(surf, you.get("name", ""), (client.x + 6, y), 20, bold=True)
        y += 32
        rows = [
            ("Level", you.get("level", 1)),
            ("Experience", you.get("xp", 0)),
            ("Next level at", xp_for_level(you.get("level", 1))),
            ("", ""),
            ("Health", f"{you.get('hp', 0)} of {you.get('max_hp', 0)}"),
            ("Mana", f"{you.get('mana', 0)} of {you.get('max_mana', 0)}"),
            ("Armour class", you.get("ac", 0)),
            ("To hit", f"{you.get('to_hit', 0):+d}"),
            ("", ""),
            ("Carrying", f"{you.get('weight', 0)/10:.1f} lb of {you.get('capacity', 1)/10:.0f} lb"),
            ("Burden", you.get("encumbrance", "")),
            ("Gold on you", you.get("gold", 0)),
            ("Gold in the strongroom", you.get("bank", 0)),
            ("", ""),
            ("Deepest level reached", you.get("deepest", 0)),
            ("Creatures slain", you.get("kills", 0)),
            ("Times killed", you.get("deaths", 0)),
        ]
        for label, value in rows:
            if label:
                W.text(surf, label, (client.x + 6, y), 13)
                W.text_right(surf, value, client.right - 6, y, 13, bold=True, mono=True)
            y += 19
        y += 6
        stats = you.get("stats", {})
        for stat in STATS:
            W.text(surf, stat.title(), (client.x + 6, y), 13)
            W.text_right(surf, stats.get(stat, 10), client.right - 6, y, 13, bold=True, mono=True)
            y += 19
        self.buttons = [W.Button((client.right - 110, client.bottom - 36, 100, 30), "Close", "close")]
        for b in self.buttons:
            b.draw(surf)


class MenuOverlay(OverlayScene):
    title = "Stormhold"
    size = (360, 230)

    def draw(self, surf):
        self.app.scene_under.draw(surf)
        client, _ = self.frame(surf)
        self.buttons = [
            W.Button((client.x + 20, client.y + 14, client.width - 40, 32), "Back to the game", "close"),
            W.Button((client.x + 20, client.y + 56, client.width - 40, 32), "How to play", "help"),
            W.Button((client.x + 20, client.y + 98, client.width - 40, 32), "Leave the keep", "leave"),
        ]
        for b in self.buttons:
            b.draw(surf)
        W.text(surf, "Your character is saved automatically.",
               (client.x + 20, client.y + 140), 12, colour=(90, 90, 90))

    def on_action(self, action):
        if action == "close":
            self.close()
        elif action == "help":
            self.app.push(HelpScene(self.app))
        elif action == "leave":
            self.app.disconnect("")


class ShopScene(OverlayScene):
    size = (820, 560)

    SHOP_BLURB = {
        "weaponsmith": "Bolgar keeps the edged goods. He buys anything, at his price.",
        "armourer": "Hesta fits plate to people who can carry it, and leather to people who cannot.",
        "general": "Pell sells the dull, necessary things. Buy torches.",
        "magic": "The Gilded Retort: potions, scrolls, and tomes to learn spells from.",
        "sage": "Ulric will tell you what a thing really is, for a fee.",
        "temple": "The Quiet Hour will mend you, cleanse you, and break a curse.",
        "bank": "The strongroom. Gold weighs a pound the hundred - leave it here.",
    }

    def __init__(self, app, data):
        super().__init__(app)
        self.data = data
        self.title = data.get("name", "Shop")
        self.mode = "buy"
        self.buy_list = W.ListBox((0, 0, 10, 10), row_height=34)
        self.sell_list = W.ListBox((0, 0, 10, 10), row_height=34)
        self.selected_buy = None
        self.selected_sell = None
        self.amount = W.TextField((0, 0, 110, 26), "100", 6, numeric=True)

    @property
    def shop(self):
        return self.data.get("shop", "general")

    def refresh(self, data):
        self.data = data

    def handle(self, event):
        self.amount.handle(event)
        i = self.buy_list.handle(event)
        if i is not None and i < len(self.data.get("stock", [])):
            self.selected_buy = self.data["stock"][i]
        j = self.sell_list.handle(event)
        if j is not None and j < len(self.data.get("sell", [])):
            self.selected_sell = self.data["sell"][j]
        super().handle(event)

    def on_action(self, action):
        npc = self.data.get("npc")
        if action == "close":
            self.close()
        elif action == "buy" and self.selected_buy:
            self.app.act({"a": "buy", "shop": self.shop, "id": self.selected_buy["id"],
                          "npc": npc, "name": self.data.get("name")})
            self.selected_buy = None
        elif action == "sell" and self.selected_sell:
            self.app.act({"a": "sell", "shop": self.shop, "id": self.selected_sell["id"],
                          "npc": npc, "name": self.data.get("name")})
            self.selected_sell = None
        elif action == "identify" and self.selected_sell:
            self.app.act({"a": "service", "what": "identify", "id": self.selected_sell["id"]})
        elif action in ("heal", "uncurse"):
            self.app.act({"a": "service", "what": action})
        elif action in ("deposit", "withdraw"):
            try:
                amount = int(self.amount.value or 0)
            except ValueError:
                amount = 0
            self.app.act({"a": "service", "what": action, "amount": amount})

    def draw(self, surf):
        self.app.scene_under.draw(surf)
        client, _ = self.frame(surf)
        sheet = self.app.sheet
        data = self.data

        W.text(surf, self.SHOP_BLURB.get(self.shop, ""), (client.x + 4, client.y + 2), 12,
               colour=(70, 70, 70))
        W.text_right(surf, f"You have {data.get('gold', 0)} gold", client.right - 4,
                     client.y + 2, 13, bold=True)

        col_w = (client.width - 20) // 2
        top = client.y + 24
        list_h = client.height - 130

        def row_drawer(price_key):
            def draw_row(target, item, rect, selected):
                img = sheet.item(item["icon"])
                if img:
                    target.blit(pygame.transform.smoothscale(img, (24, 24)), (rect.x + 3, rect.y + 4))
                colour = WHITE if selected else BLACK
                W.text(target, item["name"][:32], (rect.x + 32, rect.y + 2), 13, bold=True, colour=colour)
                W.text(target, item["desc"][:44], (rect.x + 32, rect.y + 18), 11,
                       colour=SILVER if selected else (90, 90, 90))
                W.text_right(target, f"{item[price_key]}g", rect.right - 6, rect.y + 8, 12,
                             bold=True, colour=WHITE if selected else (110, 70, 0))
            return draw_row

        if self.shop != "bank":
            W.text(surf, "For sale", (client.x, top), 13, bold=True)
            self.buy_list.rect = pygame.Rect(client.x, top + 18, col_w, list_h)
            self.buy_list.draw(surf, data.get("stock", []), row_drawer("price"))

            W.text(surf, "Your pack", (client.x + col_w + 20, top), 13, bold=True)
            self.sell_list.rect = pygame.Rect(client.x + col_w + 20, top + 18, col_w, list_h)
            self.sell_list.draw(surf, data.get("sell", []), row_drawer("price"))
        else:
            W.text(surf, "The strongroom", (client.x, top), 15, bold=True)
            W.text(surf, f"On you:        {data.get('gold', 0)} gold "
                         f"({data.get('gold', 0)/100:.1f} lb to carry)",
                   (client.x, top + 30), 14, mono=True)
            W.text(surf, f"In the vault:  {data.get('bank', 0)} gold  (weighs you nothing)",
                   (client.x, top + 52), 14, mono=True)
            for i, line in enumerate(W.wrap(
                    "A hundred coins weigh a pound. Carrying a fortune into the keep will "
                    "slow you to a crawl, and if you die down there you drop a fifth of it "
                    "on the floor. Leave it here.", client.width - 20, 13)):
                W.text(surf, line, (client.x, top + 86 + i * 17), 13, colour=(70, 70, 70))
            W.text(surf, "Amount", (client.x, top + 150), 13, bold=True)
            self.amount.rect = pygame.Rect(client.x + 70, top + 146, 110, 26)
            self.amount.draw(surf)

        by = client.bottom - 38
        self.buttons = []
        if self.shop == "bank":
            self.buttons += [
                W.Button((client.x, by, 150, 30), "Deposit", "deposit"),
                W.Button((client.x + 160, by, 150, 30), "Withdraw", "withdraw"),
            ]
        else:
            self.buttons += [
                W.Button((client.x, by, 150, 30), "Buy", "buy", enabled=bool(self.selected_buy)),
                W.Button((client.x + col_w + 20, by, 150, 30), "Sell", "sell",
                         enabled=bool(self.selected_sell)),
            ]
            if self.shop == "sage":
                self.buttons.append(W.Button((client.x + col_w + 180, by, 190, 30),
                                             f"Identify ({data.get('identify_price', 0)}g)",
                                             "identify", enabled=bool(self.selected_sell)))
            if self.shop == "temple":
                self.buttons.append(W.Button((client.x + 160, by, 170, 30),
                                             f"Heal ({data.get('heal_price', 0)}g)", "heal"))
                self.buttons.append(W.Button((client.x + col_w + 180, by, 200, 30),
                                             f"Uncurse ({data.get('uncurse_price', 0)}g)", "uncurse"))
        self.buttons.append(W.Button((client.right - 100, by, 90, 30), "Leave", "close"))
        for b in self.buttons:
            b.draw(surf)


# ===========================================================================
#  The application
# ===========================================================================

class App:
    def __init__(self, args):
        self.args = args
        pygame.init()
        try:
            pygame.mixer.quit()          # no sound files; keeps ALSA quiet on a Pi
        except Exception:
            pass
        pygame.display.set_caption("Stormhold")
        flags = pygame.RESIZABLE
        if args.fullscreen:
            flags |= pygame.FULLSCREEN
        self.screen = pygame.display.set_mode(MIN_SIZE, flags)
        self.clock = pygame.time.Clock()
        self.sheet = SpriteSheet(1).build()
        self.settings = self.load_settings()
        if args.name:
            self.settings["name"] = args.name
        self.client = GameClient()
        self.server = None
        self.scenes = [MenuScene(self)]
        self.play = None
        self.inventory = {"items": [], "equipment": {}, "gold": 0}
        self.running = True
        self.last_ping = 0.0

    # ---------------------------------------------------------- settings ---
    @property
    def settings_path(self):
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, ".stormhold.json")

    def load_settings(self):
        import json
        try:
            with open(self.settings_path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return {}

    def save_settings(self):
        import json
        try:
            with open(self.settings_path, "w", encoding="utf-8") as fh:
                json.dump(self.settings, fh)
        except OSError:
            pass

    # ------------------------------------------------------------- scenes --
    @property
    def scene(self):
        return self.scenes[-1]

    @property
    def scene_under(self):
        return self.scenes[-2] if len(self.scenes) > 1 else self.scenes[0]

    def push(self, scene):
        self.scenes.append(scene)

    def pop(self):
        if len(self.scenes) > 1:
            self.scenes.pop()

    def replace(self, scene):
        self.scenes = [scene]

    # ---------------------------------------------------------- networking -
    def start_host(self):
        from ..net.server import GameServer, lan_addresses
        port = int(self.settings.get("port", 7777))
        save_path = self.args.save or os.path.join(os.getcwd(), "data", "party.json")
        try:
            self.server = GameServer("0.0.0.0", port, self.args.seed, save_path).start()
        except OSError as exc:
            self.replace(MenuScene(self, f"Could not start a server on port {port}: {exc}"))
            return
        addresses = lan_addresses()
        self.settings["host"] = "127.0.0.1"
        self.connect_to("127.0.0.1", port,
                        hosting_note=addresses[0] if addresses else None)

    def start_join(self):
        self.connect_to(self.settings.get("host", "127.0.0.1"),
                        int(self.settings.get("port", 7777)))

    def connect_to(self, host, port, hosting_note=None):
        if not self.client.connect(host, port):
            self.replace(MenuScene(self, self.client.error or "Could not connect."))
            return
        self.hosting_note = hosting_note
        self.pending_saves = []

    def join_as(self, name, stats, colour, resume):
        self.settings["name"] = name
        self.save_settings()
        self.client.send(P.C_HELLO, {"name": name, "stats": stats, "colour": colour,
                                     "resume": resume, "version": PROTOCOL_VERSION})

    def act(self, action):
        self.client.send(P.C_ACTION, action)

    def disconnect(self, message=""):
        self.client.close()
        if self.server:
            self.server.stop()
            self.server = None
        self.play = None
        self.replace(MenuScene(self, message))

    # -------------------------------------------------------------- events -
    def pump_network(self):
        for kind, data in self.client.drain():
            if kind == "__closed":
                self.disconnect("The connection to the server was lost.")
                return
            if kind == P.S_ROSTER:
                self.pending_saves = data.get("saves", [])
                self.replace(CharGenScene(self, self.pending_saves))
            elif kind == P.S_ERROR:
                scene = self.scene
                if isinstance(scene, CharGenScene):
                    scene.error = data.get("msg", "")
                else:
                    self.disconnect(data.get("msg", ""))
            elif kind == P.S_WELCOME:
                self.play = PlayScene(self)
                self.replace(self.play)
                self.play.add_message(data.get("motd", ""), "good")
                if getattr(self, "hosting_note", None):
                    self.play.add_message(
                        f"Others on your network can join at {self.hosting_note}:"
                        f"{self.settings.get('port', 7777)}", "good")
            elif self.play is not None:
                if kind == P.S_SHOP and isinstance(self.scene, ShopScene):
                    self.scene.refresh(data)
                else:
                    self.play.on_message(kind, data)

    def run(self):
        while self.running:
            dt = self.clock.tick(30) / 1000.0
            self.pump_network()
            if self.client.connected and time.time() - self.last_ping > 5:
                self.last_ping = time.time()
                self.client.ping()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.VIDEORESIZE:
                    self.screen = pygame.display.set_mode(
                        (max(MIN_SIZE[0], event.w), max(MIN_SIZE[1], event.h)),
                        pygame.RESIZABLE)
                else:
                    self.scene.handle(event)

            self.scene.update(dt)
            self.scene.draw(self.screen)
            pygame.display.flip()

        self.client.close()
        if self.server:
            self.server.stop()
        pygame.quit()
