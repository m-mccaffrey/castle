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
