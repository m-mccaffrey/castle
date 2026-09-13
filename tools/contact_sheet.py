"""Render every sprite to one PNG so the art can be reviewed at a glance."""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
from stormhold.ui import art
from stormhold.ui.palette import SILVER, BLACK, WHITE, GRAY, NAVY

pygame.init()
pygame.font.init()

SCALE = 2
CELL = art.ICON * SCALE
PAD = 26
COLS = 10
font = pygame.font.SysFont("dejavusansmono,monospace", 10)
head = pygame.font.SysFont("dejavusans,sans", 15, bold=True)


def section(title, entries):
    rows = (len(entries) + COLS - 1) // COLS
    return title, entries, rows


sheet = art.SpriteSheet(SCALE).build()
players = [(f"pc {i}", sheet.player(i, w, s, h, r)[0]) for i, (w, s, h, r) in enumerate(
    [("sword", True, True, False), ("bow", False, False, False), ("staff", False, False, True),
     ("axe", False, True, False), ("mace", True, False, False), (None, False, False, False)])]

sections = [
    section("Terrain", sorted(sheet.terrain.items())),
    section("Player characters (drawn from equipped kit)", players),
    section("Bestiary", sorted(sheet.creatures.items())),
    section("Items", sorted(sheet.items.items())),
]

total_rows = sum(r for _, _, r in sections)
height = sum(28 + r * (CELL + PAD) for _, _, r in sections) + 20
width = COLS * (CELL + 10) + 20

surf = pygame.Surface((width, height))
surf.fill(SILVER)

y = 10
for title, entries, rows in sections:
    label = head.render(title, True, NAVY)
    surf.blit(label, (10, y))
    pygame.draw.line(surf, GRAY, (10, y + 20), (width - 10, y + 20))
    y += 28
    for i, (name, img) in enumerate(entries):
        col = i % COLS
        row = i // COLS
        x = 10 + col * (CELL + 10)
        cy = y + row * (CELL + PAD)
        pygame.draw.rect(surf, (90, 90, 90), (x, cy, CELL, CELL), 1)
        surf.blit(img, (x, cy))
        text = font.render(name[:14], True, BLACK)
        surf.blit(text, (x, cy + CELL + 2))
    y += rows * (CELL + PAD)

out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/contact_sheet.png"
pygame.image.save(surf, out)
print(f"wrote {out}  ({width}x{height})")
print(f"terrain {len(sheet.terrain)}  creatures {len(sheet.creatures)}  items {len(sheet.items)}")
