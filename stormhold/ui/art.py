"""Every sprite in Stormhold, drawn in code in the Windows 3.1 icon idiom.

House rules, all borrowed from the icon art of the period:
  * only the sixteen VGA colours, with ordered dithering for anything between
  * a hard black outline around every object
  * one light source, always upper-left: highlights up-left, shadow down-right
  * chunky and readable first, detailed second

Two rules learned by rendering the whole set at 9x and looking at it, both
about where dithering stops working:

  * A dither pair needs area. One or two pixels wide it samples the Bayer
    matrix at scattered points and comes out as a row of beads, not as a
    colour - so thin work (a bowstave, an arrow shaft, a one-pixel highlight)
    takes a flat palette colour.
  * A pair at ratio 0.5 is a full checkerboard, the noisiest screen there is.
    It is for a few pixels of transition. Anything with area wants one colour
    leading and the other speckled through it - see `palette.calm`.

Nothing here is loaded from disk. Icons are built once at start-up into pygame
surfaces and cached.
"""

import pygame

from .palette import (
    BLACK, MAROON, GREEN, OLIVE, NAVY, PURPLE, TEAL, SILVER, GRAY, RED, LIME,
    YELLOW, BLUE, FUCHSIA, AQUA, WHITE,
    BROWN, DARK_BROWN, TAN, PALE_SKIN, DARK_STONE, MID_STONE, PALE_STONE,
    DARK_GREEN, MOSS, DEEP_WATER, SHALLOW, RUST, EMBER, BONE, SHADOW_BLUE,
    BRUISE, ICE, GOLD_DITHER, COPPER, PLUM, SICK_GREEN, BOOT_LEATHER,
    WOOD_LIT,
    resolve, is_pair, darker, lighter, calm,
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
                # Only shade something with body under it. A stroke two or
                # three pixels thick - a bowstave, a haft, a chain link - has
                # nothing above it *and* nothing below it at almost every
                # pixel, so shading both edges lit and darkened alternate
                # pixels down its whole length and turned it into beads.
                if light and not solid(x, y - 1) and solid(x, y + 2):
                    self.px[y][x] = lighter(c)
                elif dark and not solid(x, y + 1) and solid(x, y - 2):
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
    ic.rect(14, 20, 1, 12, WOOD_LIT)
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
        ic.rect(3, 1, 26, 1, WOOD_LIT)
        ic.rect(3, 1, 1, 30, WOOD_LIT)
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
        ic.rect(4, 0, 1, ICON, WOOD_LIT)
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
             bulk=0, tattered=False, ribs=False, boots=BOOT_LEATHER, aura=None,
             hunched=False):
    """One upright two-legged figure, from a kobold to a king.

    Built as a silhouette rather than a stack of bands. The old version laid
    head, chest and legs out as full-width rectangles separated by black
    rules, which is readable but makes every creature in the game the same
    shape: a square head on a wide box. What tells a kobold from an ogre at
    32 pixels is the outline, so the outline is what this draws - a narrow
    head over sloped shoulders, a torso that tapers to the waist, arms set
    off the shoulder line, and a gap between the legs.

    Proportions are the ones that read at this size, not the ones that are
    anatomically right: the head is about a fifth of the figure and a bit
    over half the shoulder width.
    """
    ic = Icon()
    heavy = bulk >= 4

    # ---- the frame -------------------------------------------------------
    # Everything lives inside x 2..29 so the black outline always has a pixel
    # to sit in, whatever the bulk.
    # Bulk buys height as much as width. Spending it all on width - which is
    # what the old version did - made the Warden and Vaelrik into rectangles
    # that filled the icon edge to edge and lost their outline entirely.
    shoulder_w = max(8, min(16, 11 + bulk))
    waist_w = max(6, shoulder_w - (5 if heavy else 3))
    hip_w = max(6, shoulder_w - (4 if heavy else 2))
    head_w = 9 if heavy else (7 if bulk < 0 else 8)

    top = (2 if heavy else 4) + (2 if hunched else 0)
    head_h = 8 if heavy else 7
    neck_y = top + head_h
    torso_y = neck_y + 1
    torso_h = 13 if heavy else 10
    waist_y = torso_y + torso_h - 2
    hip_y = torso_y + torso_h
    leg_h = 28 - hip_y
    head_x = 16 - head_w // 2

    def band(y):
        """How wide the body is at this row: shoulders down to waist."""
        if y >= hip_y:
            return hip_w
        span = max(1, (waist_y - torso_y))
        t = min(1.0, max(0.0, (y - torso_y) / span))
        return int(round(shoulder_w - (shoulder_w - waist_w) * t))

    if aura:
        # A rim, not a plate. A filled disc behind the figure swallowed it.
        for i in range(0, 360, 12):
            import math
            a = math.radians(i)
            ic.set(16 + int(round(13 * math.cos(a))),
                   16 + int(round(14 * math.sin(a))), aura)
        for i in range(0, 360, 30):
            import math
            a = math.radians(i + 15)
            ic.set(16 + int(round(15 * math.cos(a))),
                   16 + int(round(15 * math.sin(a))), aura)

    # ---- legs ------------------------------------------------------------
    if tattered:
        for j in range(leg_h + 2):
            w = hip_w - (j // 3)
            ic.rect(16 - w // 2, hip_y + j, w, 1, calm(cloth))
        for i in range(16 - hip_w // 2, 16 + hip_w // 2, 3):
            ic.set(i, hip_y + leg_h + 2, cloth)          # ragged hem
    else:
        lw = max(2, (hip_w - 2) // 2)
        left = 16 - hip_w // 2
        right = 16 + hip_w // 2 - lw
        # Trousers match the tunic. Darkening them a step turned every dark
        # cloth in the game into black legs, because one step down from grey
        # or navy is black; the gap between the legs and the boots below do
        # the separating instead.
        ic.rect(left, hip_y, lw, leg_h, calm(cloth))
        ic.rect(right, hip_y, lw, leg_h, calm(cloth))
        ic.rect(left - 1, hip_y + leg_h, lw + 2, 2, boots)
        ic.rect(right - 1, hip_y + leg_h, lw + 2, 2, boots)

    # ---- torso -----------------------------------------------------------
    body = calm(cloth)
    for y in range(torso_y, hip_y):
        w = band(y)
        ic.rect(16 - w // 2, y, w, 1, body)
    if ribs:
        for y in range(torso_y + 2, waist_y - 1, 3):
            w = band(y) - 4
            ic.rect(16 - w // 2, y, w, 1, skin)
    bw = band(waist_y)
    ic.rect(16 - bw // 2, waist_y, bw, 2, trim)          # belt

    # ---- arms ------------------------------------------------------------
    # Set just outside the shoulder and shaded a step down, so they read as
    # arms rather than as more chest.
    arm_top = torso_y + 1
    arm_h = torso_h - 2
    for side in (-1, 1):
        x = 16 + side * (shoulder_w // 2 + 1) - (2 if side > 0 else 1)
        ic.rect(x, arm_top, 3, arm_h - 2, calm(cloth))
        ic.rect(x, arm_top + arm_h - 2, 3, 2, calm(skin))   # hand
        # One pixel of shadow where the arm meets the chest. Shading the
        # whole sleeve instead turned grey and navy cloth black, because a
        # step down from either of those is black.
        seam = x + (2 if side < 0 else 0)
        ic.rect(seam, arm_top, 1, arm_h - 2, darker(cloth))

    # ---- head ------------------------------------------------------------
    ic.rect(15, neck_y, 2, 1, darker(skin))              # a neck, not a rule
    ic.rect(head_x, top, head_w, head_h, calm(skin))
    ic.rect(head_x + 1, top - 1, head_w - 2, 1, skin)    # rounded crown
    ic.rect(head_x, top + head_h, head_w, 1, None)
    ic.rect(head_x + 1, top + head_h - 1, head_w - 2, 1, skin)   # rounded jaw

    eye_y = top + (4 if hood else 3)
    # Two pixels in from each side, and never nearer than two pixels to each
    # other: at a head width of eight the old spacing put them side by side,
    # so every face in the game wore one black bar instead of two eyes.
    eye_in = 1
    if hood:
        ic.rect(head_x - 1, top - 2, head_w + 2, head_h, cloth)
        ic.tri([(head_x - 1, top + head_h - 2), (16, top - 4),
                (head_x + head_w + 1, top + head_h - 2)], cloth)
        ic.rect(head_x, top + 2, head_w, head_h - 3, BLACK)      # shadowed face
        ic.rect(head_x + eye_in, eye_y, 2, 1, eyes)
        ic.rect(head_x + head_w - eye_in - 2, eye_y, 2, 1, eyes)
    else:
        ic.rect(head_x + eye_in, eye_y, 2, 2, eyes)
        ic.rect(head_x + head_w - eye_in - 2, eye_y, 2, 2, eyes)
        ic.rect(head_x + eye_in + 1, eye_y + 3, head_w - 2 * eye_in - 2, 1,
                darker(skin))                                     # mouth
    if helm:
        # A brow band and a nasal bar. The old version was four rows deep and
        # started two above the head, so on most figures it covered the eyes
        # and left a blank white bar where the face should be.
        ic.rect(head_x - 1, top - 2, head_w + 2, 3, helm)
        ic.rect(head_x + head_w // 2, top - 2, 1, eye_y - top + 3, helm)
        ic.rect(head_x - 1, top + 1, head_w + 2, 1, darker(helm))
    if horns:
        ic.tri([(head_x, top + 1), (head_x - 4, top - 5), (head_x + 2, top - 1)], BONE)
        ic.tri([(head_x + head_w, top + 1), (head_x + head_w + 4, top - 5),
                (head_x + head_w - 2, top - 1)], BONE)
    if crown:
        ic.rect(head_x - 1, top - 4, head_w + 2, 3, YELLOW)
        for i in range(0, head_w + 1, 3):
            ic.tri([(head_x - 1 + i, top - 4), (head_x + i, top - 7),
                    (head_x + 1 + i, top - 4)], YELLOW)

    # ---- held gear -------------------------------------------------------
    if shield:
        sx = 16 - shoulder_w // 2 - 5
        ic.oval(sx + 3, torso_y + 5, 4, 6, SILVER)
        ic.oval(sx + 3, torso_y + 4, 4, 5, WHITE)
        ic.oval(sx + 3, torso_y + 5, 2, 2, trim)
    _weapon(ic, weapon, 16 + shoulder_w // 2 + 3, torso_y, trim)

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
        ic.rect(x, y - 6, 3, 22, MAROON)
        ic.rect(x, y - 6, 1, 22, OLIVE)
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
    """A slab of rock with arms. Flat stone with cracks, not a grey screen.

    It used to be a fifty per cent grey checkerboard from head to foot, which
    at map size is a smudge - the one thing a golem should never be.
    """
    ic = Icon()
    body = GRAY
    ic.rect(7, 5, 18, 18, body)          # a single heavy slab
    ic.rect(4, 8, 4, 12, body)           # arms
    ic.rect(24, 8, 4, 12, body)
    ic.rect(8, 23, 7, 8, body)           # legs
    ic.rect(17, 23, 7, 8, body)
    # Lit from the upper left, as everything here is.
    ic.rect(7, 5, 18, 1, SILVER)
    ic.rect(7, 5, 1, 18, SILVER)
    ic.rect(4, 8, 1, 12, SILVER)
    ic.rect(24, 22, 4, 1, DARK_STONE)
    ic.rect(24, 5, 1, 18, DARK_STONE)
    # Cracks: a few deliberate dark strokes read as stone, a screen does not.
    ic.line(12, 6, 13, 10, DARK_STONE)
    ic.line(20, 7, 21, 11, DARK_STONE)
    ic.line(9, 26, 11, 29, DARK_STONE)
    # Two sunk rune eyes and a heavy brow. Set close together and low they
    # read as a nose; they need width apart and a brow line over both.
    ic.rect(9, 14, 5, 3, AQUA)
    ic.rect(18, 14, 5, 3, AQUA)
    ic.rect(8, 12, 16, 2, DARK_STONE)    # brow, across the whole face
    ic.rect(9, 13, 5, 1, BLACK)
    ic.rect(18, 13, 5, 1, BLACK)
    ic.rect(11, 20, 10, 2, DARK_STONE)   # the seam of a mouth
    return ic.outline().shade()


def _sentry():
    """Clockwork: brass gear in a steel case. Not, as before, a bonfire.

    Every surface was copper - maroon screened with yellow - so the whole
    thing read as flame, which is the wrong creature entirely.
    """
    ic = Icon()
    steel = GRAY
    ic.rect(11, 3, 10, 9, steel)          # head case
    ic.rect(11, 3, 10, 1, SILVER)
    ic.rect(11, 3, 1, 9, SILVER)
    ic.rect(12, 6, 3, 2, RED)             # lens slits
    ic.rect(17, 6, 3, 2, RED)
    ic.rect(12, 9, 8, 1, DARK_STONE)      # grille
    ic.rect(9, 13, 14, 12, steel)         # body case
    ic.rect(9, 13, 14, 1, SILVER)
    ic.rect(9, 13, 1, 12, SILVER)
    ic.rect(22, 13, 1, 12, DARK_STONE)
    ic.rect(9, 24, 14, 1, DARK_STONE)
    # The gear: a brass disc with square teeth, which is what makes it read
    # as a machine rather than as a glow.
    ic.oval(16, 19, 4, 4, OLIVE)
    ic.oval(16, 19, 2, 2, YELLOW)
    for dx, dy in ((0, -6), (0, 5), (-6, 0), (5, 0),
                   (-4, -4), (4, -4), (-4, 4), (4, 4)):
        ic.rect(16 + dx, 19 + dy, 2, 2, OLIVE)
    ic.rect(6, 14, 3, 9, steel)           # arms
    ic.rect(23, 14, 3, 9, steel)
    ic.rect(5, 22, 5, 3, GRAY)            # fists
    ic.rect(22, 22, 5, 3, GRAY)
    ic.rect(11, 25, 4, 6, GRAY)           # legs
    ic.rect(17, 25, 4, 6, GRAY)
    ic.rect(10, 30, 6, 2, DARK_STONE)     # feet
    ic.rect(16, 30, 6, 2, DARK_STONE)
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
        # What says "sabre" at thirty-two pixels is not a sweeping arc - an
        # arc that size is three pixels of lean and reads as a mistake, or,
        # drawn boldly, as a broken sword. It is the clipped back-angled
        # point and the knuckle bow over the grip. Both survive the scale.
        for i in range(5):                       # clip the back of the point
            ic.rect(16 + width // 2 - i, top + i, i + 1, 1, None)
        for i in range(4):                       # and re-lay the edge on it
            ic.set(16 + width // 2 - i - 1, top + i + 1, metal)
        ic.line(11, 30 - 7, 9, 30 - 3, hilt)     # knuckle bow, down to
        ic.line(9, 30 - 3, 13, 30 - 1, hilt)     # the pommel
        ic.set(10, 30 - 6, lighter(hilt) if not is_pair(hilt) else hilt)

    ic.rect(10, 30 - 8, 12, 3, hilt)               # cross-guard
    ic.rect(10, 30 - 8, 12, 1, lighter(hilt) if not is_pair(hilt) else hilt)
    ic.rect(15, 30 - 5, 3, 5, BROWN)               # grip
    ic.rect(14, 30 - 1, 5, 2, hilt)                # pommel
    return ic.outline().shade()


def _haft_weapon(head_fn, haft=MAROON):
    """A head on a shaft. The shaft is three pixels wide, so it is flat
    colour: a dither pair that narrow comes out as a string of beads."""
    ic = Icon()
    ic.rect(15, 6, 3, 25, haft)
    ic.rect(15, 6, 1, 25, OLIVE)
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
    """A war hammer: a short blocky head with a flat face and a peen."""
    def head(ic):
        ic.rect(7, 5, 18, 10, SILVER)        # the head, shorter than it was
        ic.rect(7, 5, 18, 1, WHITE)
        ic.rect(7, 5, 1, 10, WHITE)
        ic.rect(7, 14, 18, 1, GRAY)
        ic.rect(5, 6, 2, 8, GRAY)            # the striking face stands proud
        ic.rect(25, 7, 3, 6, GRAY)           # the peen on the far side
        ic.rect(13, 5, 6, 10, (SILVER, WHITE, 0.3))   # a lit band across it
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
    """A stave, a string and a nocked arrow.

    Every line here is one or two pixels wide, so all of it is flat colour:
    drawn with dither pairs the stave and the shaft came out as strings of
    red and yellow beads.
    """
    ic = Icon()
    for dx, colour in ((0, MAROON), (1, MAROON), (2, OLIVE)):
        ic.line(8 + dx, 3, 4 + dx, 16, colour)
        ic.line(4 + dx, 16, 8 + dx, 29, colour)
    ic.rect(7, 2, 2, 2, OLIVE)                     # nocks
    ic.rect(7, 28, 2, 2, OLIVE)
    ic.line(9, 3, 9, 29, SILVER)                   # the string
    ic.rect(10, 15, 16, 2, OLIVE)                  # nocked arrow
    ic.rect(10, 15, 16, 1, YELLOW)
    ic.tri([(25, 12), (31, 16), (25, 20)], SILVER)
    ic.rect(11, 13, 3, 6, MAROON)                  # fletching
    return ic.outline().shade()


def icon_crossbow():
    """A steel prod across a slim wooden stock, string drawn to the nut.

    Kept deliberately spare. Earlier tries gave it a broad stock and a flared
    butt, and at this size the extra mass just read as a brown cross with a
    lump on it.
    """
    ic = Icon()
    ic.rect(14, 4, 4, 25, MAROON)                # stock: flat, it is thin
    ic.rect(14, 4, 1, 25, OLIVE)
    ic.rect(13, 25, 6, 4, DARK_BROWN)            # butt
    ic.rect(4, 12, 24, 3, GRAY)                  # the prod: steel, solid
    ic.rect(4, 12, 24, 1, SILVER)
    ic.rect(4, 15, 24, 1, DARK_STONE)
    ic.line(5, 11, 16, 8, SILVER)                # string, drawn to the nut
    ic.line(16, 8, 27, 11, SILVER)
    ic.rect(14, 7, 4, 3, DARK_STONE)             # the nut
    ic.rect(13, 18, 6, 2, DARK_STONE)            # trigger
    return ic.outline().shade()


def icon_arrows():
    ic = Icon()
    for x in (8, 15, 22):
        ic.rect(x, 8, 2, 20, OLIVE)                # flat: two pixels is thin
        ic.rect(x, 8, 1, 20, YELLOW)
        ic.tri([(x + 1, 2), (x - 2, 9), (x + 4, 9)], SILVER)
        ic.rect(x - 2, 23, 6, 2, MAROON)           # fletching
        ic.rect(x - 2, 25, 6, 1, RED)
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
def icon_platemail():
    """The one suit with no texture, so it needs shape instead.

    Every other mail in the set is told apart by its studs, scales or rings.
    Plate has none, which left it a silver blob indistinguishable from the
    others at map size - so it gets a breastplate ridge, a neckline and
    banded tassets.
    """
    ic = _armour(body=SILVER, skirt=GRAY)
    ic.rect(15, 9, 2, 14, WHITE)                 # the central ridge, lit
    ic.rect(17, 9, 1, 14, GRAY)                  # and its shadow side
    ic.tri([(10, 8), (22, 8), (16, 14)], GRAY)   # neckline
    ic.tri([(11, 8), (21, 8), (16, 12)], SILVER)
    for y in (24, 27):                           # banded tassets
        ic.rect(7, y, 18, 1, DARK_STONE)
    ic.rect(2, 10, 4, 1, WHITE)                  # lit tops of the pauldrons
    ic.rect(26, 10, 4, 1, WHITE)
    return ic.outline().shade()


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
        # A door of a shield: rounded at the top, tapered at the foot, banded
        # and riveted. It used to be a plain rectangle with a dash on it.
        ic.oval(16, 7, 9, 6, face)
        ic.rect(7, 7, 19, 18, face)
        ic.tri([(7, 25), (26, 25), (16, 30)], face)
        ic.rect(7, 7, 1, 18, WHITE)
        ic.oval(16, 6, 9, 5, lighter(face))
        ic.rect(7, 12, 19, 2, darker(face))      # bands
        ic.rect(7, 20, 19, 2, darker(face))
        for x in (9, 15, 22):                    # rivets
            ic.rect(x, 12, 2, 2, boss)
            ic.rect(x, 20, 2, 2, boss)
        ic.rect(13, 15, 6, 4, boss)              # the boss
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
    """A great helm: dome, horizontal vision slit, cheek guards.

    The old one had a six-pixel black bar running vertically down the middle
    of a white shape, which read as a pair of trousers rather than as a helm.
    A visor slit is horizontal, and the shape below it has to narrow.
    """
    ic = Icon()
    ic.oval(16, 13, 10, 9, SILVER)       # dome
    ic.rect(6, 13, 21, 9, SILVER)        # skull
    ic.rect(7, 22, 19, 4, GRAY)          # cheek guards, a step darker
    ic.tri([(7, 26), (25, 26), (16, 29)], GRAY)
    ic.rect(7, 17, 19, 3, BLACK)         # the slit, horizontal
    ic.rect(15, 17, 2, 3, SILVER)        # nasal bar crossing it
    ic.rect(6, 21, 21, 1, GRAY)          # brow line
    ic.oval(12, 9, 3, 2, WHITE)          # the light, upper left
    return ic.outline().shade()


def icon_cap():
    ic = Icon()
    ic.oval(16, 17, 11, 9, BROWN)
    ic.rect(5, 17, 22, 6, BROWN)
    ic.rect(4, 22, 24, 3, DARK_BROWN)
    return ic.outline().shade()


def icon_gauntlets():
    """A pair of armoured gloves: cuff, back plate, four finger plates."""
    ic = Icon()
    for x in (3, 18):
        ic.rect(x, 16, 11, 6, GRAY)          # cuff, flared
        ic.rect(x + 1, 10, 9, 7, SILVER)     # back of the hand
        ic.rect(x + 1, 10, 9, 1, WHITE)
        for f in range(4):                   # fingers
            ic.rect(x + 1 + f * 2, 6, 2, 5, SILVER)
            ic.rect(x + 1 + f * 2, 6, 1, 5, GRAY)
        ic.rect(x + 9, 12, 2, 4, SILVER)     # thumb
        ic.rect(x, 21, 11, 1, DARK_STONE)
    return ic.outline().shade()


def icon_bracers():
    """Forearm guards: two banded cuffs, laced down the inside."""
    ic = Icon()
    for x in (4, 18):
        ic.rect(x, 8, 10, 17, DARK_BROWN)
        ic.rect(x, 8, 10, 2, BROWN)
        ic.rect(x, 23, 10, 2, BROWN)
        for y in (12, 16, 20):
            ic.rect(x + 1, y, 8, 1, WOOD_LIT)
        ic.rect(x + 4, 10, 2, 13, SILVER)          # the lacing
    return ic.outline().shade()


def icon_boots():
    ic = Icon()
    for x in (4, 18):
        ic.rect(x + 1, 6, 8, 16, BROWN)
        ic.rect(x, 22, 11, 5, DARK_BROWN)
        ic.rect(x + 1, 6, 8, 1, WOOD_LIT)
        ic.rect(x, 26, 11, 2, BLACK)
    return ic.outline().shade()


def icon_leggings():
    ic = Icon()
    ic.rect(8, 3, 16, 6, BROWN)
    ic.rect(8, 9, 6, 20, BROWN)
    ic.rect(18, 9, 6, 20, BROWN)
    ic.rect(8, 3, 16, 1, WOOD_LIT)
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
    ic.rect(2, 13, 28, 1, WOOD_LIT)
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
    ic.rect(4, 2, 24, 1, WOOD_LIT)
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
    ic.line(8, 24, 26, 21, WOOD_LIT)
    ic.oval(25, 8, 5, 5, FUCHSIA)
    ic.rect(23, 5, 2, 2, WHITE)
    ic.rect(20, 16, 4, 4, YELLOW)
    return ic.outline().shade()


def icon_staff():
    ic = Icon()
    ic.rect(14, 6, 4, 25, MAROON)        # flat: four pixels is still thin
    ic.rect(14, 6, 1, 25, OLIVE)
    ic.oval(16, 6, 7, 6, AQUA)
    ic.oval(16, 6, 3, 3, WHITE)
    return ic.outline().shade()


def icon_pack():
    ic = Icon()
    ic.rect(6, 8, 20, 21, BROWN)
    ic.rect(6, 8, 20, 1, WOOD_LIT)
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


def icon_quiver():
    ic = Icon()
    ic.rect(10, 8, 12, 21, DARK_BROWN)               # the tube
    ic.rect(10, 8, 12, 2, BROWN)
    ic.rect(9, 14, 14, 3, WOOD_LIT)    # strap
    for x in (12, 16, 20):                           # wands standing in it
        ic.rect(x, 3, 2, 7, SILVER)
        ic.rect(x, 3, 2, 2, AQUA)
    return ic.outline().shade()


def icon_chest():
    ic = Icon()
    ic.rect(3, 12, 26, 16, BROWN)
    ic.rect(3, 12, 26, 1, WOOD_LIT)
    ic.oval(16, 12, 13, 7, DARK_BROWN)   # domed lid
    ic.rect(3, 16, 26, 3, YELLOW)        # bands
    ic.rect(13, 16, 6, 8, YELLOW)
    ic.rect(15, 19, 2, 3, BLACK)         # keyhole
    return ic.outline().shade()


def icon_gold():
    """A heap of coins. Discs with dark rims, not one continuous puddle.

    The old one drew five wide ovals that all overlapped, so it came out as a
    single yellow amoeba with no coins in it at all.
    """
    ic = Icon()
    for cx, cy in ((7, 27), (14, 28), (21, 27), (26, 26),
                   (10, 22), (18, 22), (24, 21), (14, 17)):
        ic.oval(cx, cy, 5, 3, OLIVE)         # rim first
        ic.oval(cx, cy - 1, 4, 2, YELLOW)    # face, lit from above
        ic.set(cx - 2, cy - 2, WHITE)
    ic.oval(21, 15, 4, 3, OLIVE)             # one standing proud on top
    ic.oval(21, 14, 3, 2, YELLOW)
    ic.set(20, 13, WHITE)
    return ic.outline().shade()


def icon_gem():
    ic = Icon()
    ic.tri([(16, 3), (5, 14), (27, 14)], AQUA)
    ic.tri([(5, 14), (27, 14), (16, 29)], TEAL)
    ic.line(16, 3, 16, 29, WHITE)
    ic.line(5, 14, 27, 14, WHITE)
    ic.rect(12, 8, 3, 3, WHITE)
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
    # No ribs: it is a thing in armour, and rib lines over a stone-grey
    # tunic just read as noise.
    "iron_revenant": lambda: humanoid(skin=SILVER, cloth=DARK_STONE, trim=AQUA,
                                      eyes=AQUA, weapon="axe", helm=GRAY, bulk=3),

    # --- beasts ---------------------------------------------------------
    "dire_wolf":    lambda: beast(fur=GRAY, eyes=YELLOW, tail="bushy"),
    "ember_drake":  lambda: beast(fur=RUST, eyes=YELLOW, wings=True, horns=True,
                                  ears=False, big=True, aura=EMBER),

    # --- constructs and spirits -----------------------------------------
    "stone_golem":  _golem,
    "clockwork_sentry": _sentry,
    "storm_wisp":   _wisp,

    # --- the two that end a run ------------------------------------------
    # Charcoal hide, fire in the cracks of its harness. It used to be maroon
    # skin on a maroon body: one red block with horns.
    "warden_of_ash": lambda: humanoid(skin=DARK_STONE, cloth=MAROON, trim=EMBER,
                                      eyes=YELLOW, weapon="mace", bulk=8,
                                      horns=True, aura=EMBER),
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
