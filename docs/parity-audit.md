# Parity audit

Every gameplay claim found in the original's help files, its executable
strings, or by playing it, with what this remake does about it. The point of
the file is that nobody should have to notice a gap for me; if something is
missing it should be missing *on this list*, with a reason.

Status: **done** = implemented and tested. **partial** = present but not to the
original's rule. **open** = not built, with a task number. **ours** = a
deliberate divergence.

## Units, carrying and speed

| Rule | Status |
|---|---|
| Weight in grams, bulk in cubic centimetres | done |
| Carry rating = 2000 g per point of strength, linear | done |
| Movement speed = 100/(load/rated), capped 200%, immobile past 2x | done |
| Load affects movement only, never casting or combat | done |
| Status line shows overall speed then movement speed | done |
| Containers have both weight and bulk limits | done |
| Magical containers report a fixed weight, not their contents | done |
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
| Clairvoyance maps 10x10 including secret doors and traps | open |
| Detect Traps certain within 10 squares, falling off beyond | open |
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
| Weapon Class 0-12 sets damage; same class, same damage | open |
| Quality prefixes: Broken, Ripped, Rusty, Normal, Enchanted, Cursed | done - a battered thing is named for what it is made of: Ripped leather, Rusty steel, Broken wood |
| Class identify: one of a type identifies all of that type | done |
| Identify on use, identify on wield | done |
| The Sage identifies for a fee | done |
| Junk store buys anything, 25 CP for cursed or worthless | done |
| Cursed items cannot be removed until uncursed | done |
| Cursed items may summon monsters or lower attributes | partial |
| Two-handed weapons conflict with shields | done - there were no two-handed weapons at all. Halberds, broad swords and bows need both hands: taking one up puts the shield in your pack and says so, and a shield is refused while you hold one |
| Charged items recharge on a timer | done |
| Only worn slots and belt slots can be activated | done |
| Belts are containers sized in slots; a 10-slot belt is rare | done |
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

## Interface

| Rule | Status |
|---|---|
| Map view of the explored level, with a Fast Map option | done |
| Right click anything for a popup description, capped at 10 lines | done - on the map it names what is there and gives a creature's condition in words rather than numbers; in the pack and the store it gives name, weight, bulk and what the thing does. There was no popup of any kind. |
| Drag the player icon to walk; aborts if attacked or trapped | open |
| Double-click yourself to take stairs | done |
| Crosshair targeting with a "Command Pending" message | partial |
| About 30 messages of scrollback with its own scrollbar | done - the wheel scrolls the log, the knob tracks the position, and a new line brings you back to the bottom |
| Resizable windows | open |
| Vi keys and numeric keypad, shift to run | done |
| Run stops at objects, doors, and room-corridor boundaries | partial |
| Scroll Rooms Onto Screen option | open |
| Review Story | open |
| Sort Pack sorts by type and within type, unknowns last | done |
| Name Object | done |

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
