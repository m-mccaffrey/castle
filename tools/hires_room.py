"""What the game looks like if we up-res the whole thing.

Keeps the reference art at its own resolution with the painted backdrop
flooded away, draws the tiles and items from our own code at the same
multiple, and puts them in a room together - because the question is not
whether the portraits are nice, it is whether crisp doubled pixel-art
flagstones and a smooth painted troll can share a screen.

    python3 tools/hires_room.py stormhold/up-res.jpg --tile 64
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame                                                   # noqa: E402

from stormhold.ui import art                                    # noqa: E402
from stormhold.ui import widgets as W                           # noqa: E402
from tools.portrait_test import cells                           # noqa: E402
from tools.pixelise import strip_background                     # noqa: E402

PLAN = ["WWWWWWWWWWWWWW", "W....D.......W", "W....f...r...W",
        "W..f.....f...W", "W....>...ww..W", "W.f......ww..W",
        "W...<....f...W", "WWWWWWWWWWWWWW"]
KEY = {"W": "wall", ".": "floor", "f": "floor", "D": "door",
       ">": "stairs_down", "<": "stairs_up", "r": "rubble", "w": "water"}
WHO = ((2, 3, "goblin"), (8, 2, "dire_wolf"), (11, 5, "skeleton"),
       (5, 6, "cave_rat"), (9, 3, "ogre"), (3, 5, "storm_sorcerer"),
       (6, 1, "moss_troll"), (11, 2, "npc_sage"))
LOOT = ((3, 1, "gold"), (6, 4, "potion_red"), (9, 6, "longsword"),
        (4, 5, "chest"))


def room(pieces, tile, terrain_smooth=False, label=""):
    scale = max(1, tile // art.ICON)
    sheets = art.SpriteSheet(scale).build()
    surf = pygame.Surface((len(PLAN[0]) * tile, len(PLAN) * tile + 30))
    surf.fill((60, 60, 60))

    def place(img, x, y):
        if img.get_width() != tile:
            img = (pygame.transform.smoothscale(img, (tile, tile))
                   if terrain_smooth
                   else pygame.transform.scale(img, (tile, tile)))
        surf.blit(img, (x, y))

    for j, row in enumerate(PLAN):
        for i, ch in enumerate(row):
            place(sheets.terrain[KEY[ch]], i * tile, j * tile)
    for i, j, name in LOOT:
        place(sheets.items[name], i * tile, j * tile)
    for i, j, name in WHO:
        cell = pieces.get(name)
        if cell is None:
            continue
        # Smooth here, always: this is a painting, and nearest-neighbour on a
        # painting is the worst of both worlds.
        img = pygame.transform.smoothscale(cell, (tile, tile))
        surf.blit(img, (i * tile, j * tile))
    W.text(surf, label, (6, surf.get_height() - 26), 15, colour=(235, 235, 235))
    return surf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sheet")
    ap.add_argument("--tile", type=int, default=64)
    ap.add_argument("--out", default="docs/art/compare")
    args = ap.parse_args()

    pygame.init()
    pygame.display.set_mode((64, 64))
    os.makedirs(args.out, exist_ok=True)

    names = sorted(art.CREATURE_BUILDERS)
    sheet = pygame.image.load(args.sheet).convert_alpha()
    pieces = {n: strip_background(c) for n, c in cells(sheet, names).items()}
    print(f"alpha recovered on {len(pieces)} cells at "
          f"{pieces['goblin'].get_width()}px")

    panes = [room(pieces, args.tile, False,
                  f"{args.tile}px tiles - our art doubled, crisp"),
             room(pieces, args.tile, True,
                  f"{args.tile}px tiles - our art doubled and smoothed")]
    out = pygame.Surface((panes[0].get_width(),
                          sum(p.get_height() for p in panes) + 8))
    out.fill((40, 40, 40))
    y = 0
    for p in panes:
        out.blit(p, (0, y))
        y += p.get_height() + 8
    path = os.path.join(args.out, f"hires-{args.tile}.png")
    pygame.image.save(out, path)
    print(path, out.get_size())


if __name__ == "__main__":
    main()
