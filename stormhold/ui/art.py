"""Every sprite in Stormhold, drawn in code in the Windows 3.1 icon idiom.

House rules, all borrowed from the icon art of the period:
  * only the sixteen VGA colours, with ordered dithering for anything between
  * a hard black outline around every object
  * one light source, always upper-left: highlights up-left, shadow down-right
  * chunky and readable first, detailed second

Nothing here is loaded from disk. Icons are built once at start-up into pygame
surfaces and cached.
"""

import pygame

from .palette import (
    BLACK, MAROON, GREEN, OLIVE, NAVY, PURPLE, TEAL, SILVER, GRAY, RED, LIME,
    YELLOW, BLUE, FUCHSIA, AQUA, WHITE,
    BROWN, DARK_BROWN, TAN, PALE_SKIN, DARK_STONE, MID_STONE, PALE_STONE,
    DARK_GREEN, MOSS, DEEP_WATER, SHALLOW, RUST, EMBER, BONE, SHADOW_BLUE,
    BRUISE, ICE, GOLD_DITHER, COPPER, PLUM, SICK_GREEN,
    resolve, is_pair, darker, lighter,
)

ICON = 32          # icon grid: the Windows 3.1 standard
TILE = 32          # one map tile on screen


class Icon:
    """A small pixel canvas that speaks in palette colours and dither pairs."""

    __slots__ = ("w", "h", "px")

    def __init__(self, w=ICON, h=ICON):
        self.w = w
        self.h = h
        self.px = [[None] * w for _ in range(h)]   # None means transparent

    # ---------------------------------------------------------- primitives --
    def set(self, x, y, colour):
        if colour is None:
            return
        x = int(x); y = int(y)
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y][x] = resolve(colour, x, y)

    def get(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.px[y][x]
        return None

    def rect(self, x, y, w, h, colour):
        for j in range(int(y), int(y + h)):
            for i in range(int(x), int(x + w)):
                self.set(i, j, colour)

    def frame(self, x, y, w, h, colour):
        self.rect(x, y, w, 1, colour)
        self.rect(x, y + h - 1, w, 1, colour)
        self.rect(x, y, 1, h, colour)
        self.rect(x + w - 1, y, 1, h, colour)

    def oval(self, cx, cy, rx, ry, colour):
        for j in range(int(cy - ry), int(cy + ry) + 1):
            for i in range(int(cx - rx), int(cx + rx) + 1):
                dx = (i + 0.5 - cx) / max(0.001, rx)
                dy = (j + 0.5 - cy) / max(0.001, ry)
                if dx * dx + dy * dy <= 1.0:
                    self.set(i, j, colour)

    def line(self, x0, y0, x1, y1, colour):
        x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        for _ in range(256):
            self.set(x0, y0, colour)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

    def tri(self, pts, colour):
        """Filled triangle, used for roofs, blades, wings and teeth."""
        (ax, ay), (bx, by), (cx, cy) = pts
        min_x, max_x = int(min(ax, bx, cx)), int(max(ax, bx, cx))
        min_y, max_y = int(min(ay, by, cy)), int(max(ay, by, cy))
        d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if d == 0:
            return
        for j in range(min_y, max_y + 1):
            for i in range(min_x, max_x + 1):
                a = ((by - cy) * (i + .5 - cx) + (cx - bx) * (j + .5 - cy)) / d
                b = ((cy - ay) * (i + .5 - cx) + (ax - cx) * (j + .5 - cy)) / d
                if a >= 0 and b >= 0 and a + b <= 1:
                    self.set(i, j, colour)

    # ------------------------------------------------------------- effects --
    def outline(self, colour=BLACK):
        """Trace a hard border around everything opaque. Very icon."""
        edges = []
        for y in range(self.h):
            for x in range(self.w):
                if self.px[y][x] is not None:
                    continue
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < self.w and 0 <= ny < self.h and self.px[ny][nx] is not None:
                        edges.append((x, y))
                        break
        for x, y in edges:
            self.px[y][x] = colour
        return self

    def shade(self, light=True, dark=True):
        """Light the top edge of each solid mass and shadow its underside.

        Only horizontal edges are touched. Shading every exposed pixel rims
        the whole silhouette and makes the icon read as a flat blob.
        """
        snapshot = [row[:] for row in self.px]

        def solid(x, y):
            return (0 <= x < self.w and 0 <= y < self.h
                    and snapshot[y][x] is not None and snapshot[y][x] != BLACK)

        for y in range(self.h):
            for x in range(self.w):
                c = snapshot[y][x]
                if c is None or c == BLACK:
                    continue
                if light and not solid(x, y - 1):
                    self.px[y][x] = lighter(c)
                elif dark and not solid(x, y + 1):
                    self.px[y][x] = darker(c)
        return self

    def bevel(self, x, y, w, h, face, raised=True):
        """A raised (or sunken) 3D box, the signature Windows control look."""
        hi = WHITE if raised else GRAY
        lo = GRAY if raised else WHITE
        self.rect(x, y, w, h, face)
        self.rect(x, y, w, 1, hi)
        self.rect(x, y, 1, h, hi)
        self.rect(x, y + h - 1, w, 1, lo)
        self.rect(x + w - 1, y, 1, h, lo)
        return self

    # -------------------------------------------------------------- output --
    def surface(self, scale=1):
        surf = pygame.Surface((self.w * scale, self.h * scale), pygame.SRCALPHA)
        surf.fill((0, 0, 0, 0))
        for y in range(self.h):
            row = self.px[y]
            for x in range(self.w):
                c = row[x]
                if c is None:
                    continue
                if scale == 1:
                    surf.set_at((x, y), c)
                else:
                    surf.fill(c, (x * scale, y * scale, scale, scale))
        return surf

    def flipped(self):
        """Mirror horizontally, for creatures facing the other way."""
        out = Icon(self.w, self.h)
        for y in range(self.h):
            for x in range(self.w):
                out.px[y][self.w - 1 - x] = self.px[y][x]
        return out


# ===========================================================================
#  Terrain. These fill the whole cell, so no transparency and no outline.
# ===========================================================================

def _noise(x, y, seed=0):
    """Small deterministic hash so tile variants look the same everywhere."""
    n = (x * 73856093) ^ (y * 19349663) ^ (seed * 83492791)
    n = (n ^ (n >> 13)) * 1274126177
    return ((n ^ (n >> 16)) & 0xFFFF) / 65535.0


def tile_floor(variant=0):
    ic = Icon()
    ic.rect(0, 0, ICON, ICON, BLACK)
    # Dark flagstones. Kept deliberately low in value: the walls are the light
    # thing on screen, so a lit room reads at a glance.
    for by in range(0, ICON, 16):
        for bx in range(0, ICON, 16):
            off = 8 if (by // 16) % 2 else 0
            x = (bx + off) % ICON
            ic.rect(x + 1, by + 1, 14, 14, DARK_STONE)
            ic.rect(x + 1, by + 1, 14, 1, GRAY)
            ic.rect(x + 1, by + 1, 1, 14, GRAY)
    for i in range(5):
        n1 = _noise(variant, i, 3)
        n2 = _noise(i, variant, 7)
        ic.set(int(n1 * ICON), int(n2 * ICON), GRAY)
    return ic


def tile_wall(variant=0):
    ic = Icon()
    ic.rect(0, 0, ICON, ICON, GRAY)
    # Brick courses, offset row to row, each brick individually bevelled.
    bh = 8
    for row, by in enumerate(range(0, ICON, bh)):
        off = 0 if row % 2 == 0 else 8
        for bx in range(-8, ICON, 16):
            x = bx + off
            ic.rect(x + 1, by + 1, 14, bh - 2, MID_STONE)
            ic.rect(x + 1, by + 1, 14, 1, SILVER)     # lit top
            ic.rect(x + 1, by + 1, 1, bh - 2, SILVER)  # lit left
            ic.rect(x + 1, by + bh - 2, 14, 1, DARK_STONE)
            ic.rect(x + 14, by + 1, 1, bh - 2, DARK_STONE)
    ic.rect(0, 0, ICON, 1, SILVER)
    ic.rect(0, ICON - 1, ICON, 1, BLACK)
    return ic


def tile_shop_floor(variant=0):
    ic = Icon()
    ic.rect(0, 0, ICON, ICON, DARK_BROWN)
    for x in range(0, ICON, 8):
        ic.rect(x + 1, 0, 6, ICON, BROWN)      # boards
        ic.rect(x, 0, 1, ICON, BLACK)          # seam between them
    for i in range(4):                          # a few nail heads
        ic.set(3 + (i % 2) * 8, 4 + i * 7, OLIVE)
    return ic


def tile_grass(variant=0):
    ic = Icon()
    ic.rect(0, 0, ICON, ICON, MOSS)
    for i in range(18):
        x = int(_noise(variant, i, 11) * (ICON - 2))
        y = int(_noise(i, variant, 13) * (ICON - 3))
        c = LIME if _noise(i, i, variant) > 0.75 else DARK_GREEN
        ic.rect(x, y, 1, 3, c)
    return ic


def tile_road(variant=0):
    ic = Icon()
    ic.rect(0, 0, ICON, ICON, (OLIVE, GRAY, 0.5))
    for i in range(10):
        x = int(_noise(variant, i, 17) * (ICON - 3))
        y = int(_noise(i, variant, 19) * (ICON - 3))
        ic.rect(x, y, 2, 2, SILVER if i % 2 else GRAY)
    return ic


def tile_tree(variant=0):
    ic = Icon()
    ic.rect(0, 0, ICON, ICON, MOSS)
    ic.rect(14, 20, 5, 12, BROWN)
    ic.rect(14, 20, 1, 12, (MAROON, YELLOW, 0.25))
    ic.oval(16, 14, 11, 11, GREEN)
    ic.oval(13, 11, 6, 6, LIME)          # sunlit crown
    ic.oval(21, 19, 5, 5, DARK_GREEN)    # shaded underside
    return ic


def tile_water(variant=0):
    ic = Icon()
    ic.rect(0, 0, ICON, ICON, DEEP_WATER)
    for y in range(2, ICON, 8):
        off = int(_noise(variant, y, 23) * 10)
        ic.rect(off, y, ICON - off - 6, 2, SHALLOW)
        ic.rect(off + 2, y, 5, 1, AQUA)
    return ic


def tile_rubble(variant=0):
    ic = Icon()
    ic.rect(0, 0, ICON, ICON, DARK_STONE)
    chunks = [(2, 3, 9, 7), (14, 2, 11, 8), (25, 6, 6, 6),
              (1, 13, 8, 8), (11, 12, 10, 9), (22, 15, 9, 8),
              (4, 23, 10, 8), (16, 23, 7, 8), (25, 25, 6, 6)]
    for i, (x, y, w, h) in enumerate(chunks):
        jx = int(_noise(variant, i, 29) * 2)
        x = min(x + jx, ICON - w)
        ic.rect(x, y, w, h, MID_STONE)
        ic.rect(x, y, w, 1, SILVER)         # lit top face
        ic.rect(x, y, 1, h, SILVER)
        ic.rect(x, y + h - 1, w, 1, BLACK)  # shadow under
        ic.rect(x + w - 1, y, 1, h, BLACK)
    return ic


def tile_door(closed=True):
    ic = Icon()
    ic.rect(0, 0, ICON, ICON, DARK_STONE)
    if closed:
        ic.rect(3, 1, 26, 30, BROWN)
        ic.rect(3, 1, 26, 1, (MAROON, YELLOW, 0.35))
        ic.rect(3, 1, 1, 30, (MAROON, YELLOW, 0.35))
        ic.rect(3, 30, 26, 1, BLACK)
        ic.rect(28, 1, 1, 30, BLACK)
        for y in range(4, 30, 7):                    # plank seams
            ic.rect(5, y, 22, 1, DARK_BROWN)
        ic.rect(22, 14, 5, 4, YELLOW)                # handle plate
        ic.rect(22, 14, 5, 1, WHITE)
        ic.rect(24, 15, 2, 2, BLACK)                 # keyhole
    else:
        # Stone jambs either side, the door itself folded back against one.
        ic.rect(0, 0, 4, ICON, MID_STONE)
        ic.rect(28, 0, 4, ICON, MID_STONE)
        ic.rect(0, 0, 1, ICON, SILVER)
        ic.rect(28, 0, 1, ICON, SILVER)
        ic.rect(4, 0, 24, ICON, BLACK)               # the opening
        ic.rect(4, 0, 7, ICON, BROWN)                # swung-back door panel
        ic.rect(4, 0, 1, ICON, (MAROON, YELLOW, 0.35))
        ic.rect(10, 0, 1, ICON, BLACK)
        for y in range(3, 30, 7):
            ic.rect(5, y, 5, 1, DARK_BROWN)
        ic.rect(11, 26, 17, 6, MID_STONE)            # floor showing through
    return ic


def tile_stairs(down=True):
    ic = Icon()
    ic.rect(0, 0, ICON, ICON, DARK_STONE)
    if down:
        # Steps receding into the dark; each tread lit on its leading edge.
        for i in range(4):
            inset = i * 4
            ic.rect(inset, inset, ICON - inset * 2, 4, MID_STONE)
            ic.rect(inset, inset, ICON - inset * 2, 1, SILVER)
            ic.rect(inset, inset + 3, ICON - inset * 2, 1, BLACK)
        ic.rect(12, 16, 8, 15, BLACK)
    else:
        # Steps climbing away, each narrower than the one in front of it.
        for i in range(5):
            w = ICON - 4 - i * 5
            x = (ICON - w) // 2
            y = ICON - 6 - i * 5
            ic.rect(x, y, w, 5, MID_STONE)
            ic.rect(x, y, w, 1, WHITE)           # lit tread
            ic.rect(x, y + 4, w, 1, BLACK)       # riser shadow
            ic.rect(x, y, 1, 5, SILVER)
            ic.rect(x + w - 1, y, 1, 5, GRAY)
    return ic


def tile_altar():
    ic = Icon()
    ic.rect(0, 0, ICON, ICON, DARK_STONE)
    ic.rect(6, 12, 20, 16, MID_STONE)
    ic.rect(6, 12, 20, 1, WHITE)
    ic.rect(6, 27, 20, 1, BLACK)
    ic.rect(3, 8, 26, 5, SILVER)
    ic.rect(3, 8, 26, 1, WHITE)
    ic.rect(12, 2, 8, 6, PLUM)
    ic.rect(12, 2, 8, 1, FUCHSIA)
    return ic


def tile_void():
    ic = Icon()
    ic.rect(0, 0, ICON, ICON, BLACK)
    return ic


# ===========================================================================
#  Creatures. All original designs, built from a few parametric bodies so the
#  bestiary reads as one coherent icon set.
# ===========================================================================

def humanoid(skin=TAN, cloth=NAVY, trim=YELLOW, eyes=WHITE, weapon=None,
             shield=False, helm=None, hood=False, horns=False, crown=False,
             bulk=0, tattered=False, ribs=False, boots=DARK_BROWN, aura=None,
             hunched=False):
    """One upright two-legged figure, from a kobold to a king.

    Laid out in horizontal bands with a black rule between each, because on a
    32-pixel icon the only thing that separates a head from a chest is a line.
    """
    ic = Icon()
    heavy = bulk >= 4

    head_w = 10 + (2 if heavy else 0)
    torso_w = 14 + bulk
    head_x = 16 - head_w // 2
    torso_x = 16 - torso_w // 2

    head_y = 3 if hunched else 2
    head_h = 9 if heavy else 8
    neck_y = head_y + head_h                 # black rule
    torso_y = neck_y + 1
    torso_h = 13 if heavy else 11
    waist_y = torso_y + torso_h
    leg_y = waist_y + 1
    leg_h = max(3, 30 - leg_y)

    arm_w = 4
    arm_l = torso_x - arm_w
    arm_r = torso_x + torso_w
    hand_y = torso_y + torso_h - 4

    if aura:
        ic.oval(16, 17, 15, 15, aura)

    # ---- legs ------------------------------------------------------------
    if tattered:
        ic.rect(torso_x + 1, leg_y, torso_w - 2, leg_h, cloth)
        for i in range(torso_x + 1, torso_x + torso_w - 1, 3):
            ic.rect(i, leg_y + leg_h, 2, 2, cloth)       # ragged hem
    else:
        gap = 2
        lw = (torso_w - gap - 4) // 2
        ic.rect(torso_x + 2, leg_y, lw, leg_h, cloth)
        ic.rect(torso_x + torso_w - 2 - lw, leg_y, lw, leg_h, cloth)
        ic.rect(torso_x + 1, leg_y + leg_h, lw + 2, 2, boots)
        ic.rect(torso_x + torso_w - 3 - lw, leg_y + leg_h, lw + 2, 2, boots)
        ic.rect(torso_x + 2 + lw, leg_y, gap, leg_h, BLACK)   # gap between legs

    # ---- torso -----------------------------------------------------------
    ic.rect(torso_x, torso_y, torso_w, torso_h, cloth)
    if ribs:
        for y in range(torso_y + 2, torso_y + torso_h - 1, 3):
            ic.rect(torso_x + 2, y, torso_w - 4, 1, skin)
    ic.rect(torso_x, waist_y - 2, torso_w, 2, trim)          # belt
    ic.rect(torso_x, waist_y, torso_w, 1, BLACK)             # waist rule

    # ---- arms, drawn outside the torso and ruled off from it -------------
    ic.rect(arm_l, torso_y + 1, arm_w, torso_h - 3, cloth)
    ic.rect(arm_r, torso_y + 1, arm_w, torso_h - 3, cloth)
    ic.rect(arm_l + arm_w - 1, torso_y + 1, 1, torso_h - 3, BLACK)
    ic.rect(arm_r, torso_y + 1, 1, torso_h - 3, BLACK)
    ic.rect(arm_l, hand_y, arm_w, 3, skin)                   # hands
    ic.rect(arm_r, hand_y, arm_w, 3, skin)

    # ---- head ------------------------------------------------------------
    ic.rect(torso_x, neck_y, torso_w, 1, BLACK)              # neck rule
    ic.rect(head_x, head_y, head_w, head_h, skin)
    eye_y = head_y + (4 if hood else 3)
    if hood:
        ic.rect(head_x - 1, head_y - 2, head_w + 2, head_h - 2, cloth)
        ic.rect(head_x, head_y + 3, head_w, head_h - 4, BLACK)   # shadowed face
        ic.rect(head_x + 2, eye_y, 2, 2, eyes)
        ic.rect(head_x + head_w - 4, eye_y, 2, 2, eyes)
    else:
        ic.rect(head_x + 2, eye_y, 2, 2, eyes)
        ic.rect(head_x + head_w - 4, eye_y, 2, 2, eyes)
        ic.rect(head_x + 3, eye_y + 3, head_w - 6, 1, BLACK)     # mouth
    if helm:
        ic.rect(head_x - 1, head_y - 2, head_w + 2, 4, helm)
        ic.rect(head_x + head_w // 2 - 1, head_y - 2, 2, head_h - 1, helm)  # nasal
        ic.rect(head_x - 1, head_y + 2, head_w + 2, 1, BLACK)
    if horns:
        ic.tri([(head_x, head_y + 1), (head_x - 4, head_y - 6), (head_x + 3, head_y - 1)], BONE)
        ic.tri([(head_x + head_w, head_y + 1), (head_x + head_w + 4, head_y - 6),
                (head_x + head_w - 3, head_y - 1)], BONE)
    if crown:
        ic.rect(head_x, head_y - 4, head_w, 3, YELLOW)
        for i in range(0, head_w - 1, 4):
            ic.tri([(head_x + i, head_y - 4), (head_x + i + 2, head_y - 8),
                    (head_x + i + 4, head_y - 4)], YELLOW)

    # ---- held gear -------------------------------------------------------
    if shield:
        sx = arm_l - 5
        ic.rect(sx, torso_y, 6, torso_h - 1, SILVER)
        ic.rect(sx, torso_y, 6, 1, WHITE)
        ic.rect(sx + 1, torso_y + 4, 4, 4, trim)
        ic.rect(sx + 5, torso_y, 1, torso_h - 1, BLACK)
    _weapon(ic, weapon, arm_r + arm_w, torso_y, trim)

    return ic.outline().shade()


def _weapon(ic, kind, x, y, trim=YELLOW):
    """Whatever the figure is holding. Drawn into the hand so it is not clipped."""
    if kind is None:
        return
    x = min(x, 25)                       # always leave room for the blade
    if kind == "sword":
        ic.rect(x, y - 3, 3, 13, SILVER)
        ic.rect(x, y - 3, 1, 13, WHITE)
        ic.rect(x - 1, y + 10, 5, 2, trim)
        ic.rect(x, y + 12, 3, 3, BROWN)
    elif kind == "axe":
        ic.rect(x, y, 3, 16, BROWN)
        ic.tri([(x, y - 4), (x - 6, y - 1), (x, y + 7)], SILVER)
        ic.rect(x - 4, y - 1, 2, 5, WHITE)
    elif kind == "mace":
        ic.rect(x, y + 5, 3, 11, BROWN)
        ic.oval(x + 1, y + 2, 4, 4, SILVER)
        ic.rect(x - 1, y - 1, 2, 2, WHITE)
    elif kind == "hammer":
        ic.rect(x, y + 4, 3, 12, BROWN)
        ic.rect(x - 3, y - 2, 8, 6, SILVER)
        ic.rect(x - 3, y - 2, 8, 1, WHITE)
    elif kind == "staff":
        ic.rect(x, y - 6, 3, 22, BROWN)
        ic.oval(x + 1, y - 7, 4, 4, AQUA)
        ic.rect(x, y - 10, 2, 2, WHITE)
    elif kind == "bow":
        ic.line(x + 2, y - 5, x + 2, y + 15, BROWN)
        ic.line(x + 3, y - 5, x + 3, y + 15, BROWN)
        ic.line(x + 1, y - 4, x - 1, y + 5, BROWN)
        ic.line(x + 1, y + 14, x - 1, y + 6, BROWN)
        ic.line(x + 4, y - 5, x + 4, y + 15, SILVER)
    elif kind == "spear":
        ic.rect(x, y - 7, 3, 23, BROWN)
        ic.tri([(x + 1, y - 12), (x - 2, y - 6), (x + 4, y - 6)], SILVER)
    elif kind == "claw":
        for i in range(3):
            ic.line(x - 1, y + 5 + i * 3, x + 4, y + 8 + i * 3, BONE)


def beast(fur=BROWN, eyes=RED, ears=True, tail="thin", wings=False,
          horns=False, big=False, legs=4, aura=None):
    """Four-legged creatures: rats, wolves, drakes."""
    ic = Icon()
    top = 8 if big else 12
    bh = 12 if big else 9

    if aura:
        ic.oval(16, 18, 15, 13, aura)
    if wings:
        ic.tri([(10, top), (0, top - 7), (4, top + 8)], darker(fur) if not is_pair(fur) else fur)
        ic.tri([(22, top), (32, top - 7), (28, top + 8)], darker(fur) if not is_pair(fur) else fur)

    ic.oval(14, top + bh // 2, 11, bh // 2 + 1, fur)      # body
    ic.oval(24, top + 2, 6, 5, fur)                        # head
    ic.rect(29, top + 3, 3, 3, darker(fur) if not is_pair(fur) else fur)   # snout
    ic.rect(22, top, 2, 2, eyes)
    ic.rect(26, top, 2, 2, eyes)
    if ears:
        ic.tri([(22, top - 2), (20, top - 8), (26, top - 3)], fur)
        ic.tri([(27, top - 2), (29, top - 8), (31, top - 2)], fur)
    if horns:
        ic.tri([(22, top - 2), (19, top - 9), (25, top - 3)], BONE)
        ic.tri([(27, top - 2), (30, top - 9), (31, top - 3)], BONE)

    legy = top + bh
    for lx in (6, 11, 18, 23)[:legs]:
        ic.rect(lx, legy, 3, 8 if big else 6, fur)
        ic.rect(lx, legy + (7 if big else 5), 4, 2, BLACK)
    if tail == "thin":
        ic.line(4, top + 4, 0, top - 1, fur)
    elif tail == "bushy":
        ic.oval(3, top + 3, 4, 4, fur)
    return ic.outline().shade()


def _spider():
    ic = Icon()
    ic.oval(16, 20, 9, 7, PLUM)
    ic.oval(16, 11, 6, 5, PURPLE)
    for x in (12, 16, 20):
        ic.rect(x, 8, 2, 2, RED)
    for y0, y1 in ((10, 2), (15, 13), (20, 26)):
        ic.line(8, y0, 0, y1, BLACK)
        ic.line(24, y0, 31, y1, BLACK)
        ic.line(8, y0, 2, y1, PURPLE)
        ic.line(24, y0, 29, y1, PURPLE)
    return ic.outline().shade()


def _bat():
    ic = Icon()
    ic.tri([(13, 12), (0, 6), (6, 20)], BRUISE)
    ic.tri([(19, 12), (32, 6), (26, 20)], BRUISE)
    ic.oval(16, 15, 5, 6, PURPLE)
    ic.tri([(13, 10), (12, 4), (16, 9)], PURPLE)
    ic.tri([(19, 10), (20, 4), (16, 9)], PURPLE)
    ic.rect(13, 13, 2, 2, YELLOW)
    ic.rect(17, 13, 2, 2, YELLOW)
    return ic.outline().shade()


def _ooze():
    ic = Icon()
    ic.oval(16, 22, 13, 9, SICK_GREEN)
    ic.oval(16, 16, 9, 7, SICK_GREEN)
    ic.oval(11, 14, 3, 3, LIME)          # highlight blob
    ic.rect(12, 19, 3, 3, BLACK)
    ic.rect(19, 19, 3, 3, BLACK)
    for x in (7, 14, 22, 27):            # drips
        ic.rect(x, 29, 2, 3, SICK_GREEN)
    return ic.outline().shade()


def _golem():
    ic = Icon()
    ic.rect(8, 6, 16, 17, MID_STONE)
    ic.rect(4, 9, 4, 11, MID_STONE)      # arms
    ic.rect(24, 9, 4, 11, MID_STONE)
    ic.rect(9, 23, 6, 8, MID_STONE)      # legs
    ic.rect(17, 23, 6, 8, MID_STONE)
    ic.rect(8, 6, 16, 1, WHITE)
    ic.rect(8, 6, 1, 17, WHITE)
    ic.rect(11, 11, 3, 3, AQUA)          # rune eyes
    ic.rect(18, 11, 3, 3, AQUA)
    ic.rect(10, 17, 12, 2, DARK_STONE)
    return ic.outline().shade()


def _sentry():
    ic = Icon()
    ic.rect(11, 4, 10, 8, COPPER)        # head
    ic.rect(13, 6, 2, 3, RED)
    ic.rect(17, 6, 2, 3, RED)
    ic.rect(9, 12, 14, 12, COPPER)       # body
    ic.oval(16, 18, 4, 4, YELLOW)        # gear
    for a in range(0, 8):
        import math
        ic.rect(16 + int(5 * math.cos(a)), 18 + int(5 * math.sin(a)), 2, 2, OLIVE)
    ic.rect(5, 14, 4, 8, GRAY)
    ic.rect(23, 14, 4, 8, GRAY)
    ic.rect(11, 24, 4, 7, GRAY)
    ic.rect(17, 24, 4, 7, GRAY)
    return ic.outline().shade()


def _wisp():
    ic = Icon()
    ic.oval(16, 16, 7, 7, AQUA)
    ic.oval(16, 16, 4, 4, WHITE)
    for dx, dy in ((-10, -6), (10, -8), (-8, 8), (9, 7), (0, -12), (0, 12)):
        ic.rect(16 + dx, 16 + dy, 2, 2, AQUA)
    return ic.outline().shade()


# ===========================================================================
#  Item icons. These are what fills the pack and the shop shelves.
# ===========================================================================

def _blade(length=20, width=4, hilt=YELLOW, metal=SILVER, curved=False):
    ic = Icon()
    top = 30 - length
    ic.rect(16 - width // 2, top, width, length - 6, metal)
    ic.rect(16 - width // 2, top, 1, length - 6, WHITE)
    ic.tri([(16 - width // 2, top), (16 + width // 2, top), (16, top - 4)], metal)
    if curved:
        for i in range(length - 8):
            ic.set(16 + width // 2 + i // 6, top + i, metal)
    ic.rect(10, 30 - 8, 12, 3, hilt)               # cross-guard
    ic.rect(10, 30 - 8, 12, 1, lighter(hilt) if not is_pair(hilt) else hilt)
    ic.rect(15, 30 - 5, 3, 5, BROWN)               # grip
    ic.rect(14, 30 - 1, 5, 2, hilt)                # pommel
    return ic.outline().shade()


def _haft_weapon(head_fn, haft=BROWN):
    ic = Icon()
    ic.rect(15, 6, 3, 25, haft)
    ic.rect(15, 6, 1, 25, (MAROON, YELLOW, 0.35))
    head_fn(ic)
    return ic.outline().shade()


def icon_dagger():      return _blade(length=14, width=3)
def icon_shortsword():  return _blade(length=19, width=4)
def icon_longsword():   return _blade(length=25, width=5)
def icon_broadsword():  return _blade(length=25, width=7)
def icon_sabre():       return _blade(length=23, width=4, curved=True)


def icon_axe():
    def head(ic):
        ic.tri([(15, 4), (3, 6), (15, 17)], SILVER)
        ic.tri([(18, 4), (28, 7), (18, 15)], SILVER)
        ic.rect(5, 7, 3, 7, WHITE)
    return _haft_weapon(head)


def icon_mace():
    def head(ic):
        ic.oval(16, 9, 7, 7, SILVER)
        for dx, dy in ((0, -9), (-9, 0), (9, 0), (0, 9), (-6, -6), (6, -6), (-6, 6), (6, 6)):
            ic.rect(16 + dx - 1, 9 + dy - 1, 3, 3, GRAY)
        ic.oval(13, 6, 2, 2, WHITE)
    return _haft_weapon(head)


def icon_hammer():
    def head(ic):
        ic.rect(5, 4, 22, 11, SILVER)
        ic.rect(5, 4, 22, 1, WHITE)
        ic.rect(5, 14, 22, 1, GRAY)
        ic.rect(5, 4, 1, 11, WHITE)
    return _haft_weapon(head)


def icon_spear():
    def head(ic):
        ic.tri([(16, 1), (11, 12), (21, 12)], SILVER)
        ic.rect(12, 11, 8, 2, GRAY)
        ic.line(13, 3, 13, 11, WHITE)
    return _haft_weapon(head)


def icon_halberd():
    def head(ic):
        ic.tri([(16, 0), (12, 11), (20, 11)], SILVER)
        ic.tri([(18, 4), (29, 8), (18, 14)], SILVER)
        ic.tri([(15, 6), (6, 9), (15, 13)], GRAY)
    return _haft_weapon(head)


def icon_bow():
    ic = Icon()
    ic.line(9, 3, 5, 16, BROWN); ic.line(5, 16, 9, 29, BROWN)
    ic.line(10, 3, 6, 16, (MAROON, YELLOW, 0.35)); ic.line(6, 16, 10, 29, (MAROON, YELLOW, 0.35))
    ic.line(9, 3, 9, 29, SILVER)
    ic.rect(10, 15, 16, 2, BROWN)                  # nocked arrow
    ic.tri([(26, 12), (32, 16), (26, 20)], GRAY)
    return ic.outline().shade()


def icon_crossbow():
    ic = Icon()
    ic.rect(4, 13, 24, 4, BROWN)
    ic.rect(12, 6, 4, 20, BROWN)
    ic.line(12, 7, 20, 4, SILVER); ic.line(12, 25, 20, 28, SILVER)
    ic.rect(20, 4, 2, 24, GRAY)
    return ic.outline().shade()


def icon_arrows():
    ic = Icon()
    for x in (8, 15, 22):
        ic.rect(x, 8, 2, 20, BROWN)
        ic.tri([(x + 1, 2), (x - 2, 9), (x + 4, 9)], SILVER)
        ic.rect(x - 2, 24, 6, 2, RED)
    return ic.outline().shade()


def _armour(body=SILVER, skirt=None, studs=False, scales=False, rings=False):
    ic = Icon()
    ic.rect(9, 4, 14, 6, body)                     # shoulders
    ic.rect(5, 8, 22, 16, body)                    # chest
    ic.rect(2, 10, 4, 9, body)                     # pauldrons
    ic.rect(26, 10, 4, 9, body)
    if skirt:
        ic.rect(7, 23, 18, 7, skirt)
    if studs:
        for y in range(11, 23, 4):
            for x in range(8, 25, 5):
                ic.rect(x, y, 2, 2, SILVER)
    if scales:
        for y in range(9, 24, 4):
            off = 0 if (y // 4) % 2 else 2
            for x in range(6 + off, 26, 4):
                ic.oval(x, y + 1, 2, 2, darker(body) if not is_pair(body) else body)
    if rings:
        for y in range(10, 24, 3):
            for x in range(7, 26, 3):
                ic.set(x, y, darker(body) if not is_pair(body) else BLACK)
    ic.rect(5, 8, 22, 1, WHITE)
    ic.rect(5, 8, 1, 16, WHITE)
    return ic.outline().shade()


def icon_leather():   return _armour(body=BROWN, skirt=DARK_BROWN)
def icon_studded():   return _armour(body=BROWN, skirt=DARK_BROWN, studs=True)
def icon_ringmail():  return _armour(body=GRAY, rings=True)
def icon_chainmail(): return _armour(body=(GRAY, SILVER, 0.5), rings=True)
def icon_scalemail(): return _armour(body=SILVER, scales=True)
def icon_platemail(): return _armour(body=SILVER, skirt=GRAY)


def icon_robe():
    ic = Icon()
    ic.rect(11, 3, 10, 5, NAVY)
    ic.tri([(11, 8), (21, 8), (27, 30)], NAVY)
    ic.tri([(11, 8), (21, 8), (5, 30)], NAVY)
    ic.rect(5, 26, 22, 5, NAVY)
    ic.rect(14, 9, 4, 20, (NAVY, BLUE, 0.5))
    ic.rect(5, 28, 22, 2, PURPLE)
    return ic.outline().shade()


def _shield(shape="kite", face=SILVER, boss=YELLOW):
    ic = Icon()
    if shape == "round":
        ic.oval(16, 16, 12, 12, face)
        ic.oval(16, 16, 4, 4, boss)
    elif shape == "tower":
        ic.rect(7, 2, 18, 26, face)
        ic.rect(7, 2, 18, 1, WHITE)
        ic.rect(14, 12, 4, 8, boss)
    else:
        ic.rect(6, 3, 20, 14, face)
        ic.tri([(6, 17), (26, 17), (16, 30)], face)
        ic.rect(6, 3, 20, 1, WHITE)
        ic.rect(6, 3, 1, 14, WHITE)
        ic.rect(13, 9, 6, 8, boss)
    return ic.outline().shade()


def icon_buckler(): return _shield("round", SILVER, MAROON)
def icon_shield():  return _shield("kite", SILVER, MAROON)
def icon_tower():   return _shield("tower", GRAY, YELLOW)


def icon_helm():
    ic = Icon()
    ic.oval(16, 15, 11, 11, SILVER)
    ic.rect(5, 15, 22, 11, SILVER)
    ic.rect(5, 24, 22, 3, GRAY)
    ic.rect(13, 12, 6, 15, BLACK)        # visor slit
    ic.rect(15, 8, 3, 19, SILVER)        # nasal
    ic.oval(12, 10, 3, 3, WHITE)
    return ic.outline().shade()


def icon_cap():
    ic = Icon()
    ic.oval(16, 17, 11, 9, BROWN)
    ic.rect(5, 17, 22, 6, BROWN)
    ic.rect(4, 22, 24, 3, DARK_BROWN)
    return ic.outline().shade()


def icon_gauntlets():
    ic = Icon()
    for x in (4, 18):
        ic.rect(x, 10, 10, 13, SILVER)
        ic.rect(x, 10, 10, 1, WHITE)
        ic.rect(x + 1, 6, 3, 5, SILVER)
        ic.rect(x + 5, 5, 3, 6, SILVER)
        ic.rect(x, 20, 10, 3, GRAY)
    return ic.outline().shade()


def icon_boots():
    ic = Icon()
    for x in (4, 18):
        ic.rect(x + 1, 6, 8, 16, BROWN)
        ic.rect(x, 22, 11, 5, DARK_BROWN)
        ic.rect(x + 1, 6, 8, 1, (MAROON, YELLOW, 0.35))
        ic.rect(x, 26, 11, 2, BLACK)
    return ic.outline().shade()


def icon_leggings():
    ic = Icon()
    ic.rect(8, 3, 16, 6, BROWN)
    ic.rect(8, 9, 6, 20, BROWN)
    ic.rect(18, 9, 6, 20, BROWN)
    ic.rect(8, 3, 16, 1, (MAROON, YELLOW, 0.35))
    return ic.outline().shade()


def icon_cloak():
    ic = Icon()
    ic.rect(10, 3, 12, 4, PURPLE)
    ic.tri([(10, 6), (22, 6), (28, 29)], PURPLE)
    ic.tri([(10, 6), (22, 6), (4, 29)], PURPLE)
    ic.rect(4, 25, 24, 5, PURPLE)
    ic.rect(9, 4, 3, 3, YELLOW)          # clasp
    return ic.outline().shade()


def icon_belt():
    ic = Icon()
    ic.rect(2, 13, 28, 6, BROWN)
    ic.rect(2, 13, 28, 1, (MAROON, YELLOW, 0.35))
    ic.rect(12, 10, 9, 12, YELLOW)       # buckle
    ic.rect(15, 13, 3, 6, BROWN)
    return ic.outline().shade()


def icon_ring():
    ic = Icon()
    ic.oval(16, 19, 9, 9, YELLOW)
    ic.oval(16, 19, 5, 5, None)
    for y in range(14, 25):
        for x in range(11, 22):
            dx, dy = (x + .5 - 16) / 5.0, (y + .5 - 19) / 5.0
            if dx * dx + dy * dy <= 1.0:
                ic.px[y][x] = None
    ic.oval(16, 8, 5, 5, AQUA)
    ic.rect(14, 6, 2, 2, WHITE)
    return ic.outline().shade()


def icon_amulet():
    ic = Icon()
    ic.line(9, 3, 14, 15, YELLOW)
    ic.line(23, 3, 18, 15, YELLOW)
    ic.oval(16, 21, 8, 8, YELLOW)
    ic.oval(16, 21, 4, 4, RED)
    ic.rect(13, 17, 2, 2, WHITE)
    return ic.outline().shade()


def _potion(liquid=RED):
    ic = Icon()
    ic.rect(13, 2, 6, 4, BROWN)          # cork
    ic.rect(12, 6, 8, 3, SILVER)         # neck
    ic.oval(16, 20, 9, 10, liquid)
    ic.oval(12, 16, 2, 3, WHITE)         # glass highlight
    ic.rect(8, 22, 16, 2, darker(liquid) if not is_pair(liquid) else liquid)
    return ic.outline().shade()


def icon_potion_red():    return _potion(RED)
def icon_potion_blue():   return _potion(BLUE)
def icon_potion_green():  return _potion(LIME)
def icon_potion_yellow(): return _potion(YELLOW)
def icon_potion_purple(): return _potion(FUCHSIA)
def icon_potion_clear():  return _potion(AQUA)


def icon_scroll():
    ic = Icon()
    ic.rect(6, 4, 20, 24, (SILVER, WHITE, 0.5))
    ic.rect(4, 2, 24, 4, BROWN)
    ic.rect(4, 26, 24, 4, BROWN)
    ic.rect(4, 2, 24, 1, (MAROON, YELLOW, 0.35))
    for y in range(9, 25, 4):
        ic.rect(9, y, 14, 1, GRAY)
    return ic.outline().shade()


def _book(cover=MAROON, clasp=YELLOW):
    ic = Icon()
    ic.rect(5, 3, 22, 26, cover)
    ic.rect(5, 3, 22, 1, lighter(cover) if not is_pair(cover) else cover)
    ic.rect(5, 3, 2, 26, darker(cover) if not is_pair(cover) else cover)   # spine
    ic.rect(24, 5, 4, 22, (SILVER, WHITE, 0.5))                            # page edges
    ic.rect(12, 11, 9, 9, clasp)                                           # sigil
    ic.rect(14, 13, 5, 5, cover)
    return ic.outline().shade()


def icon_book_red():   return _book(MAROON, YELLOW)
def icon_book_blue():  return _book(NAVY, SILVER)
def icon_book_green(): return _book(GREEN, YELLOW)
def icon_book_black(): return _book(GRAY, FUCHSIA)


def icon_wand():
    ic = Icon()
    ic.rect(8, 22, 18, 3, BROWN)
    ic.line(8, 24, 26, 21, (MAROON, YELLOW, 0.35))
    ic.oval(25, 8, 5, 5, FUCHSIA)
    ic.rect(23, 5, 2, 2, WHITE)
    ic.rect(20, 16, 4, 4, YELLOW)
    return ic.outline().shade()


def icon_staff():
    ic = Icon()
    ic.rect(14, 6, 4, 25, BROWN)
    ic.rect(14, 6, 1, 25, (MAROON, YELLOW, 0.35))
    ic.oval(16, 6, 7, 6, AQUA)
    ic.oval(16, 6, 3, 3, WHITE)
    return ic.outline().shade()


def icon_pack():
    ic = Icon()
    ic.rect(6, 8, 20, 21, BROWN)
    ic.rect(6, 8, 20, 1, (MAROON, YELLOW, 0.35))
    ic.rect(4, 4, 24, 6, DARK_BROWN)     # flap
    ic.rect(14, 9, 4, 5, YELLOW)         # buckle
    ic.rect(6, 26, 20, 3, DARK_BROWN)
    return ic.outline().shade()


def icon_sack():
    ic = Icon()
    ic.oval(16, 21, 11, 10, (OLIVE, SILVER, 0.5))
    ic.rect(12, 6, 8, 8, (OLIVE, SILVER, 0.5))
    ic.rect(11, 11, 10, 3, BROWN)        # tie
    return ic.outline().shade()


def icon_chest():
    ic = Icon()
    ic.rect(3, 12, 26, 16, BROWN)
    ic.rect(3, 12, 26, 1, (MAROON, YELLOW, 0.35))
    ic.oval(16, 12, 13, 7, DARK_BROWN)   # domed lid
    ic.rect(3, 16, 26, 3, YELLOW)        # bands
    ic.rect(13, 16, 6, 8, YELLOW)
    ic.rect(15, 19, 2, 3, BLACK)         # keyhole
    return ic.outline().shade()


def icon_gold():
    ic = Icon()
    for cx, cy in ((10, 24), (21, 25), (16, 19), (11, 14), (20, 15)):
        ic.oval(cx, cy, 6, 4, YELLOW)
        ic.oval(cx, cy - 1, 6, 4, (YELLOW, WHITE, 0.35))
    ic.rect(8, 12, 2, 2, WHITE)
    return ic.outline().shade()


def icon_gem():
    ic = Icon()
    ic.tri([(16, 3), (5, 14), (27, 14)], AQUA)
    ic.tri([(5, 14), (27, 14), (16, 29)], TEAL)
    ic.line(16, 3, 16, 29, WHITE)
    ic.line(5, 14, 27, 14, WHITE)
    ic.rect(12, 8, 3, 3, WHITE)
    return ic.outline().shade()


def icon_food():
    ic = Icon()
    ic.oval(16, 18, 12, 9, BROWN)
    ic.oval(16, 16, 12, 8, (MAROON, YELLOW, 0.35))
    for x in (10, 16, 22):
        ic.rect(x, 11, 2, 3, DARK_BROWN)
    return ic.outline().shade()


def icon_torch():
    ic = Icon()
    ic.rect(14, 12, 4, 19, BROWN)
    ic.oval(16, 9, 6, 8, RED)
    ic.oval(16, 8, 4, 5, YELLOW)
    ic.oval(16, 7, 2, 3, WHITE)
    return ic.outline().shade()


def icon_lantern():
    ic = Icon()
    ic.rect(11, 4, 10, 3, GRAY)
    ic.line(16, 1, 11, 5, GRAY); ic.line(16, 1, 21, 5, GRAY)
    ic.rect(9, 7, 14, 18, SILVER)
    ic.rect(11, 9, 10, 14, YELLOW)
    ic.oval(16, 16, 3, 4, WHITE)
    ic.rect(8, 25, 16, 4, GRAY)
    return ic.outline().shade()


def icon_key():
    ic = Icon()
    ic.oval(9, 10, 6, 6, YELLOW)
    ic.oval(9, 10, 3, 3, None)
    for y in range(6, 15):
        for x in range(5, 14):
            dx, dy = (x + .5 - 9) / 3.0, (y + .5 - 10) / 3.0
            if dx * dx + dy * dy <= 1.0:
                ic.px[y][x] = None
    ic.rect(12, 15, 4, 14, YELLOW)
    ic.rect(16, 22, 5, 3, YELLOW)
    ic.rect(16, 26, 4, 3, YELLOW)
    return ic.outline().shade()


# ===========================================================================
#  The bestiary and the townsfolk, then the registry everything loads from.
# ===========================================================================

CREATURE_BUILDERS = {
    # --- vermin ---------------------------------------------------------
    "cave_rat":     lambda: beast(fur=BROWN, eyes=RED, tail="thin"),
    "cellar_spider": _spider,
    "cave_bat":     _bat,
    "acid_pudding": _ooze,

    # --- humanoids ------------------------------------------------------
    "kobold":       lambda: humanoid(skin=RUST, cloth=DARK_BROWN, trim=OLIVE,
                                     eyes=YELLOW, weapon="spear", horns=True, bulk=-2),
    "goblin":       lambda: humanoid(skin=GREEN, cloth=DARK_BROWN, trim=MAROON,
                                     eyes=YELLOW, weapon="sword", bulk=-1),
    "goblin_archer": lambda: humanoid(skin=MOSS, cloth=DARK_GREEN, trim=BROWN,
                                      eyes=YELLOW, weapon="bow", bulk=-1),
    "orc":          lambda: humanoid(skin=DARK_GREEN, cloth=MAROON, trim=OLIVE,
                                     eyes=RED, weapon="axe", bulk=3, helm=GRAY),
    "ogre":         lambda: humanoid(skin=OLIVE, cloth=BROWN, trim=DARK_BROWN,
                                     eyes=YELLOW, weapon="mace", bulk=6),
    "moss_troll":   lambda: humanoid(skin=GREEN, cloth=MOSS, trim=DARK_GREEN,
                                     eyes=LIME, weapon="claw", bulk=5, horns=True),
    "ash_cultist":  lambda: humanoid(skin=MAROON, cloth=MAROON, trim=RED,
                                     eyes=RED, weapon="staff", hood=True),
    "storm_sorcerer": lambda: humanoid(skin=PALE_SKIN, cloth=PLUM, trim=FUCHSIA,
                                       eyes=WHITE, weapon="staff", hood=True, aura=PLUM),

    # --- undead ---------------------------------------------------------
    "skeleton":     lambda: humanoid(skin=BONE, cloth=BONE, trim=GRAY, eyes=RED,
                                     weapon="sword", ribs=True, boots=GRAY),
    "shambler":     lambda: humanoid(skin=SICK_GREEN, cloth=DARK_BROWN, trim=OLIVE,
                                     eyes=LIME, weapon="claw", tattered=True, hunched=True),
    "crypt_ghoul":  lambda: humanoid(skin=OLIVE, cloth=DARK_STONE,
                                     trim=GRAY, eyes=LIME, weapon="claw", tattered=True),
    "pale_wraith":  lambda: humanoid(skin=ICE, cloth=(NAVY, TEAL, 0.5), trim=AQUA,
                                     eyes=WHITE, hood=True, tattered=True, aura=ICE),
    "iron_revenant": lambda: humanoid(skin=GRAY, cloth=DARK_STONE, trim=SILVER,
                                      eyes=AQUA, weapon="axe", helm=SILVER, bulk=3, ribs=True),

    # --- beasts ---------------------------------------------------------
    "dire_wolf":    lambda: beast(fur=GRAY, eyes=YELLOW, tail="bushy"),
    "ember_drake":  lambda: beast(fur=RUST, eyes=YELLOW, wings=True, horns=True,
                                  ears=False, big=True, aura=EMBER),

    # --- constructs and spirits -----------------------------------------
    "stone_golem":  _golem,
    "clockwork_sentry": _sentry,
    "storm_wisp":   _wisp,

    # --- the two that end a run ------------------------------------------
    "warden_of_ash": lambda: humanoid(skin=EMBER, cloth=MAROON, trim=YELLOW,
                                      eyes=YELLOW, weapon="mace", bulk=8,
                                      horns=True, helm=RUST, aura=EMBER),
    "vaelrik":      lambda: humanoid(skin=ICE, cloth=PLUM, trim=AQUA, eyes=WHITE,
                                     weapon="sword", bulk=7, crown=True, aura=PLUM),

    # --- townsfolk -------------------------------------------------------
    "npc_smith":     lambda: humanoid(skin=TAN, cloth=DARK_BROWN, trim=RED,
                                      weapon="hammer", eyes=BLACK),
    "npc_armourer":  lambda: humanoid(skin=TAN, cloth=GRAY, trim=SILVER,
                                      eyes=BLACK, helm=SILVER),
    "npc_alchemist": lambda: humanoid(skin=PALE_SKIN, cloth=PURPLE, trim=LIME,
                                      eyes=BLACK, hood=True),
    "npc_sage":      lambda: humanoid(skin=PALE_SKIN, cloth=NAVY, trim=AQUA,
                                      eyes=BLACK, weapon="staff", hood=True),
    "npc_priest":    lambda: humanoid(skin=TAN, cloth=SILVER, trim=NAVY,
                                      eyes=BLACK, hood=True),
    "npc_banker":    lambda: humanoid(skin=TAN, cloth=OLIVE, trim=YELLOW, eyes=BLACK),
    "npc_trader":    lambda: humanoid(skin=TAN, cloth=GREEN, trim=BROWN, eyes=BLACK),
}


# Hair/tunic colours a player character can be drawn in, so everyone in the
# party is instantly tellable apart on the map.
PLAYER_COLOURS = [MAROON, NAVY, GREEN, PURPLE, TEAL, OLIVE]


def adventurer(colour=NAVY, weapon=None, shield=False, helm=None, robe=False):
    """The player figure. What you are wearing is what you see on the map."""
    return humanoid(skin=TAN, cloth=colour, trim=YELLOW, eyes=BLACK,
                    weapon=weapon, shield=shield, helm=helm,
                    hood=robe, boots=DARK_BROWN)


TERRAIN_BUILDERS = {
    "void":        tile_void,
    "floor":       tile_floor,
    "wall":        tile_wall,
    "shop_floor":  tile_shop_floor,
    "grass":       tile_grass,
    "road":        tile_road,
    "tree":        tile_tree,
    "water":       tile_water,
    "rubble":      tile_rubble,
    "door":        lambda: tile_door(True),
    "door_open":   lambda: tile_door(False),
    "stairs_down": lambda: tile_stairs(True),
    "stairs_up":   lambda: tile_stairs(False),
    "altar":       tile_altar,
}


class SpriteSheet:
    """Builds every sprite once and hands out pygame surfaces."""

    def __init__(self, scale=1):
        self.scale = scale
        self.terrain = {}
        self.creatures = {}
        self.creatures_flipped = {}
        self.items = {}
        self._player_cache = {}

    def build(self):
        import sys
        for name, fn in TERRAIN_BUILDERS.items():
            self.terrain[name] = fn().surface(self.scale)
        for name, fn in CREATURE_BUILDERS.items():
            icon = fn()
            self.creatures[name] = icon.surface(self.scale)
            self.creatures_flipped[name] = icon.flipped().surface(self.scale)
        module = sys.modules[__name__]
        for name in dir(module):
            if name.startswith("icon_"):
                self.items[name[5:]] = getattr(module, name)().surface(self.scale)
        return self

    def player(self, colour_index=0, weapon=None, shield=False, helm=False, robe=False):
        """Player sprites vary with kit, so they are built on demand and cached."""
        key = (colour_index, weapon, shield, helm, robe)
        cached = self._player_cache.get(key)
        if cached is None:
            colour = PLAYER_COLOURS[colour_index % len(PLAYER_COLOURS)]
            icon = adventurer(colour, weapon, shield, SILVER if helm else None, robe)
            cached = (icon.surface(self.scale), icon.flipped().surface(self.scale))
            self._player_cache[key] = cached
        return cached

    def item(self, name):
        return self.items.get(name) or self.items.get("gold")
