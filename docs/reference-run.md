# Measurements taken from the original program

Everything on this page was read off Castle of the Winds 1.1A *while it was
running*, not remembered and not inferred. The original is a Windows 3.x NE
binary; it runs under Wine's 16-bit loader on a virtual X display, which makes
it a black-box measuring instrument. `tools/reference-harness.sh` sets that up.

This is observation of behaviour, the same thing you would do by hand with the
game open and a notebook. No code was decompiled and no assets were copied.

## How to reproduce

    dpkg --add-architecture i386
    apt-get update
    apt-get install -y libgd3:i386     # install first; the resolver gives up otherwise
    apt-get install -y wine wine32 xvfb imagemagick xdotool
    tools/reference-harness.sh /path/to/CASTLE1.EXE

Wine's 32-bit tree carries the real 16-bit modules (`krnl386.exe16`,
`user.exe16`, `gdi.exe16`), which is what makes this work at all. A 64-bit-only
Wine cannot load a Win16 program, so `wine32:i386` is not optional.

## The carry weight law

Measured by creating characters that differ only in strength and reading
`Weight: current (max)` off the character sheet.

| points spent on strength | max weight |
|---|---|
| +0  | 25000 |
| +5  | 27000 |
| +12 (the whole pool) | 49000 |

Exactly **2000 units per point of strength**, linear across the entire range
with no curve and no cap. The chargen pool is 12 points.

The unit is a hundredth of a pound - a small pack reads 1000, i.e. ten pounds.
Our own unit is a tenth of a pound, so the same law in our units is
`CARRY_PER_STRENGTH = 200` plus a constant offset.

What is *not* pinned down: the absolute strength number. The original never
displays attributes numerically - they are bars only, and the Attributes button
opens a list of special attributes and resistances, which is empty at level 1.
So the slope is exact and the intercept is ours to choose.

## Bulk is not a strength limit

`Bulk: 3300 (1000000)` on the character sheet, and the maximum stayed at
1000000 across every strength value tested. It never binds. The real bulk limit
is the pack: its window caption reads

    Small Pack Wt 1000 (12000) Bulk 1000 (50000)

so a small pack weighs 10lb, carries 120lb, and has a bulk capacity of 50000.
Our previous `BULK_PER_STRENGTH` model was wrong and is gone.

## The character sheet block

A fresh level-1 character on Intermediate:

    Character Level:        1
    Character Experience:   0
    Next Level At:         20
    Weight:      3300 (25000)
    Bulk:      3300 (1000000)
    Speed:        100% / 200%
    Hit Points:         10 (10)
    Mana Points:          5 (5)
    Copper:              1500
    Armor Value:            0

Level 2 costs **20** experience. Starting copper is **1500**. Speed's second
figure is 200%, a ceiling rather than an encumbrance readout.

The four attribute bars are drawn in two colours side by side - blue and green,
base against current - which is how drain shows up without any numbers.

## Character creation

Name field, then five bars: **Available**, Strength, Intelligence, Constitution,
Dexterity, each with up/down arrows. Spending from Available is the whole
mechanic. Leaving points unspent prompts *"Undistributed points available, exit
anyway?"* - it is allowed, just queried.

Gender is Male/Female with a character icon beside it, and a Custom Character
Icon checkbox with a filename field.

Difficulty is four ski-trail symbols: **Easy** (green circle), **Intermediate**
(blue square), **Difficult** (black diamond), **Experts Only** (yellow warning
triangle). Intermediate is the default.

Then a starting spell is chosen from a list of six:

    Heal Minor Wounds, Detect Objects, Light, Magic Arrow, Phase Door, Shield

## The inventory window

Not a grid. A **line-art figure of the character** stands in the middle, with
labelled slot boxes ranged around the edges and dotted leader lines running from
each box to the body part it belongs to. Slots observed:

    Armor  Neckwear  Overgarment  Helmet  Shield
    Bracers  Gauntlets  Right Ring  Left Ring  Belt  Boots
    (weapon slot, showing "Normal Dagger")  Free Hand

Containers are separate child windows with the weight/bulk caption described
above; **Floor** is one of them, so the ground is just another container.

Menus here: `Exit!  Character!  Sort Pack!  Name Object  Spell  Activate  Window`.
The exclamation marks are the original's own convention for a menu that acts
immediately instead of opening a submenu.

A character starts with a Normal Dagger and a Small Pack.

## Verbs menu

    Get
    Examine
    Free Hand
    Search
    Disarm Trap
    Rest Until Healed
    Sleep Until Mana is Restored
    Open
    Close
    < Climb Up Stairs
    > Climb Down Stairs

This matches the verb set extracted from the binary's menu resources exactly.

The button bar is `Get | Free Hand | Search | Disarm | Rest | Save`, followed by
ten spell slots.

## File menu and options

`New Game, Load..., Save, Save As..., Options..., Review Story..., Exit`

Options dialog:

    [ ] Use Fast Mapping              [x] Stop Running on Special Sites
    [x] Use Visual Effects            [x] Scroll Rooms On Screen On Entry
    [x] Show Button Bar               [ ] Keep Backup Save File
    [ ] Save Levels To Disk

"Stop Running on Special Sites" confirms run mode, and confirms that what stops
a run is a *site* rather than a monster.

## Still not measured

The numbers below remain ours, and are marked as such in `ux-reference.md`:

- absolute attribute values, so the carry intercept
- the rest of the experience curve past level 2
- armour value computation
- spell mana costs
- what the difficulty settings actually change
- trap mechanics
