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
# A note on ratios, learned the hard way by looking at the results at 11x.
# `ratio` is how much of the *second* colour shows. A pair at 0.5 is a full
# checkerboard, which is the noisiest screen there is and only works over a
# few pixels. For anything with area, one colour has to lead and the other
# has to speckle - so the dark tones below are written as "mostly the colour,
# with black through it" rather than as half and half. Half black over maroon
# is not a dark brown, it is a hole with red in it.
# Olive leads, maroon warms it. The other way round - which is how this
# started - makes every wooden and leather thing in the game red, because
# maroon is the stronger of the two and there is a lot of it about.
BROWN        = (OLIVE, MAROON, 0.4)     # leather, wood, earth
DARK_BROWN   = (OLIVE, MAROON, 0.7)    # dark warm leather, not dark red
TAN          = (OLIVE, SILVER, 0.5)     # skin, parchment, sand
PALE_SKIN    = (SILVER, WHITE, 0.5)
DARK_STONE   = (GRAY, BLACK, 0.4)
MID_STONE    = (GRAY, SILVER, 0.5)
PALE_STONE   = (SILVER, WHITE, 0.35)
DARK_GREEN   = (GREEN, BLACK, 0.35)
MOSS         = (GREEN, OLIVE, 0.5)
DEEP_WATER   = (NAVY, BLUE, 0.5)
SHALLOW      = (BLUE, TEAL, 0.5)
RUST         = (MAROON, RED, 0.5)
EMBER        = (RED, YELLOW, 0.5)
BONE         = (SILVER, YELLOW, 0.12)
SHADOW_BLUE  = (NAVY, BLACK, 0.4)
BRUISE       = (PURPLE, MAROON, 0.5)
ICE          = (AQUA, WHITE, 0.5)
GOLD_DITHER  = (YELLOW, OLIVE, 0.5)
COPPER       = (MAROON, YELLOW, 0.35)
# Boot leather. Dark enough to sit down at the outline rather than read as a
# pair of red shoes, which is what the old default gave every figure in the
# game at once.
BOOT_LEATHER = (MAROON, BLACK, 0.82)
# The lit edge of anything wooden - a haft, a shaft, a stave, the spine of a
# book. It was written out as (MAROON, YELLOW, 0.35) in fifteen separate
# places, and maroon next to yellow is too far apart to blend at this size:
# every wooden thing in the game came out looking like a candy cane. Olive
# and yellow are neighbours, so they read as one warm lit brown.
WOOD_LIT     = (OLIVE, YELLOW, 0.4)
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


def calm(c, strength=0.62):
    """The same colour, screened more gently, for filling a large area.

    A fifty per cent Bayer screen is the noisiest pattern there is: over a
    whole tunic it reads as static rather than as a shade. Icon artists of
    the period used it for a few pixels of transition and reached for a
    quarter screen when they had a whole area to fill. This is that - the
    dominant colour with the second one speckled through it.
    """
    if not is_pair(c):
        return c
    return (c[0], c[1], round(c[2] * strength, 3))


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
        one, two = darker(c[0]), darker(c[1])
        if one == two:
            # Both halves have bottomed out - (black, maroon) darkens to
            # (black, black), which is not a shade, it is a hole. Thin the
            # screen instead, so the pair keeps its identity and only gets
            # darker.
            return (c[0], c[1], round(c[2] * 0.45, 3))
        return (one, two, c[2])
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
        one, two = lighter(c[0]), lighter(c[1])
        if one == two:
            return (c[0], c[1], min(1.0, round(c[2] * 1.6 + 0.15, 3)))
        return (one, two, c[2])
    return table.get(c, WHITE)
