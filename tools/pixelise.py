"""Turn generated art into sprites in this game's own format.

The upscaled portraits are good designs in the wrong medium: they arrive as
opaque 85-pixel JPEG cells in thousands of colours, and what the game needs
is 32 pixels, sixteen colours, a hard black outline and real transparency.

This does the conversion rather than the argument. Four steps, each of which
matters:

  1. Flood the painted background away from the border. It cannot simply
     match grey - the wolf, the golem, the skeleton and the revenant are all
     grey - so it takes only what is connected to the edge and only what is
     achromatic, which leaves grey creatures alone because they are islands.
  2. Average down to 32x32, ignoring transparent pixels in the average so
     edges do not bleed towards the old background.
  3. Quantise to the sixteen VGA colours through the same 4x4 Bayer matrix
     the rest of the art uses. Nearest-colour on its own bands badly - that
     is what shattered the first attempt - and ordered dithering is the
     house style anyway.
  4. Lay the black outline on, because every object in this game has one.

The result is written out as Python source, not as image files: a palette
index per pixel, so the sprites stay in the repository as code, keep working
with Icon's scaling and flipping, and never need a binary asset loaded from
disk.

    python3 tools/pixelise.py stormhold/up-res.jpg --out /tmp/preview
    python3 tools/pixelise.py stormhold/up-res.jpg --emit stormhold/ui/drawn.py
"""

import argparse
import os
import sys
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame                                                   # noqa: E402

from stormhold.ui import art                                    # noqa: E402
from stormhold.ui import widgets as W                           # noqa: E402
from stormhold.ui.palette import PALETTE, BAYER4, BLACK         # noqa: E402
from tools.portrait_test import cells                           # noqa: E402

CHROMA = 26        # how far r, g and b may differ before it counts as colour
BG_LO, BG_HI = 40, 160    # the luminance band the backdrop and chequer live in


def strip_background(cell):
    """Flood the painted backdrop away, starting from the border."""
    w, h = cell.get_size()
    out = cell.copy().convert_alpha()
    seen = [[False] * w for _ in range(h)]
    q = deque()

    def background(px):
        r, g, b = px[0], px[1], px[2]
        if max(r, g, b) - min(r, g, b) > CHROMA:
            return False                      # it has colour in it
        return BG_LO <= (r + g + b) / 3 <= BG_HI

    for x in range(w):
        for y in (0, h - 1):
            q.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            q.append((x, y))
    while q:
        x, y = q.popleft()
        if not (0 <= x < w and 0 <= y < h) or seen[y][x]:
            continue
        seen[y][x] = True
        if not background(cell.get_at((x, y))):
            continue
        out.set_at((x, y), (0, 0, 0, 0))
        q.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    return out


