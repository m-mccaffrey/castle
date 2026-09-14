# Where the interface decisions came from

Stormhold is an original game, but it is deliberately modelled on the feel of
*Castle of the Winds* (Rick Saada, 1993). This file records which of our
interface decisions are **verified** against the original and which are our own
invention, so nobody later has to guess which is which.

The verified items were read from the resource directory of the original
executable: a 16-bit NE binary stores its dialog and menu templates as plain
structured data (control type, position, size, id, caption). No code was
decompiled, and no artwork, text, item names, monster names or other content
was taken. Our sprites, names, bestiary, spell list and prose are all our own.

## Verified: the verb set

The menu carries these commands, which is why our toolbar and key bindings
cover them:

| Verb | Notes |
| --- | --- |
| Get | Pick up what is underfoot. |
| Examine | Look at something without touching it. |
| Free Hand | Put your weapon away so a hand is free. |
| Search | Take a turn looking for traps and hidden doors. |
| Disarm Trap | Defuse a trap you have already found. |
| Rest Until Healed | Sit until health is restored or something interrupts. |
| Sleep Until Mana is Restored | The same, for mana. A separate command. |
| Open / Close | Doors, explicitly, as their own verbs. |
| Climb Up / Down Stairs | Bound to `<` and `>`. |

Top-level menus: File, Character!, Inventory!, Map!, Spells, Activate, Verbs,
Window, Help. The `!` items open their window immediately rather than dropping
a menu.

## Verified: the Cast Spell dialog

Six spell classes as a radio group on the left - Attack, Defense, Healing,
Movement, Divination, Miscellaneous - filtering a list on the right with
**Spell Name** and **Mana** columns. Buttons are Cast, Cancel and Help.

**Cancel is the default button**, not Cast. Pressing Enter backs out of the
dialog rather than firing a spell. We copy that: it is a deliberate guard
against casting something expensive by reflex.

## Verified: the character sheet

One window carries all of it:

    Character Level        Weight:  current (maximum)
    Character Experience   Bulk:    current (maximum)
    Next Level At          Speed:   base / current percent
    Hit Points             Copper
    Mana Points            Armor Value

Four attributes - Strength, Intelligence, Constitution, Dexterity - each drawn
as **two** adjacent bar gauges rather than a number. Buttons: OK, Cancel,
Attributes, Help. A separate Attributes window is a plain scrolling list.

## Verified: the options

Fast Mapping, Stop Running on Special Sites, Visual Effects, Scroll Rooms On
Screen On Entry, Show Button Bar, Keep Backup Save File, Save Levels To Disk.

Two of these imply mechanics rather than preferences: there is a **run** mode
that travels until something interesting appears, and the map **scrolls by
room** rather than keeping the character centred.

## Verified: the temple

The temple presents a priced list of services, not a heal button:

| Service | Price |
| --- | --- |
| Heal Minor / Medium / Major Wounds | 500 / 900 / 1400 CP |
| Heal | 2500 CP |
| Remove Curse | 2500 CP |
| Neutralize Poison | 1800 CP |
| Rune of Return | 1000 CP |
| Restore Strength / Intelligence / Constitution / Dexterity | 3000 CP each |
| Restore Drained Hit Points | 3000 CP |

Two mechanics follow from that list existing at all. **Attributes and maximum
hit points can be permanently drained** - nobody sells restoration otherwise -
and the **economy runs in hundreds and thousands of copper**, which is why a
single early find here is worth a few hundred rather than a few dozen.

## Verified: three more dialogs

- **Select An Object** - a list of your pack, for spells and scrolls that need
  a target.
- **Call Object** - a single text field, which is the rename command.
- **How many pieces?** - a number field with a scrollbar beside it, for
  splitting stacks and naming an amount.

## On the licence

The question of whether the original's artwork could be reused was settled by
the program itself. Its startup notice reads "Castle of the Winds is a
shareware product, it is not freeware", above "Copyright (c) 1989-1993 by
SaadaSoft" and "Published by Epic Megagames", and grants only the right to pass
the complete package on to friends.

Rick Saada later wrote on his homepage, "At this point, I give the game away
for free" - which waives the registration fee and makes it freeware, but is a
statement about price rather than a grant of rights. Nothing in either place
relinquishes copyright.

So: we match how the program behaves, which is not protected and is where all
the value is anyway. Every sprite, name and line of text here is our own.

## Verified from screenshots

- Layout: map across the top, message log bottom left, a five-line status
  panel bottom right - not a sidebar.
- Status lines: HP, Mana, Speed as `100% / n%`, Time as `Nd,HH:MM:SS`, and the
  name of where you are.
- Currency is copper.
- Explored-but-unseen floor is drawn stippled; unexplored is blank.
- Monsters with several attacks report them in one line rather than several.

## Ours, not theirs

Everything below is our own design and should not be assumed to match:

- The shared-clock multiplayer scheduler, the grace window, and the idle
  watchdog. The original is single-player; none of this has an equivalent.
- Death and temple resurrection rules.
- Trap kinds and their effects; the search and disarm success formulas.
- The specific encumbrance tier names and thresholds. (An earlier draft of this
  project used tier names borrowed from a different roguelike; they are ours
  now, and the numbers are tuned to our own item weights.)
- The paper-doll figure drawing, all sprites, the palette, and every item,
  monster, spell and place name.

## Measured from the running program

Since this file was first written, the original has been run under Wine and
measured directly - see `reference-run.md`. That supersedes guesswork for: the
carry weight law (2000 units per strength point, linear), bulk not being a
strength limit at all, the level-1 character sheet block, `Next Level At: 20`,
starting copper 1500, the chargen dialog and its four difficulty settings, the
six starting spells, the inventory window's line-art paper doll, and the
Options dialog. Items listed as ours below that are contradicted there have
been corrected in the code.
