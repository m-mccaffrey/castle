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
    DIFFICULTIES, DEFAULT_DIFFICULTY,
    TILE_NAMES, T, SIGHT_DUNGEON, SIGHT_TOWN, chebyshev, xp_for_level,
)
from ..common.fov import compute_fov
from ..game.spells import SPELLS, STARTING_SPELLS
from ..net import protocol as P
from ..net.client import GameClient
from . import widgets as W
from .art import SpriteSheet, TILE
from .palette import (BLACK, WHITE, SILVER, GRAY, NAVY, MAROON, GREEN, RED,
                      YELLOW, LIME, AQUA, TEAL, OLIVE, PURPLE, FUCHSIA, BLUE)


def speed_text(you):
    """The original prints overall speed, then movement speed: "100% / 200%".

    The first figure is how fast every action goes; the second is movement
    alone, which is what the load you carry actually affects.
    """
    mv = you.get("move_speed")
    if mv is None:
        return "OVERLOADED"
    return f"{you.get('speed', 100)}% / {mv}%"

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

    def layout(self, size):
        """Position widgets for a window of this size.

        Called when the scene appears and again whenever the window changes.
        Anything that builds click targets must do it here, not in __init__,
        or the buttons end up drawn in one place and clickable in another.
        """

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
        self.layout(app.screen.get_size())
        self.name.focused = not self.name.value

    def layout(self, size):
        app = self.app
        cx = size[0] // 2
        keep = {}
        for field in ("name", "host", "port"):
            widget = getattr(self, field, None)
            if widget is not None:
                keep[field] = (widget.value, widget.focused)
        self.name = W.TextField((cx - 90, 250, 220, 28), app.settings.get("name", ""), 14)
        self.host = W.TextField((cx - 90, 380, 220, 28), app.settings.get("host", "127.0.0.1"), 24)
        self.port = W.TextField((cx + 140, 380, 70, 28), str(app.settings.get("port", 7777)), 5, numeric=True)
        for field, (value, focused) in keep.items():
            widget = getattr(self, field)
            widget.value, widget.focused = value, focused
        self.buttons = [
            W.Button((cx - 200, 300, 190, 34), "Host a game", "host"),
            W.Button((cx + 10, 300, 190, 34), "Join a game", "join"),
            W.Button((cx - 200, 430, 190, 34), "How to play", "help"),
            W.Button((cx + 10, 430, 190, 34), "Quit", "quit"),
        ]

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
    # Every y on this screen, in one place. layout() builds the hit targets
    # from it and draw() puts the labels at the same numbers, which is the
    # only way the two stay in agreement - they drifted once already.
    Y = {
        "intro": 92, "blurb": 112, "points": 172,
        "stats": 194, "stat_step": 34,
        "difficulty_label": 330, "difficulty": 346, "difficulty_step": 28,
        "spell_label": 410, "spell": 426, "spell_step": 30,
        "colour_label": 492, "colour": 508,
        "actions": 552, "saves_label": 594, "saves": 610, "saves_step": 26,
        "error": 676,
    }

    def __init__(self, app, saves=None):
        super().__init__(app)
        self.saves = saves or []
        self.stats = {k: START_STAT for k in STATS}
        self.points = START_POINTS
        self.colour = 0
        self.spell = STARTING_SPELLS[0]
        self.difficulty = app.settings.get("difficulty", DEFAULT_DIFFICULTY)
        self.error = ""
        self.layout(app.screen.get_size())

    def layout(self, size):
        cx = size[0] // 2
        self.plus = {}
        self.minus = {}
        for i, stat in enumerate(STATS):
            y = self.Y["stats"] + i * self.Y["stat_step"]
            self.minus[stat] = W.Button((cx - 30, y, 28, 26), "-", ("dec", stat))
            self.plus[stat] = W.Button((cx + 88, y, 28, 26), "+", ("inc", stat))
        self.difficulty_buttons = []
        for i, (label, _symbol, _t, _x) in enumerate(DIFFICULTIES):
            col, row = i % 2, i // 2
            self.difficulty_buttons.append(
                W.Button((cx - 210 + col * 222,
                          self.Y["difficulty"] + row * self.Y["difficulty_step"],
                          214, 26),
                         label, ("difficulty", label)))

        # The original's last step is choosing one starting spell from six.
        self.spell_buttons = []
        for i, name in enumerate(STARTING_SPELLS):
            col, row = i % 3, i // 3
            self.spell_buttons.append(
                W.Button((cx - 210 + col * 148,
                          self.Y["spell"] + row * self.Y["spell_step"],
                          140, 28),
                         name, ("spell", name)))
        self.buttons = [
            W.Button((cx - 210, self.Y["actions"], 180, 32), "Enter the keep", "go"),
            W.Button((cx + 30, self.Y["actions"], 180, 32), "Back", "back"),
        ]
        self.resume_buttons = []
        for i, s in enumerate(self.saves[:6]):
            self.resume_buttons.append(
                W.Button((cx - 210, self.Y["saves"] + i * self.Y["saves_step"],
                          420, 24),
                         f"Carry on as {s['name']} (level {s['level']}, reached {s.get('deepest', 0)})",
                         ("resume", s["name"])))

    def handle(self, event):
        for b in (list(self.plus.values()) + list(self.minus.values())
                  + self.difficulty_buttons + self.spell_buttons
                  + self.buttons + self.resume_buttons):
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
                elif op == "spell":
                    self.spell = value
                elif op == "difficulty":
                    self.difficulty = value
                    self.app.settings["difficulty"] = value
                elif op == "resume":
                    self.app.join_as(value, self.stats, self.colour, resume=True,
                                     spell=self.spell, difficulty=self.difficulty)
            elif action == "go":
                self.app.join_as(self.app.settings.get("name", "Adventurer"),
                                 self.stats, self.colour, resume=False,
                                 spell=self.spell, difficulty=self.difficulty)
            elif action == "back":
                self.app.disconnect("")
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                self.app.join_as(self.app.settings.get("name", "Adventurer"),
                                 self.stats, self.colour, resume=False,
                                 spell=self.spell, difficulty=self.difficulty)
            elif event.key == pygame.K_LEFT:
                self.colour = (self.colour - 1) % 6
            elif event.key == pygame.K_RIGHT:
                self.colour = (self.colour + 1) % 6

    def draw(self, surf):
        surf.fill((18, 24, 40))
        w = surf.get_width()
        cx = w // 2
        box = pygame.Rect(cx - 300, 46, 600,
                          min(surf.get_height() - 56, self.Y["error"] + 30))
        client = W.window(surf, box, "Create a character")

        W.text(surf, "Stormhold has no character classes.",
               (client.x + 8, self.Y["intro"]), 14, bold=True)
        for i, line in enumerate(W.wrap(
                "Spend your points however you like. Strength carries armour and swings "
                "it hard, Dexterity hits and dodges, Intelligence powers spells, "
                "Constitution keeps you alive. You learn magic from books you find or buy.",
                client.width - 16, 13)):
            W.text(surf, line, (client.x + 8, self.Y["blurb"] + i * 17), 13)

        W.text(surf, f"Points left: {self.points}", (cx - 210, self.Y["points"]), 15, bold=True,
               colour=(0, 96, 0) if self.points else (120, 0, 0))

        for i, stat in enumerate(STATS):
            y = self.Y["stats"] + i * self.Y["stat_step"]
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

        W.text(surf, "How hard should the keep be?",
               (cx - 210, self.Y["difficulty_label"]), 13, bold=True)
        for b in self.difficulty_buttons:
            b.selected = (b.action[1] == self.difficulty)
            b.draw(surf)

        W.text(surf, "Colour on the map (left/right arrows)",
               (cx - 210, self.Y["colour_label"]), 13, bold=True)
        for i in range(6):
            img = self.app.sheet.player(i, "sword", False, False, False)[0]
            spot = pygame.Rect(cx - 210 + i * 40, self.Y["colour"], 36, 36)
            W.panel(surf, spot, raised=i != self.colour)
            surf.blit(img, (spot.x + 2, spot.y + 2))

        W.text(surf, "The one spell you already know",
               (cx - 210, self.Y["spell_label"]), 13, bold=True)
        for b in self.spell_buttons:
            b.selected = (b.action[1] == self.spell)
            b.draw(surf)

        for b in self.buttons:
            b.draw(surf)
        if self.resume_buttons:
            W.text(surf, "Or carry on with a character already saved here:",
                   (cx - 210, self.Y["saves_label"]), 13, bold=True)
            for b in self.resume_buttons:
                b.draw(surf)
        if self.error:
            W.text(surf, self.error, (cx - 210, self.Y["error"]), 13,
                   colour=(150, 0, 0), bold=True)

    @staticmethod
    def hint(stat):
        return {
            "strength": "carry more, hit harder",
            "dexterity": "hit and dodge better",
            "intelligence": "more mana, more spells",
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
                "Weight matters. Armour and loot slow you down, and a hundred copper "
                "weigh a kilo - which is why there is a strongroom in town. If you die "
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
        self.log_scroll = 0           # lines back from the newest
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
            shop = data.get("shop", "general")
            # "Stores operate as an extension of the inventory. When you enter
            # a store, the inventory window appears, but with the floor
            # replaced by the contents of the store." The temple and the bank
            # are counters rather than stores, and stay dialogs.
            if shop in ("temple", "bank"):
                self.app.push(ServiceScene(self.app, data))
            else:
                self.app.push(StoreScene(self.app, data))
        elif kind == P.S_CHAT:
            self.add_message(f"{data['from']}: {data['text']}", "chat")
        elif kind == P.S_DIED:
            self.add_message("You have died. You wake on the temple floor.", "bad")

    def add_message(self, text, kind="info"):
        self.messages.append((text, kind))
        self.log_scroll = 0           # a new line always brings you back down
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
        self.build_chrome()

        chosen = self.menubar.handle(event)
        if chosen:
            self.menu_command(chosen)
            return
        if self.menubar.is_open:
            return

        hit = self.toolbar.handle(event)
        if hit:
            what, value = hit
            if what == "verb":
                self.menu_command(value)
            else:
                from ..game.spells import SPELLS, STARTING_SPELLS
                if value in SPELLS:
                    self.begin_target(value, SPELLS[value])
            return

        if event.type == pygame.MOUSEWHEEL:
            if self.log_rect(self.app.screen).collidepoint(pygame.mouse.get_pos()):
                self.log_scroll = max(0, self.log_scroll + event.y * 3)
                self.dirty = True
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
            if kind == "examine":
                self.send_action({"a": "examine", "x": tx, "y": ty})
            else:
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
    MENU_H = W.MenuBar.HEIGHT
    TOOL_H = W.Toolbar.HEIGHT
    BOTTOM_H = 152
    STATUS_W = 250

    def viewport(self, surf):
        top = self.MENU_H + self.TOOL_H
        return pygame.Rect(0, top, surf.get_width(),
                           surf.get_height() - top - self.BOTTOM_H)

    def log_rect(self, surf):
        return pygame.Rect(0, surf.get_height() - self.BOTTOM_H,
                           surf.get_width() - self.STATUS_W, self.BOTTOM_H)

    def status_rect(self, surf):
        return pygame.Rect(surf.get_width() - self.STATUS_W,
                           surf.get_height() - self.BOTTOM_H,
                           self.STATUS_W, self.BOTTOM_H)

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

    def build_chrome(self):
        """The menu and toolbar, built once and reused."""
        if getattr(self, "menubar", None) is not None:
            return
        self.menubar = W.MenuBar([
            ("File", [("Save", "save", True), ("-", None, True),
                      ("Options...", "options", True),
                      ("-", None, True), ("Leave the keep", "leave", True)]),
            ("Character!", []),
            ("Inventory!", []),
            ("Map!", []),
            ("Spells", [("Spellbook...", "spellbook", True),
                        ("Customize Spell Menu...", "customize", True)]),
            ("Verbs", [("Get", "pickup", True),
                       ("Examine", "examine", True),
                       ("Free Hand", "freehand", True),
                       ("Search", "search", True),
                       ("Disarm Trap", "disarm", True),
                       ("-", None, True),
                       ("Rest Until Healed", "rest", True),
                       ("Sleep Until Mana is Restored", "sleep", True),
                       ("-", None, True),
                       ("Open", "open", True),
                       ("Close", "close", True),
                       ("-", None, True),
                       ("< Climb Up Stairs", "stairs", True),
                       ("> Climb Down Stairs", "stairs", True)]),
            ("Help", [("Help Contents", "help", True),
                      ("Keyboard Commands", "help", True)]),
        ])
        self.toolbar = W.Toolbar([
            ("Get", "pickup"), ("Free Hand", "freehand"), ("Search", "search"),
            ("Disarm", "disarm"), ("Rest", "rest"), ("Save", "save"),
        ])

    def menu_command(self, action):
        if action == "Character!":
            self.app.push(SheetScene(self.app))
        elif action == "Inventory!":
            self.app.push(PackScene(self.app))
        elif action == "Map!":
            self.show_overview = not getattr(self, "show_overview", False)
        elif action in ("spellbook", "customize"):
            self.app.push(SpellScene(self.app, self))
        elif action == "help":
            self.app.push(HelpScene(self.app))
        elif action == "leave":
            self.app.disconnect("")
        elif action == "options":
            self.add_message("Options are kept in the launcher for now.", "info")
        elif action == "examine":
            self.target_mode = ("examine", None)
            self.add_message("Click something to examine it.", "info")
        elif action == "save":
            self.add_message("The server saves everyone automatically.", "info")
        elif action:
            self.send_action({"a": action})

    def draw(self, surf):
        self.build_chrome()
        surf.fill(W.FACE)
        self.draw_map(surf, self.viewport(surf))
        self.draw_log(surf)
        self.draw_status(surf)
        spells = self.you.get("spells", []) if self.you else []
        self.toolbar.draw(surf, surf.get_width(), self.app.sheet, spells)
        self.menubar.draw(surf, surf.get_width())

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
                f"Click a target for {self.target_mode[1] or 'Examine'}  (Esc to cancel)",
            True, YELLOW)
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

    def draw_status(self, surf):
        """Five lines, as in the original: health, mana, pace, the clock, and
        where you are. The party list sits underneath because we need one."""
        rect = self.status_rect(surf)
        W.panel(surf, rect, raised=True)
        you = self.you
        if not you:
            return
        from ..common.constants import format_clock

        x = rect.x + 8
        value_x = rect.x + 72
        y = rect.y + 6
        rows = [
            ("HP", f"{you.get('hp', 0)} ({you.get('max_hp', 0)})",
             (150, 0, 0) if you.get("hp", 1) < you.get("max_hp", 1) * 0.34 else BLACK),
            ("Mana", f"{you.get('mana', 0)} ({you.get('max_mana', 0)})", BLACK),
            # A bare "0%" tells a player nothing. If they cannot move, say so.
            ("Speed",
             speed_text(you),
             (170, 0, 0) if (you.get("move_speed") or 200) < 100 else BLACK),
            ("Time", format_clock(you.get("clock", 0)), BLACK),
        ]
        for label, value, colour in rows:
            W.text(surf, label, (x, y), 12, bold=True)
            W.text(surf, value, (value_x, y), 12, mono=True, colour=colour)
            y += 16

        # The original's last status row is the place you are standing in, and
        # it should agree with what the log just called it.
        depth = you.get("depth", 0)
        place = getattr(self.map, "name", None)
        if place:
            place = place[:1].upper() + place[1:]     # "the Cellars" heads a line
        if not place:
            place = "Aldershade" if depth == 0 else f"Dungeon Level {depth}"
        W.text(surf, place, (x, y), 12, bold=True)
        y += 18

        effects = you.get("effects", {})
        if effects:
            W.text(surf, " ".join(sorted(effects))[:28], (x, y), 10, colour=(90, 0, 120))
            y += 14

        if len(self.party) > 1:
            pygame.draw.line(surf, W.FACE_SHADOW, (x, y), (rect.right - 8, y))
            y += 4
            for mate in self.party:
                if mate["id"] == you.get("id"):
                    continue
                here = mate["d"] == depth
                W.text(surf, mate["n"][:9], (x, y), 11,
                       bold=True, colour=BLACK if here else GRAY)
                W.bar(surf, (x + 66, y + 2, rect.width - 84, 9),
                      mate["hp"] / max(1, mate["mhp"]),
                      (176, 32, 32) if here else GRAY)
                if not here:
                    W.text(surf, "town" if mate["d"] == 0 else f"lv{mate['d']}",
                           (rect.right - 38, y), 10, colour=GRAY)
                y += 15

    def draw_log(self, surf):
        rect = self.log_rect(surf)
        W.panel(surf, rect, raised=True)
        inner = rect.inflate(-8, -8)
        W.panel(surf, inner, raised=False, fill=(246, 246, 242))

        lines = []
        for text, kind in self.messages[-200:]:
            for part in W.wrap(text, inner.width - 26, 13):
                lines.append((part, kind))
        visible = (inner.height - 6) // 17
        self.log_lines, self.log_visible = len(lines), visible

        # The original's log scrolls back, oldest at top. Ours drew a scrollbar
        # that did nothing, which is worse than not drawing one.
        self.log_scroll = max(0, min(self.log_scroll, max(0, len(lines) - visible)))
        end = len(lines) - self.log_scroll
        for i, (text, kind) in enumerate(lines[max(0, end - visible):end]):
            W.text(surf, text, (inner.x + 6, inner.y + 3 + i * 17), 13,
                   colour=MSG_COLOURS.get(kind, BLACK))

        track = pygame.Rect(inner.right - 14, inner.y, 14, inner.height)
        W.panel(surf, track, raised=False, fill=(214, 214, 210))
        if len(lines) > visible:
            frac = visible / max(1, len(lines))
            knob_h = max(16, int(track.height * frac))
            room = track.height - knob_h
            back = self.log_scroll / max(1, len(lines) - visible)
            W.panel(surf, pygame.Rect(track.x, int(track.bottom - knob_h - room * back),
                                      14, knob_h), raised=True)

        if self.chatting:
            box = pygame.Rect(inner.x, inner.bottom - 22, inner.width - 16, 22)
            W.panel(surf, box, raised=False, fill=WHITE)
            W.text(surf, "Say: " + self.chat_text + "_", (box.x + 5, box.y + 3), 13, mono=True)


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
    """The paper doll.

    A figure in the middle, the slots arranged around it with a line drawn to
    the part of the body each one belongs to, and the pack below. Everything
    moves by dragging: pack to body to wear it, body to pack to take it off.
    The totals live in the title bars, one for what you are wearing and one for
    what you are carrying.
    """

    size = (940, 690)
    SLOT_W = 196
    SLOT_H = 46
    DOLL_H = 430

    def __init__(self, app):
        super().__init__(app)
        self.slot_rects = {}
        self.cell_rects = []
        self.selected = None
        self.drag = None            # {"item", "from", "icon", "pos"}
        self.hover_slot = None
        self.naming = None          # a TextField while renaming something
        self.grid_rect = pygame.Rect(0, 0, 10, 10)
        self.scroll = 0

    # ------------------------------------------------------------ helpers --
    @property
    def inv(self):
        return self.app.inventory

    def items(self):
        return self.inv.get("items", [])

    def equipment(self):
        return self.inv.get("equipment", {})

    def item_at(self, pos):
        """Whatever is under the cursor: (item, source) or (None, None)."""
        for slot, rect in self.slot_rects.items():
            if rect.collidepoint(pos):
                worn = self.equipment().get(slot)
                if worn:
                    return worn, ("slot", slot)
                return None, ("slot", slot)
        for rect, item in self.cell_rects:
            if rect.collidepoint(pos):
                return item, ("pack", None)
        return None, (None, None)

    def slot_accepts(self, slot, item):
        want = item.get("slot")
        if want is None:
            return False
        if want in ("ring_left", "ring_right"):
            return slot in ("ring_left", "ring_right")
        return slot == want

    # -------------------------------------------------------------- input --
    def handle(self, event):
        if self.naming is not None:
            self.handle_naming(event)
            return

        if event.type == pygame.MOUSEWHEEL and self.grid_rect.collidepoint(pygame.mouse.get_pos()):
            self.scroll = max(0, self.scroll - event.y)
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # The buttons get first refusal. Without this the press never
            # reaches them, they never arm, and the release does nothing -
            # which left Close, Drop, Use and the rest dead in every store.
            for b in self.buttons:
                if b.rect.collidepoint(event.pos):
                    b.handle(event)
                    return
            item, (source, slot) = self.item_at(event.pos)
            if item is not None:
                self.selected = item
                self.drag = {"item": item, "from": source, "slot": slot,
                             "pos": event.pos, "moved": False}
            return

        if event.type == pygame.MOUSEMOTION:
            if self.drag:
                self.drag["pos"] = event.pos
                self.drag["moved"] = True
                self.hover_slot = None
                for slot, rect in self.slot_rects.items():
                    if rect.collidepoint(event.pos):
                        self.hover_slot = slot
            return

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.drag:
            self.finish_drag(event.pos)
            return

        for b in self.buttons:
            action = b.handle(event)
            if action:
                self.on_action(action)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.close()

    def finish_drag(self, pos):
        drag = self.drag
        self.drag = None
        self.hover_slot = None
        item = drag["item"]

        if not drag["moved"]:
            return                                   # a click, not a drag

        for slot, rect in self.slot_rects.items():
            if not rect.collidepoint(pos):
                continue
            if drag["from"] == "slot" and slot == drag["slot"]:
                return                               # dropped back where it started
            if not self.slot_accepts(slot, item):
                self.app.play.add_message(
                    f"{item['name']} does not go there.", "warn")
                return
            self.app.act({"a": "equip", "id": item["id"], "slot": slot})
            return

        if self.grid_rect.collidepoint(pos):
            if drag["from"] == "slot":
                self.app.act({"a": "unequip", "slot": drag["slot"]})
            return

    def handle_naming(self, event):
        self.naming.handle(event)
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                self.app.act({"a": "rename", "id": self.naming_id,
                              "name": self.naming.value})
                self.naming = None
            elif event.key == pygame.K_ESCAPE:
                self.naming = None

    def on_action(self, action):
        item = self.selected
        if action == "close":
            self.close()
        elif action == "sort":
            self.app.act({"a": "sort"})
            self.scroll = 0
        elif action == "name" and item:
            self.naming_id = item["id"]
            self.naming = W.TextField((0, 0, 260, 26),
                                      "" if not item.get("custom") else item["name"], 24)
            self.naming.focused = True
        elif item and action == "use":
            self.app.act({"a": "use", "id": item["id"]})
        elif item and action == "drop":
            self.app.act({"a": "drop", "id": item["id"]})
            self.selected = None

    # ------------------------------------------------------------ drawing --
    def draw(self, surf):
        below = self.app.under(self)
        if below is not None:
            below.draw(surf)
        inv = self.inv
        cp = inv.get("copper", 0)
        wt, wt_max = inv.get("weight", 0), max(1, inv.get("capacity", 1))
        bk, bk_max = inv.get("bulk", 0), max(1, inv.get("bulk_capacity", 1))
        self.title = (f"{self.app.play.you.get('name', 'Pack')}"
                      f"   Cp: {cp}   Weight: {wt} ({wt_max})"
                      f"   Bulk: {bk} ({bk_max})")
        client, _ = self.frame(surf)

        # A store splits the lower half in two, so the doll gives some height
        # back - otherwise neither grid is tall enough to show a whole cell.
        doll_h = self.DOLL_H
        doll = pygame.Rect(client.x, client.y, client.width, doll_h)
        self.draw_doll(surf, doll)

        grid_top = doll.bottom + 6
        self.draw_pack(surf, pygame.Rect(client.x, grid_top,
                                         client.width, client.bottom - grid_top - 40))
        self.draw_buttons(surf, client)
        if self.drag and self.drag["moved"]:
            img = self.app.sheet.item(self.drag["item"]["icon"])
            if img:
                surf.blit(img, (self.drag["pos"][0] - TILE // 2,
                                self.drag["pos"][1] - TILE // 2))
        if self.naming is not None:
            self.draw_naming(surf, client)

    def draw_doll(self, surf, area):
        """Slots down each side, three across the top, and the figure between."""
        from ..common.constants import (DOLL_TOP, DOLL_LEFT, DOLL_RIGHT,
                                        SLOT_LABELS, SLOT_ANCHORS)
        self.slot_rects = {}
        sw, sh = self.SLOT_W, self.SLOT_H

        top_y = area.y
        gap = (area.width - sw * 3) // 4
        for i, slot in enumerate(DOLL_TOP):
            x = area.x + gap + i * (sw + gap)
            self.slot_rects[slot] = pygame.Rect(x, top_y, sw, sh)

        col_top = top_y + sh + 8
        rows = max(len(DOLL_LEFT), len(DOLL_RIGHT))
        row_h = (area.height - sh - 14) // rows
        for i, slot in enumerate(DOLL_LEFT):
            self.slot_rects[slot] = pygame.Rect(area.x, col_top + i * row_h, sw, sh)
        for i, slot in enumerate(DOLL_RIGHT):
            self.slot_rects[slot] = pygame.Rect(area.right - sw, col_top + i * row_h, sw, sh)

        gap_area = pygame.Rect(area.x + sw + 20, col_top,
                               area.width - 2 * sw - 40, area.height - sh - 14)
        fig_w = int(gap_area.height * 0.46)
        figure = pygame.Rect(gap_area.centerx - fig_w // 2, gap_area.y,
                             fig_w, gap_area.height)

        # Leader lines first, so the boxes sit on top of them.
        for slot, rect in self.slot_rects.items():
            anchor = SLOT_ANCHORS.get(slot)
            if not anchor:
                continue
            ax = figure.x + int(anchor[0] * figure.width)
            ay = figure.y + int(anchor[1] * figure.height)
            if rect.centerx < figure.centerx:
                start = (rect.right, rect.centery)
            elif rect.centerx > figure.centerx:
                start = (rect.left, rect.centery)
            else:
                start = (rect.centerx, rect.bottom)
            worn = self.equipment().get(slot)
            if worn:
                self.dashed_line(surf, start, (ax, ay), (150, 40, 40))
            else:
                # Just a stub: a full line from every empty slot crosses the
                # figure and turns the whole window into a cat's cradle.
                dx, dy = ax - start[0], ay - start[1]
                length = max(1.0, (dx * dx + dy * dy) ** 0.5)
                stub = min(26.0, length)
                self.dashed_line(surf, start,
                                 (start[0] + dx / length * stub,
                                  start[1] + dy / length * stub), (175, 175, 170))

        self.draw_figure(surf, gap_area)

        for slot, rect in self.slot_rects.items():
            self.draw_slot(surf, rect, slot, SLOT_LABELS.get(slot, slot))

    def dashed_line(self, surf, a, b, colour, dash=5):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = max(1.0, (dx * dx + dy * dy) ** 0.5)
        steps = int(length // dash)
        for i in range(0, steps, 2):
            t0, t1 = i / max(1, steps), min(1.0, (i + 1) / max(1, steps))
            pygame.draw.line(surf, colour,
                             (a[0] + dx * t0, a[1] + dy * t0),
                             (a[0] + dx * t1, a[1] + dy * t1))

    def draw_figure(self, surf, area):
        """An outline of a person, and what they are visibly wearing.

        The space between the two columns is much wider than a person, so the
        drawing is fitted to a tall narrow box in the middle of it - otherwise
        every proportion stretches sideways.
        """
        ink = (40, 40, 40)
        height = area.height
        width = int(height * 0.46)               # roughly human proportions
        box = pygame.Rect(area.centerx - width // 2, area.y, width, height)

        def px(fx, fy):
            return (int(box.x + fx * box.width), int(box.y + fy * box.height))

        worn = self.equipment()

        # --- a cloak hangs behind everything else -------------------------
        if worn.get("back"):
            pygame.draw.polygon(surf, (96, 64, 140), [
                px(0.28, 0.24), px(0.72, 0.24), px(0.86, 0.78),
                px(0.66, 0.72), px(0.34, 0.72), px(0.14, 0.78)])
            pygame.draw.polygon(surf, ink, [
                px(0.28, 0.24), px(0.72, 0.24), px(0.86, 0.78),
                px(0.66, 0.72), px(0.34, 0.72), px(0.14, 0.78)], 2)

        # --- the pack, slung on the back, showing above the shoulders --------
        if worn.get("pack"):
            pk_w, pk_h = int(box.width * 0.44), int(box.height * 0.26)
            pk = pygame.Rect(box.centerx - pk_w // 2, px(0, 0.20)[1], pk_w, pk_h)
            pygame.draw.rect(surf, (120, 86, 48), pk)
            pygame.draw.rect(surf, ink, pk, 2)
            for fx in (0.40, 0.60):                     # shoulder straps
                pygame.draw.line(surf, (96, 68, 38), px(fx, 0.22), px(fx, 0.44), 3)

        # --- legs and boots ------------------------------------------------
        for fx in (0.42, 0.58):
            pygame.draw.line(surf, ink, px(fx, 0.56), px(fx, 0.88), 2)
        if worn.get("legs"):
            pygame.draw.polygon(surf, (120, 86, 48), [
                px(0.38, 0.56), px(0.62, 0.56), px(0.62, 0.76), px(0.38, 0.76)])
            pygame.draw.polygon(surf, ink, [
                px(0.38, 0.56), px(0.62, 0.56), px(0.62, 0.76), px(0.38, 0.76)], 2)
        for fx in (0.42, 0.58):
            foot = pygame.Rect(px(fx - 0.09, 0.88)[0], px(0, 0.88)[1],
                               int(box.width * 0.18), int(box.height * 0.05))
            pygame.draw.rect(surf, (150, 110, 60) if worn.get("feet") else W.FACE, foot)
            pygame.draw.rect(surf, ink, foot, 2)

        # --- torso ----------------------------------------------------------
        torso = [px(0.32, 0.22), px(0.68, 0.22), px(0.62, 0.57), px(0.38, 0.57)]
        pygame.draw.polygon(surf, (128, 138, 152) if worn.get("torso") else W.FACE, torso)
        pygame.draw.polygon(surf, ink, torso, 2)

        # --- arms, bracers and gauntlets ------------------------------------
        for side in (-1, 1):
            sx = 0.50 + side * 0.18
            ex = 0.50 + side * 0.30
            pygame.draw.line(surf, ink, px(sx, 0.25), px(ex, 0.42), 2)
            pygame.draw.line(surf, ink, px(ex, 0.42), px(ex, 0.58), 2)
            if worn.get("bracers"):
                pygame.draw.line(surf, (150, 120, 70), px(ex, 0.44), px(ex, 0.50), 5)
            hand = px(ex, 0.60)
            if worn.get("arms"):
                pygame.draw.circle(surf, (120, 130, 145), hand, 6)
                pygame.draw.circle(surf, ink, hand, 6, 2)
            else:
                pygame.draw.circle(surf, W.FACE, hand, 5)
                pygame.draw.circle(surf, ink, hand, 5, 2)
            ring = "ring_left" if side < 0 else "ring_right"
            if worn.get(ring):
                pygame.draw.circle(surf, (210, 180, 50), px(ex + side * 0.05, 0.62), 3)

        # --- belt -------------------------------------------------------------
        pygame.draw.line(surf, (130, 90, 45) if worn.get("waist") else ink,
                         px(0.38, 0.555), px(0.62, 0.555), 5 if worn.get("waist") else 2)

        # --- shield, on the arm rather than floating beside the shoulder -------
        if worn.get("shield"):
            sh_w, sh_h = int(box.width * 0.26), int(box.height * 0.18)
            sh = pygame.Rect(px(0.80, 0.40)[0] - sh_w // 2, px(0, 0.40)[1], sh_w, sh_h)
            pygame.draw.ellipse(surf, (150, 155, 165), sh)
            pygame.draw.ellipse(surf, ink, sh, 2)
            pygame.draw.circle(surf, (110, 60, 50), sh.center, 4)

        # --- weapon, gripped in the other hand ----------------------------------
        if worn.get("weapon"):
            hx = px(0.20, 0)[0]
            top, bottom = px(0, 0.34)[1], px(0, 0.64)[1]
            pygame.draw.line(surf, (180, 185, 195), (hx, top), (hx, bottom), 5)
            pygame.draw.line(surf, ink, (hx, top), (hx, bottom), 1)
            pygame.draw.line(surf, (150, 110, 40), (hx - 7, px(0, 0.58)[1]),
                             (hx + 7, px(0, 0.58)[1]), 3)

        # --- neck and head ------------------------------------------------------
        pygame.draw.line(surf, ink, px(0.50, 0.18), px(0.50, 0.22), 2)
        head_w = int(box.width * 0.26)
        head_h = int(box.height * 0.13)
        head = pygame.Rect(box.centerx - head_w // 2, px(0, 0.055)[1], head_w, head_h)
        pygame.draw.ellipse(surf, W.FACE, head)
        pygame.draw.ellipse(surf, ink, head, 2)
        if worn.get("head"):
            cap = pygame.Rect(head.x - 2, head.y - 3, head.width + 4, head.height // 2 + 3)
            pygame.draw.rect(surf, (128, 138, 152), cap)
            pygame.draw.rect(surf, ink, cap, 2)
        if worn.get("neck"):
            pygame.draw.circle(surf, (210, 180, 50), px(0.50, 0.235), 4)
            pygame.draw.circle(surf, ink, px(0.50, 0.235), 4, 1)

        return box

    def draw_slot(self, surf, rect, slot, label):
        worn = self.equipment().get(slot)
        highlight = (self.drag and self.hover_slot == slot
                     and self.slot_accepts(slot, self.drag["item"]))
        fill = (210, 225, 200) if highlight else (W.FACE if worn else (198, 198, 194))
        W.panel(surf, rect, raised=bool(worn), fill=fill)
        W.text(surf, label, (rect.x + 5, rect.y + 3), 10, colour=(90, 90, 90))
        if worn:
            img = self.app.sheet.item(worn["icon"])
            if img:
                surf.blit(pygame.transform.smoothscale(img, (22, 22)), (rect.x + 5, rect.y + 18))
            colour = (150, 0, 0) if worn.get("cursed") else BLACK
            name = worn["name"]
            f = W.font(11, bold=True)
            if f.size(name)[0] > rect.width - 36:
                while f.size(name + "...")[0] > rect.width - 36 and len(name) > 3:
                    name = name[:-1]
                name += "..."
            W.text(surf, name, (rect.x + 31, rect.y + 21), 11, bold=True, colour=colour)
        if self.selected is not None and worn is not None and worn["id"] == self.selected["id"]:
            pygame.draw.rect(surf, W.TITLE_A, rect, 2)

    CELL = 96
    CELL_H = 84

    @staticmethod
    def caption(label, width, size=10, lines=2):
        """Break an item's name across a cell, rather than cutting it short.

        A grid of "2 Potions of...", "Scroll of Ca...", "Tome of La..." tells
        you nothing about what you are about to buy, so the name gets two
        lines and only gives up if it still will not fit.
        """
        f = W.font(size)
        words, out, cur = label.split(), [], ""
        for word in words:
            trial = f"{cur} {word}".strip()
            if cur and f.size(trial)[0] > width:
                out.append(cur)
                cur = word
                if len(out) == lines:
                    break
            else:
                cur = trial
        if len(out) < lines and cur:
            out.append(cur)
        out = out[:lines]
        if out and f.size(out[-1])[0] > width:
            tail = out[-1]
            while tail and f.size(tail + "...")[0] > width:
                tail = tail[:-1]
            out[-1] = tail + "..."
        return out

    def draw_pack(self, surf, area):
        inv = self.inv
        name = inv.get("pack_name", "Pack")
        pw, pwm = inv.get("pack_weight", 0), max(1, inv.get("pack_max_weight", 1))
        pb, pbm = inv.get("pack_bulk", 0), max(1, inv.get("pack_max_bulk", 1))
        bar = pygame.Rect(area.x, area.y, area.width, 18)
        pygame.draw.rect(surf, W.TITLE_B, bar)
        W.text(surf, f"{name}   Wt {pw} ({pwm})   Bulk {pb} ({pbm})",
               (bar.x + 6, bar.y + 2), 12, bold=True, colour=WHITE)

        self.grid_rect = pygame.Rect(area.x, bar.bottom, area.width, area.height - bar.height)
        W.panel(surf, self.grid_rect, raised=False, fill=(236, 236, 232))

        cell, cell_h = self.CELL, self.CELL_H
        cols = max(1, (self.grid_rect.width - 8) // cell)
        rows = max(1, (self.grid_rect.height - 8) // cell_h)
        items = self.items()
        max_scroll = max(0, (len(items) + cols - 1) // cols - rows)
        self.scroll = min(self.scroll, max_scroll)

        self.cell_rects = []
        clip = surf.get_clip()
        surf.set_clip(self.grid_rect)
        for index, item in enumerate(items):
            row, col = divmod(index, cols)
            row -= self.scroll
            if row < 0 or row >= rows + 1:
                continue
            r = pygame.Rect(self.grid_rect.x + 4 + col * cell,
                            self.grid_rect.y + 4 + row * cell_h, cell - 4, cell_h - 4)
            selected = self.selected is not None and item["id"] == self.selected["id"]
            if selected:
                pygame.draw.rect(surf, (210, 220, 245), r)
                pygame.draw.rect(surf, W.TITLE_A, r, 1)
            img = self.app.sheet.item(item["icon"])
            if img:
                surf.blit(img, (r.centerx - TILE // 2, r.y + 2))
            colour = (150, 0, 0) if item.get("cursed") else BLACK
            lines = self.caption(item["name"], r.width - 4)
            ly = r.bottom - 6 - 11 * len(lines)
            for line in lines:
                img2 = W.font(10).render(line, True, colour)
                surf.blit(img2, (r.centerx - img2.get_width() // 2, ly))
                ly += 11
            qty = item.get("qty", 1)
            if qty > 1:
                W.text(surf, f"x{qty}", (r.right - 20, r.y + 2), 10, bold=True)
            self.cell_rects.append((r, item))
        surf.set_clip(clip)

        if not items:
            W.text(surf, "Empty. Drag something in, or press G in the keep to pick things up.",
                   (self.grid_rect.x + 10, self.grid_rect.y + 10), 12, colour=(120, 120, 120))
        if max_scroll:
            W.text(surf, f"{self.scroll + 1}/{max_scroll + 1}  (scroll wheel)",
                   (self.grid_rect.right - 110, self.grid_rect.bottom - 16), 10,
                   colour=(120, 120, 120))

    def draw_buttons(self, surf, client):
        item = self.selected
        label = "Use"
        if item:
            if item.get("slot"):
                label = "Wear"
            elif item.get("spell"):
                label = "Study"
            elif item.get("kind") == "potion":
                label = "Drink"
            elif item.get("kind") == "scroll":
                label = "Read"
        by = client.bottom - 32
        self.buttons = [
            W.Button((client.x, by, 110, 28), "Sort Pack", "sort"),
            W.Button((client.x + 118, by, 130, 28), "Name Object", "name", enabled=bool(item)),
            W.Button((client.x + 256, by, 100, 28), label, "use", enabled=bool(item)),
            W.Button((client.x + 364, by, 90, 28), "Drop", "drop", enabled=bool(item)),
            W.Button((client.right - 90, by, 90, 28), "Close", "close"),
        ]
        for b in self.buttons:
            b.draw(surf)

        # The detail line shares the row with the Close button, so it has to
        # stop short of it rather than run underneath.
        text_x = client.x + 466
        room = (client.right - 100) - text_x
        detail = (f"{item['name']} - {item['desc']}" if item
                  else "Drag things between your body and your pack.")
        f = W.font(11)
        if f.size(detail)[0] > room:
            while f.size(detail + "...")[0] > room and len(detail) > 3:
                detail = detail[:-1]
            detail += "..."
        W.text(surf, detail, (text_x, by + 7), 11,
               colour=(70, 70, 70) if item else (120, 120, 120))

    def draw_naming(self, surf, client):
        box = pygame.Rect(client.centerx - 170, client.centery - 50, 340, 100)
        W.panel(surf, box, raised=True)
        W.text(surf, "Call it what you like:", (box.x + 12, box.y + 12), 13, bold=True)
        self.naming.rect = pygame.Rect(box.x + 12, box.y + 36, box.width - 24, 26)
        self.naming.draw(surf)
        W.text(surf, "Enter to keep it, Esc to forget it.",
               (box.x + 12, box.y + 70), 11, colour=(90, 90, 90))


class SpellScene(OverlayScene):
    """Cast Spell: pick a class on the left, a spell on the right.

    Cancel is the default button, not Cast. Pressing Enter backs out rather
    than firing something expensive by reflex - the original does this and it
    is plainly the right call.
    """

    title = "Cast Spell"
    size = (620, 380)

    def __init__(self, app, play):
        super().__init__(app)
        self.play = play
        # Open on a class you actually have spells in, rather than on "Pick a
        # class on the left." - one click of ceremony before every cast.
        self.klass = None
        for name, usable in self.classes_for(app):
            if usable:
                self.klass = name
                break
        self.selected = None
        self.list = W.ListBox((0, 0, 10, 10), row_height=20)
        self.class_rects = []

    @staticmethod
    def classes_for(app):
        from ..game.spells import SCHOOLS
        known = [n for n in app.play.you.get("spells", []) if n in SPELLS]
        have = {SPELLS[n]["school"] for n in known}
        return [(c, c in have) for c in SCHOOLS]

    def known(self):
        return [n for n in self.app.play.you.get("spells", []) if n in SPELLS]

    def classes(self):
        return self.classes_for(self.app)

    def rows(self):
        if self.klass is None:
            return []
        return [n for n in self.known() if SPELLS[n]["school"] == self.klass]

    def handle(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for rect, name, usable in self.class_rects:
                if rect.collidepoint(event.pos) and usable:
                    self.klass = name
                    self.selected = None
                    self.list.selected = None
                    self.list.scroll = 0
                    return
        index = self.list.handle(event)
        if index is not None:
            rows = self.rows()
            if index < len(rows):
                self.selected = rows[index]
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                self.close()                     # Cancel is the default
                return
            if pygame.K_1 <= event.key <= pygame.K_9:
                rows = self.rows()
                i = event.key - pygame.K_1
                if i < len(rows):
                    self.selected = rows[i]
                    self.cast()
                    return
        super().handle(event)

    def on_action(self, action):
        if action == "cast":
            self.cast()
        elif action == "help":
            self.app.push(HelpScene(self.app))
        else:
            super().on_action(action)

    def cast(self):
        if not self.selected:
            return
        spell = SPELLS[self.selected]
        if self.app.play.you.get("mana", 0) < spell["mana"]:
            self.app.play.add_message("You have not the mana for that.", "warn")
            return
        name = self.selected
        self.close()
        self.play.begin_target(name, spell)

    def draw(self, surf):
        below = self.app.under(self)
        if below is not None:
            below.draw(surf)
        client, _ = self.frame(surf)
        you = self.app.play.you

        if not self.known():
            W.text(surf, "You know no spells yet.", (client.x + 8, client.y + 10), 15, bold=True)
            for i, line in enumerate(W.wrap(
                    "Magic comes from books. The Gilded Retort in Aldershade sells tomes, "
                    "and they turn up in the keep. Read one and the spell is yours for "
                    "good, provided you are experienced and clever enough for it.",
                    client.width - 16, 13)):
                W.text(surf, line, (client.x + 8, client.y + 36 + i * 17), 13)
            self.buttons = [W.Button((client.right - 100, client.bottom - 34, 90, 28),
                                     "Close", "close")]
            for b in self.buttons:
                b.draw(surf)
            return

        col_w = 200
        W.text(surf, "Spell Class:", (client.x + 4, client.y + 2), 13, bold=True)
        W.text(surf, "Spell Name", (client.x + col_w + 16, client.y + 2), 13, bold=True)
        W.text_right(surf, "Mana", client.right - 8, client.y + 2, 13, bold=True)

        group = pygame.Rect(client.x, client.y + 18, col_w, client.height - 66)
        W.panel(surf, group, raised=False, fill=W.FACE)
        self.class_rects = []
        y = group.y + 8
        for name, usable in self.classes():
            rect = pygame.Rect(group.x + 8, y, group.width - 16, 22)
            dot = pygame.Rect(rect.x, rect.y + 5, 12, 12)
            pygame.draw.ellipse(surf, WHITE if usable else (208, 208, 204), dot)
            pygame.draw.ellipse(surf, (90, 90, 90), dot, 1)
            if name == self.klass:
                pygame.draw.ellipse(surf, (20, 20, 90), dot.inflate(-6, -6))
            W.text(surf, f"{name} Spells", (rect.x + 18, rect.y + 3), 13,
                   colour=BLACK if usable else GRAY)
            self.class_rects.append((rect, name, usable))
            y += 24

        self.list.rect = pygame.Rect(client.x + col_w + 12, client.y + 18,
                                     client.width - col_w - 12, client.height - 66)
        rows = self.rows()

        def draw_row(target, name, rect, selected):
            spell = SPELLS[name]
            affordable = you.get("mana", 0) >= spell["mana"]
            colour = WHITE if selected else (BLACK if affordable else GRAY)
            W.text(target, name, (rect.x + 6, rect.y + 2), 13, colour=colour)
            W.text_right(target, str(spell["mana"]), rect.right - 10, rect.y + 2, 13,
                         mono=True, colour=colour)

        self.list.draw(surf, rows, draw_row)
        if self.klass is None:
            W.text(surf, "Pick a class on the left.",
                   (self.list.rect.x + 8, self.list.rect.y + 8), 12, colour=(120, 120, 120))

        info = self.selected and SPELLS[self.selected]
        if info:
            W.text(surf, info["desc"], (client.x, client.bottom - 54), 12, colour=(60, 60, 60))
        W.text_right(surf, f"Mana {you.get('mana', 0)} of {you.get('max_mana', 0)}",
                     client.right, client.bottom - 54, 12, bold=True)

        by = client.bottom - 34
        self.buttons = [
            W.Button((client.x + 40, by, 90, 28), "Cast", "cast", enabled=bool(self.selected)),
            W.Button((client.x + 150, by, 90, 28), "Cancel", "close"),
            W.Button((client.x + 260, by, 80, 28), "Help", "help"),
        ]
        for b in self.buttons:
            b.draw(surf)
        W.text(surf, "Enter cancels.", (client.x + 352, by + 7), 11, colour=(120, 120, 120))


class SheetScene(OverlayScene):
    """The character sheet: four attributes as paired gauges, and the numbers.

    Each attribute gets two bars side by side - what you were born with, and
    what you are walking around with once gear and potions are counted. Seeing
    a ring push a bar up is much more legible than watching a number change.
    """

    title = "Character"
    size = (720, 486)

    def draw(self, surf):
        below = self.app.under(self)
        if below is not None:
            below.draw(surf)
        client, _ = self.frame(surf)
        you = self.app.play.you
        inv = self.app.inventory
        from ..common.constants import format_clock

        W.text(surf, "Character name:", (client.x + 6, client.y + 4), 13, bold=True)
        namebox = pygame.Rect(client.x + 128, client.y, 220, 22)
        W.panel(surf, namebox, raised=False, fill=WHITE)
        W.text(surf, you.get("name", ""), (namebox.x + 6, namebox.y + 3), 14)

        # ---- the gauges ----------------------------------------------------
        gauge_top = client.y + 34
        gauge_h = 150
        base = you.get("base_stats", {})
        now = you.get("stats", {})
        x = client.x + 14
        for stat in STATS:
            natural = base.get(stat, 10)
            effective = now.get(stat, natural)
            for i, value in enumerate((natural, effective)):
                bar = pygame.Rect(x + i * 16, gauge_top, 14, gauge_h)
                W.panel(surf, bar, raised=False, fill=WHITE)
                frac = max(0.0, min(1.0, value / 25.0))
                fill_h = int((gauge_h - 4) * frac)
                colour = (60, 90, 190) if i == 0 else (
                    (40, 140, 60) if effective >= natural else (170, 40, 40))
                pygame.draw.rect(surf, colour,
                                 (bar.x + 2, bar.bottom - 2 - fill_h, bar.width - 4, fill_h))
                W.text(surf, str(value), (bar.x - 1, bar.bottom + 2), 10,
                       bold=True, mono=True)
            label = STAT_ABBR[stat]
            W.text(surf, label, (x + 2, gauge_top + gauge_h + 16), 11, bold=True)
            x += 46

        W.text(surf, "born with / carrying", (client.x + 14, gauge_top + gauge_h + 32),
               10, colour=(120, 120, 120))

        # ---- the numbers ---------------------------------------------------
        col = client.x + 210
        right = client.right - 8
        y = client.y + 34
        level = you.get("level", 1)
        rows = [
            ("Character Level:", level),
            ("Character Experience:", you.get("xp", 0)),
            ("Next Level At:", xp_for_level(level)),
            ("", ""),
            ("Weight:", f"{inv.get('weight', 0)} ({inv.get('capacity', 0)})"),
            ("Bulk:", f"{inv.get('bulk', 0)} ({inv.get('bulk_capacity', 0)})"),
            ("Speed:", speed_text(you)),
            ("", ""),
            ("Hit Points:", f"{you.get('hp', 0)} ({you.get('max_hp', 0)})"),
            ("Mana Points:", f"{you.get('mana', 0)} ({you.get('max_mana', 0)})"),
            ("Copper:", you.get("copper", 0)),
            ("Armor Value:", you.get("ac", 0)),
            ("", ""),
            ("In the strongroom:", you.get("bank", 0)),
            ("", ""),
            ("Time played:", format_clock(you.get("clock", 0))),
            ("Deepest level reached:", you.get("deepest", 0)),
            ("Creatures slain:", you.get("kills", 0)),
            ("Times killed:", you.get("deaths", 0)),
        ]
        for label, value in rows:
            if label:
                W.text(surf, label, (col, y), 13)
                W.text_right(surf, value, right, y, 13, bold=True, mono=True)
            y += 17

        by = client.bottom - 34
        self.buttons = [
            W.Button((client.x, by, 90, 28), "OK", "close"),
            W.Button((client.x + 100, by, 110, 28), "Attributes", "attributes"),
            W.Button((client.right - 90, by, 90, 28), "Help", "help"),
        ]
        for b in self.buttons:
            b.draw(surf)

    def on_action(self, action):
        if action == "help":
            self.app.push(HelpScene(self.app))
        elif action == "attributes":
            self.app.push(AttributesScene(self.app))
        else:
            super().on_action(action)


class AttributesScene(OverlayScene):
    """A plain scrolling list of everything the character currently has going
    on, the way the original's Attributes window works."""

    title = "Character Attributes"
    size = (480, 420)

    def __init__(self, app):
        super().__init__(app)
        self.list = W.ListBox((0, 0, 10, 10), row_height=18)

    def lines(self):
        you = self.app.play.you
        inv = self.app.inventory
        out = [
            f"Level {you.get('level', 1)}, {you.get('xp', 0)} experience",
            f"Next level at {xp_for_level(you.get('level', 1))}",
            "",
        ]
        for stat in STATS:
            natural = you.get("base_stats", {}).get(stat, 10)
            effective = you.get("stats", {}).get(stat, natural)
            note = "" if effective == natural else f"  ({effective - natural:+d} from gear)"
            out.append(f"{stat.title():<14} {effective}{note}")
        out += [
            "",
            f"Armour value    {you.get('ac', 0)}",
            f"Chance to hit   {you.get('to_hit', 0):+d}",
            f"Speed           {speed_text(you)}",
            f"Burden          {you.get('encumbrance', '')}",
            f"Carrying        {inv.get('weight', 0)} g of "
            f"{inv.get('capacity', 1)} g",
            f"Bulk            {inv.get('bulk', 0)} of {inv.get('bulk_capacity', 0)}",
            "",
        ]
        effects = you.get("effects", {})
        if effects:
            out.append("Currently affected by:")
            out += [f"   {name}" for name in sorted(effects)]
        else:
            out.append("Nothing is affecting you.")
        spells = you.get("spells", [])
        out += ["", f"Spells known: {len(spells)}"]
        out += [f"   {name}" for name in spells]
        return out

    def draw(self, surf):
        below = self.app.under(self)
        if below is not None:
            below.draw(surf)
        client, _ = self.frame(surf)
        self.list.rect = pygame.Rect(client.x, client.y, client.width, client.height - 40)

        def draw_row(target, text, rect, selected):
            W.text(target, text, (rect.x + 6, rect.y + 1), 13, mono=True,
                   colour=WHITE if selected else BLACK)

        self.list.draw(surf, self.lines(), draw_row)
        self.buttons = [W.Button((client.centerx - 45, client.bottom - 32, 90, 28),
                                 "OK", "close")]
        for b in self.buttons:
            b.draw(surf)

    def handle(self, event):
        self.list.handle(event)
        super().handle(event)


class MenuOverlay(OverlayScene):
    title = "Stormhold"
    size = (360, 230)

    def draw(self, surf):
        below = self.app.under(self)
        if below is not None:
            below.draw(surf)
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


class ServiceScene(OverlayScene):
    size = (820, 560)

    SHOP_BLURB = {
        "weaponsmith": "Bolgar keeps the edged goods. He buys anything, at his price.",
        "armourer": "Hesta fits plate to people who can carry it, and leather to people who cannot.",
        "general": "Pell sells the dull, necessary things: packs, sacks, belts, cloaks.",
        "magic": "The Gilded Retort: potions, scrolls, and tomes to learn spells from.",
        "sage": "Ulric will tell you what a thing really is, for a fee.",
        "temple": "The Quiet Hour will mend you, cleanse you, and break a curse.",
        "bank": "The strongroom. A thousand copper weigh a kilo - leave them here.",
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
        self.selected_service = None
        self.service_rects = []
        self.amount = W.TextField((0, 0, 110, 26), "100", 6, numeric=True)

    @property
    def shop(self):
        return self.data.get("shop", "general")

    def refresh(self, data):
        self.data = data

    def handle(self, event):
        self.amount.handle(event)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for rect, key in self.service_rects:
                if rect.collidepoint(event.pos):
                    self.selected_service = key
                    return
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
        elif action == "service" and self.selected_service:
            self.app.act({"a": "service", "what": self.selected_service,
                          "temple": True, "npc": npc,
                          "name": self.data.get("name")})
            self.selected_service = None
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

    def draw_temple(self, surf, client, top, list_h):
        """Services and their prices, the way the temple presents them."""
        data = self.data
        services = data.get("services", [])
        drained = data.get("drained", {})
        drained_hp = data.get("drained_hp", 0)

        W.text(surf, "Services", (client.x, top), 13, bold=True)
        box = pygame.Rect(client.x, top + 18, client.width * 3 // 5, list_h)
        W.panel(surf, box, raised=False, fill=(240, 240, 236))

        self.service_rects = []
        y = box.y + 6
        for svc in services:
            row = pygame.Rect(box.x + 6, y, box.width - 12, 22)
            usable = svc["useful"] and svc["afford"]
            dot = pygame.Rect(row.x, row.y + 5, 12, 12)
            pygame.draw.ellipse(surf, WHITE if usable else (212, 212, 208), dot)
            pygame.draw.ellipse(surf, (90, 90, 90), dot, 1)
            if self.selected_service == svc["key"]:
                pygame.draw.ellipse(surf, (20, 20, 90), dot.inflate(-6, -6))
            colour = BLACK if usable else GRAY
            W.text(surf, svc["label"], (row.x + 18, row.y + 3), 13, colour=colour)
            W.text_right(surf, f"{svc['price']} CP", row.right - 4, row.y + 3, 12,
                         mono=True, colour=colour if svc["afford"] else (150, 0, 0))
            if usable:
                self.service_rects.append((row, svc["key"]))
            y += 23

        # What is actually wrong with you, stated plainly.
        side = pygame.Rect(box.right + 12, top + 18,
                           client.right - box.right - 12, list_h)
        W.text(surf, "The sisters look you over", (side.x, side.y), 12, bold=True)
        sy = side.y + 20
        notes = []
        you = self.app.play.you
        if you.get("hp", 1) < you.get("max_hp", 1):
            notes.append(f"Wounded: {you['hp']} of {you['max_hp']}")
        for stat, lost in sorted(drained.items()):
            notes.append(f"{stat.title()} drained by {lost}")
        if drained_hp:
            notes.append(f"{drained_hp} hit points drained away")
        if "poisoned" in (you.get("effects") or {}):
            notes.append("Poison in the blood")
        if not notes:
            notes.append("Nothing ails you.")
        for note in notes:
            for line in W.wrap(note, side.width - 8, 12):
                W.text(surf, line, (side.x, sy), 12, colour=(90, 30, 30))
                sy += 16
        sy += 8
        for line in W.wrap("Draining is not an injury that heals on its own. "
                           "Only the temple can give back what was taken.",
                           side.width - 8, 11):
            W.text(surf, line, (side.x, sy), 11, colour=(110, 110, 110))
            sy += 14

    def draw(self, surf):
        below = self.app.under(self)
        if below is not None:
            below.draw(surf)
        client, _ = self.frame(surf)
        sheet = self.app.sheet
        data = self.data

        W.text(surf, self.SHOP_BLURB.get(self.shop, ""), (client.x + 4, client.y + 2), 12,
               colour=(70, 70, 70))
        W.text_right(surf, f"You have {data.get('copper', 0)} CP", client.right - 4,
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

        if self.shop == "temple":
            self.draw_temple(surf, client, top, list_h)
        elif self.shop != "bank":
            W.text(surf, "For sale", (client.x, top), 13, bold=True)
            self.buy_list.rect = pygame.Rect(client.x, top + 18, col_w, list_h)
            self.buy_list.draw(surf, data.get("stock", []), row_drawer("price"))

            W.text(surf, "Your pack", (client.x + col_w + 20, top), 13, bold=True)
            self.sell_list.rect = pygame.Rect(client.x + col_w + 20, top + 18, col_w, list_h)
            self.sell_list.draw(surf, data.get("sell", []), row_drawer("price"))

        elif self.shop == "temple":
            pass
        else:
            W.text(surf, "The strongroom", (client.x, top), 15, bold=True)
            W.text(surf, f"On you:        {data.get('copper', 0)} CP "
                         f"({data.get('copper', 0)} g to carry)",
                   (client.x, top + 30), 14, mono=True)
            W.text(surf, f"In the vault:  {data.get('bank', 0)} CP  (weighs you nothing)",
                   (client.x, top + 52), 14, mono=True)
            for i, line in enumerate(W.wrap(
                    "A thousand copper weigh a kilo. Carrying a fortune into the keep will "
                    "slow you to a crawl, and if you die down there you drop a fifth of it "
                    "on the floor. Leave it here.", client.width - 20, 13)):
                W.text(surf, line, (client.x, top + 86 + i * 17), 13, colour=(70, 70, 70))
            W.text(surf, "Amount", (client.x, top + 150), 13, bold=True)
            self.amount.rect = pygame.Rect(client.x + 70, top + 146, 110, 26)
            self.amount.draw(surf)

        by = client.bottom - 38
        self.buttons = []
        if self.shop == "temple":
            self.buttons += [
                W.Button((client.x + 60, by, 110, 30), "Cast", "service",
                         enabled=bool(self.selected_service)),
            ]
        elif self.shop == "bank":
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
            if self.shop == "sage":
                pass
        self.buttons.append(W.Button((client.right - 100, by, 90, 30),
                                     "Exit" if self.shop == "temple" else "Leave", "close"))
        for b in self.buttons:
            b.draw(surf)


# ===========================================================================
#  The application
# ===========================================================================


class StoreScene(PackScene):
    """A shop, which is the inventory screen with the floor replaced by stock.

    The original is explicit about this: "Stores operate as an extension of the
    inventory. When you enter a store, the inventory window appears, but with
    the floor replaced by the contents of the store. Clicking and dragging out
    of the store window buys an item, dragging into the store window sells an
    item. In either case, a dialog with the price asked/offered appears and you
    are given a chance to accept or reject the offer."

    So there is no separate shop interface: the same paper doll, the same pack,
    the same dragging, with one more container to drag to and from.
    """

    size = (980, 760)
    DOLL_H = 360

    def __init__(self, app, data):
        super().__init__(app)
        self.data = data
        self.store_rect = pygame.Rect(0, 0, 10, 10)
        self.store_cells = []
        self.store_scroll = 0
        self.confirm = None          # {"text", "yes", "no", "action"}

    @property
    def shop(self):
        return self.data.get("shop", "general")

    def refresh(self, data):
        self.data = data

    def store_title(self):
        # PackScene keeps a `title` attribute of its own, so this is not one.
        return self.data.get("name", "Store")

    # ------------------------------------------------------------ helpers --
    def stock(self):
        return self.data.get("stock", [])

    def sell_price(self, item):
        for row in self.data.get("sell", []):
            if row["id"] == item["id"]:
                return row.get("price", 0)
        return 0

    def item_at(self, pos):
        for rect, item in self.store_cells:
            if rect.collidepoint(pos):
                return item, ("store", None)
        return super().item_at(pos)

    # -------------------------------------------------------------- input --
    def handle(self, event):
        if self.confirm is not None:
            self.handle_confirm(event)
            return
        if (event.type == pygame.MOUSEWHEEL
                and self.store_rect.collidepoint(pygame.mouse.get_pos())):
            self.store_scroll = max(0, self.store_scroll - event.y)
            return
        super().handle(event)

    def handle_confirm(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.confirm["yes"].collidepoint(event.pos):
                self.app.act(self.confirm["action"])
                self.confirm = None
            elif self.confirm["no"].collidepoint(event.pos):
                self.confirm = None
        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_y, pygame.K_RETURN):
                self.app.act(self.confirm["action"])
                self.confirm = None
            elif event.key in (pygame.K_n, pygame.K_ESCAPE):
                self.confirm = None

    def ask(self, text, action):
        self.confirm = {"text": text, "action": action,
                        "yes": pygame.Rect(0, 0, 1, 1),
                        "no": pygame.Rect(0, 0, 1, 1)}

    def finish_drag(self, pos):
        drag = self.drag
        if drag is None:
            return
        item = drag["item"]
        npc = self.data.get("npc")

        # dragging out of the store window buys
        if drag["from"] == "store":
            self.drag = None
            self.hover_slot = None
            if not drag["moved"] or self.store_rect.collidepoint(pos):
                return
            price = item.get("price", 0)
            self.ask(f"It'll cost you {price} C.P. for that. Take it?",
                     {"a": "buy", "shop": self.shop, "id": item["id"],
                      "npc": npc, "name": self.data.get("name")})
            return

        # dragging into the store window sells - or asks the sage to identify
        if drag["moved"] and self.store_rect.collidepoint(pos):
            self.drag = None
            self.hover_slot = None
            if self.shop == "sage":
                price = self.data.get("identify_price", 0)
                self.ask(f"I can tell you what that is for {price} C.P. Well?",
                         {"a": "service", "shop": self.shop, "key": "identify",
                          "id": item["id"], "npc": npc})
            else:
                price = self.sell_price(item)
                self.ask(f"I'll give you {price} C.P. for that. Take it?",
                         {"a": "sell", "shop": self.shop, "id": item["id"],
                          "npc": npc, "name": self.data.get("name")})
            return

        super().finish_drag(pos)

    # --------------------------------------------------------------- draw --
    def draw(self, surf):
        super().draw(surf)
        if self.confirm is not None:
            self.draw_confirm(surf)

    def draw_pack(self, surf, area):
        """Split the right-hand side: the store above, your pack below."""
        top = pygame.Rect(area.x, area.y, area.width, area.height // 2 - 6)
        bottom = pygame.Rect(area.x, top.bottom + 12, area.width,
                             area.height - top.height - 12)
        self.draw_store(surf, top)
        super().draw_pack(surf, bottom)

    def draw_store(self, surf, area):
        bar = pygame.Rect(area.x, area.y, area.width, 18)
        pygame.draw.rect(surf, W.TITLE_B, bar)
        purse = self.data.get("copper", 0)
        W.text(surf, f"{self.store_title()}      you have {purse} C.P.",
               (bar.x + 6, bar.y + 2), 12, bold=True, colour=WHITE)

        self.store_rect = pygame.Rect(area.x, bar.bottom, area.width,
                                      area.height - bar.height)
        W.panel(surf, self.store_rect, raised=False, fill=(236, 236, 232))

        cell, cell_h = self.CELL, self.CELL_H
        cols = max(1, (self.store_rect.width - 8) // cell)
        rows = max(1, (self.store_rect.height - 8) // cell_h)
        stock = self.stock()
        max_scroll = max(0, (len(stock) + cols - 1) // cols - rows)
        self.store_scroll = min(self.store_scroll, max_scroll)

        self.store_cells = []
        clip = surf.get_clip()
        surf.set_clip(self.store_rect)
        for index, item in enumerate(stock):
            row, col = divmod(index, cols)
            row -= self.store_scroll
            if row < 0 or row >= rows + 1:
                continue
            r = pygame.Rect(self.store_rect.x + 4 + col * cell,
                            self.store_rect.y + 4 + row * cell_h, cell - 4, cell_h - 4)
            img = self.app.sheet.item(item["icon"])
            if img:
                surf.blit(img, (r.centerx - TILE // 2, r.y + 2))
            lines = self.caption(item["name"], r.width - 4)
            ly = r.bottom - 18 - 11 * len(lines)
            for line in lines:
                img2 = W.font(10).render(line, True, BLACK)
                surf.blit(img2, (r.centerx - img2.get_width() // 2, ly))
                ly += 11
            price = f"{item.get('price', 0)}"
            W.text(surf, price, (r.centerx - W.font(10, bold=True).size(price)[0] // 2,
                                 r.bottom - 14), 10, bold=True, colour=(0, 90, 0))
            self.store_cells.append((r, item))
        surf.set_clip(clip)

        if max_scroll:
            W.text(surf, f"{self.store_scroll + 1}/{max_scroll + 1}  (scroll wheel)",
                   (self.store_rect.right - 110, self.store_rect.bottom - 16), 10,
                   colour=(120, 120, 120))
        if not stock:
            W.text(surf, "Nothing for sale today.",
                   (self.store_rect.x + 10, self.store_rect.y + 10), 12,
                   colour=(120, 120, 120))

    def draw_confirm(self, surf):
        w, h = 430, 120
        box = pygame.Rect(surf.get_width() // 2 - w // 2,
                          surf.get_height() // 2 - h // 2, w, h)
        W.panel(surf, box, raised=True)
        W.text(surf, self.confirm["text"], (box.x + 20, box.y + 26), 13, bold=True)
        yes = pygame.Rect(box.x + 90, box.bottom - 46, 90, 30)
        no = pygame.Rect(box.right - 180, box.bottom - 46, 90, 30)
        for rect, label in ((yes, "Yes"), (no, "No")):
            W.panel(surf, rect, raised=True)
            img = W.font(13, bold=True).render(label, True, BLACK)
            surf.blit(img, (rect.centerx - img.get_width() // 2,
                            rect.centery - img.get_height() // 2))
        self.confirm["yes"], self.confirm["no"] = yes, no


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
        if args.port:
            # --port was parsed and then ignored: hosting always read the
            # saved setting, so the flag did nothing.
            self.settings["port"] = args.port
        self.client = GameClient()
        self.server = None
        self.scenes = [MenuScene(self)]
        self.play = None
        self.inventory = {"items": [], "equipment": {}, "copper": 0}
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

    def under(self, scene):
        """The scene directly beneath this one in the stack.

        Overlays draw whatever is behind them. Asking for "the scene under the
        top of the stack" is wrong as soon as two overlays are open: the lower
        one is handed itself and draws forever. This asks relative to the
        scene that is actually drawing.
        """
        try:
            i = self.scenes.index(scene)
        except ValueError:
            return None
        return self.scenes[i - 1] if i > 0 else None

    def push(self, scene):
        scene.layout(self.screen.get_size())
        self.scenes.append(scene)

    def pop(self):
        if len(self.scenes) > 1:
            self.scenes.pop()

    def replace(self, scene):
        scene.layout(self.screen.get_size())
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

    def join_as(self, name, stats, colour, resume, spell=None, difficulty=None):
        self.settings["name"] = name
        self.save_settings()
        self.client.send(P.C_HELLO, {"name": name, "stats": stats, "colour": colour,
                                     "resume": resume, "spell": spell,
                                     "difficulty": difficulty,
                                     "version": PROTOCOL_VERSION})

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
                if kind == P.S_SHOP and isinstance(self.scene, (ServiceScene, StoreScene)):
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
                    self.scene.layout(self.screen.get_size())
                else:
                    self.scene.handle(event)

            self.scene.update(dt)
            self.scene.draw(self.screen)
            pygame.display.flip()

        self.client.close()
        if self.server:
            self.server.stop()
        pygame.quit()