def shrink(cell, size=art.ICON):
    """Average down to icon size, weighting by alpha so edges stay clean."""
    w, h = cell.get_size()
    out = pygame.Surface((size, size), pygame.SRCALPHA)
    for j in range(size):
        for i in range(size):
            x0, x1 = i * w // size, max(i * w // size + 1, (i + 1) * w // size)
            y0, y1 = j * h // size, max(j * h // size + 1, (j + 1) * h // size)
            r = g = b = a = n = 0
            for y in range(y0, y1):
                for x in range(x0, x1):
                    px = cell.get_at((x, y))
                    a += px[3]
                    n += 1
                    if px[3] > 128:
                        r += px[0]; g += px[1]; b += px[2]
            solid = sum(1 for y in range(y0, y1) for x in range(x0, x1)
                        if cell.get_at((x, y))[3] > 128)
            if solid and a / max(1, n) > 110:
                out.set_at((i, j), (r // solid, g // solid, b // solid, 255))
            else:
                out.set_at((i, j), (0, 0, 0, 0))
    return out


def boost(small, saturation=1.55, contrast=1.35, lift=1.45):
    """Push colour and contrast up before the palette crushes both.

    Averaging an 85-pixel painting down to 32 pulls everything towards the
    middle, and then sixteen colours pull it further. Without this the whole
    set converts to a muddy brown-black: the step is not a stylistic choice,
    it is putting back what the two reductions take out.
    """
    size = small.get_width()
    out = pygame.Surface((size, size), pygame.SRCALPHA)
    for y in range(size):
        for x in range(size):
            px = small.get_at((x, y))
            if px[3] < 128:
                out.set_at((x, y), (0, 0, 0, 0))
                continue
            r, g, b = px[0], px[1], px[2]
            grey = (r + g + b) / 3.0
            r, g, b = (grey + (c - grey) * saturation for c in (r, g, b))
            r, g, b = (128 + (c - 128) * contrast for c in (r, g, b))
            # Lift the shadows. Between black and mid-grey the sixteen
            # colours have nothing at all, so every dark tone in the source
            # snaps to pure black and dark creatures convert to silhouettes.
            r, g, b = (255.0 * (max(0.0, min(1.0, c / 255.0)) ** (1.0 / lift))
                       for c in (r, g, b))
            out.set_at((x, y), (min(255, max(0, int(r))),
                                min(255, max(0, int(g))),
                                min(255, max(0, int(b))), 255))
    return out


def quantise(small, spread=42):
    """Into the sixteen colours, through the Bayer screen."""
    size = small.get_width()
    out = pygame.Surface((size, size), pygame.SRCALPHA)
    for y in range(size):
        for x in range(size):
            px = small.get_at((x, y))
            if px[3] < 128:
                out.set_at((x, y), (0, 0, 0, 0))
                continue
            bump = (BAYER4[y & 3][x & 3] / 16.0 - 0.5) * spread
            want = tuple(min(255, max(0, c + bump)) for c in px[:3])
            best = min(PALETTE, key=lambda c: (c[0] - want[0]) ** 2 +
                       (c[1] - want[1]) ** 2 + (c[2] - want[2]) ** 2)
            out.set_at((x, y), (*best, 255))
    return out


def to_icon(surf):
    """A pygame surface back into an Icon, so outline() and friends apply."""
    ic = art.Icon()
    for y in range(art.ICON):
        for x in range(art.ICON):
            px = surf.get_at((x, y))
            if px[3] > 128:
                ic.px[y][x] = (px[0], px[1], px[2])
    return ic


def convert(cell, spread=42, outline=True, saturation=1.55, contrast=1.35,
            lift=1.45):
    small = boost(shrink(strip_background(cell)), saturation, contrast, lift)
    ic = to_icon(quantise(small, spread))
    return ic.outline() if outline else ic


def emit(icons, path):
    """Write the sprites out as Python source: one palette index per pixel."""
    order = [BLACK] + [c for c in PALETTE if c != BLACK]
    index = {c: "0123456789abcdef"[i] for i, c in enumerate(order)}
    lines = ['"""Creature sprites, converted from reference art by',
             'tools/pixelise.py.',
             '',
             'One character per pixel: a hex index into the sixteen VGA',
             'colours, or "." for transparent. Kept as source rather than as',
             'image files so the game still loads nothing from disk.',
             '"""',
             '',
             'from .palette import PALETTE, BLACK',
             '',
             'ORDER = [BLACK] + [c for c in PALETTE if c != BLACK]',
             '',
             'SPRITES = {']
    for name, ic in sorted(icons.items()):
        rows = []
        for y in range(art.ICON):
            row = "".join(index.get(ic.px[y][x], ".") if ic.px[y][x] else "."
                          for x in range(art.ICON))
            rows.append(f'        "{row}",')
        lines.append(f'    "{name}": (')
        lines += rows
        lines.append("    ),")
    lines += ["}", ""]
    open(path, "w").write("\n".join(lines))
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sheet")
    ap.add_argument("--out", default="docs/art/compare")
    ap.add_argument("--emit", default=None)
    ap.add_argument("--spread", type=int, default=42)
    ap.add_argument("--saturation", type=float, default=1.55)
    ap.add_argument("--contrast", type=float, default=1.35)
    ap.add_argument("--lift", type=float, default=1.45)
    args = ap.parse_args()

    pygame.init()
    pygame.display.set_mode((64, 64))
    os.makedirs(args.out, exist_ok=True)

    names = sorted(art.CREATURE_BUILDERS)
    sheet = pygame.image.load(args.sheet).convert_alpha()
    pieces = cells(sheet, names)
    icons = {n: convert(pieces[n], args.spread, True, args.saturation,
                        args.contrast, args.lift)
             for n in names if n in pieces}

    zoom = 4
    cell = art.ICON * zoom
    cols = 8
    rows = (len(icons) + cols - 1) // cols
    surf = pygame.Surface((cols * (cell * 2 + 16) + 20, rows * (cell + 26) + 40))
    surf.fill((108, 108, 108))
    W.text(surf, f"ours | converted (spread {args.spread})", (10, 10), 16,
           colour=(20, 20, 20), bold=True)
    for n, name in enumerate(sorted(icons)):
        col, row = n % cols, n // cols
        x0, y0 = 10 + col * (cell * 2 + 16), 34 + row * (cell + 26)
        surf.blit(art.CREATURE_BUILDERS[name]().surface(zoom), (x0, y0))
        surf.blit(icons[name].surface(zoom), (x0 + cell, y0))
        W.text(surf, name, (x0, y0 + cell + 2), 11, colour=(20, 20, 20))
    path = os.path.join(args.out,
                        f"converted-s{args.spread}-l{args.lift}.png")
    pygame.image.save(surf, path)
    print(path)
    if args.emit:
        print(emit(icons, args.emit))


if __name__ == "__main__":
    main()
