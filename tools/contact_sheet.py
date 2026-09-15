"""Render every sprite in the game to one image, big enough to criticise.

Art you cannot see is art you cannot fix. This lays the whole set out on a
grid at whatever zoom you ask for, labelled, on a background that shows both
the silhouette and the transparent pixels - which is where most of the
problems in a 32x32 icon actually live.

    python3 tools/contact_sheet.py                 # everything, 4x
    python3 tools/contact_sheet.py --zoom 8 --only creatures
    python3 tools/contact_sheet.py --actual        # also at map size

Writes into docs/art/ so the sheets can be looked at side by side between
passes.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame                                                   # noqa: E402

from stormhold.ui import art                                    # noqa: E402
from stormhold.ui import widgets as W                           # noqa: E402

BACKDROP = (108, 108, 108)      # mid grey: shows both dark and light edges
GRID = (86, 86, 86)
LABEL = (18, 18, 18)


def collect(only=None):
    """Every sprite, grouped, as (group, name, Icon)."""
    out = []
    if only in (None, "terrain"):
        for name, fn in sorted(art.TERRAIN_BUILDERS.items()):
            out.append(("terrain", name, fn()))
    if only in (None, "creatures"):
        for name, fn in sorted(art.CREATURE_BUILDERS.items()):
            out.append(("creatures", name, fn()))
    if only in (None, "player"):
        for label, kit in (("plain", {}),
                           ("sword", {"weapon": "sword"}),
                           ("sword+shield", {"weapon": "sword", "shield": True}),
                           ("axe+helm", {"weapon": "axe", "helm": art.SILVER}),
                           ("bow", {"weapon": "bow"}),
                           ("staff+robe", {"weapon": "staff", "robe": True})):
            out.append(("player", label, art.adventurer(**kit)))
    if only in (None, "items"):
        module = sys.modules[art.__name__]
        for name in sorted(dir(module)):
            if name.startswith("icon_"):
                out.append(("items", name[5:], getattr(module, name)()))
    return out


def sheet(entries, zoom=4, columns=10, title=""):
    cell = art.ICON * zoom
    pad, label_h, head = 10, 16, 34 if title else 6
    rows = (len(entries) + columns - 1) // columns
    w = columns * (cell + pad) + pad
    h = head + rows * (cell + pad + label_h) + pad
    surf = pygame.Surface((w, h))
    surf.fill(BACKDROP)
    if title:
        W.text(surf, title, (pad, 8), 18, colour=LABEL, bold=True)
    for n, (_group, name, icon) in enumerate(entries):
        col, row = n % columns, n // columns
        x = pad + col * (cell + pad)
        y = head + row * (cell + pad + label_h)
        # A chequer under each cell, so transparent pixels read as transparent
        for j in range(0, cell, 8 * zoom // 4 or 8):
            for i in range(0, cell, 8 * zoom // 4 or 8):
                if ((i // (8 * zoom // 4 or 8)) + (j // (8 * zoom // 4 or 8))) % 2:
                    surf.fill(GRID, (x + i, y + j, 8 * zoom // 4 or 8,
                                     8 * zoom // 4 or 8))
        surf.blit(icon.surface(zoom), (x, y))
        pygame.draw.rect(surf, (40, 40, 40), (x, y, cell, cell), 1)
        W.text(surf, name, (x, y + cell + 2), 11, colour=LABEL)
    return surf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zoom", type=int, default=4)
    ap.add_argument("--columns", type=int, default=10)
    ap.add_argument("--only", default=None,
                    choices=("terrain", "creatures", "items", "player"))
    ap.add_argument("--out", default="docs/art")
    ap.add_argument("--tag", default="", help="suffix, e.g. --tag before")
    args = ap.parse_args()

    pygame.init()
    pygame.display.set_mode((64, 64))
    os.makedirs(args.out, exist_ok=True)

    groups = {}
    for group, name, icon in collect(args.only):
        groups.setdefault(group, []).append((group, name, icon))

    for group, entries in groups.items():
        cols = args.columns if group != "player" else 6
        img = sheet(entries, args.zoom, cols,
                    f"{group} - {len(entries)} sprites, {args.zoom}x")
        tag = f"-{args.tag}" if args.tag else ""
        path = os.path.join(args.out, f"{group}{tag}.png")
        pygame.image.save(img, path)
        print(f"{path}  {img.get_width()}x{img.get_height()}  "
              f"{len(entries)} sprites")


if __name__ == "__main__":
    main()
