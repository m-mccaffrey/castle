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
        self.pressed = False

    def draw(self, surf):
        panel(surf, self.rect, raised=not self.pressed)
        colour = INK if self.enabled else DISABLED
        img = font(13, bold=True).render(self.label, True, colour)
        off = 1 if self.pressed else 0
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
