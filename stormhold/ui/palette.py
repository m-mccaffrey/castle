"""The sixteen colours a Windows 3.1 icon was allowed to use, and the tricks
icon artists used to get more apparent shades out of them.

Everything drawn in Stormhold is restricted to this palette. Intermediate
tones come from ordered dithering, exactly as they did in 1993.
"""

# The standard VGA/EGA sixteen. Names are the ones Windows used.
BLACK   = (0,   0,   0)
MAROON  = (128, 0,   0)
GREEN   = (0,   128, 0)
OLIVE   = (128, 128, 0)
NAVY    = (0,   0,   128)
PURPLE  = (128, 0,   128)
TEAL    = (0,   128, 128)
SILVER  = (192, 192, 192)
GRAY    = (128, 128, 128)
RED     = (255, 0,   0)
LIME    = (0,   255, 0)
YELLOW  = (255, 255, 0)
BLUE    = (0,   0,   255)
FUCHSIA = (255, 0,   255)
AQUA    = (0,   255, 255)
WHITE   = (255, 255, 255)

PALETTE = [BLACK, MAROON, GREEN, OLIVE, NAVY, PURPLE, TEAL, SILVER,
           GRAY, RED, LIME, YELLOW, BLUE, FUCHSIA, AQUA, WHITE]

NAMES = {
    "black": BLACK, "maroon": MAROON, "green": GREEN, "olive": OLIVE,
    "navy": NAVY, "purple": PURPLE, "teal": TEAL, "silver": SILVER,
    "gray": GRAY, "grey": GRAY, "red": RED, "lime": LIME, "yellow": YELLOW,
    "blue": BLUE, "fuchsia": FUCHSIA, "aqua": AQUA, "white": WHITE,
}

TRANSPARENT = (0, 0, 0, 0)

# A 4x4 ordered (Bayer) matrix. Thresholding against this is what produces
# the regular checkerboards and 25%/75% screens seen all over era artwork.
BAYER4 = (
    (0,  8,  2,  10),
    (12, 4,  14, 6),
    (3,  11, 1,  9),
    (15, 7,  13, 5),
)


def dither_pick(x, y, c1, c2, ratio=0.5):
    """Which of two palette colours this pixel takes, for an ordered screen.

    ratio is how much of c2 shows through: 0.0 is pure c1, 1.0 is pure c2.
    """
    if ratio <= 0.0:
        return c1
    if ratio >= 1.0:
        return c2
    return c2 if (BAYER4[y & 3][x & 3] / 16.0) < ratio else c1


# Palette-legal pairs that read as a colour we do not actually have.
# These are the workhorses: there is no brown in the palette, so brown is
# maroon screened over olive, and so on.
BROWN        = (MAROON, OLIVE, 0.5)     # leather, wood, earth
DARK_BROWN   = (BLACK, MAROON, 0.5)
TAN          = (OLIVE, SILVER, 0.5)     # skin, parchment, sand
PALE_SKIN    = (SILVER, WHITE, 0.5)
DARK_STONE   = (BLACK, GRAY, 0.5)
MID_STONE    = (GRAY, SILVER, 0.5)
PALE_STONE   = (SILVER, WHITE, 0.35)
DARK_GREEN   = (BLACK, GREEN, 0.5)
MOSS         = (GREEN, OLIVE, 0.5)
DEEP_WATER   = (NAVY, BLUE, 0.5)
SHALLOW      = (BLUE, TEAL, 0.5)
RUST         = (MAROON, RED, 0.5)
EMBER        = (RED, YELLOW, 0.5)
BONE         = (SILVER, YELLOW, 0.25)
SHADOW_BLUE  = (BLACK, NAVY, 0.5)
BRUISE       = (PURPLE, MAROON, 0.5)
ICE          = (AQUA, WHITE, 0.5)
GOLD_DITHER  = (YELLOW, OLIVE, 0.5)
COPPER       = (MAROON, YELLOW, 0.35)
PLUM         = (PURPLE, NAVY, 0.5)
SICK_GREEN   = (GREEN, LIME, 0.35)


def is_pair(c):
    """True for a (c1, c2, ratio) dither pair rather than a flat colour."""
    return isinstance(c, tuple) and len(c) == 3 and isinstance(c[0], tuple)


def resolve(c, x, y):
    """Flatten either a plain colour or a dither pair to one RGB value."""
    if is_pair(c):
        return dither_pick(x, y, c[0], c[1], c[2])
    return c


def darker(c):
    """The palette's darker neighbour for a colour, for shading."""
    table = {
        WHITE: SILVER, SILVER: GRAY, GRAY: BLACK,
        RED: MAROON, MAROON: BLACK,
        LIME: GREEN, GREEN: BLACK,
        YELLOW: OLIVE, OLIVE: MAROON,
        BLUE: NAVY, NAVY: BLACK,
        FUCHSIA: PURPLE, PURPLE: MAROON,
        AQUA: TEAL, TEAL: NAVY,
        BLACK: BLACK,
    }
    if is_pair(c):
        return (darker(c[0]), darker(c[1]), c[2])
    return table.get(c, BLACK)


def lighter(c):
    """The palette's lighter neighbour for a colour, for highlights."""
    table = {
        BLACK: GRAY, GRAY: SILVER, SILVER: WHITE, WHITE: WHITE,
        MAROON: RED, RED: YELLOW,
        GREEN: LIME, LIME: WHITE,
        OLIVE: YELLOW, YELLOW: WHITE,
        NAVY: BLUE, BLUE: AQUA,
        PURPLE: FUCHSIA, FUCHSIA: WHITE,
        TEAL: AQUA, AQUA: WHITE,
    }
    if is_pair(c):
        return (lighter(c[0]), lighter(c[1]), c[2])
    return table.get(c, WHITE)
