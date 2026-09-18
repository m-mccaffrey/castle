# Parity audit

Every gameplay claim found in the original's help files, its executable
strings, or by playing it, with what this remake does about it. The point of
the file is that nobody should have to notice a gap for me; if something is
missing it should be missing *on this list*, with a reason.

Status: **done** = implemented and tested. **partial** = present but not to the
original's rule. **open** = not built, with a task number. **ours** = a
deliberate divergence.

A warning about this file, earned the hard way. It is a list of claims, and a
claim is not a fact: "Vi keys and numeric keypad, shift to run" sat here
marked **done** while neither the vi keys nor shift-to-run had ever been
written. Two UI bugs were reported, marked fixed, and reported again, because
the tests that were supposed to cover them clicked in a way no player clicks.
So: prefer a test to a row in this table, and where a row cannot be tested,
say how it was checked. The tools that are worth more than a hundred lines of
this:

| tool | what it does |
|---|---|
| `tools/ui_audit.py` | opens every screen, presses every control, reports the dead ones |
| `tools/key_audit.py` | presses every key the original's help file documents and prints what ours did beside what the help says |
| `tools/interaction_audit.py` | drags things about and trades at every shop, checking the money that moves is the money that was named |
| `tools/rule_audit.py` | the arithmetic the help files state outright - the load curve, heal amounts, teleport ranges, shop prices |
| `tools/soak.py` | plays for hundreds of actions and checks after **every one** that the window and the game still agree about the pack, the doll, the vitals, the map and the prices |

The last one exists because of what the others kept missing. Every bug a
person has reported from play was a drift between two things that are meant
to agree, and every test we had asked one question about one function.

## Units, carrying and speed

| Rule | Status |
|---|---|
| Weight in grams, bulk in cubic centimetres | done |
| Carry rating = 2000 g per point of strength, linear | done |
| Movement speed = 100/(load/rated), capped 200%, immobile past 2x | done |
| Load affects movement only, never casting or combat | done |
| Status line shows overall speed then movement speed | done |
| Containers have both weight and bulk limits | done |
| Magical containers report a fixed weight, not their contents | done - and this row was wrong for a long time. The fixed figure was applied to the container and the contents were counted in full anyway, because what is "in the pack" is the character's inventory list and not the pack item. A Pack of Holding was heavier than the backpack it replaced. |
| Bags' bulk varies with contents, chests' is fixed | done - a Chest was added with a fixed bulk beside the sack that swells |
| Copper weighs 1 g and displaces 1 cc per coin | done |
| Four coinages: copper, silver 10, gold 100, platinum 1000 | done |
| Coins are not consolidated; deep finds come in better metal | done |
| Bank holds money weightlessly; Copper readout = purse + bank | partial - readout separates them |

## Character

| Rule | Status |
|---|---|
| Attributes on a 0-100 scale | ours - we use a 3-18 range, which the to-hit maths is tuned around |
| Chargen is a pool against per-attribute caps | done |
| Above-average attributes give bonuses; specialising beats spreading | partial |
| Strength: damage, carrying, and gates what armour you may wear | done |
| Intelligence: mana, and disarming traps | done |
| Constitution: hit points, and extra per level | done |
| Dexterity: armour value, to-hit, disarming traps | done |
| HP regenerate about 1 per minute | done |
| Mana regenerates about 1 per hour | done |
| Level gain restores mana fully | done |
| Undead drain experience and can cost a level, losing its gains | partial |
| Character may be renamed mid-game | done - the character sheet's name box used to be a drawn rectangle that looked like a field; it is one now, and the save follows the new name |

## Magic

| Rule | Status |
|---|---|
| Six spell classes, Cancel the default button | done |
| Healing = greater of a flat floor or a fraction of maximum | done |
| Resistances halve damage and stack multiplicatively | done |
| Slow stacks harmonically: 1/2, 1/3, 1/4 ... | done |
| Ball spells: full damage centre, half on the eight around | done |
| Elements: a creature resists its own, fears its opposite | done |
| Immunity: some creatures take nothing from an element | done |
| Casting time by class - 5s, 30s detection, 60s identify | done |
| Slow spells are interruptible | partial - flagged, not enforced |
| Overdrawing mana costs hit points | done |
| Mana cost falls as you outgrow a spell, rises above your level | done |
| Spells are bought as books, not only chosen at creation | partial |
| Ten spells on the menu and button bar, customisable | partial |
| Phase Door 5-10 squares; Teleport at least 10 | done |
| Clairvoyance maps 10x10 including secret doors and traps | done |
| Detect Traps certain within 10 squares, falling off beyond | done |
| Light: 3x3 in a corridor, the whole room in a room | done |
| Sleep Monster broken by attacking it | done |
| Transmogrify preserves the target's fraction of hit points | done |
| Rune of Return is two-way fast travel | done |
| Four spells are monster-only: Clone, Create Traps, Haste, Teleport Away | partial |

