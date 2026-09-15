"""Window chrome in the style of the period: grey faces, hard bevels, and a
blue title bar. Everything is drawn with rectangles, so it costs a Raspberry Pi
almost nothing."""

import pygame

from .palette import (BLACK, WHITE, SILVER, GRAY, NAVY, TEAL, MAROON, YELLOW,
                      GREEN, RED, LIME, AQUA, OLIVE, PURPLE, FUCHSIA, BLUE)

FACE = SILVER
FACE_LIGHT = WHITE
FACE_SHADOW = GRAY
FACE_DARK = (64, 64, 64)
TITLE_A = (0, 0, 128)
TITLE_B = (58, 110, 165)
INK = BLACK
DISABLED = GRAY

_fonts = {}


def font(size=14, bold=False, mono=False):
    key = (size, bold, mono)
    cached = _fonts.get(key)
    if cached is not None:
        return cached
    names = ("dejavusansmono,couriernew,consolas,monospace" if mono
             else "dejavusans,tahoma,verdana,arial,sans")
    try:
        f = pygame.font.SysFont(names, size, bold=bold)
    except Exception:
        f = pygame.font.Font(None, size + 2)
    if f is None:
        f = pygame.font.Font(None, size + 2)
    _fonts[key] = f
    return f


def bevel(surf, rect, raised=True, width=2):
    """The signature raised or sunken border."""
    x, y, w, h = rect
    hi = FACE_LIGHT if raised else FACE_DARK
    lo = FACE_DARK if raised else FACE_LIGHT
    for i in range(width):
        pygame.draw.line(surf, hi, (x + i, y + i), (x + w - 2 - i, y + i))
        pygame.draw.line(surf, hi, (x + i, y + i), (x + i, y + h - 2 - i))
        pygame.draw.line(surf, lo, (x + i, y + h - 1 - i), (x + w - 1 - i, y + h - 1 - i))
        pygame.draw.line(surf, lo, (x + w - 1 - i, y + i), (x + w - 1 - i, y + h - 1 - i))


def panel(surf, rect, raised=True, fill=FACE):
    pygame.draw.rect(surf, fill, rect)
    bevel(surf, rect, raised)


def window(surf, rect, title, active=True):
    """A framed window with a title bar. Returns the client rectangle."""
    x, y, w, h = rect
    panel(surf, rect, raised=True)
    bar = pygame.Rect(x + 4, y + 4, w - 8, 20)
    for i in range(bar.height):
        t = i / max(1, bar.height - 1)
        col = tuple(int(TITLE_A[c] + (TITLE_B[c] - TITLE_A[c]) * t) for c in range(3))
        pygame.draw.line(surf, col if active else GRAY,
                         (bar.x, bar.y + i), (bar.right - 1, bar.y + i))
    label = font(13, bold=True).render(title, True, WHITE)
    surf.blit(label, (bar.x + 5, bar.y + 3))
    return pygame.Rect(x + 6, y + 28, w - 12, h - 34)


def text(surf, value, pos, size=13, colour=INK, bold=False, mono=False):
    img = font(size, bold, mono).render(str(value), True, colour)
    surf.blit(img, pos)
    return img.get_rect(topleft=pos)


def text_right(surf, value, right, y, size=13, colour=INK, bold=False, mono=False):
    img = font(size, bold, mono).render(str(value), True, colour)
    surf.blit(img, (right - img.get_width(), y))
    return img.get_width()


def wrap(value, width_px, size=13, mono=False):
    """Break a string into lines that fit a pixel width."""
    f = font(size, mono=mono)
    words = str(value).split()
    lines, current = [], ""
    for word in words:
        trial = f"{current} {word}".strip()
        if f.size(trial)[0] <= width_px or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


