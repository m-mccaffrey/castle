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
| Slow spells are interruptible | **fixed** - SPELLS already carried the `interruptible` flag (everything 30 seconds or more: Detect Life, Cartography, Revelation, Clairvoyance, Detect Traps, Treasure Sense, True Sight), set and never once read. Casting one of these now spends the mana and the busy period up front but defers the actual effect - the resolution that used to happen in the same call it started in - to the moment that busy period runs out, the way `_act_rest`'s own open-ended continuation already worked. A blow landing before then (combat.apply_damage) cancels it: the mana stays spent, the spell is lost, and the caster is free to act again at once rather than standing frozen for whatever was left of the original casting time. On an empty floor nothing can interrupt it anyway, so it still resolves in the same turn it was cast, same as resting does when nothing is hunting you. |
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
| A gear item's *name* never carries the enchantment number, only the word | **fixed** - flagged directly: "match the enchantment tiers and system... currently the system is very vague and it's not clear what it does." The manual is explicit and was not being followed: "The object's name, weight and bulk will always be given. If the object has been identified, then all the properties of the object will be listed, and the name will also indicate if the object is Enchanted or Cursed." Not a number - the reference run's own general-store listing bears this out too, "Enchanted Cape of Protection", never "+3 Cape of Protection". Ours showed a raw `+2 Long Sword` once identified, which read exactly as vague as reported: a bare number with nothing beside it to say whether it was to-hit, damage, armour, or all three. The name now stays a grade word (Normal/Enchanted/`Ripped, Rusty, Broken`/Cursed) at every identification state; the number moved to the popup description, where it belongs. Broadened while there: grading used to require a damage die or an armour value, so a Ring of Might could never read "Enchanted" even once identified - now anything wearable grades, rings and amulets included. |
| An identified property reads as three parts: what to do, what it does, how long it lasts | **fixed** - same report. The manual gives the template and two exact examples: `"Each property description has three parts: 1. What you have to do to the object for the property to apply ... 2. What it does ... 3. How long it lasts."` - `"An 'Amulet of Resist Fire', for example, will say 'When wielded, makes the character more resistant to fire, until removed'."` Ours read as a flat, comma-joined fragment list - `"+2 enchantment"` told you a number and nothing about what it touched. `Item.describe()` now writes one sentence per magical property in that exact template: an enchanted weapon's `"When wielded, adds +2 to your chance to hit and to damage, until removed."`, enchanted armour's `"...adds +2 to your Armor Value..."`, a ring's stat bonus, an amulet's armour value, and hp/mana bonuses all follow suit. Physical facts a mundane item already shows on sight - its damage die, a suit of armour's own armour value, weight, bulk - stay outside this: they are not something identification reveals. |
| Armour Value and ring/amulet stat bonuses land on named steps, not a rolled number | **fixed, and corrected mid-flight.** First pass (wrong): flagged directly - "Vote [note] has tiers, enchanted, strongly, very strongly enchanted" - and checked against `CASTLE1.EXE`'s own string table, which has no `Strongly Enchanted` name string, only vocabulary (`strongly `/`greatly `/`very `) loose in the table with no attachment shown; that pass guessed it modified the property sentence by a numeric band (3+, 5+) of our own invention. The user then supplied the actual RPGClassics shrine pages (`shrines.rpgclassics.com/pc/castle1/armor.shtml` and `rings.shtml`), which this environment's egress proxy blocks fetching directly - and those give the real, exact mechanic, word for word, on two independent pages that agree: `"Increases Armor Value: Normal Armor Value + 5"`, `"Strongly Increases Armor Value: ... + 10"`, `"Very Strongly Increases Armor Value: ... + 20"`, and the mirrored `Decreases`/-5/-10/-20 for a curse - and the identical three-step table again for a ring's stat bonus. Not a magnitude adverb on a number - the number is never shown at all; the tier word *is* the whole sentence. The shrine's weapons page draws the contrast itself: a weapon's hit/damage bonus is "generated randomly", no named steps - confirming that part of the design should stay a plain rolled number, unchanged. Rebuilt on the real mechanic: `roll_tier()`/`tier_verb()` replace the invented magnitude-adverb pass for every non-weapon wearable (armour, shields, helms, gauntlets, boots, leggings, cloaks, and a ring/amulet's own extra roll); `roll_ring_bonus()` gives Ring of Might and its three siblings a genuine +5/+10/+20 tier instead of the fixed `+2` they carried before (a real balance change, not just wording - their base data now names only the stat, `bonus_stat="strength"`, and `Player.stat()` reads the tier off `item.enchant`). The exact odds between the three tiers, and how they shift with depth, are still not sourced anywhere we have; that curve is flagged in `items.py`'s `_pick_tier()` as our own placement of the game's real, confirmed step sizes. |
| Enchanted gear looks different on the shelf, not just in the tooltip | **fixed** - same report: "The enchanted items also have a glowing modification to the icons." Identified, genuinely-beneficial gear (`Item.is_glowing()` - the same condition as the "Enchanted " name prefix, so cursed and merely-normal items are unaffected) now draws with a soft gold halo behind the icon, everywhere an item icon is drawn: pack, paper doll, belt, ground, map, shop stock, and the drag ghost. This is a UI legibility addition, not a claim about the original's exact pixels - no icon assets exist to compare against, only the report that enchanted things should look it. |
| Shield/helmet names and Armor Values match the real tier ladder | **fixed** - the user pasted the actual `shields.shtml` and `helmets.shtml` tables directly (blocked from automated fetch the same way as before). Verified genuine first: an earlier paste in this same thread, claiming a *different* set of shield/helmet names and values under `utm_source=gemini` links, gave the game's own subtitle wrong ("A Question of Security"/"Lifthrasir's Lair" against the real "A Question of Vengeance"/"Lifthransir's Bane", both independently confirmed from `CASTLE1.EXE`'s own splash text) and invented a shield ladder with no overlap with `BASES` - that one was refused. This one checks out: it independently reproduces `"Enchanted Cape of Protection"`, a string already captured from the real game itself in `docs/reference-run.md:397` via the Wine reference harness, well before this shrine page ever came up. Our shields were Buckler/Kite Shield/Tower Shield at +3/+9/+12 (names and middle/top values invented); the real ladder is nine tiers, Small/Medium/Large across Wooden/Iron/Steel, +3 through +15. Our helmets were Leather Cap/Steel Helm at +3/+9 (the values happened to already match the real low and top tier by coincidence - the names and the missing Iron Helmet middle tier did not). `buckler`/`shield`/`towershield` and `cap`/`helm` keep their key names (armourer stock, `tools/balance.py`'s grouping, `tools/interaction_audit.py` all reference them directly) but now carry the shrine's low/mid/top tier; the tiers in between are new keys. The shrine's own damaged-item name for both is "Broken", not "Rusty" or "Ripped" - moved into the `wood` bucket in `MATERIAL` accordingly (previously helmets fell through to the "metal" default). Cloaks: real is a single "Wool Cloak" at +1 (ours had a plain "Cloak" at +3, invented) - corrected in place, key unchanged. Icons are reused across the nine shield tiers and shared between Iron/Leather Helmet, by size/tier rather than one icon per name - we have three shield icons and two helmet icons, not nine and three; a stated simplification, not a claim about the original's art. |
| Gauntlets' and cloaks' magic is a named ego item, not an Enchanted/Cursed prefix | **fixed** - the follow-up to the row above. `gauntlets.shtml`'s own rows: `Cursed Gauntlets of Protection/Dexterity/Strength/Intelligence/Constitution`, `Enchanted Gauntlets of Slaying`, and at the `+10` tier, `Enchanted Gauntlets of Protection/Dexterity/Strength/Intelligence/Constitution` - never a bare "Enchanted Gauntlets". `cloaks.shtml` shows the same idea with a twist: the label itself changes, not just a prefix - `"Enchanted Cape of Protection"`, not `"Enchanted Wool Cloak of Protection"` (independently confirmed again by `docs/reference-run.md:397`, captured from the real game before this shrine page ever came up). And the shrine gives the exact combined formula for a stat kind: `"Increases (name of stat) = Stat + 5, Armor Value + 5"` - both at once, not one or the other. Built as `Item.ego` (persisted on save/load), set by `roll_ego()` at generation and read by `name()`/`describe()`: a stat kind (`strength`/`dexterity`/`intelligence`/`constitution`) writes two property sentences, the stat and the Armor Value, both at the rolled tier; `protection` writes the one Armor Value sentence (no special-casing needed - it's the same wording the plain tier system already gives); `slaying` writes a plain rolled hit/damage sentence, the same as a weapon's, and is the one kind `roll_ego()` never lets a curse land on, matching the shrine table's own five-cursed-kinds-not-six shape. `Gauntlets of Slaying` needed real wiring beyond wording, too: nothing previously read a non-weapon slot for combat bonuses, so `Player.to_hit`/`damage_roll` now also add an equipped `arms`-slot Slaying gauntlet's roll, and `Item.ac()` excludes that same roll from Armor Value (the shrine's own `+0` AV column on that row) where every other kind includes it. |
| The Sage identifies for a fee | done |
| Junk store buys anything, market price under 25 CP, else a flat 25, and her window says so | done - and this row was wrong for a while: the code paid a tenth of the value with the flat rate as a floor, on the grounds that the same 25 for a quarrel and a suit of plate was insulting. It is meant to be. Checked by `tools/rule_audit.py`. |
| Cursed items cannot be removed until uncursed | done |
| Cursed items may summon monsters or lower attributes | partial |
| Two-handed weapons conflict with shields | done - there were no two-handed weapons at all. Halberds, broad swords and bows need both hands: taking one up puts the shield in your pack and says so, and a shield is refused while you hold one |
| Charged items recharge on a timer | done |
| Only worn slots and belt slots can be activated | done |
| Free Hand: a doll slot beside the weapon, separate from Shield, for one unwearable thing | done - read off the running inventory window in `reference-run.md`. We had Shield and no Free Hand, so a character with a full pack and no belt could not drink a potion at all; buying and wearing a belt is not something the original ever requires just to use one. Drag anything unwearable onto it and it is reachable exactly like something on a belt. |
| Belts are containers sized in slots; a 10-slot belt is rare | done |
| The inventory window shows every container at once: body, belt, floor and pack | done - a running screenshot of the original shows all four on screen together, Floor included, with nothing to click through to see it. Ours drew the doll, a bare strip for the belt, and the pack, but never the floor: closing the window to look at what was underfoot, walking over it and pressing G, then reopening the window was the only way to reach it. The window now has a Floor panel between the doll and the pack, live off the same ground tile Get reads, with its own drag-and-drop: drag a floor item onto the body to wear it, into the pack to carry it, or onto the pack to drop something you are carrying. A dragged pile of coins deposits into the purse and vanishes rather than sitting in the pack as an object, the same as Get already did. A store's own window replaces this with its shelf instead, per the manual's own wording for how a store extends the inventory screen. |
| The belt reads as its own container, the way the original's own window shows it | **fixed** - flagged directly: "I don't really like the to-hand strip. It's not intuitive. I would prefer how CotW does it, which is the belt gets its own window with a specific number of available slots." The belt (and the Wand Quiver, if one is worn) used to be a row of bare 26px squares captioned only "to hand:" tucked under the paper doll's feet, drawn only when something was worn there and easy to miss entirely. It is now a titled panel next to Floor, named for the belt actually worn ("Two Slot Belt", "Three Slot Belt & Wand Quiver" if both a belt and a quiver are on), with exactly as many boxes as it has slots - empty ones included, same as Floor and Pack already show their own bounds regardless of what is in them. |
| The inventory window is genuinely several windows, not one pane wearing several labels | **fixed** - flagged directly, after the belt fix above: "The dashed red lines are in the original. I would like genuinely separate windows... frankly all of the deviations from the original game are worse." The Person, Floor, Belt and Pack panels were four labelled regions inside one bordered frame; a running screenshot of the original shows four actual windows, each with its own title bar and its own close box, sitting independently over the game. PackScene (and StoreScene, whose fourth window is the shop's shelf in Floor's place) now draw and track each container as its own window: its own chrome from `draw_window()`, its own position in `win_rect`, draggable by its title bar exactly like the original's, closable with its own X (closing Person closes the whole screen, since it carries Exit! and the rest of the menu the way the original's anchor window does; closing Floor, Belt, Pack or Store just hides that one until the screen is reopened - there is still no Window menu to reopen one without doing that, which the row below already tracks). All the drag-and-drop between them - pack to body, floor to pack, body to belt, buying out of a store, selling into one - keeps working unchanged, because every window still populates the same rect lists (`cell_rects`, `stow_rects`, `slot_rects`, and so on) that the interaction code already read; only where those rects are drawn, and what frames them, changed. |
| Packs come in more than one size | done - the original sells a Small, a Medium and a Large, each a real step up in capacity for more coin; we had only the small one, named "Backpack" rather than "Small Pack". Figures for all three are read off the measured shop captions in `reference-run.md`. |
| Wand Quiver slot | done - a slot on the doll that takes wands and nothing else, and a wand in it is within reach. A spent wand reads as a Dead Wand. |
| A wand does something when activated | **fixed** - this row used to read "done" on the strength of the Quiver slot and the Dead Wand naming alone, and neither one was true: a wand's `kind` had no entry in BASES and fell through to the "gear" default, so it never matched the Activate menu's own `kind == "wand"` filter and could not even be selected there; and nothing anywhere ever spent a charge or did anything with one, which made a 300-copper, depth-5 wand a strictly worse dagger in melee - all cost, no effect, forever rechargeable to a maximum it could never be spent below. Activating one now fires a bolt down the line you are facing, out to the range Spark itself reaches (nothing in the source material says how far a wand should carry, and matching an existing beginner attack spell is the least invented number available), in the "blast" style `combat.WEAPON_CLASS` had already named for a wand's melee swing. Also fixed in the same pass: the weaponsmith built a wand for sale the ordinary weapon's way, which defaults to zero charges and reads as a Dead Wand the moment `known` is set (which the shop does immediately) - a wand on the shelf is now rolled a charge count the way `generate_item()` already rolls one found in the dungeon. |

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