## Items

| Rule | Status |
|---|---|
| Item figures in grams and cc from the Object Directory | done |
| Armour value ladder 0-54 in sixes; shields a size x material grid | done |
| Weapon Class 0-12 sets damage; same class, same damage | ours - our weapons carry their own dice rather than falling into twelve classes. Recorded as a divergence rather than left open: adopting it would re-tune every weapon in the game against a table we cannot read. |
| Quality prefixes: Broken, Ripped, Rusty, Normal, Enchanted, Cursed | done - a battered thing is named for what it is made of: Ripped leather, Rusty steel, Broken wood |
| Class identify: one of a type identifies all of that type | done |
| Identify on use, identify on wield | done |
| The Sage identifies for a fee | done |
| Junk store buys anything, market price under 25 CP, else a flat 25, and her window says so | done - and this row was wrong for a while: the code paid a tenth of the value with the flat rate as a floor, on the grounds that the same 25 for a quarrel and a suit of plate was insulting. It is meant to be. Checked by `tools/rule_audit.py`. |
| Cursed items cannot be removed until uncursed | done |
| Cursed items may summon monsters or lower attributes | partial |
| Two-handed weapons conflict with shields | done - there were no two-handed weapons at all. Halberds, broad swords and bows need both hands: taking one up puts the shield in your pack and says so, and a shield is refused while you hold one |
| Charged items recharge on a timer | done |
| Only worn slots and belt slots can be activated | done |
| Free Hand: a doll slot beside the weapon, separate from Shield, for one unwearable thing | done - read off the running inventory window in `reference-run.md`. We had Shield and no Free Hand, so a character with a full pack and no belt could not drink a potion at all; buying and wearing a belt is not something the original ever requires just to use one. Drag anything unwearable onto it and it is reachable exactly like something on a belt. |
| Belts are containers sized in slots; a 10-slot belt is rare | done |
| The inventory window shows every container at once: body, belt, floor and pack | done - a running screenshot of the original shows all four on screen together, Floor included, with nothing to click through to see it. Ours drew the doll, the belt strip and the pack but never the floor: closing the window to look at what was underfoot, walking over it and pressing G, then reopening the window was the only way to reach it. The window now has a Floor panel between the doll and the pack, live off the same ground tile Get reads, with its own drag-and-drop: drag a floor item onto the body to wear it, into the pack to carry it, or onto the pack to drop something you are carrying. A dragged pile of coins deposits into the purse and vanishes rather than sitting in the pack as an object, the same as Get already did. A store's own window replaces this with its shelf instead, per the manual's own wording for how a store extends the inventory screen. |
| Packs come in more than one size | done - the original sells a Small, a Medium and a Large, each a real step up in capacity for more coin; we had only the small one, named "Backpack" rather than "Small Pack". Figures for all three are read off the measured shop captions in `reference-run.md`. |
| Wand Quiver slot | done - a slot on the doll that takes wands and nothing else, and a wand in it is within reach. A spent wand reads as a Dead Wand. |

## The world

| Rule | Status |
|---|---|
| Temple service list and prices | done |
| Remove Curse never greyed, to avoid leaking identification | done |
| Shops are the inventory screen with a Store container | done |
| Buy at 1.4x base, sell at 0.8x | done |
| Fountains and thrones: may help, harm, or do nothing | done |
| A known trap is less likely to spring, not immune | done |
| Searching and disarming may take several tries; disarming can spring it | done |
| Trap list: arrow, dart, blade, fire, acid, three gases, pit, deadfall, teleport, glyph | done |
| Trap door drops you a level; animation trap raises the dead | done |
| Levitation avoids gravity-operated traps | done |
| Difficulty alters monsters, traps, treasure and the XP curve | partial |

## Monsters

Resistance spells (Ward Fire, Ward Frost, Ward Storm) were added this pass -
the original has all three at spell level 3, and without them a breath weapon
is simply a death sentence.

