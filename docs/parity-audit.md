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
| Bags' bulk varies with contents, chests' is fixed | open |
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
| Character may be renamed mid-game | open |

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
| Quality prefixes: Broken, Ripped, Rusty, Normal, Enchanted, Cursed | partial |
| Class identify: one of a type identifies all of that type | done |
| Identify on use, identify on wield | done |
| The Sage identifies for a fee | partial - exists, not by drag |
| Junk store buys anything, 25 CP for cursed or worthless | done |
| Cursed items cannot be removed until uncursed | done |
| Cursed items may summon monsters or lower attributes | partial |
| Two-handed weapons conflict with shields | partial |
| Charged items recharge on a timer | done |
| Only worn slots and belt slots can be activated | done |
| Belts are containers sized in slots; a 10-slot belt is rare | done |
| Wand Quiver slot | open |

## The world

| Rule | Status |
|---|---|
| Temple service list and prices | done |
| Remove Curse never greyed, to avoid leaking identification | done |
| Shops are the inventory screen with a Store container | partial |
| Buy at 1.4x base, sell at 0.8x | done |
| Fountains and thrones: may help, harm, or do nothing | done |
| A known trap is less likely to spring, not immune | done |
| Searching and disarming may take several tries; disarming can spring it | done |
| Trap list: arrow, dart, blade, fire, acid, three gases, pit, deadfall, teleport, glyph | done |
| Trap door drops you a level; animation trap raises the dead | open |
| Levitation avoids gravity-operated traps | open |
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
| Earth elementals pass through rock and break doors | open |
| Manticores taunt during combat | open |
| Slime is sessile, drawn by vibration, and clings and grows | open |
| Dragon breath by colour: white cold, red fire, blue lightning, green poison | partial |
| Green dragon poison is delayed and curable | open |
| Goblin tribes may hire a larger monster as a guard | open |

## Interface

| Rule | Status |
|---|---|
| Map view of the explored level, with a Fast Map option | partial |
| Right click anything for a popup description, capped at 10 lines | partial |
| Drag the player icon to walk; aborts if attacked or trapped | open |
| Double-click yourself to take stairs | open |
| Crosshair targeting with a "Command Pending" message | partial |
| About 30 messages of scrollback | partial |
| Resizable windows | open |
| Vi keys and numeric keypad, shift to run | done |
| Run stops at objects, doors, and room-corridor boundaries | partial |
| Scroll Rooms Onto Screen option | open |
| Review Story | open |
| Sort Pack sorts by type and within type, unknowns last | partial |
| Name Object | done |

## Deliberate divergences

| Ours | Why |
|---|---|
| Death returns you to the temple; the original is permadeath with a Valhalla's Champions scroll | chosen so a child losing a character does not lose the afternoon |
| Multiplayer on a shared per-floor clock | the original is single player |
| Our own names, art, story, bestiary and item list | only the gameplay is being reproduced |
| 3-18 attribute range rather than 0-100 | ours; the armour ladder and hit chances are now the original's, and the attribute range is the remaining scale difference |