| Menu bar: File, Character!, Inventory!, Map!, Spells, Activate, Verbs, Window, Help | partial - Activate was missing and is now built from what you have to hand. Window is still not there: the inventory screen is genuinely several windows now (see above), which is what a Window menu would manage, but there is nothing yet to tile or cascade them back into place or to reopen one you closed short of closing and reopening the whole screen. |
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
| The Floor window keeps up with your feet | **fixed - twice.** Reported directly: "The floor window is always empty." First pass: it reads `inventory_view()`'s own `"floor"` field, which is only ever recomputed when an `"inv"` event fires; picking something up fires one, but simply walking onto - or off of - a tile with something on it never did, so the panel kept showing whatever it last saw (usually nothing, from before the character had ever stood on anything) no matter what was actually underfoot. `describe_floor()` already ran on every step regardless of what was there, so that is where the event now fires too, plus the same gap on landing via stairs in `move_player_to()`. The report came back unchanged after that, so it was re-verified through the real client and server (`tools/playtest.Session`, not just `World` calls directly) rather than assumed fixed - which found the actual remaining gap: standing on something and opening the Pack window with *no* prior action (right after spawning on top of it, say) still showed an empty panel, because opening the window is not an action either, and the client had never asked for a snapshot on its own - it only ever reacted to what the server volunteered. `PackScene` now sends `C_RESYNC` (already "my map and your world disagree; send me the floor", answered with a fresh `S_INV` among other things) as soon as it opens, skipped only when it was opened to answer a pick prompt, where the server just sent fresh state to prompt it in the first place. |
| A scroll (or potion) held in the Free Hand was never used up | **fixed** - reported directly: "The scrolls don't disappear after use." `Player.consume()` only knew how to remove something from the pack list, or from a container's `contents` (a belt or quiver) - a scroll held in the Free Hand is neither: it is not in the pack, and it is not inside anything's `contents`, it *is* the thing that slot points at directly. Reading it worked, tore itself an identify or a map or whatever it did - and then sat there in the free hand exactly as before, ready to read again, forever. `consume()` now also checks whether the item itself is a slot's own equipped item, and clears that slot (or decrements it in place, for a stack). A potion drunk from the free hand had the identical bug; fixed the same way. |
| Dropping a worn item refused, "no room", even though the drop was never going through the pack | **fixed - and there was more of it.** Reported directly: "Can't put things on floor if no room in pack." First pass fixed `_act_drop()`: a worn item goes through `unequip()` first, which checks pack room before letting anything come off, cursed items aside - the right check for the *actual* Take It Off verb, where the item really does stay in the pack afterward, but wrong here, since `_act_drop()` immediately pulls it straight back out to put it on the floor. `unequip()` takes a `skip_room_check` now, and `_act_drop()` passes it. The report came back as "Pack bulk still prevents adding/removing things from/to other slots like floor, belt, freehand, etc" - the same bug, in the other two places that route a drag through the pack on the way to somewhere else. `_act_take()` (a Floor-window drag straight onto a slot) and `_act_buy()` (a shop purchase dropped straight onto a slot) both called `room_for()`/`add_item()` unconditionally, before ever looking at where the drag had actually ended, so a full pack refused a potion bound for an empty belt cell exactly as readily as one bound for the pack itself. Both now work out the real destination first - a body slot via `equip()`, a belt or quiver via the same `_stow_refusal()` check `_act_stow()` uses (now split out so both can share it) - and only fall back to `room_for()` when the pack really is where the thing is going to end up. |
| Duplication bugs putting things in belts/free hand | **fixed** - reported directly, and real: `Player.equip()` only ever took the item it was placing out of the pack list before assigning it to the new slot. Dragged from a belt's own `contents` instead - or straight from another slot, such as the free hand - the same `Item` object ended up worn in the new slot AND still listed wherever it had been: not a rendering glitch, the object really was in both places in the actual save state, so it drew twice, and selling or dropping one copy left the other behaving oddly. `equip()` now also checks a worn container's `contents` and every other equipment slot for the item before placing it, removing it from wherever it actually was; moving a cursed thing this way is refused the same as `unequip()` already refuses it through the front door. `_act_stow()` had the mirror-image bug, minus the duplication - it also only pulled from the pack, so a free-hand or belt-to-belt drag onto the belt silently did nothing instead of duplicating; fixed the same way, without the cursed case (nothing reaches the belt cursed and worn at once, so the case cannot arise there). |
| No one buys the gemstone | **fixed** - reported directly. `"gem"` (a Gemstone, base value 350, 2800 copper once identified) is the only base item with `kind="treasure"`, and no trade's `SHOP_TAKES` listed `"treasure"` - every shop but Nan's junk store refused it outright ("We don't buy those..."), and Nan only ever pays a flat 25 regardless of what the thing was actually worth, which in practice meant nobody paid what it was worth for it anywhere. Added `"treasure"` to the general store's list - it already catches "the soft gear the armourer doesn't bother with," and a loose gem is exactly that kind of leftover, not a weapon or a piece of armour. |
| Shops should update along with the level of the player | **checked, already true** - `stock_for()` already builds a shop's shelf from `self.party_deepest` (the deepest floor the party has reached), and `move_player_to()` already clears the cached stock every time anyone steps back into town, so the shelf genuinely restocks to reflect how far the party has been, not just what it looked like on day one. Verified directly (`stock_for("weaponsmith")` before and after a return from depth 10 turns up an entirely different weapon list) and pinned down with a test so it stays true. If what prompted the report was something more specific - stale prices, a particular shop, a multiplayer party where one character is much deeper than another - say so and it can be chased further; nothing broken was found in the restocking mechanism itself. |
| A floor tile holding more than one item showed only the last one drawn | **fixed** - "We need an icon for when multiple things are on the floor." Not a parity claim - neither the manual nor the extracted string table say anything about a floor-pile indicator - so this is a Stormhold-only UI affordance. A small three-gem corner badge (`badge_pile()` in `art.py`) now draws over whichever item's icon is on top, wherever more than one item shares a tile: map, and anywhere else floor items render. |
| A heavy enough purse could freeze a character permanently, with no way to shed the weight | **fixed - Drop Coin was a safety valve, not the cause.** Asked directly: "Are you sure copper is supposed to weigh? It can't be dropped, so there's a condition where one could freeze themselves out of the game by carrying too much copper." Checked against source before changing anything: coin weight itself is faithful, not invented - a prior session's own commit records a direct measurement against the reference harness, not a guess: "Buying a 1000 g sword for 1470 coins moved total carried weight by exactly -470, which means the purse held 1470 actual copper pieces weighing 1470 grams. Had the original quietly consolidated that into 1 platinum, 4 gold and 7 silver it would have weighed 12 g and the arithmetic would not have worked." Coins really do weigh a gram each, uncollapsed, and past the game's own hard carry limit movement genuinely stops. First pass added `drop_coins` (below) as an escape hatch - useful in general, but the report came back: "I dropped everything and still can't move because I have copper... This never happened in CotW." That sent the search back to why a purse could get that heavy in the first place, and found the real bug: nearly every source of income - selling, temple refunds, bank withdrawals - reached for money with `p.copper += amount`. `copper` is a computed property with no storage of its own; its setter's own docstring says what that line actually does - "Set the purse to a plain value" - so *every single sale re-minted the entire purse as flat copper pieces*, discarding whatever platinum a long trip down had already earned. Since weight is coin *count*, not coin *value* (that's the whole point of the denomination system the same earlier commit built), this made carrying real wealth heavier with every sale: a purse settled into a handful of platinum went back to weighing a kilogram the moment a single potion sold. This is what actually froze the character, at perfectly ordinary amounts of money, not just in a deliberately extreme test. New `Player.gain_value()` mints the fewest coins for an amount (reusing `coin_purse()`, a helper that already existed and was never called) and adds them without touching what's already in the purse; every `+=`/`-=` call site that gains or spends money now goes through `gain_value()` or the pre-existing, composition-preserving `spend()`, never the raw property. Confirmed with a 50-sale simulation: 448,000 copper worth of income, which the old code would have made weigh 448 kg, now mints down to a purse of a little over a kilogram. |
| Nothing let you shed a purse's weight once it was heavy | **fixed** - the escape hatch from the first pass above, kept because it is still a real gap on its own terms: the manual's money page implies coin can be carried as an ordinary pack object, not only as the abstract purse total ("[Copper] doesn't include any money you have in your pack" only makes sense if it can), but nothing in `_act_pickup`/`_act_take` ever created that form - a coin pile picked up always deposits straight into the purse, with no way back out. New `drop_coins` action puts an exact, chosen amount of copper back on the ground as a real coin-pile item, the same kind a monster or the floor already drops - available from a Drop Coin button in the Person panel, prompting for an amount the same way Name Object already prompts for text. Deliberately costed like every other Drop (`action_cost` without `moving=True`), so it still works on the rare occasion a purse alone is genuinely too heavy to move, without needing a shop to reach first. |

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