| Rule | Status |
|---|---|
| Condition reported in six words, never a number | done |
| Packs: rats, wolves, dogs and goblins arrive in numbers | done |
| Fearless creatures never break off | done |
| Ranged attackers have finite ammunition and keep a reserve | done |
| Wights drain strength, constitution, dexterity | done |
| Wraiths drain mana, or intelligence if there is no mana | done |
| Vampires drain hit points that will not come back unaided | partial |
| Summoners gate in more of their own kind | partial |
| Thieves steal from the purse and vanish | done |
| Something passes through rock and breaks doors | done - our stone golems swim through stone at half speed and blast doors rather than opening them |
| Something taunts you during combat | done - the cutpurse talks while it robs you |
| Slime is sessile, drawn by vibration, and clings and grows | open |
| Dragon breath by colour: white cold, red fire, blue lightning, green poison | partial |
| A poison that is slow to take hold | done - the crypt ghoul's bite numbs first and burns later, which is what makes a cure worth carrying |
| A tribe may hire something larger as a guard | done - a goblin pack turns up with a shambler behind it about a quarter of the time |

| Get lifts everything on the floor, not one thing at a time | done - it took the top of the pile and left the rest |
| A pack, purse or belt you are not wearing is worn when picked up | done - it used to go into the pack you did not have |

| Menu bar: File, Character!, Inventory!, Map!, Spells, Activate, Verbs, Window, Help | partial - Activate was missing and is now built from what you have to hand; Window is not there, because our three panes do not resize |
| Activate menu lists what is to hand, so a potion needs no window | done |

## Interface

| Rule | Status |
|---|---|
| Map view of the explored level, with a Fast Map option | done |
| Right click anything for a popup description, capped at 10 lines | done - on the map it names what is there and gives a creature's condition in words rather than numbers; in the pack and the store it gives name, weight, bulk and what the thing does. There was no popup of any kind. |
| Drag the player icon to walk; aborts if attacked or trapped | open |
| Double-click yourself to take stairs | done |
| Crosshair targeting with a "Command Pending" message | done - the message now says Command Pending, and the crosshairs are drawn and driven from the keyboard |
| About 30 messages of scrollback with its own scrollbar | done - the wheel scrolls the log, the knob tracks the position, and a new line brings you back to the bottom |
| Resizable windows | open |
| The command letters: `<` `>` `o` `c` `s` `d` `m` `i` `r` `R` `x` `v` `f` `g` | done - all fourteen, checked against the table in CASTLE1.HLP by `tools/key_audit.py`, which presses each one and prints what ours did beside what the help says. Eleven of them were wrong: `s` and `d` walked (WASD shadowed Search and Disarm, so WASD is gone), `c` opened the character sheet, `f` fired an arrow, `<` picked up off the floor because the Get branch matched the comma before it looked at the shift, and `o m r R x v` did nothing at all. |
| Crosshairs driven by the movement keys, Return to confirm | done - `x` and any targeted spell put the crosshairs on you, the movement keys move them without moving you, Return takes the shot |
| `v` scrolls the dungeon window from the keyboard | done |
| The command letters: `<` `>` `o` `c` `s` `d` `m` `i` `r` `R` `x` `v` `f` `g` | done - all fourteen, checked against the table in CASTLE1.HLP by `tools/key_audit.py`, which presses each one and prints what ours did beside what the help says. Eleven of them were wrong: `s` and `d` walked (WASD shadowed Search and Disarm, so WASD is gone), `c` opened the character sheet, `f` fired an arrow, `<` picked up off the floor because the Get branch matched the comma before it looked at the shift, and `o m r R x v` did nothing at all. |
| Crosshairs driven by the movement keys, Return to confirm | done - `x` and any targeted spell put the crosshairs on you, the movement keys move them without moving you, Return takes the shot |
| `v` scrolls the dungeon window from the keyboard | done |
| Vi keys and numeric keypad, shift to run | done - and a caution: this row said "done" for months while neither the vi keys nor shift-to-run existed. Only the arrow keys, WASD and the keypad were wired up, so on a laptop there was no way to step diagonally at all. Now covered by a test. |
| Run stops at objects, doors, and room-corridor boundaries | partial |
| Scroll Rooms Onto Screen option | open |
| Review Story | open |
| Sort Pack sorts by type and within type, unknowns last | done |
| Name Object | done |

