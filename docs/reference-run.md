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


# Second session: playing it through

Character created, town explored, shop used, wilderness crossed, mine entered,
and a kobold met. Everything below was read off the running program.

## The screen

At 1024x768 the real layout appears, and it is the one this remake already
uses: **map filling the top, message log along the bottom left, status panel
bottom right**. The status panel reads:

    HP        10 (10)
    Mana        5 (5)
    Speed  100% / 200%
    Time   0d,00:00:52
    A Tiny Hamlet

The last row is the location, and underground it becomes `Mine Level 0`. The
message log keeps a scrollback with its own scrollbar, oldest at top.

## Time: one step is 2.5 game-seconds

Measured by stepping and reading the clock. From 75s: 77, 80, 82 - then a
prediction of 85, 87, 90, 92 for the next four steps, which is exactly what
happened. Checked again over a 16-move run (2:55 to 3:35, 40s = 16 x 2.5)
and a 24-move run. Display truncates, which is why the deltas read 2,3,2,2.

Our MOVE_COST is 100 ticks, so `TICKS_PER_SECOND = 40`. It was 10.

## Movement keys

Arrow keys move orthogonally. Diagonals are **vi keys**: `y u h j k l b n`,
exactly as in NetHack - the numeric keypad did nothing. Shift plus a direction
runs, and the run stops on reaching anything interesting, a monster included.
Clicking a map square does not walk there.

## The economy

Shop prices are one base value with two multipliers:

| item | buy | sell | implied base |
|---|---|---|---|
| Normal Club | 105 | 60 | 75 |
| Normal Short Sword | 1470 | 840 | 1050 |
| Normal Leather Helmet | 525 | - | 375 |
| Normal Suit of Leather Armor | 1050 | - | 750 |

**buy = 1.4 x base, sell = 0.8 x base.** The 4/7 ratio held on both items
tested, so there is no per-item haggling. Predicting the club would sell for
60 before selling it, and getting 60, is the check that this is the real rule.

Buying prompts *"It'll cost you 1470 C.P. for that. Take it?"* with Yes/No;
selling prompts *"I'll give you 840 C.P. for that. Take it?"*. Too little
money gives *"You don't have enough money!"*.

A character starts with **1500 copper** - so a short sword at 1470 is very
nearly the entire starting purse.

## Copper weighs, and so does everything else

Buying the short sword moved three numbers at once, and they reconcile exactly:

    copper   1500 -> 30      (spent 1470)
    pack     Wt 1000 -> 2000, Bulk 1000 -> 6000
    character Weight 3300 -> 2830, Bulk 3300 -> 6830

Total weight *fell* by 470 because 1470 coins left the purse and a 1000-weight
sword entered the pack. So **one copper piece is 1 weight and 1 bulk**, and
100 coins make a pound. Item figures measured the same way:

| item | weight | bulk |
|---|---|---|
| Normal Short Sword | 1000 | 5000 |
| Normal Club | 1500 | 3000 |
| Small Pack (empty) | 1000 | 1000 |

A small pack holds 12000 weight and 50000 bulk. Note the club is heavier and
far cheaper than the sword.

## Armour

A Normal Leather Helmet alone gives **Armor Value 3**.

## Shops are the inventory screen

Walking into a shop opens the *same* inventory window with one extra container
window titled `Store`. Buying and selling is dragging between windows - drag to
the pack to buy, drag to the Store to sell, and dragging onto a body slot buys
and equips in one move. There is no separate shop interface.

Container windows carry their contents in the caption:

    Small Pack Wt 2500 (12000) Bulk 4000 (50000)

`Floor` is one of these windows too, so the ground is just another container.
The `Window` menu offers Open Container, Arrange All and Auto Arrange - there
is no detail or list view, so item weights and prices are never shown as text.

## The full slot list

    Armor  Neckwear  Overgarment  Helmet  Shield
    Bracers  Gauntlets  Free Hand
    Right Ring  Left Ring  Belt  Boots
    (weapon)  Small Pack  Purse

Fifteen, which is what this remake already has.

## Spells

The Spell menu lists bound spells as `0: Heal Minor Wounds (1)` - slot number,
name, and **mana cost in parentheses**. Heal Minor Wounds costs 1. The menu
also has Spellbook... and Customize Spell Menu...

The Spellbook dialog is the Cast dialog: six class radio buttons (Attack,
Defense, Healing, Movement, Divination, Miscellaneous) against a two-column
`Spell Name | Mana` list, with Cast/Cancel/Help.

## The temple

Walking into the temple opens **Temple of Odin**, a radio list with prices:

    Heal Minor Wounds            500 CP
    Heal Medium Wounds           900 CP
    Heal Major Wounds           1400 CP
    Heal                        2500 CP
    Remove Curse                2500 CP
    Neutralize Poison           1800 CP
    Rune of Return              1000 CP
    Restore Strength            3000 CP
    Restore Intelligence        3000 CP
    Restore Constitution        3000 CP
    Restore Dexterity           3000 CP
    Restore Drained Hit Points  3000 CP

This matches the prices extracted from the binary earlier, and matches what
this remake already charges. Services you have no need of are **greyed out** -
at full health only Remove Curse and Rune of Return were selectable. Buttons
are Cast and Exit.

## The world outside town

Town is "A Tiny Hamlet"; leaving by the north gate reaches "A Rough Trail", an
overworld of roads and highways with mountains along the north edge. Entering
the mountains reaches the mine, and the status line switches to `Mine Level 0`.

`Map!` opens a full-screen zoomed-out view of the current region with a box
around the part you are looking at, and only an `Exit!` menu.

Story arrives as a **modal box with a Done button**, fired by walking onto the
place it belongs to - the burned farm delivers the whole opening in one.

## Combat, and death

Attacking is walking into the monster. Messages name the weapon's action and
give no numbers:

    The Kobold missed you!
    The Kobold hits you!
    You slash at air as the Kobold dances back.

A level-1 character on Intermediate - 10 hit points, Armor Value 3, a dagger -
was killed by a single kobold. That is the difficulty calibration point: the
first monster you meet can kill you.

Death is **permanent**, and ends on a scroll headed **Valhalla's Champions**:

    Probe,  Experience : 0 on Intermediate
    Killed by a Kobold after 0 days, at 00:09

A persistent high-score list of dead characters, recording name, experience,
difficulty, what killed you, and how long you lasted. Buttons Done and Reset.
The death message in the log is *"Another one bites the dust..."*.

This remake deliberately diverges here: you chose temple resurrection so that
a child losing a character does not lose the afternoon. Recording the original
rule so the divergence stays a decision rather than a mistake.

## Corrected in the code this session

- `TICKS_PER_SECOND` 10 -> 40, so a step is 2.5 game-seconds
- shop markup 1.0 -> 1.4 and sell rate 0.4 -> 0.8
- starting copper 400 -> 1500
- "You cannot afford that." -> "You don't have enough money!"

## Still ours, still unmeasured

- the experience curve past level 2 (the character died at 0 XP)
- what the four difficulty settings actually change
- monster statistics beyond "a kobold kills a level-1 character"
- trap mechanics
- spell costs other than Heal Minor Wounds at 1
