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


# The floor covers most of the screen, so it is the one tile that has to be
# quiet. It used to draw four big flagstones per tile, each with a black
# gutter round it and a bright grey edge on two sides, which laid a hard grid
# of dark boxes under everything and fought every creature standing on it.
FLOOR_STONE = (BLACK, GRAY, 0.3)        # charcoal: dark, with grit in it


def tile_floor(variant=0):
    ic = Icon()
    ic.rect(0, 0, ICON, ICON, FLOOR_STONE)
    # Joints only - no bevel, no highlight. Big slabs, softly marked.
    for by in range(0, ICON, 16):
        off = 8 if (by // 16) % 2 else 0
        ic.rect(0, by, ICON, 1, BLACK)
        ic.rect((off) % ICON, by, 1, 16, BLACK)
        ic.rect((off + 16) % ICON, by, 1, 16, BLACK)
    # A little grit, so a big room is not a flat field.
    for i in range(3):
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
            ic.rect(x + 1, by + 1, 14, bh - 2, calm(MID_STONE))
            ic.rect(x + 1, by + 1, 14, 1, SILVER)     # lit top
            ic.rect(x + 1, by + 1, 1, bh - 2, SILVER)  # lit left
            ic.rect(x + 1, by + bh - 2, 14, 1, DARK_STONE)
            ic.rect(x + 14, by + 1, 1, bh - 2, DARK_STONE)
    ic.rect(0, 0, ICON, 1, SILVER)
    ic.rect(0, ICON - 1, ICON, 1, BLACK)
    return ic


def tile_shop_floor(variant=0):
    """Floorboards. Wide, quiet ones - it is a floor, not a barcode.

    Eight-pixel boards with a black seam between every one of them made four
    hard stripes per tile, and the shopkeeper standing on it disappeared.
    """
    ic = Icon()
    ic.rect(0, 0, ICON, ICON, DARK_BROWN)
    for x in range(0, ICON, 16):               # half as many boards
        ic.rect(x + 1, 0, 14, ICON, calm(BROWN))
        ic.rect(x, 0, 1, ICON, MAROON)               # a soft seam
    for i in range(3):                          # a few nail heads
        ic.set(4 + (i % 2) * 16, 6 + i * 9, OLIVE)
    return ic


def tile_grass(variant=0):
    """Turf with a few blades. The blades used to be drawn in a near-black
    green, which at map size read as a scatter of holes in the ground."""
    ic = Icon()
    ic.rect(0, 0, ICON, ICON, calm(MOSS))
    for i in range(12):
        x = int(_noise(variant, i, 11) * (ICON - 2))
        y = int(_noise(i, variant, 13) * (ICON - 3))
        c = LIME if _noise(i, i, variant) > 0.8 else GREEN
        ic.rect(x, y, 1, 2, c)
    return ic


def tile_road(variant=0):
    ic = Icon()
    ic.rect(0, 0, ICON, ICON, calm((OLIVE, GRAY, 0.5), 0.8))
    for i in range(10):
        x = int(_noise(variant, i, 17) * (ICON - 3))
        y = int(_noise(i, variant, 19) * (ICON - 3))
        ic.rect(x, y, 2, 2, SILVER if i % 2 else GRAY)
    return ic


def tile_tree(variant=0):
    """A canopy of clumps over a trunk, not a lollipop.

    One circle with a smaller bright circle on it reads as a balloon on a
    stick. A tree reads as a tree when its outline is lumpy.
    """
    ic = Icon()
    ic.rect(0, 0, ICON, ICON, calm(MOSS))
    ic.rect(14, 21, 4, 11, OLIVE)                # trunk, flat: it is thin
    ic.rect(14, 21, 1, 11, YELLOW)
    ic.rect(17, 21, 1, 11, MAROON)
    ic.rect(13, 31, 6, 1, GREEN)                 # roots in the grass
    for cx, cy, r in ((16, 15, 9), (9, 17, 5), (23, 17, 5),
                      (12, 9, 5), (21, 10, 5)):
        ic.oval(cx, cy, r, r - 1, GREEN)         # clumps make the outline
    for cx, cy, r in ((12, 10, 4), (18, 8, 3), (9, 15, 3)):
        ic.oval(cx, cy, r, r - 1, LIME)          # lit from the upper left
    for cx, cy, r in ((21, 19, 4), (16, 21, 4)):
        ic.oval(cx, cy, r, r - 1, DARK_GREEN)    # and shaded beneath
    return ic


def tile_water(variant=0):
    """Dark water with a little light on it.

    It was a flat sheet of the brightest blue in the palette, which made a
    pond the loudest thing on the screen - brighter than the creatures, and
    with a hard edge that read as a panel rather than as water.
    """
    ic = Icon()
    ic.rect(0, 0, ICON, ICON, calm(DEEP_WATER))
    for y in range(3, ICON, 7):
        off = int(_noise(variant, y, 23) * 12)
        ic.rect(off, y, ICON - off - 10, 1, BLUE)          # ripples
        ic.rect(off + 3, y, 4, 1, AQUA)                    # a glint on one
    for i in range(4):
        x = int(_noise(variant, i, 31) * ICON)
        y = int(_noise(i, variant, 37) * ICON)
        ic.set(x, y, NAVY)
    return ic


def tile_rubble(variant=0):
    ic = Icon()
    ic.rect(0, 0, ICON, ICON, FLOOR_STONE)   # sitting on the same floor
    chunks = [(2, 3, 9, 7), (14, 2, 11, 8), (25, 6, 6, 6),
              (1, 13, 8, 8), (11, 12, 10, 9), (22, 15, 9, 8),
              (4, 23, 10, 8), (16, 23, 7, 8), (25, 25, 6, 6)]
    for i, (x, y, w, h) in enumerate(chunks):
        jx = int(_noise(variant, i, 29) * 2)
        x = min(x + jx, ICON - w)
        ic.rect(x, y, w, h, GRAY)
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

# ===========================================================================
#  Creatures, drawn close.
#
#  These used to be whole figures: a head, a body, two arms and two legs
#  inside thirty-two pixels, which leaves about five pixels for a face. Every
#  creature in the game therefore looked like the same small person in a
#  different colour, and what tells a kobold from an orc - the snout, the
#  tusks, the ears, the brow - was below the resolution.
#
#  So they are cropped now, the way Castle of the Winds crops its own: head
#  and shoulders, filling the frame. The limbs are gone and the face is worth
#  half the icon. A creature is recognised by its head; this is the room to
#  draw one.
# ===========================================================================

def portrait(skin=TAN, cloth=NAVY, trim=YELLOW, eyes=WHITE,
             head_w=16, head_h=15, brow=True, ears=None, horns=None,
             muzzle=0, tusks=False, fangs=False, hood=False, helm=None,
             crown=False, hat=None, hair=None, beard=None, eye_style="dot",
             shoulders="cloth", weapon=None, aura=None, skull=False):
    """One creature, head and shoulders, filling the icon.

    Everything is measured off the head, so a wide head brings wide shoulders
    and a heavy brow with it and the proportions hold from a kobold to an
    ogre.
    """
    ic = Icon()
    hx = 16 - head_w // 2
    hy = 3 if head_h >= 15 else 4
    hb = hy + head_h                      # the jaw line
    neck_y = hb
    sh_y = min(30, hb + 3)
    sh_w = min(30, head_w + 10)

    if aura:
        for i in range(0, 360, 14):
            import math
            a = math.radians(i)
            ic.set(16 + int(round(14.5 * math.cos(a))),
                   16 + int(round(15.0 * math.sin(a))), aura)

    # ---- shoulders, cut off by the bottom of the frame -------------------
    ic.rect(16 - 4, neck_y, 8, sh_y - neck_y + 1, calm(skin))     # neck
    ic.rect(16 - 4, neck_y, 1, sh_y - neck_y + 1, darker(skin))
    body = calm(cloth)
    for y in range(sh_y, ICON):
        grow = (y - sh_y)
        w = min(sh_w, 12 + grow * 4)
        ic.rect(16 - w // 2, y, w, 1, body)
    if shoulders == "armour":
        ic.rect(16 - sh_w // 2, sh_y + 2, 5, ICON - sh_y - 2, calm(trim))
        ic.rect(16 + sh_w // 2 - 5, sh_y + 2, 5, ICON - sh_y - 2, calm(trim))
        ic.rect(16 - sh_w // 2, sh_y + 2, sh_w, 1, lighter(trim))
    elif shoulders == "robe":
        ic.tri([(16 - 7, sh_y), (16 + 7, sh_y), (16, ICON - 1)], calm(trim))
        ic.tri([(16 - 5, sh_y), (16 + 5, sh_y), (16, ICON - 3)], calm(skin))
    elif shoulders == "rags":
        for x in range(16 - sh_w // 2, 16 + sh_w // 2, 4):
            ic.rect(x, ICON - 3, 2, 3, None)
    ic.rect(16 - 6, sh_y, 12, 1, darker(cloth))                  # collar

    # ---- the head --------------------------------------------------------
    ic.rect(hx, hy, head_w, head_h, calm(skin))
    ic.rect(hx + 1, hy - 1, head_w - 2, 1, calm(skin))           # rounded crown
    ic.rect(hx + 1, hb, head_w - 2, 1, calm(skin))               # rounded jaw
    ic.rect(hx, hy, 1, head_h, lighter(skin))                    # lit left side
    ic.rect(hx + head_w - 1, hy, 1, head_h, darker(skin))        # shaded right

    eye_y = hy + head_h // 3
    eye_in = 3 if head_w >= 15 else 2
    ew = 3 if head_w >= 15 else 2
    lx, rx = hx + eye_in, hx + head_w - eye_in - ew

    if brow:
        ic.rect(hx + 1, eye_y - 2, head_w - 2, 2, darker(skin))
        ic.rect(hx + 1, eye_y - 2, head_w - 2, 1, BLACK)

    # ---- the eyes, which is where the character lives --------------------
    if eye_style == "socket":                    # a skull, or something gaunt
        ic.rect(lx - 1, eye_y - 1, ew + 2, 5, BLACK)
        ic.rect(rx - 1, eye_y - 1, ew + 2, 5, BLACK)
        ic.rect(lx, eye_y + 1, ew, 2, eyes)
        ic.rect(rx, eye_y + 1, ew, 2, eyes)
    elif eye_style == "glow":                    # burning, from inside a hood
        for ex in (lx, rx):
            ic.rect(ex - 1, eye_y, ew + 2, 3, darker(eyes))
            ic.rect(ex, eye_y, ew, 3, eyes)
            ic.set(ex, eye_y, lighter(eyes))
    elif eye_style == "slit":                    # a visor, or a machine
        ic.rect(hx + 2, eye_y, head_w - 4, 3, BLACK)
        ic.rect(lx, eye_y + 1, ew, 1, eyes)
        ic.rect(rx, eye_y + 1, ew, 1, eyes)
    else:
        for ex in (lx, rx):
            ic.rect(ex, eye_y, ew, 3, WHITE if eyes != WHITE else SILVER)
            ic.rect(ex + (1 if ex == lx else 0), eye_y + 1, ew - 1, 2, eyes)

    # ---- snout, mouth, teeth ---------------------------------------------
    mouth_y = hy + head_h - 4
    if muzzle:
        # A snout pushed forward out of the jaw, the same colour as the face
        # with the nostrils dark on top of it - not, as it was, a pale patch
        # stuck on the middle of the face.
        mw = head_w // 2 + 2
        ic.rect(16 - mw // 2, mouth_y - 2, mw, 4 + muzzle, calm(skin))
        ic.rect(16 - mw // 2, mouth_y - 2, mw, 1, lighter(skin))
        ic.rect(16 - mw // 2, mouth_y - 2, 1, 4 + muzzle, lighter(skin))
        ic.rect(16 + mw // 2 - 1, mouth_y - 2, 1, 4 + muzzle, darker(skin))
        ic.rect(16 - 2, mouth_y - 1, 2, 2, BLACK)                # nostrils
        ic.rect(16 + 1, mouth_y - 1, 2, 2, BLACK)
        mouth_y = mouth_y + 2 + muzzle
        ic.rect(16 - mw // 2 + 1, mouth_y, mw - 2, 1, BLACK)     # the mouth
    else:
        ic.rect(16 - 1, mouth_y - 3, 2, 3, darker(skin))         # a nose
        ic.rect(16 - head_w // 4, mouth_y, head_w // 2, 1, BLACK)
    if tusks:
        for tx in (16 - head_w // 4, 16 + head_w // 4 - 2):
            ic.rect(tx, mouth_y - 3, 2, 4, BONE)
            ic.set(tx, mouth_y - 3, WHITE)
    if fangs:
        for tx in (16 - 4, 16 + 3):
            ic.rect(tx, mouth_y + 1, 1, 2, BONE)
    if skull:
        ic.rect(16 - 1, mouth_y - 5, 2, 3, BLACK)                # nasal cavity
        for tx in range(16 - 6, 16 + 6, 2):                      # teeth
            ic.rect(tx, mouth_y, 1, 3, BLACK)
        ic.rect(16 - 7, mouth_y - 1, 14, 1, BLACK)

    # ---- what is on or around the head -----------------------------------
    if ears == "pointed":
        ic.tri([(hx, hy + 3), (hx - 5, hy - 2), (hx + 1, hy + 8)], calm(skin))
        ic.tri([(hx + head_w - 1, hy + 3), (hx + head_w + 5, hy - 2),
                (hx + head_w - 2, hy + 8)], calm(skin))
    elif ears == "big":
        ic.oval(hx - 2, hy + 6, 4, 5, calm(skin))
        ic.oval(hx + head_w + 1, hy + 6, 4, 5, calm(skin))
        ic.oval(hx - 2, hy + 6, 2, 3, darker(skin))
        ic.oval(hx + head_w + 1, hy + 6, 2, 3, darker(skin))
    elif ears == "round":
        ic.oval(hx - 1, hy + 7, 3, 3, calm(skin))
        ic.oval(hx + head_w, hy + 7, 3, 3, calm(skin))

    if hair:
        ic.rect(hx - 1, hy - 2, head_w + 2, 5, hair)
        ic.rect(hx - 1, hy - 2, head_w + 2, 1, lighter(hair))
        ic.rect(hx - 2, hy + 1, 2, 7, hair)
        ic.rect(hx + head_w, hy + 1, 2, 7, hair)
    if beard:
        # Below the mouth and narrower than the face, tapering. Drawn as a
        # full-width block from the mouth down it reads as a bib.
        ic.rect(16 - 4, mouth_y - 1, 8, 2, calm(beard))           # moustache
        ic.rect(16 - 4, mouth_y - 1, 8, 1, lighter(beard))
        for i in range(hb - mouth_y + 4):
            w = max(3, head_w - 4 - i)
            ic.rect(16 - w // 2, mouth_y + 1 + i, w, 1, calm(beard))
        ic.rect(16 - 1, mouth_y + 1, 2, 1, BLACK)                 # the mouth
    if hood:
        # A ring of cloth around the skull and down past the jaw, and that is
        # all. Every version of this that put anything *over* the face - a
        # cone, a dome, a band of shadow at the brow - read as a mask or as a
        # dark shape with no creature in it. The cloth frames the face; the
        # face is left alone.
        ic.oval(16, hy + head_h // 2 - 1, head_w // 2 + 3, head_h // 2 + 3,
                calm(cloth))
        ic.rect(16 - head_w // 2 - 3, hy + head_h // 2, head_w + 6,
                head_h // 2 + 4, calm(cloth))
        ic.oval(16, hy + head_h // 2 - 2, head_w // 2 + 3, 3, lighter(cloth))
        # and the face back out of it
        ic.oval(16, hy + head_h // 2, head_w // 2 - 1, head_h // 2 + 1,
                calm(skin))
        for ex in (lx, rx):
            ic.rect(ex, eye_y, ew, 3, WHITE if eyes != WHITE else SILVER)
            ic.rect(ex, eye_y + 1, ew, 2, eyes)
        ic.rect(16 - head_w // 5, mouth_y, 2 * (head_w // 5), 1, BLACK)

    if helm:
        # A cap down to the brow and a nasal bar between the eyes. Taken any
        # lower it covers them, and a helmet with no eyes under it is a
        # bucket.
        ic.rect(hx - 2, hy - 2, head_w + 4, eye_y - hy, calm(helm))
        ic.rect(hx - 2, hy - 2, head_w + 4, 1, lighter(helm))
        ic.rect(hx - 2, eye_y - 1, head_w + 4, 1, darker(helm))
        ic.rect(16 - 1, hy - 2, 2, head_h - 6, calm(helm))       # nasal
        ic.rect(16 - 1, hy - 2, 1, head_h - 6, lighter(helm))
        ic.rect(hx - 3, hy + 2, 2, 6, calm(helm))                # cheek plates
        ic.rect(hx + head_w + 1, hy + 2, 2, 6, calm(helm))
    if hat:
        # The crown of a hat used to be drawn seven rows above the head, and
        # the head starts on row three, so every hat in the game was cut off
        # by the top of the icon. It sits on the head now.
        ic.rect(hx + 2, hy - 2, head_w - 4, 5, calm(hat))        # crown
        ic.rect(hx + 2, hy - 2, head_w - 4, 1, lighter(hat))
        ic.rect(hx + 2, hy - 2, 1, 5, lighter(hat))
        ic.rect(hx - 4, hy + 2, head_w + 8, 2, calm(hat))        # brim
        ic.rect(hx - 4, hy + 2, head_w + 8, 1, lighter(hat))
        ic.rect(hx - 4, hy + 4, head_w + 8, 1, darker(hat))
    if horns == "curved":
        for side, x0 in ((-1, hx + 1), (1, hx + head_w - 2)):
            for i in range(6):
                ic.rect(x0 + side * i, hy - 1 - i, 2, 2, BONE)
            ic.rect(x0 + side * 5, hy - 7, 2, 3, WHITE)
    elif horns == "straight":
        ic.tri([(hx + 1, hy), (hx - 3, hy - 8), (hx + 5, hy - 1)], BONE)
        ic.tri([(hx + head_w - 2, hy), (hx + head_w + 3, hy - 8),
                (hx + head_w - 6, hy - 1)], BONE)
    elif horns == "crest":
        for i, x in enumerate(range(16 - 6, 16 + 7, 3)):
            h = 5 - abs(i - 2)
            ic.rect(x, hy - h, 2, h + 1, BONE)
    if crown:
        ic.rect(hx, hy - 2, head_w, 3, YELLOW)
        ic.rect(hx, hy - 2, head_w, 1, WHITE)
        for i in range(0, head_w - 1, 4):
            ic.tri([(hx + i, hy - 2), (hx + i + 2, hy - 6),
                    (hx + i + 4, hy - 2)], YELLOW)
        ic.rect(16 - 1, hy - 1, 2, 2, AQUA)

    # ---- something held up beside the head -------------------------------
    if weapon:
        _portrait_weapon(ic, weapon)
    return ic.outline().shade()


def _portrait_weapon(ic, kind):
    """A blade or a haft rising past the shoulder. Enough to read as armed."""
    x = 26
    if kind == "sword":
        ic.rect(x, 4, 4, 20, SILVER)
        ic.rect(x, 4, 1, 20, WHITE)
        ic.tri([(x, 4), (x + 4, 4), (x + 2, 0)], SILVER)
        ic.rect(x - 1, 24, 6, 2, YELLOW)
    elif kind == "axe":
        ic.rect(x, 6, 3, 22, OLIVE)
        ic.rect(x, 6, 1, 22, YELLOW)
        ic.tri([(x, 4), (x - 7, 8), (x, 15)], SILVER)
        ic.rect(x - 5, 6, 2, 6, WHITE)
    elif kind == "mace":
        ic.rect(x, 10, 3, 18, OLIVE)
        ic.rect(x, 10, 1, 18, YELLOW)
        ic.oval(x + 1, 7, 5, 5, SILVER)
        ic.set(x - 1, 5, WHITE)
    elif kind == "staff":
        ic.rect(x, 8, 3, 22, OLIVE)
        ic.rect(x, 8, 1, 22, YELLOW)
        ic.oval(x + 1, 5, 4, 4, AQUA)
        ic.oval(x + 1, 5, 2, 2, WHITE)
    elif kind == "bow":
        for dx, colour in ((0, MAROON), (1, OLIVE), (2, OLIVE)):
            ic.line(x + dx, 2, x - 3 + dx, 15, colour)
            ic.line(x - 3 + dx, 15, x + dx, 28, colour)
        ic.line(x + 3, 2, x + 3, 28, SILVER)
    elif kind == "claw":
        for i in range(3):
            ic.line(x - 2 + i * 2, 12, x + 2 + i * 2, 22, BONE)
            ic.set(x - 2 + i * 2, 12, WHITE)
    elif kind == "hammer":
        ic.rect(x, 10, 3, 18, OLIVE)
        ic.rect(x, 10, 1, 18, YELLOW)
        ic.rect(x - 3, 4, 9, 6, SILVER)
        ic.rect(x - 3, 4, 9, 1, WHITE)
    elif kind == "spear":
        ic.rect(x, 6, 3, 24, OLIVE)
        ic.rect(x, 6, 1, 24, YELLOW)
        ic.tri([(x + 1, 0), (x - 2, 7), (x + 4, 7)], SILVER)


def beast_head(fur=BROWN, eyes=RED, ears="pointed", snout=8, fangs=True,
               horns=False, wings=False, mane=None, aura=None, nose=BLACK):
    """An animal, close: skull, muzzle, ears, eyes. Filling the frame.

    Drawn three-quarters on, because a head straight on is symmetrical and
    symmetry at this size reads as a mask rather than as an animal.
    """
    ic = Icon()
    if aura:
        for i in range(0, 360, 16):
            import math
            a = math.radians(i)
            ic.set(16 + int(round(14.5 * math.cos(a))),
                   17 + int(round(14.0 * math.sin(a))), aura)
    if wings:
        ic.tri([(8, 8), (0, 1), (6, 20)], calm(darker(fur)))
        ic.tri([(24, 8), (32, 1), (26, 20)], calm(darker(fur)))
    if mane:
        ic.oval(16, 18, 15, 13, calm(mane))

    ic.oval(15, 15, 11, 10, calm(fur))                 # skull
    ic.rect(6, 15, 19, 12, calm(fur))                  # cheeks and jaw
    ic.rect(6, 15, 1, 12, lighter(fur))
    ic.rect(24, 15, 1, 12, darker(fur))

    # muzzle, pushed out to the lower right so the head reads at an angle
    mx, my = 17, 20
    ic.rect(mx, my, snout, 8, calm(fur))
    ic.rect(mx, my, snout, 1, lighter(fur))
    ic.rect(mx, my + 7, snout, 1, darker(fur))
    ic.oval(mx + snout - 1, my + 2, 3, 3, nose)        # the nose at the end
    ic.rect(mx + 1, my + 5, snout - 2, 1, BLACK)       # the mouth line
    if fangs:
        for i in range(3):
            ic.rect(mx + 2 + i * 3, my + 6, 1, 3, BONE)
        ic.rect(mx + 1, my + 4, 2, 3, BONE)

    if ears == "pointed":
        ic.tri([(7, 12), (4, 0), (14, 9)], calm(fur))
        ic.tri([(19, 10), (25, 0), (26, 12)], calm(fur))
        ic.tri([(8, 11), (6, 3), (13, 9)], darker(fur))
        ic.tri([(20, 10), (24, 3), (25, 11)], darker(fur))
    elif ears == "round":
        ic.oval(7, 9, 5, 5, calm(fur))
        ic.oval(24, 9, 5, 5, calm(fur))
        ic.oval(7, 9, 3, 3, darker(fur))
        ic.oval(24, 9, 3, 3, darker(fur))
    elif ears == "bat":
        ic.tri([(8, 13), (1, 0), (15, 8)], calm(fur))
        ic.tri([(18, 8), (30, 0), (25, 13)], calm(fur))
        ic.tri([(9, 12), (4, 3), (14, 8)], darker(fur))
        ic.tri([(19, 8), (28, 3), (24, 12)], darker(fur))
    if horns:
        for side, x0 in ((-1, 9), (1, 22)):
            for i in range(5):
                ic.rect(x0 + side * i, 9 - i * 2, 3, 3, BONE)
            ic.set(x0 + side * 4, 0, WHITE)

    ic.rect(9, 13, 5, 4, BLACK)                        # eye sockets
    ic.rect(18, 13, 5, 4, BLACK)
    ic.rect(10, 14, 3, 2, eyes)
    ic.rect(19, 14, 3, 2, eyes)
    ic.set(10, 14, lighter(eyes))
    ic.set(19, 14, lighter(eyes))
    return ic.outline().shade()


def _spider():
    """Eight legs round a fat body, eyes across the front."""
    ic = Icon()
    for i, (ax, ay, bx, by) in enumerate((
            (10, 14, 1, 3), (10, 17, 0, 12), (10, 20, 1, 24), (11, 23, 4, 31),
            (22, 14, 31, 3), (22, 17, 32, 12), (22, 20, 31, 24), (21, 23, 28, 31))):
        kx = ax - 6 if ax < 16 else ax + 6
        ky = ay + (5 if i % 4 > 1 else -3)
        ic.line(ax, ay, kx, ky, BLACK)                 # the knee
        ic.line(kx, ky, bx, by, BLACK)
        ic.line(ax, ay - 1, kx, ky - 1, PURPLE)
        ic.line(kx, ky - 1, bx, by - 1, PURPLE)
    ic.oval(16, 21, 11, 10, calm(BRUISE))              # abdomen
    ic.oval(13, 18, 5, 4, PURPLE)
    ic.oval(16, 12, 9, 7, calm((PURPLE, BLACK, 0.35)))  # cephalothorax
    ic.rect(11, 8, 11, 3, BLACK)
    for x in (11, 15, 19):                             # the row of eyes
        ic.rect(x, 9, 2, 2, RED)
        ic.set(x, 9, YELLOW)
    ic.rect(13, 14, 3, 2, BONE)                        # fangs
    ic.rect(17, 14, 3, 2, BONE)
    for i in range(4):                                 # the mark on its back
        ic.rect(15, 18 + i * 2, 2, 1, YELLOW)
    return ic.outline().shade()


def _ooze():
    """A blob with things dissolving in it. No face: that is the point."""
    ic = Icon()
    ic.oval(16, 20, 14, 11, calm(SICK_GREEN))
    ic.oval(16, 14, 10, 8, calm(SICK_GREEN))
    ic.oval(11, 12, 5, 4, LIME)                        # the lit dome
    for x, y, r in ((9, 24, 3), (20, 25, 4), (25, 20, 3)):
        ic.oval(x, y, r, r - 1, LIME)                  # it bulges as it moves
    for x, y in ((12, 19), (19, 17), (22, 23), (14, 26)):
        ic.oval(x, y, 2, 2, DARK_GREEN)                # bubbles
    ic.rect(13, 22, 3, 4, BONE)                        # a bone, going down
    ic.rect(19, 20, 2, 5, BONE)
    ic.rect(8, 29, 16, 2, DARK_GREEN)                  # the puddle it leaves
    return ic.outline().shade()


def _golem():
    """A boulder with a face cut into it."""
    ic = Icon()
    body = GRAY
    ic.rect(4, 6, 24, 22, body)
    ic.rect(7, 3, 18, 4, body)
    ic.rect(2, 12, 3, 12, body)                        # shoulders, cut off
    ic.rect(27, 12, 3, 12, body)
    ic.rect(4, 28, 24, 4, body)
    ic.rect(4, 6, 24, 1, SILVER)                       # lit from upper left
    ic.rect(7, 3, 18, 1, SILVER)
    ic.rect(4, 6, 1, 22, SILVER)
    ic.rect(27, 6, 1, 22, DARK_STONE)
    ic.line(11, 5, 13, 11, DARK_STONE)                 # cracks
    ic.line(20, 4, 22, 10, DARK_STONE)
    ic.line(7, 24, 10, 30, DARK_STONE)
    ic.rect(5, 12, 22, 3, DARK_STONE)                  # the brow shelf
    ic.rect(6, 15, 8, 5, BLACK)                        # sunk sockets
    ic.rect(18, 15, 8, 5, BLACK)
    ic.rect(7, 16, 6, 3, AQUA)
    ic.rect(19, 16, 6, 3, AQUA)
    ic.rect(7, 16, 2, 1, WHITE)
    ic.rect(19, 16, 2, 1, WHITE)
    ic.rect(9, 24, 14, 3, DARK_STONE)                  # the seam of a mouth
    for x in range(10, 23, 3):
        ic.rect(x, 24, 1, 3, BLACK)
    return ic.outline().shade()


def _sentry():
    """Brass and steel: a lens, a grille, a gear where a heart would be."""
    ic = Icon()
    ic.rect(6, 4, 20, 20, GRAY)                        # the case
    ic.rect(6, 4, 20, 1, SILVER)
    ic.rect(6, 4, 1, 20, SILVER)
    ic.rect(25, 4, 1, 20, DARK_STONE)
    ic.rect(4, 8, 2, 10, DARK_STONE)                   # bolts at the temples
    ic.rect(26, 8, 2, 10, DARK_STONE)
    ic.rect(7, 10, 18, 5, BLACK)                       # the lens band
    ic.rect(9, 11, 5, 3, RED)
    ic.rect(18, 11, 5, 3, RED)
    ic.set(9, 11, YELLOW)
    ic.set(18, 11, YELLOW)
    for x in range(9, 24, 3):                          # the grille
        ic.rect(x, 18, 2, 4, DARK_STONE)
    ic.rect(7, 17, 18, 1, SILVER)
    ic.rect(4, 24, 24, 8, GRAY)                        # shoulders
    ic.rect(4, 24, 24, 1, SILVER)
    ic.oval(16, 29, 5, 5, OLIVE)                       # the gear in its chest
    ic.oval(16, 29, 2, 2, YELLOW)
    for dx, dy in ((0, -6), (-6, 0), (6, 0), (-4, -4), (4, -4)):
        ic.rect(16 + dx, 29 + dy, 2, 2, OLIVE)
    return ic.outline().shade()


def _wisp():
    """A knot of lightning. It has no body, so it gets no outline."""
    ic = Icon()
    for r, colour in ((9, TEAL), (7, AQUA), (4, (AQUA, WHITE, 0.5)), (2, WHITE)):
        ic.oval(16, 16, r, r, colour)
    import math
    for i in range(8):                                 # arcs thrown off it
        a = math.radians(i * 45 + 10)
        for step in range(3, 8):
            x = 16 + int(round(step * 1.9 * math.cos(a)))
            y = 16 + int(round(step * 1.9 * math.sin(a)))
            ic.set(x + (step % 2), y, AQUA if step % 2 else WHITE)
    for dx, dy in ((-13, -5), (12, -8), (-10, 9), (11, 8), (1, -14), (-2, 13)):
        ic.rect(16 + dx, 16 + dy, 2, 2, AQUA)
    return ic


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


def _haft_weapon(head_fn, haft=OLIVE):
    """A head on a shaft.

    The shaft is three pixels wide, so it is flat colour: a dither pair that
    narrow comes out as a string of beads. Olive body, yellow catching the
    light on the left, maroon in shadow on the right - the same three tones
    every other wooden thing in the set is built from.
    """
    ic = Icon()
    ic.rect(15, 6, 3, 25, haft)
    ic.rect(15, 6, 1, 25, YELLOW)
    ic.rect(17, 6, 1, 25, MAROON)
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
    ic.rect(14, 6, 4, 25, OLIVE)         # flat: four pixels is still thin
    ic.rect(14, 6, 1, 25, YELLOW)
    ic.rect(17, 6, 1, 25, MAROON)
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
    "cave_rat":     lambda: beast_head(fur=BROWN, eyes=RED, ears="round",
                                       snout=10, nose=FUCHSIA),
    "cellar_spider": _spider,
    "cave_bat":     lambda: beast_head(fur=BRUISE, eyes=YELLOW, ears="bat",
                                       snout=5, wings=True, nose=PURPLE),
    "acid_pudding": _ooze,

    # --- humanoids ------------------------------------------------------
    "kobold":       lambda: portrait(skin=RUST, cloth=DARK_BROWN, trim=OLIVE,
                                     eyes=YELLOW, head_w=14, head_h=13,
                                     ears="pointed", horns="straight",
                                     muzzle=2, fangs=True, weapon="spear"),
    "goblin":       lambda: portrait(skin=GREEN, cloth=DARK_BROWN, trim=MAROON,
                                     eyes=YELLOW, head_w=15, head_h=14,
                                     ears="pointed", fangs=True, muzzle=1,
                                     weapon="sword"),
    "goblin_archer": lambda: portrait(skin=MOSS, cloth=DARK_GREEN, trim=BROWN,
                                      eyes=YELLOW, head_w=15, head_h=14,
                                      ears="pointed", fangs=True,
                                      hood=True, weapon="bow"),
    "orc":          lambda: portrait(skin=DARK_GREEN, cloth=MAROON, trim=OLIVE,
                                     eyes=RED, head_w=18, head_h=16,
                                     ears="pointed", tusks=True, muzzle=1,
                                     helm=GRAY, shoulders="armour",
                                     weapon="axe"),
    "ogre":         lambda: portrait(skin=OLIVE, cloth=BROWN, trim=DARK_BROWN,
                                     eyes=YELLOW, head_w=20, head_h=17,
                                     ears="round", tusks=True, muzzle=2,
                                     hair=MAROON, weapon="mace"),
    "moss_troll":   lambda: portrait(skin=GREEN, cloth=MOSS, trim=DARK_GREEN,
                                     eyes=LIME, head_w=19, head_h=17,
                                     ears="pointed", horns="crest", muzzle=3,
                                     fangs=True, weapon="claw"),
    "ash_cultist":  lambda: portrait(skin=(OLIVE, MAROON, 0.5), cloth=MAROON, trim=RED,
                                     eyes=RED, head_w=15, head_h=14,
                                     hood=True, eye_style="glow",
                                     shoulders="robe", weapon="staff"),
    "storm_sorcerer": lambda: portrait(skin=PALE_SKIN, cloth=PLUM, trim=FUCHSIA,
                                       eyes=AQUA, head_w=15, head_h=14,
                                       hood=True, eye_style="glow",
                                       beard=SILVER, shoulders="robe",
                                       weapon="staff", aura=PLUM),

    # --- undead ---------------------------------------------------------
    "skeleton":     lambda: portrait(skin=BONE, cloth=DARK_STONE, trim=GRAY,
                                     eyes=RED, head_w=16, head_h=15,
                                     skull=True, eye_style="socket",
                                     brow=False, weapon="sword"),
    "shambler":     lambda: portrait(skin=SICK_GREEN, cloth=DARK_BROWN,
                                     trim=OLIVE, eyes=LIME, head_w=16,
                                     head_h=15, eye_style="socket",
                                     shoulders="rags", weapon="claw",
                                     hair=DARK_GREEN),
    "crypt_ghoul":  lambda: portrait(skin=(OLIVE, SILVER, 0.4), cloth=SHADOW_BLUE,
                                     trim=OLIVE, eyes=LIME, head_w=15,
                                     head_h=16, eye_style="socket", fangs=True,
                                     ears="pointed", shoulders="rags",
                                     weapon="claw"),
    "pale_wraith":  lambda: portrait(skin=ICE, cloth=(NAVY, TEAL, 0.5),
                                     trim=AQUA, eyes=AQUA, head_w=15,
                                     head_h=14, hood=True, eye_style="glow",
                                     shoulders="rags", aura=ICE),
    "iron_revenant": lambda: portrait(skin=GRAY, cloth=DARK_STONE, trim=SILVER,
                                      eyes=AQUA, head_w=17, head_h=15,
                                      helm=SILVER, eye_style="slit",
                                      shoulders="armour", weapon="axe"),

    # --- beasts ---------------------------------------------------------
    "dire_wolf":    lambda: beast_head(fur=GRAY, eyes=YELLOW, ears="pointed",
                                       snout=10, mane=DARK_STONE),
    "ember_drake":  lambda: beast_head(fur=RUST, eyes=YELLOW, ears="pointed",
                                       snout=9, horns=True, wings=True,
                                       aura=EMBER, nose=BLACK),

    # --- constructs and spirits -----------------------------------------
    "stone_golem":  _golem,
    "clockwork_sentry": _sentry,
    "storm_wisp":   _wisp,

    # --- the two that end a run ------------------------------------------
    "warden_of_ash": lambda: portrait(skin=DARK_STONE, cloth=MAROON, trim=EMBER,
                                      eyes=YELLOW, head_w=20, head_h=17,
                                      horns="curved", eye_style="glow",
                                      tusks=True, muzzle=1, aura=EMBER,
                                      shoulders="armour", weapon="mace"),
    "vaelrik":      lambda: portrait(skin=SHADOW_BLUE, cloth=PLUM, trim=AQUA,
                                     eyes=AQUA, head_w=17, head_h=16,
                                     crown=True, eye_style="glow",
                                     beard=(NAVY, TEAL, 0.4), aura=PLUM,
                                     shoulders="armour", weapon="sword"),

    # --- townsfolk -------------------------------------------------------
    "npc_smith":     lambda: portrait(skin=TAN, cloth=DARK_BROWN, trim=GRAY,
                                      eyes=BLACK, beard=(MAROON, OLIVE, 0.3),
                                      hair=MAROON, weapon="hammer"),
    "npc_armourer":  lambda: portrait(skin=TAN, cloth=GRAY, trim=MAROON,
                                      eyes=BLACK, helm=OLIVE,
                                      shoulders="armour"),
    "npc_alchemist": lambda: portrait(skin=PALE_SKIN, cloth=PURPLE, trim=LIME,
                                      eyes=BLACK, hat=PURPLE, beard=SILVER,
                                      shoulders="robe"),
    "npc_sage":      lambda: portrait(skin=PALE_SKIN, cloth=NAVY, trim=AQUA,
                                      eyes=BLACK, hood=True, beard=SILVER,
                                      shoulders="robe", weapon="staff"),
    "npc_priest":    lambda: portrait(skin=TAN, cloth=NAVY, trim=SILVER,
                                      eyes=BLACK, hood=True, shoulders="robe"),
    "npc_banker":    lambda: portrait(skin=TAN, cloth=OLIVE, trim=YELLOW,
                                      eyes=BLACK, hat=OLIVE, hair=GRAY),
    "npc_trader":    lambda: portrait(skin=TAN, cloth=GREEN, trim=BROWN,
                                      eyes=BLACK, hat=BROWN, beard=OLIVE),
}


# Hair/tunic colours a player character can be drawn in, so everyone in the
# party is instantly tellable apart on the map.
PLAYER_COLOURS = [MAROON, NAVY, GREEN, PURPLE, TEAL, OLIVE]


def adventurer(colour=NAVY, weapon=None, shield=False, helm=None, robe=False):
    """The player figure, cropped like everything else.

    A shield cannot sit beside the head the way a weapon can - there is only
    one free shoulder - so a shielded character wears it as a pauldron, which
    is what reads at this size anyway.
    """
    return portrait(skin=TAN, cloth=colour, trim=YELLOW, eyes=BLACK,
                    head_w=16, head_h=15, hair=MAROON,
                    helm=helm, hood=robe,
                    shoulders="armour" if shield else
                              ("robe" if robe else "cloth"),
                    weapon=weapon)


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
        self.spells = {}
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
        for name in SPELL_BUILDERS:
            self.spells[name] = spell_icon(name).surface(self.scale)
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

    def spell(self, name):
        """A spell's glyph. Built on demand for anything added since start-up."""
        found = self.spells.get(name)
        if found is None:
            found = spell_icon(name).surface(self.scale)
            self.spells[name] = found
        return found


# ===========================================================================
#  Spell icons
#
#  The quick-cast slots under the menu used to draw the numbers 1 to 10, which
#  told you how many spells you knew and nothing else. These are the same
#  idiom as everything above, at half the size: sixteen pixels is enough for a
#  silhouette and a colour, and a silhouette and a colour is what you read at
#  a glance in a fight.
#
#  The shape says what family the spell belongs to - bolt, ball, ward, cross,
#  eye, arrow - and the colour says which one it is within the family. Nothing
#  here is dithered: at this size a pair comes out as beads, which is the
#  first house rule above.
# ===========================================================================

SPELL_ICON = 16


def _glyph():
    return Icon(SPELL_ICON, SPELL_ICON)


def _outline(ic, colour=BLACK):
    """A black edge around whatever has been drawn, as the house style asks."""
    filled = [[ic.px[y][x] is not None for x in range(ic.w)] for y in range(ic.h)]
    for y in range(ic.h):
        for x in range(ic.w):
            if filled[y][x]:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < ic.w and 0 <= ny < ic.h and filled[ny][nx]:
                    ic.set(x, y, colour)
                    break
    return ic


def _bolt(colour, hot=WHITE, big=False):
    """A zigzag: the missile spells."""
    ic = _glyph()
    path = [(10, 1), (6, 7), (9, 7), (4, 14)] if not big else \
           [(11, 0), (6, 7), (10, 7), (3, 15)]
    for i in range(len(path) - 1):
        (x0, y0), (x1, y1) = path[i], path[i + 1]
        ic.line(x0, y0, x1, y1, colour)
        ic.line(x0 + 1, y0, x1 + 1, y1, colour)
        if big:
            ic.line(x0 + 2, y0, x1 + 2, y1, colour)
    ic.line(path[0][0], path[0][1], path[1][0], path[1][1], hot)
    return _outline(ic)


def _spark(colour=YELLOW):
    """The first spell anyone learns: a small bright fleck, not a thunderbolt."""
    ic = _glyph()
    ic.line(10, 4, 7, 8, colour)
    ic.line(11, 4, 8, 8, colour)
    ic.line(7, 8, 9, 8, colour)
    ic.line(9, 8, 6, 12, colour)
    ic.set(10, 4, WHITE)
    for x, y in ((4, 4), (13, 9), (5, 13)):
        ic.set(x, y, WHITE)
    return _outline(ic)


def _forked(colour):
    ic = _bolt(colour, big=True)
    ic.line(9, 8, 13, 13, colour)
    ic.line(10, 8, 14, 13, colour)
    return _outline(ic)


def _shard(colour, hot=WHITE):
    """An icicle: the cold missiles."""
    ic = _glyph()
    ic.tri([(8, 1), (12, 10), (4, 10)], colour)
    ic.tri([(8, 15), (12, 9), (4, 9)], colour)
    ic.line(8, 2, 8, 13, hot)
    return _outline(ic)


def _ball(colour, hot, ring=None):
    """A ball of something, thrown."""
    ic = _glyph()
    ic.oval(8, 8, 6, 6, colour)
    ic.oval(6, 6, 3, 3, hot)
    if ring:
        for x, y in ((1, 8), (15, 8), (8, 1), (8, 15),
                     (3, 3), (13, 3), (3, 13), (13, 13)):
            ic.set(x, y, ring)
    return _outline(ic)


def _storm(colour, hot):
    """A cloud with hail coming out of it.

    Four one-pixel streaks got a black edge each and the bottom half came out
    as a checkerboard - the same rule as thin dithered work, one line up in
    the file. Three fat shards with space between them read as falling ice.
    """
    ic = _glyph()
    ic.oval(6, 5, 5, 3, colour)
    ic.oval(11, 6, 4, 3, colour)
    ic.oval(8, 4, 4, 3, lighter(colour))
    for x in (4, 9, 13):
        ic.tri([(x, 10), (x + 2, 10), (x - 1, 15)], hot)
        ic.set(x, 11, WHITE)
    return _outline(ic)


def _burst(colour, hot):
    """Rays out of a centre: the spells that go off all around you."""
    ic = _glyph()
    ic.oval(8, 8, 4, 4, colour)
    ic.oval(7, 7, 2, 2, hot)
    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0),
                   (-1, -1), (1, -1), (-1, 1), (1, 1)):
        for step in (5, 6, 7):
            ic.set(8 + dx * step, 8 + dy * step, hot if step < 7 else colour)
    return _outline(ic)


def _ward(face, trim=SILVER, mark=None):
    """A shield: the defensive spells."""
    ic = _glyph()
    for y in range(2, 10):
        half = 6
        ic.rect(8 - half, y, half * 2, 1, face)
    for i, y in enumerate(range(10, 15)):
        half = max(1, 6 - i * 3 // 2)
        ic.rect(8 - half, y, half * 2, 1, face)
    ic.rect(2, 2, 12, 1, trim)
    ic.line(2, 3, 2, 9, trim)
    if mark:
        ic.rect(7, 5, 2, 6, mark)
        ic.rect(5, 7, 6, 2, mark)
    return _outline(ic)


def _ward_element(face, flame):
    ic = _ward(face)
    ic.oval(8, 7, 3, 3, flame)
    ic.set(7, 5, WHITE)
    return _outline(ic)


def _cross(colour, hot=WHITE, doubled=False, ring=None):
    """The healing family."""
    ic = _glyph()
    ic.rect(6, 2, 4, 12, colour)
    ic.rect(2, 6, 12, 4, colour)
    ic.rect(7, 3, 1, 10, hot)
    if doubled:
        ic.rect(6, 2, 4, 1, hot)
        ic.rect(6, 13, 4, 1, hot)
    if ring:
        for x, y in ((0, 5), (0, 10), (15, 5), (15, 10),
                     (5, 0), (10, 0), (5, 15), (10, 15)):
            ic.set(x, y, ring)
    return _outline(ic)


def _flask(body, fluid):
    ic = _glyph()
    ic.rect(6, 1, 4, 3, SILVER)
    ic.oval(8, 9, 5, 5, body)
    ic.oval(8, 10, 3, 3, fluid)
    return _outline(ic)


def _eye(iris, rays=None):
    """The divinations."""
    ic = _glyph()
    ic.oval(8, 8, 7, 4, WHITE)
    ic.oval(8, 8, 3, 3, iris)
    ic.oval(8, 8, 1, 1, BLACK)
    ic.set(6, 6, WHITE)
    if rays:
        for x, y in ((1, 2), (8, 0), (15, 2), (1, 14), (8, 15), (15, 14)):
            ic.set(x, y, rays)
    return _outline(ic)


def _arrow(colour, hot=WHITE, dashed=False, doubled=False):
    """The movement spells: a coloured arrow with a light top edge.

    The head used to be drawn in white, which swallowed the shaft and left
    Blink, Farstep and Haste as three identical white wedges.
    """
    ic = _glyph()
    spans = ((1, 5), (7, 11)) if dashed else ((1, 11),)
    for x0, x1 in spans:
        ic.rect(x0, 6, x1 - x0, 4, colour)
        ic.rect(x0, 6, x1 - x0, 1, hot)
    ic.tri([(9, 2), (15, 8), (9, 14)], colour)
    ic.line(9, 3, 14, 8, hot)
    if doubled:
        ic.tri([(4, 3), (9, 8), (4, 13)], colour)
        ic.line(4, 4, 8, 8, hot)
    return _outline(ic)


def _return_arrow(colour, hot=WHITE):
    """Recall: a hook back to where you started."""
    ic = _glyph()
    ic.rect(5, 3, 8, 3, colour)
    ic.rect(10, 3, 3, 9, colour)
    ic.rect(5, 3, 8, 1, hot)
    ic.tri([(11, 15), (15, 10), (7, 10)], colour)
    ic.line(8, 10, 14, 10, hot)
    ic.oval(4, 4, 2, 2, hot)
    return _outline(ic)


def _lamp():
    ic = _glyph()
    ic.rect(6, 1, 4, 2, GRAY)
    ic.oval(8, 8, 5, 6, YELLOW)
    ic.oval(8, 8, 3, 4, WHITE)
    ic.rect(4, 13, 8, 2, GRAY)
    return _outline(ic)


def _feather():
    ic = _glyph()
    ic.line(11, 2, 4, 14, BONE)
    for i in range(9):
        ic.line(11 - i * 0.8, 2 + i * 1.3, 11 - i * 0.8 - 3, 2 + i * 1.3 + 1, WHITE)
    return _outline(ic)


def _scroll_map():
    ic = _glyph()
    ic.rect(2, 3, 12, 10, BONE)
    ic.rect(2, 3, 12, 1, TAN)
    ic.rect(2, 12, 12, 1, TAN)
    ic.line(4, 6, 8, 6, MAROON)
    ic.line(8, 6, 8, 10, MAROON)
    ic.line(8, 10, 12, 10, MAROON)
    ic.set(12, 10, RED)
    return _outline(ic)


def _wall_through():
    """Passwall: a hole through stonework, and you going through it.

    The courses are drawn as notches in the edges rather than lines across
    the whole block, because a line across a six-pixel block plus its black
    edge is a checkerboard, not masonry.
    """
    ic = _glyph()
    # Flat GRAY, not the MID_STONE dither pair the wall tile uses: at sixteen
    # pixels a pair samples the Bayer matrix at scattered points and comes out
    # as television snow. That is the first house rule at the top of the file.
    ic.rect(4, 0, 8, 16, GRAY)
    ic.rect(4, 0, 1, 16, SILVER)
    ic.rect(11, 0, 1, 16, darker(GRAY))
    for y in (3, 12):
        ic.set(4, y, darker(GRAY))
        ic.set(11, y, darker(GRAY))
    ic.oval(8, 8, 4, 3, BLACK)
    ic.rect(0, 7, 13, 3, AQUA)
    ic.tri([(11, 4), (15, 8), (11, 12)], AQUA)
    ic.rect(0, 7, 12, 1, WHITE)
    return _outline(ic)


def _sleep():
    ic = _glyph()
    for i, (x, y, w) in enumerate(((7, 2, 6), (5, 7, 5), (3, 11, 4))):
        ic.rect(x, y, w, 1, PURPLE)
        ic.rect(x, y + w // 2 + 1, w, 1, PURPLE)
        ic.line(x + w - 1, y, x, y + w // 2 + 1, PURPLE)
    return _outline(ic)


def _swap():
    """Reshape: one thing becomes another. Two arrows, head to tail."""
    ic = _glyph()
    ic.rect(2, 3, 8, 3, LIME)
    ic.tri([(9, 1), (14, 4), (9, 8)], LIME)
    ic.line(2, 3, 9, 3, WHITE)
    ic.rect(6, 10, 8, 3, GREEN)
    ic.tri([(7, 8), (2, 11), (7, 15)], GREEN)
    ic.line(7, 15, 12, 15, darker(GREEN))
    return _outline(ic)


def _coin_eye():
    ic = _eye(OLIVE)
    ic.oval(12, 12, 3, 3, YELLOW)
    ic.oval(12, 12, 1, 1, GOLD_DITHER if not is_pair(GOLD_DITHER) else OLIVE)
    return _outline(ic)


def _spike_eye():
    ic = _eye(RED)
    ic.tri([(8, 11), (11, 15), (5, 15)], GRAY)
    return _outline(ic)


SPELL_BUILDERS = {
    # attack
    "Spark":            lambda: _spark(),
    "Lightning":        lambda: _bolt(YELLOW, big=True),
    "Chain Lightning":  lambda: _forked(YELLOW),
    "Frost Shard":      lambda: _shard(AQUA),
    "Ice Storm":        lambda: _storm(ICE if not is_pair(ICE) else AQUA, WHITE),
    "Fire Bolt":        lambda: _bolt(RED, hot=YELLOW),
    "Fireball":         lambda: _ball(RED, YELLOW, ring=EMBER if not is_pair(EMBER) else RED),
    "Sunburst":         lambda: _burst(YELLOW, WHITE),
    # defense
    "Shield":           lambda: _ward(BLUE),
    "Stoneskin":        lambda: _ward(GRAY, trim=SILVER),
    "Sanctuary":        lambda: _ward(WHITE, trim=YELLOW, mark=BLUE),
    "Bulwark":          lambda: _ward(NAVY, trim=SILVER, mark=SILVER),
    "Ward Fire":        lambda: _ward_element(GRAY, RED),
    "Ward Frost":       lambda: _ward_element(GRAY, AQUA),
    "Ward Storm":       lambda: _ward_element(GRAY, YELLOW),
    # healing
    "Mend Wounds":      lambda: _cross(RED),
    "Greater Mending":  lambda: _cross(RED, doubled=True),
    "Circle of Mending": lambda: _cross(RED, doubled=True, ring=FUCHSIA),
    "Cure Affliction":  lambda: _flask(GREEN, LIME),
    "Restoration":      lambda: _cross(WHITE, hot=YELLOW, doubled=True, ring=YELLOW),
    # divination
    "Detect Life":      lambda: _eye(GREEN),
    "True Sight":       lambda: _eye(YELLOW, rays=WHITE),
    "Clairvoyance":     lambda: _eye(BLUE, rays=AQUA),
    "Revelation":       lambda: _eye(PURPLE, rays=FUCHSIA),
    "Detect Traps":     _spike_eye,
    "Treasure Sense":   _coin_eye,
    "Cartography":      _scroll_map,
    # movement
    "Blink":            lambda: _arrow(AQUA, dashed=True),
    "Farstep":          lambda: _arrow(BLUE),
    "Haste":            lambda: _arrow(LIME, doubled=True),
    "Recall":           lambda: _return_arrow(PURPLE),
    # miscellaneous
    "Lantern":          _lamp,
    "Featherweight":    _feather,
    "Passwall":         _wall_through,
    "Lull":             _sleep,
    "Reshape":          _swap,
}


def spell_icon(name):
    """A spell's glyph, falling back to a plain star for anything new."""
    builder = SPELL_BUILDERS.get(name)
    if builder is not None:
        return builder()
    return _burst(SILVER, WHITE)