class Button:
    def __init__(self, rect, label, action=None, enabled=True, hotkey=None):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.action = action
        self.enabled = enabled
        self.hotkey = hotkey
        self.pressed = False        # held down right now
        self.selected = False       # the chosen one of a set, drawn sunken

    def draw(self, surf):
        # `pressed` belongs to the mouse and is cleared on release. A caller
        # that wants a button to look chosen sets `selected` instead: writing
        # to `pressed` from draw() disarms the button between the press and
        # the release, so the click never fires.
        down = self.pressed or self.selected
        # A chosen button is also tinted: a two-pixel bevel alone is too quiet
        # to answer "which difficulty am I on?" at a glance.
        panel(surf, self.rect, raised=not down,
              fill=(198, 208, 232) if self.selected else FACE)
        colour = INK if self.enabled else DISABLED
        img = font(13, bold=True).render(self.label, True, colour)
        off = 1 if down else 0
        surf.blit(img, (self.rect.centerx - img.get_width() // 2 + off,
                        self.rect.centery - img.get_height() // 2 + off))

    def handle(self, event):
        if not self.enabled:
            return None
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.pressed = True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            was = self.pressed
            self.pressed = False
            if was and self.rect.collidepoint(event.pos):
                return self.action
        elif event.type == pygame.KEYDOWN and self.hotkey and event.key == self.hotkey:
            return self.action
        return None


class TextField:
    def __init__(self, rect, value="", max_len=14, numeric=False):
        self.rect = pygame.Rect(rect)
        self.value = value
        self.max_len = max_len
        self.numeric = numeric
        self.focused = False
        self._blink = 0

    def draw(self, surf):
        panel(surf, self.rect, raised=False, fill=WHITE)
        img = font(14, mono=True).render(self.value, True, INK)
        surf.blit(img, (self.rect.x + 5, self.rect.centery - img.get_height() // 2))
        if self.focused:
            self._blink = (self._blink + 1) % 60
            if self._blink < 34:
                cx = self.rect.x + 6 + img.get_width()
                pygame.draw.line(surf, INK, (cx, self.rect.y + 5), (cx, self.rect.bottom - 5))

    def handle(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.focused = self.rect.collidepoint(event.pos)
        elif event.type == pygame.KEYDOWN and self.focused:
            if event.key == pygame.K_BACKSPACE:
                self.value = self.value[:-1]
            elif event.key in (pygame.K_RETURN, pygame.K_TAB, pygame.K_ESCAPE):
                self.focused = False
            elif event.unicode and len(self.value) < self.max_len:
                ch = event.unicode
                if ch.isprintable() and (not self.numeric or ch.isdigit()):
                    self.value += ch
        return None


class ListBox:
    """A sunken scrolling list. Rows are drawn by a callback."""

    def __init__(self, rect, row_height=34):
        self.rect = pygame.Rect(rect)
        self.row_height = row_height
        self.scroll = 0
        self.selected = None
        self.count = 0

    @property
    def visible_rows(self):
        return max(1, (self.rect.height - 4) // self.row_height)

    def clamp(self):
        max_scroll = max(0, self.count - self.visible_rows)
        self.scroll = max(0, min(self.scroll, max_scroll))

    def draw(self, surf, rows, draw_row):
        self.count = len(rows)
        self.clamp()
        panel(surf, self.rect, raised=False, fill=(232, 232, 228))
        clip = surf.get_clip()
        inner = self.rect.inflate(-4, -4)
        surf.set_clip(inner)
        for i in range(self.visible_rows + 1):
            index = self.scroll + i
            if index >= len(rows):
                break
            row_rect = pygame.Rect(inner.x, inner.y + i * self.row_height,
                                   inner.width, self.row_height)
            if index == self.selected:
                pygame.draw.rect(surf, TITLE_A, row_rect)
            draw_row(surf, rows[index], row_rect, index == self.selected)
        surf.set_clip(clip)

        if self.count > self.visible_rows:
            track = pygame.Rect(self.rect.right - 14, self.rect.y + 2, 12, self.rect.height - 4)
            panel(surf, track, raised=False, fill=(210, 210, 206))
            span = max(1, self.count - self.visible_rows)
            frac = self.scroll / span
            knob_h = max(18, int(track.height * self.visible_rows / self.count))
            knob_y = track.y + int((track.height - knob_h) * frac)
            panel(surf, pygame.Rect(track.x, knob_y, track.width, knob_h), raised=True)

    def handle(self, event):
        """Returns the index clicked, or None."""
        if event.type == pygame.MOUSEWHEEL:
            mouse = pygame.mouse.get_pos()
            if self.rect.collidepoint(mouse):
                self.scroll -= event.y
                self.clamp()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                inner_y = event.pos[1] - self.rect.y - 2
                index = self.scroll + inner_y // self.row_height
                if 0 <= index < self.count:
                    self.selected = index
                    return index
        return None


def bar(surf, rect, fraction, colour, label=None, back=(40, 40, 40)):
    """A sunken meter: health, mana, experience, encumbrance."""
    pygame.draw.rect(surf, back, rect)
    inner = pygame.Rect(rect)
    inner.width = max(0, int(rect[2] * max(0.0, min(1.0, fraction))))
    if inner.width:
        pygame.draw.rect(surf, colour, inner)
    bevel(surf, rect, raised=False, width=1)
    if label:
        img = font(11, bold=True, mono=True).render(label, True, WHITE)
        shadow = font(11, bold=True, mono=True).render(label, True, BLACK)
        cx = rect[0] + rect[2] // 2 - img.get_width() // 2
        cy = rect[1] + rect[3] // 2 - img.get_height() // 2
        surf.blit(shadow, (cx + 1, cy + 1))
        surf.blit(img, (cx, cy))


class MenuBar:
    """A Windows-style menu bar with drop-downs.

    Menus are given as (label, [(item label, action, enabled), ...]). An item
    whose label is "-" draws a separator. A menu with no items acts as a button
    and fires its own action immediately, which is how the original's
    Character!, Inventory! and Map! entries behave.
    """

    HEIGHT = 22

    def __init__(self, menus):
        self.menus = menus
        self.open_index = None
        self.hover_item = None
        self._rects = []
        self._item_rects = []

    def layout(self, width):
        self._rects = []
        x = 4
        f = font(13)
        for label, _items in self.menus:
            w = f.size(label)[0] + 18
            self._rects.append(pygame.Rect(x, 0, w, self.HEIGHT))
            x += w

    def draw(self, surf, width):
        self.layout(width)
        bar = pygame.Rect(0, 0, width, self.HEIGHT)
        pygame.draw.rect(surf, FACE, bar)
        pygame.draw.line(surf, FACE_SHADOW, (0, self.HEIGHT - 1), (width, self.HEIGHT - 1))

        for i, (label, items) in enumerate(self.menus):
            rect = self._rects[i]
            if i == self.open_index and items:
                pygame.draw.rect(surf, TITLE_A, rect)
            colour = WHITE if (i == self.open_index and items) else INK
            img = font(13).render(label, True, colour)
            surf.blit(img, (rect.x + 9, rect.centery - img.get_height() // 2))

        self._item_rects = []
        if self.open_index is None:
            return
        items = self.menus[self.open_index][1]
        if not items:
            return
        f = font(13)
        w = max(f.size(t)[0] for t, _a, _e in items) + 44
        h = sum(8 if t == "-" else 20 for t, _a, _e in items) + 8
        origin = self._rects[self.open_index]
        panel_rect = pygame.Rect(origin.x, self.HEIGHT, w, h)
        panel(surf, panel_rect, raised=True)

        y = panel_rect.y + 4
        for text, action, enabled in items:
            if text == "-":
                pygame.draw.line(surf, FACE_SHADOW, (panel_rect.x + 4, y + 3),
                                 (panel_rect.right - 4, y + 3))
                y += 8
                continue
            row = pygame.Rect(panel_rect.x + 2, y, panel_rect.width - 4, 20)
            if enabled and self.hover_item == len(self._item_rects):
                pygame.draw.rect(surf, TITLE_A, row)
                colour = WHITE
            else:
                colour = INK if enabled else DISABLED
            img = f.render(text, True, colour)
            surf.blit(img, (row.x + 20, row.centery - img.get_height() // 2))
            self._item_rects.append((row, action, enabled))
            y += 20

    def handle(self, event):
        """Returns an action string when something is chosen."""
        if event.type == pygame.MOUSEMOTION:
            self.hover_item = None
            for i, (rect, _a, enabled) in enumerate(self._item_rects):
                if rect.collidepoint(event.pos) and enabled:
                    self.hover_item = i
            if self.open_index is not None:
                for i, rect in enumerate(self._rects):
                    if rect.collidepoint(event.pos) and self.menus[i][1]:
                        self.open_index = i
            return None

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, rect in enumerate(self._rects):
                if not rect.collidepoint(event.pos):
                    continue
                label, items = self.menus[i]
                if not items:
                    self.open_index = None
                    return label            # an immediate command, not a menu
                self.open_index = None if self.open_index == i else i
                return None
            for rect, action, enabled in self._item_rects:
                if rect.collidepoint(event.pos) and enabled:
                    self.open_index = None
                    return action
            self.open_index = None
        return None

    @property
    def is_open(self):
        return self.open_index is not None


class Toolbar:
    """The row of verb buttons under the menu, plus quick-cast spell icons."""

    HEIGHT = 30

    def __init__(self, verbs):
        self.verbs = verbs                  # [(label, action)]
        self.buttons = []
        self.spell_rects = []

    def draw(self, surf, width, sheet=None, spells=()):
        bar = pygame.Rect(0, MenuBar.HEIGHT, width, self.HEIGHT)
        pygame.draw.rect(surf, FACE, bar)
        pygame.draw.line(surf, FACE_SHADOW, (0, bar.bottom - 1), (width, bar.bottom - 1))

        self.buttons = []
        x = 4
        f = font(12, bold=True)
        for label, action in self.verbs:
            w = f.size(label)[0] + 16
            rect = pygame.Rect(x, bar.y + 3, w, self.HEIGHT - 7)
            panel(surf, rect, raised=True)
            img = f.render(label, True, INK)
            surf.blit(img, (rect.centerx - img.get_width() // 2,
                            rect.centery - img.get_height() // 2))
            self.buttons.append((rect, action))
            x += w + 3

        # Quick-cast slots, which fill up as spells are learned.
        self.spell_rects = []
        x += 10
        for i, name in enumerate(spells[:12]):
            rect = pygame.Rect(x, bar.y + 3, 26, self.HEIGHT - 7)
            panel(surf, rect, raised=True)
            img = font(11, bold=True).render(str(i + 1), True, (60, 60, 120))
            surf.blit(img, (rect.centerx - img.get_width() // 2,
                            rect.centery - img.get_height() // 2))
            self.spell_rects.append((rect, name))
            x += 28

    def handle(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for rect, action in self.buttons:
                if rect.collidepoint(event.pos):
                    return ("verb", action)
            for rect, name in self.spell_rects:
                if rect.collidepoint(event.pos):
                    return ("spell", name)
        return None