| No missile weapon for the player: the weapon table is name, damage, weight, price, and carries no bow | done - bows, crossbows, arrows and quarrels are gone, with the `shoot` verb and the key that fired it. Monsters still shoot, which the help is explicit about: jotuns hurl boulders and a manticore flings quills "with the accuracy and effect of a company of crossbowmen" |

| A heavy weapon is slow to swing | ours - the original's weapon table is name, damage, weight and price with no speed column, so this is our own rule. It was true of nothing once the crossbow came out; the heavy end of the rack now carries a penalty scaled to weight, from the dagger's 80% to the halberd's 140%, and the item label says which way it cuts. |

## Things we had that the original does not

| Ours | Status |
|---|---|
| Rations, and eating them for hit points | removed - the original has no food, hunger or eating of any kind; "Food" appears once in the executable as an object category and nowhere in the manual |
| Torches and lanterns, and a light radius that gear widened | removed - the original has no light sources at all. Sight is a flat radius and the Light spell is the only thing that changes what you can see. Pell's stocks what the original's general store stocked instead. |
| Dexterity raising overall speed | removed - the original reads 100% for every fresh character whatever their Dexterity |
| A weapon's speed applying to every action | removed - a heavy weapon is slow to swing, not slow to read or walk with |
| A Burden row on the character sheet | removed - the original's sheet has no such row; the speed law replaced the tiers |

## Found by playing it (this pass)

| Item | Status |
|---|---|
| A starting spell chosen from six at creation | done - was missing entirely |
| Four difficulty settings | done, with our own multipliers |
| Level 2 costs 20 experience | done - was 18 |
| "Normal"/"Enchanted" grade in gear names | done |
| Character sheet row order: Copper then Armor Value | done |
| The clock is the character's, not the floor's | done - it restarted at zero on every staircase |
| Status bar names the floor it is standing on | done - it said "Dungeon Level 1" while the log said "the Cellars" |
| Inventory weight shown in grams, not tenths of a pound | done |
| Weapon-aware, located, escalating combat messages | done - the verb follows the weapon, the blow lands somewhere, it escalates with the wound, kills and shield blocks have their own lines, and no damage number appears in the log |
| The message log actually scrolls | done - the scrollbar used to be decoration |
| The keep can be finished | checked - all 25 floors generate, both bosses are placed, and the last one ends the game |
| Named bosses take no article | done |
| Doors on every floor, opened by walking into them | done - the keep had none at all: the pass that places them ran before the pass that builds the walls it looks for, so Open, Close, the blocked-door message and the door-opening code in the monster AI were all dead |
| A closed door blocks sight, so a room is a sealed box | done, and now actually reachable |
| Disarming can fail, and can go off in your face | done - the thresholds were fixed while skill is worth about thirty points, so every attempt succeeded and two of the three outcomes could not happen to anybody. The numbers are ours; the three outcomes are the original's. |
| Shops refuse junk and say why | done - a trade takes what it deals in and answers "We don't buy those..." for the rest, and nobody buys a thing beaten past use. A sale that could not happen used to fail in silence. |
| Two people in one keep | tested - joining, chat, seeing each other, split floors, and an idle player not freezing the rest |
| Anything consumable could be used at all | **fixed** - nothing in the game ever put anything on a belt, and "objects in your pack cannot be activated" was enforced, so every potion, scroll and wand in the game answered "That is buried in your pack". Dragging onto the belt or quiver stows; dragging back out returns it; and using something up now actually uses it up wherever it was carried |
| The trap door and the animation trap | done - the last two of the original's fourteen. A trap door does no damage and drops you a floor; an animation trap raises the dead around you |
| Levitation avoids pits and trap doors | done, with a Potion of Levitation to get it |
| Saving, and carrying a character between evenings | done - autosave, File > Save, and a round trip test |
| Map! | done |

## Known rough edges in our own window

| Issue | Note |
|---|---|
| Overlay hit targets are computed during draw, not layout | Correct after the first frame, so a click in the ~33ms before a screen's first draw is swallowed. Harmless in practice; recorded rather than papered over. |

## Deliberate divergences

| Ours | Why |
|---|---|
| Death returns you to the temple; the original is permadeath with a Valhalla's Champions scroll | chosen so a child losing a character does not lose the afternoon |
| Multiplayer on a shared per-floor clock | the original is single player |
| Our own names, art, story, bestiary and item list | only the gameplay is being reproduced |
| 3-18 attribute range rather than 0-100 | ours; the armour ladder and hit chances are now the original's, and the attribute range is the remaining scale difference |
