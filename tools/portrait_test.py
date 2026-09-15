"""Put generated portrait art through the only test that matters: the map.

Art that looks good on a contact sheet at 4x is not the same as art that
works at 32 pixels with a dungeon floor under it. This slices a re-rendered
contact sheet back into its cells, brings each one down to map size three
different ways, and lays the results beside the pixel sprite it replaced -
then builds a room out of the winner so the comparison is a comparison of
the actual thing.

    python3 tools/portrait_test.py incoming/creatures-upscaled.png

The sheet is assumed to be tools/contact_sheet.py's own layout re-rendered
at some other size: eleven columns, a title bar, a label under each cell.
Its width tells us the scale, so any resolution works.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame                                                   # noqa: E402

from stormhold.ui import art                                    # noqa: E402
from stormhold.ui import widgets as W                           # noqa: E402
from stormhold.ui.palette import PALETTE                        # noqa: E402

# The geometry tools/contact_sheet.py produces at --zoom 4 --columns 11.
REF_ZOOM, REF_COLS, REF_PAD, REF_LABEL, REF_HEAD = 4, 11, 10, 16, 34
REF_CELL = art.ICON * REF_ZOOM
REF_WIDTH = REF_COLS * (REF_CELL + REF_PAD) + REF_PAD


def cells(sheet, names, cols=REF_COLS, scale=None):
    """Cut the sheet back into one surface per creature, whatever its size.

    A regenerated sheet is rarely the exact proportions of the one it came
    from - a generator will crop or pad a few pixels - so the scale can be
    given explicitly and `--probe` draws the grid it is about to cut on, to
    be looked at before any of the results are believed.
    """
    scale = scale or sheet.get_width() / float(REF_WIDTH)
    cell = REF_CELL * scale
    pad = REF_PAD * scale
    head = REF_HEAD * scale
    row_h = cell + pad + REF_LABEL * scale
    out = {}
    for n, name in enumerate(names):
        col, row = n % cols, n // cols
        x = pad + col * (cell + pad)
        y = head + row * row_h
        rect = pygame.Rect(int(x), int(y), int(cell), int(cell))
        rect = rect.clip(sheet.get_rect())
        if rect.width and rect.height:
            out[name] = sheet.subsurface(rect).copy()
    return out


def probe(sheet, names, cols, scale, out_path):
    """Draw the cutting grid onto the sheet so the alignment can be checked."""
    shot = sheet.copy()
    s = scale or sheet.get_width() / float(REF_WIDTH)
    cell, pad, head = REF_CELL * s, REF_PAD * s, REF_HEAD * s
    row_h = cell + pad + REF_LABEL * s
    for n, _name in enumerate(names):
        col, row = n % cols, n // cols
        r = pygame.Rect(int(pad + col * (cell + pad)),
                        int(head + row * row_h), int(cell), int(cell))
        pygame.draw.rect(shot, (255, 0, 255), r, 2)
    pygame.image.save(shot, out_path)
    return out_path


def to_tile(surf, how="smooth"):
    """Bring one portrait down to a 32x32 map tile."""
    if how == "nearest":
        return pygame.transform.scale(surf, (art.ICON, art.ICON))
    small = pygame.transform.smoothscale(surf, (art.ICON, art.ICON))
    if how == "smooth":
        return small
    # "quantised": force it into the sixteen colours the rest of the game uses
    out = pygame.Surface((art.ICON, art.ICON), pygame.SRCALPHA)
    for y in range(art.ICON):
        for x in range(art.ICON):
            r, g, b, a = small.get_at((x, y))
            best = min(PALETTE, key=lambda c: (c[0] - r) ** 2 +
                       (c[1] - g) ** 2 + (c[2] - b) ** 2)
            out.set_at((x, y), (*best, a))
    return out


def comparison(pieces, sheet_of_ours, names, out_path):
    """Four rows per creature: ours, then the three ways of shrinking theirs."""
    ways = ("nearest", "smooth", "quantised")
    zoom = 4
    cell = art.ICON * zoom
    cols = min(8, len(names))
    rows = (len(names) + cols - 1) // cols
    band = cell + 18
    surf = pygame.Surface((cols * (cell * 4 + 24) + 20,
                           rows * (band + 10) + 40))
    surf.fill((108, 108, 108))
    W.text(surf, "ours | nearest | smooth | quantised to 16 colours",
           (10, 10), 16, colour=(20, 20, 20), bold=True)
    for n, name in enumerate(names):
        if name not in pieces:
            continue
        col, row = n % cols, n // cols
        x0 = 10 + col * (cell * 4 + 24)
        y0 = 34 + row * (band + 10)
        ours = art.CREATURE_BUILDERS[name]().surface(zoom)
        surf.blit(ours, (x0, y0))
        for i, how in enumerate(ways):
            tile = to_tile(pieces[name], how)
            surf.blit(pygame.transform.scale(tile, (cell, cell)),
                      (x0 + (i + 1) * cell, y0))
        W.text(surf, name, (x0, y0 + cell + 2), 11, colour=(20, 20, 20))
    pygame.image.save(surf, out_path)
    return out_path


def room(pieces, how, out_path, zoom=2):
    """The same room tools/mapview draws, with their art standing in it."""
    T = art.ICON * zoom
    sheets = art.SpriteSheet(zoom).build()
    plan = ["WWWWWWWWWWWWWW", "W....D.......W", "W....f...r...W",
            "W..f.....f...W", "W....>...ww..W", "W.f......ww..W",
            "W...<....f...W", "WWWWWWWWWWWWWW"]
    key = {"W": "wall", ".": "floor", "f": "floor", "D": "door",
           ">": "stairs_down", "<": "stairs_up", "r": "rubble", "w": "water"}
    surf = pygame.Surface((len(plan[0]) * T, len(plan) * T + 30))
    surf.fill((60, 60, 60))
    for y, line in enumerate(plan):
        for x, ch in enumerate(line):
            surf.blit(sheets.terrain[key[ch]], (x * T, y * T))
    for cx, cy, name in ((2, 3, "goblin"), (8, 2, "dire_wolf"),
                         (11, 5, "skeleton"), (5, 6, "cave_rat"),
                         (9, 3, "ogre"), (3, 5, "storm_sorcerer")):
        if name in pieces:
            tile = to_tile(pieces[name], how)
            surf.blit(pygame.transform.scale(tile, (T, T)), (cx * T, cy * T))
    W.text(surf, f"their art, {how}, at map size",
           (6, surf.get_height() - 26), 14, colour=(230, 230, 230))
    pygame.image.save(surf, out_path)
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sheet", help="the re-rendered contact sheet")
    ap.add_argument("--out", default="docs/art/compare")
    ap.add_argument("--cols", type=int, default=REF_COLS)
    ap.add_argument("--scale", type=float, default=None,
                    help="override the sheet scale if the grid is off")
    args = ap.parse_args()

    pygame.init()
    pygame.display.set_mode((64, 64))
    os.makedirs(args.out, exist_ok=True)

    names = sorted(art.CREATURE_BUILDERS)
    sheet = pygame.image.load(args.sheet).convert_alpha()
    pieces = cells(sheet, names, args.cols, args.scale)
    print(f"sliced {len(pieces)} cells from {sheet.get_width()}x"
          f"{sheet.get_height()}")
    print(probe(sheet, names, args.cols, args.scale,
                os.path.join(args.out, "grid-check.png")))

    print(comparison(pieces, None, names,
                     os.path.join(args.out, "side-by-side.png")))
    for how in ("nearest", "smooth", "quantised"):
        print(room(pieces, how, os.path.join(args.out, f"room-{how}.png")))


if __name__ == "__main__":
    main()
