# Measurements taken from the original program

Everything on this page was read off Castle of the Winds 1.1A *while it was
running*, not remembered and not inferred. The original is a Windows 3.x NE
binary; it runs under Wine's 16-bit loader on a virtual X display, which makes
it a black-box measuring instrument. `tools/reference-harness.sh` sets that up.

This is observation of behaviour, the same thing you would do by hand with the
game open and a notebook. No code was decompiled and no assets were copied.

`tools/reference_driver.py` sends keys and clicks and reads the status panel and
message log back through OCR; `tools/reference_bot.py` is a small bot that plays
using them. Both exist to measure the original, not to ship with the game.

## How to reproduce

    dpkg --add-architecture i386
    apt-get update
    apt-get install -y libgd3:i386     # install first; the resolver gives up otherwise
    apt-get install -y wine wine32 xvfb imagemagick xdotool tesseract-ocr
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

# Third session: a bot plays it

To get past hand-driving, this session added OCR (tesseract) and a small bot
that reads the game as text and plays it: `tools/reference-harness.sh` sets up
the environment, and the driver and bot live in the scratchpad notes below.
The bot finds the player by sprite colour, finds monsters as colour blobs that
are neither terrain nor player, attacks what is adjacent, runs to explore, and
writes every message it sees to a journal.

## Character creation has caps and a costed pool

Raising an attribute is not simply one point per click. Strength hit a **cap**
partway through spending: the Available bar stopped falling while points were
still left, and further clicks did nothing. The pool then had to be spent
elsewhere. So chargen is a pool against per-attribute maxima, not a free
allocation.

The pool is worth about 12 increments from the starting values.

## What Constitution buys

A character with the whole pool in Constitution has **14 hit points** at level
1, against **10** for one that spends nothing there. That is roughly one hit
point per three points of Constitution - a much weaker return than the carry
weight law, and worth knowing before treating Constitution as the survival
stat. Armour is the better early buy.

## Armour values

| item | Armor Value | weight | bulk | base value |
|---|---|---|---|---|
| Normal Suit of Leather Armor | 6 | 5000 | 24000 | 750 |
| Normal Leather Helmet | 3 | - | - | 375 |

Armour Value is additive across pieces and starts at 0 with no armour.

## A second shop, and spell books

The town has more than the weaponsmith. The general/magic store stocks:

    Potion of Levitation, Spell Book: Detect Objects, Spell Book: Magic Arrow,
    Wool Cloak, Enchanted Cape of Protection, Normal Leather Boots,
    2 Slot Belt, Small Pack, Medium Bag

Three things follow. Spells are **bought as books**, so the starting spell is
not the only way to learn one. Belts are sized in **slots** ("2 Slot Belt"), so
the belt is itself a small container. And items carry quality prefixes -
`Normal` for plain, `Enchanted` for better ("Enchanted Cape of Protection").

The weaponsmith's full stock, for the item list: Club, Hammer, Hand Axe,
Quarter Staff, Spear, Short Sword, Flail, Dagger, Suit of Leather Armor,
Suit of Studded Leather Armor, Small Wooden Shield, Medium Wooden Shield,
Large Wooden Shield, Medium Iron Shield, Leather Helmet, Bracers, Gauntlets.

## One price that does not fit

Every weapon and armour price so far is a clean 1.4x an integer base: 105/75,
1470/1050, 525/375, 1050/750. **Spell Book: Magic Arrow costs 416**, which is
not 1.4x a whole number (it implies 297.14). So either spell books are priced
by a different rule, or something else - spell level, or a per-item modifier -
enters for them. Flagged rather than guessed at.

## Shops rearrange themselves

The Store window auto-arranges after every purchase, so item positions shift.
Anything scripted against the shop has to re-read the window between buys.

## Two things that will bite anyone repeating this

The game window must sit fully on screen at (0, 0). Moving it even 8 pixels
above the top edge leaves menus working but **silently stops the game clock** -
movement and actions are accepted and do nothing. It looks exactly like a
wedged game and is not one.

Resizing the window repeatedly while a game is running eventually leaves the
map pane blank and unrecoverable. Set the size once, before starting a game.

# Fourth session: reading the game's own name tables

The Help menu turned out to carry the whole manual - **Help Contents, Keyboard
Commands, Mouse Commands, Spell Directory, Object Directory, Bestiary, High
Scores**. Opening any of them asks for `castle1.hlp`, which is not in the
upload; only the `.EXE` is. That file ships in the original archive and would
be the authoritative source for everything below.

Failing that, the runtime name tables are in the executable itself as plain
text, and `strings` reads them without decompiling anything. What follows is
the vocabulary the game actually uses. Names are recorded here as *reference*;
this remake keeps its own names and art.

## The bestiary is a taxonomy, not a flat list

Dragons come in four colours and six ages, which is 24 distinct monsters from
one family:

    White / Green / Blue / Red
    Young, Young Adult, Adult, Old, Very Old, Ancient

Elementals come in six materials: Air, Dust, Earth, Fire, Ice, Magma.
Undead ladder through Wights (Barrow, Castle) and Wraiths (Pale, Dark, Abyss).
Giants ladder through Hill, Stone, Frost, Fire.

The rest, roughly in order of depth: Giant Rat, Kobold, Goblin, Goblin Fighter,
Hobgoblin, Orc, Giant Bat, Large Snake, Ant, Giant Red Ant, Gray Wolf, White
Wolf, Bandit, Berserker, Skeleton, Walking Corpse, Eerie Ghost, Giant Scorpion,
Giant Trapdoor Spider, Carrion Creeper, Brown Bear, Cave Bear, Bear-Man,
Huge Ogre, Gruesome Troll, Smirking Sneak Thief.

Named bosses, each a set piece:

    Hrungnir, The Hill Giant Lord
    Rungnir, The Stone Giant King
    Thrym, The Frost Giant King
    Thiassa, The Fire Giant King
    The Demon Lord Surtur

The lesson for our own bestiary is structural: families with tiers inside them,
so one art idea and one behaviour carry six or more depths of difficulty, and
each act closes on a named giant.

## The spell list

    Attack:     Magic Arrow, Fire Bolt, Cold Bolt, Lightning Bolt,
                Fireball, Cold Ball, Ball Lightning
    Healing:    Heal Minor Wounds, Heal Medium Wounds, Heal Major Wounds,
                Heal, Neutralize Poison, Remove Curse
    Divination: Detect Monsters, Detect Objects, Detect Traps, Identify,
                True Sight, Clairvoyance
    Movement:   Phase Door, Teleport Away, Teleportation, Levitation
    Defense:    Shield, Protection, Banishing Fear
    Misc:       Light, Slow, Blindness, Ogre Power, Clone Monster,
                Transmogrify Monster

Attack spells form a clean grid: three elements (fire, cold, lightning) times
two shapes (bolt, ball), plus Magic Arrow as the starter. Healing ladders in
four steps and the temple sells exactly those four.

The Spell Directory's own descriptions are in the binary too, e.g. *"detect
objects on the current level"*, *"detect traps close by"*, *"neutralizes poison
in the character"*, *"creates a return field about the player"* (Rune of Return).

## Casting without mana is allowed, and hurts

> "You don't have enough mana. Casting this spell may damage your health.
> Continue?"

So mana is not a hard gate - you may overdraw and pay in hit points. That is a
real tactical mechanic and this remake does not have it.

## Items are composed at runtime, not stored whole

This is the useful discovery. Most item names do not exist in the binary as
complete strings - they are assembled from word tables through templates:

    %i Sword     %i Bow      %i Cloak    %i Boots     %i Helmet
    %i Belt      %i Bag      %i Pack     %i Chest     %i Scroll
    %i %i Shield             %i Pack Of Holding
    %i %d charge%z

which is why the shop shows "Normal Suit of Leather Armor" and "Normal Medium
Iron Shield" rather than fixed names. The word tables that feed them, all
verified present:

    quality:   Broken, Ripped, Rusty, Normal, Enchanted, Cursed
    size:      Small, Medium, Large
    material:  Leather, Studded Leather, Chain, Scale, Plate, Splint,
               Iron, Wooden, Meteoric Steel
    weapons:   Dagger, Club, Quarter Staff, Spear, Hand Axe, Battle Axe,
               Axe, Mace, Hammer, War Hammer, Morning Star, Flail,
               Short, Broad, Bastard, Two Handed (+ Sword)
    wearables: Helmet, Gauntlets, Bracers, Boots, Cloak, Belt, Ring,
               Amulet, Shield
    carried:   Pack, Pack Of Holding, Bag, Chest, Potion, Scroll, Wand,
               Wand Quiver, Food

So the identification system and the quality system are the same mechanism: an
unidentified item shows a plain noun, and identifying it reveals the adjective.

Two slots we did not have: a **Wand Quiver**, and belts that are containers
sized in slots ("2 Slot Belt", "4 Slot"). A spent wand becomes a **Dead Wand**.
Charged items show "%i %d charge%z" and recharge on a timer, "(Once every %d
hour%z)".

Two-handed weapons conflict with shields, and the game says so rather than
silently refusing: *"Can't use both a Two Handed Sword and a Shield"*, and
*"You drop something to wield your sword with both hands"*.

Named unique gear exists: Thangbrand's Sword and Scabbard, Isleif's Sword and
Scabbard, 7 League Boots, Red Dragon Blood.

## Shops have proprietors

Shops are named for their owners, which is why the town feels inhabited:

    Beinir the Strong's Armor Shop
    Sverting's Armor Shop
    Eirik's House of Armor
    Thangbrand's Sword and Scabbard
    Isleif's Sword and Scabbard

## The trap list

    an arrow trap, a dart trap, a blade trap (a scything blade), a fire trap,
    an acid trap, a poison gas trap, a sleep gas trap, a slow gas trap,
    a teleport trap, an animation trap, a deadfall, a pit, a trap door,
    a glyph of warding, an unknown trap

Ours were invented; this is the real set. Note the spread of effects - damage,
status, movement, and *animation* (which raises the dead), plus a trap door
that drops you a level rather than hurting you.

## Health is reported in words, not numbers

Examining something gives one of six states rather than a number:

    Uninjured, Barely scratched, Slightly injured, Injured,
    Heavily injured, Critically injured

## Combat messages are weapon-aware and located

The messages vary by weapon class and by where the blow lands, which is why
combat reads well without ever printing a damage number:

    You hit <foe> in the arm! / in the chest! / in the head! / in the leg!
                              / on the flank!
    You slash <foe>, opening a bloodless cut.
    You slash at air as <foe> dances back.
    You deal <foe> a solid blow! / a crushing blow!
    You smash into <foe>'s shield, striking sparks.
    You miss <foe> by a league!

Kill messages are their own escalated set:

    You slash through <foe>'s throat with a neat lunge and slice.
    You chop open <foe>'s chest, splintering ribs and shredding viscera.
    You crush <foe>'s skull into jelly.
    You pound <foe> until it stops moving.
    You deal <foe> a final murderous cut.

Slash verbs go with blades, crush and pound with blunt weapons, chop with axes.
A shield block is its own message. This is the single most copyable thing in
the game for feel, and it costs nothing but a message table.

## Status line formats, verbatim

    %i %d (%d)          HP and Mana:  "HP  10 (10)"
    %i %d%% / %d%%      Speed:        "Speed  100% / 200%"
    %i %dd,%D:%D:%D     Time:         "Time  0d,00:00:52"
    %i (%i)             Weight/Bulk

## Other mechanics the strings give away

- Thieves steal from the purse: *"You feel a tug on your purse"*, and
  *"The Thief vanishes!"* - so theft plus teleport-away is a monster behaviour.
- Money auto-banks into the pack: *"Placing money in your pack..."*
- Doors can be smashed: *"The %i blasts open the door!"*, *"A broken door"*,
  and they can be blocked: *"There are objects blocking the door"*.
- Level features include a stone sarcophagus, a shrine to Odin, an elemental
  portal, fountains and thrones you can use, and webs you must fight through.
- Shops refuse junk: *"We don't buy those..."*, *"We don't buy worthless items!"*
- The game warns before the point of no return: *"This is your last chance to
  save if you want to carry your character forward to part two."*
- Quitting is called what it is: *"cowardly restart"*.

# Fifth session: the manual, decoded

You supplied `CASTLE1.HLP` and `CASTLE2.HLP`. WinHelp 3.0 stores its topics
phrase-compressed, so `strings` shows only the file skeleton; `tools/hlp.py`
reads the B-tree directory, rebuilds the phrase table and expands the topic
text. That turns the game's own manual into something greppable, and it settles
most of what was still guesswork.

## Units: grams and cubic centimetres

> "Weight: How much all the equipment you are currently carrying weighs,
> **measured in grams**." ... "Bulk: A measure of how much space all your
> equipment takes, **measured in cubic centimetres**."

So the numbers read off the character sheet are plain metric: a fresh character
carries 3300 g and is rated for 25000 g, a small pack weighs 1000 g and holds
12000 g and 50 litres, and one copper piece is **1 gram**. My earlier guess of
"hundredths of a pound" was wrong about the unit, though the 2000-per-strength
law it was derived from stands.

## Attributes run 0-100

> "In each pair, the left bar gives your current value, and the right gives the
> maximum value, **on a scale of 0-100**. Your current value can be above or
> below your maximum if you are wearing magical items that modify an attribute."

That explains the paired bars on the character sheet: current against maximum,
not base against modified. A ring of strength pushes current *above* maximum.
Our 3-18 style range is not what the original uses.

## The speed model, which we had wrong

Two numbers, and they measure different things:

> "The first number is overall speed. This affects how long it takes you to
> perform most actions, such as casting spells, searching, or combat."
> "The second number is movement speed ... affected by how much weight the
> character is carrying. If your character is lightly loaded (carrying less
> than 1/2 his or her rated maximum) then he/she will be able to move at 200%
> of normal speed. ... At your rated maximum you will be moving at 100%, and at
> twice your rated maximum (the real limit on what you can carry) you will be
> moving at 50%. Note that movement speed (or slowness) doesn't affect other
> actions, so you can cast spells at the same rate no matter how heavily
> loaded you are."

Those three points - 0.5x load gives 200%, 1x gives 100%, 2x gives 50% - are
exactly `100 / (load / rated)`, capped at 200, with 2x rated as the hard limit.
A clean hyperbola, and it replaces the six invented encumbrance tiers.

We had this materially wrong in two ways: load was slowing *every* action, and
the status line printed a fixed "100%" for the first figure. Both are fixed;
the readout now shows overall speed and movement speed, as the original does.

## Regeneration rates

> "Hit points regenerate fairly quickly as time passes, **about 1 per minute**."
> "Mana ... replenished by going up a level in experience, by using certain
> magic items, or slowly with time (**1 point per hour**)."

Mana is sixty times slower to come back than health. That single ratio explains
why the game feels the way it does - you rest off wounds freely and hoard
spells.

## Casting is not gated by mana

> "You don't have enough mana. Casting this spell may damage your health.
> Continue?"

You may overdraw and pay the shortfall in hit points. Now implemented: an
unconfirmed cast is refused with the cost quoted, a confirmed one takes the
hit points, and it can kill you.

## The full spell table

Levels, mana and casting time, verbatim from the Spell Directory:

    Detect Objects          1     1   30 seconds  (interruptible)
    Heal Minor Wounds       1     1   5 seconds
    Light                   1     1   5 seconds
    Magic Arrow             1     1   5 seconds
    Phase Door              1     1   5 seconds
    Clairvoyance            2     3   30 seconds  (interruptible)
    Cold Bolt               2     2   5 seconds
    Detect Monsters         2     2   30 seconds  (interruptible)
    Detect Traps            2     2   30 seconds  (interruptible)
    Identify                2     2   60 seconds  (interruptible)
    Levitation              2     2   5 seconds
    Neutralize Poison       2     3   5 seconds
    Cold Ball               3     4   5 seconds
    Fire Bolt               3     3   5 seconds
    Heal Medium Wounds      3     3   5 seconds
    Lightning Bolt          3     3   5 seconds
    Remove Curse            3     3   60 seconds  (interruptible)
    Resist Cold             3     3   5 seconds
    Resist Fire             3     3   5 seconds
    Resist Lightning        3     3   5 seconds
    Rune Of Return          3     3   5 seconds
    Sleep Monster           3     4   5 seconds
    Slow Monster            3     4   5 seconds
    Teleport                3     3   5 seconds
    Ball Lightning          4     4   5 seconds
    Fireball                4     5   5 seconds
    Heal Major Wounds       4     5   5 seconds
    Healing                 5     6   5 seconds
    Transmogrify Monster    5     6   5 seconds
    Clone Monster          NA    NA   NA
    Create Traps           NA    NA   NA
    Haste Monster          NA    NA   NA
    Teleport Away          NA    NA   NA

The four marked NA are cast by monsters, not by the player - Clone Monster,
Create Traps, Haste Monster, Teleport Away. Worth knowing before treating the
spell list as the player's alone.

The shape: mana runs 1-6 across five spell levels, so no spell is ever more
than a few points. Casting time is set by what the spell does rather than how
strong it is - attack, healing and movement at 5 seconds, all detection at 30,
and Identify and Remove Curse at 60. Everything from 30 seconds up is marked
"this spell can be interrupted". Adopted: our spells now carry the same cast
times by school, with Revelation (our Identify) as the one-minute spell.

## What else the manual settles

- **Experience** is gained "for killing monsters and for certain actions such
  as disarming traps" - so trap disarming is a deliberate second income.
- **Undead drain levels**: "if you lose a level due to loss of experience to
  undead such as ghosts and vampires, these added skills will be lost."
- **Difficulty** changes four things at once: "more monsters and traps, less
  treasure and objects to find, and you need more experience to increase in
  levels of power." So it is not a damage multiplier.
- **Constitution's real job** is per-level hit points: "Characters with a high
  constitution will gain extra hit points for each level as well." That matches
  the measurement - it barely moves level-1 HP, because its effect compounds.
- **Strength** gates armour, not just carrying: "Playing a character with a low
  strength will really cramp what armor you can wear!"
- **Armour Value** is a to-hit reduction, not damage absorption: "A high armor
  value means monsters have a lesser chance of making a hit that inflicts
  damage." The author notes the simplification that it applies to every attack
  rather than per body part.
- **Ball spells** cover 3x3 and "the monster in the center takes the most
  damage."
- **Magic containers** can lighten what they hold: "certain magical containers
  may cause the weight of their contents to be less than expected."
- The **bestiary** is prose - lore and ecology rather than numbers - so
  per-monster damage, hit points and experience values remain ours. The
  **object directory is not**: see the tables below, which I missed on the
  first pass.

# The object tables, which I had said did not exist

I told you the Object Directory was prose. That was wrong, and it was the one
thing in the help file worth finding: it carries **stat tables with exact
numbers**, under the topics Weapon Class, Armor Value, Weight, Bulk and
Containers. My line-oriented dump had scrambled them, because table cells are
separated by control bytes rather than newlines, and I did not go back and
check. The cross-check that should have caught it was sitting in my own notes:
I had measured Leather Armour in-game at AV 6, 5000 weight, 24000 bulk, and
the table says exactly that.

## Body armour

| Armour | Armor Value | Weight (g) | Bulk (cc) |
|---|---|---|---|
| Rusty Armor | 0 | 10000 | 30000 |
| Leather Armor | 6 | 5000 | 24000 |
| Studded Leather Armor | 12 | 7000 | 25000 |
| Ring Mail | 18 | 8000 | 30000 |
| Scale Mail | 24 | 9000 | 30000 |
| Chain Mail | 30 | 10000 | 30000 |
| Splint Mail | 36 | 12000 | 40000 |
| Plate Mail | 42 | 15000 | 40000 |
| Plate Armor | 48 | 15000 | 60000 |
| Elven Mail | 52 | 5000 | 24000 |
| Meteoric Steel Plate | 54 | 5000 | 30000 |

Armour value climbs in **steps of exactly 6**, and the two best suits are the
lightest: Elven Mail weighs what leather does, Meteoric Steel Plate a third of
plate. Rusty Armor is the joke entry - heavier than plate mail and worth
nothing.

## Helmets and shields

| Helmet | AV | Wt | Bulk |          | Shield | AV | Wt | Bulk |
|---|---|---|---|---|---|---|---|---|
| Broken Helmet | 0 | 1000 | 1000 | | Broken Shield | 0 | 4000 | 35000 |
| Leather Helmet | 3 | 500 | 500 | | Small Wooden | 3 | 3000 | 15000 |
| Iron Helmet | 6 | 2000 | 2000 | | Medium Wooden | 6 | 4000 | 35000 |
| Steel Helmet | 9 | 2500 | 2000 | | Small Iron | 6 | 4000 | 15000 |
| Meteoric Steel Helmet | 15 | 1000 | 2000 | | Large Wooden | 9 | 5000 | 50000 |
| Helmet of Detect Monsters | 9 | 2500 | 2000 | | Medium Iron | 9 | 5000 | 35000 |
| | | | | | Small Steel | 9 | 4000 | 15000 |
| | | | | | Large Iron | 12 | 6000 | 50000 |
| | | | | | Medium Steel | 12 | 5000 | 35000 |
| | | | | | Large Steel | 15 | 6000 | 50000 |
| | | | | | Small Meteoric | 15 | 2500 | 10000 |
| | | | | | Medium Meteoric | 18 | 3500 | 25000 |

Shields are a clean grid of size against material: each step up in size or up
in material is +3, so a small steel shield and a large wooden one are worth the
same. That is a nice design to steal - two axes, one number.

## Weapons, by Weapon Class

| Weapon | Class | Wt | Bulk |
|---|---|---|---|
| Broken Sword | 0 | 1000 | 5000 |
| Club | 1 | 1500 | 3000 |
| Dagger | 2 | 500 | 500 |
| Hammer | 2 | 2000 | 3000 |
| Hand Axe | 3 | 1000 | 3000 |
| Quarterstaff | 3 | 750 | 5000 |
| Spear | 4 | 1500 | 5000 |
| Short Sword | 5 | 1000 | 5000 |
| Mace | 5 | 2500 | 4375 |
| Flail | 6 | 2000 | 3250 |
| Axe | 6 | 2000 | 5000 |
| War Hammer | 7 | 1400 | 7500 |
| Long Sword | 8 | 1500 | 8000 |
| Battle Axe | 8 | 3000 | 6000 |
| Broad Sword | 9 | 1600 | 9000 |
| Morningstar | 10 | 3000 | 9000 |
| Bastard Sword | 11 | 3000 | 10000 |
| Two Handed Sword | 12 | 5000 | 12000 |

Weapon Class runs 0-12 with ties at every step - the dagger and the hammer are
both class 2, and weigh 500 g against 2000 g. So weight is a real cost paid for
nothing but flavour at equal class, which is what makes the dagger a sensible
early weapon.

## Containers

Six columns: `Wt | Bulk | Wt. Max | Bulk Max | Wt.Fx | Bulk Fx`.

| Container | Wt | Bulk | Wt Max | Bulk Max | Wt Fx | Bulk Fx |
|---|---|---|---|---|---|---|
| Broken Pack | 1000 | 1000 | 0 | 0 | 0 | 0 |
| Small Bag | 300 | 500 | 5000 | 6000 | 0 | 0 |
| Medium Bag | 500 | 700 | 10000 | 12000 | 0 | 0 |
| Large Bag | 900 | 900 | 15000 | 18000 | 0 | 0 |
| Small Pack | 1000 | 1000 | 12000 | 50000 | 0 | 0 |
| Medium Pack | 2000 | 1500 | 22000 | 75000 | 0 | 0 |
| Large Pack | 4000 | 2000 | 35000 | 100000 | 0 | 100000 |
| Small Chest | 5000 | 10000 | 100000 | 50000 | 0 | 50000 |
| Medium Chest | 15000 | 2000 | 100000 | 150000 | 0 | 150000 |
| Large Chest | 25000 | 4000 | 100000 | 250000 | 0 | 250000 |
| Small Pack of Holding | 1000 | 1000 | 50000 | 150000 | 5000 | 75000 |
| Medium Pack of Holding | 2000 | 1500 | 75000 | 200000 | 7500 | 100000 |
| Large Pack of Holding | 4000 | 2000 | 100000 | 250000 | 10000 | 125000 |

Small Pack reads `Wt 1000, Bulk 1000, Wt Max 12000, Bulk Max 50000`, which is
character-for-character the caption the game showed in the shop, so the first
four columns are certain. The two Fx columns are the magical-container effect
the manual mentions - only Packs of Holding carry a non-zero weight figure -
but the exact semantics are not settled from the table alone, and I have not
guessed at them.

## What this changed in the code

- Weight is now in **grams** and bulk in **cubic centimetres** throughout, and
  the items that map onto the original's list carry its exact figures.
  A coin weighs 1 g and displaces 1 cc.
- Containers carry the real capacities: a pack holds 12 kg and 50 litres.
- The starting kit is now a dagger, a pack and a purse, as the original's is.
  We had been handing out a short sword and a suit of leather armour, which
  left the character at 84% of rated capacity before leaving town - moving at
  120% instead of 200% - and made the 1500 starting copper pointless. The
  original's design is that the purse buys your first armour (1050) or your
  first real sword (1470), and you cannot have both.

## What this has not changed, and why

The armour value ladder is **not** adopted. Ours runs 1-16 against a d20 roll
(`10 + AC - to_hit`); the original runs 0-54 and its manual describes armour as
reducing the *chance* of a damaging hit, which points at a percentage roll
rather than a d20. Taking the ladder means rewriting the hit formula and
rebalancing every monster, so it is written down as a decision for you rather
than done quietly.

## The bank

Both games have one, and it is the same institution: **First Bank of
Crossroads** in the city of Part Two, and **First Bank of Crossroads (branch
office)** in the Part One hamlet. It prompts *"Would you like to deposit your
money in the bank?"*, and Part Two's manual describes it as "a bank where you
can leave your money for safe keeping".

It exists for two reasons, and both are mechanical rather than decorative.

**Weight.** A copper piece weighs a gram, so ten thousand coins are ten
kilograms against a rated capacity of twenty-five. Coin is the single heaviest
thing a successful character carries, and since load drives movement speed
directly, a full purse is the difference between moving at 200% and crawling.
Banking is how you convert loot into speed.

**Theft.** The Smirking Sneak Thief steals coin - *"You feel a tug on your
purse"* - and then leaves: *"The Thief vanishes!"*. Banked money cannot be
taken.

The status line reflects this: Copper "indicates how much money you are
carrying in your purse, **plus any money you have in the bank**. It doesn't
include any money you have in your pack." So banked coin still reads as yours,
while coins loose in the pack do not count at all - which is a quiet nudge
toward keeping money in the purse or the bank and nowhere else.

We have the strongroom and the weight relief. We have no thieves, so half the
reason for the bank is missing; that is task #29.

# Sixth session: reading the manual line by line

You were right that one finding was not the end of it. Going through both help
files in order, rather than grepping for what I expected, turned up a great
deal more. What follows is organised by subject; the implemented items are
marked.

## Spell formulas, exact

Every healing spell is **a floor or a fraction, whichever is greater**:

| Spell | Restores |
|---|---|
| Heal Minor Wounds | the greater of 8 HP or 20% of maximum |
| Heal Medium Wounds | the greater of 16 or 40% |
| Heal Major Wounds | the greater of 24 or 60% |
| Healing | all of it |

That shape matters: the flat floor keeps the low spell useful at level 1, and
the percentage keeps it useful at level 20. **Implemented.**

**Resistances halve damage and stack multiplicatively** - "casting two Resist
Cold spells cuts the damage from White Dragon breath to 1/4 its normal value".

**Slowing stacks harmonically, not geometrically**: "a monster will move at
1/2, then 1/3, then 1/4, then 1/5 ... of its normal speed", so each further
casting helps less than the last. A lovely way to allow stacking without
letting it run away. **Implemented.**

**Ball spells**: the target square takes full damage, "those on the eight
adjoining squares take half damage". **Implemented.**

**Elements are symmetric**: a creature built of an element takes only partial
damage from it and extra damage from its opposite - cold bolts hurt
fire-creatures more and fire-creatures' own element less. Lightning creatures
such as Blue Dragons resist lightning. **Implemented**, with monsters that
attack with an element now made of it.

Other exact figures: **Phase Door** moves you 5 to 10 squares; **Teleport** at
least 10; **Clairvoyance** maps a 10x10 area including secret doors and traps;
**Detect Monsters** lasts 30 minutes plus one per character level; **Detect
Traps** is guaranteed within 10 squares and falls off with distance; **Light**
lights a 3x3 in a corridor but the whole room in a room; **Sleep Monster** is
broken by attacking the sleeper, and lasts 10 minutes; **Transmogrify**
preserves the target's *fraction* of hit points, so a half-dead dragon becomes
a half-dead hill giant.

**Rune of Return works both ways**: from underground it returns you to the
surface, and from the surface it sends you to the deepest level you have
reached. That is the fast-travel system, and we had it as a one-way escape.

## Mana is not a fixed cost

"The mana required for a spell decreases as you go up in level. Casting a spell
that is more powerful than you can normally handle requires extra mana, but
casting low level spells gets easier." So the cost printed in the directory is
a *base*, adjusted by the gap between your level and the spell's.

Mana is also fully restored on gaining a level, and high intelligence gives
extra mana per level, exactly as constitution gives extra hit points.

## Rest and Sleep are different commands

Resting recovers hit points and breaks "as soon as a monster comes in sight".
Sleeping "regenerates mana at twice the normal rate, but it is only interrupted
when a monster attacks you, not when they come into view". So sleep is the
gamble: twice the recovery, but you let something walk up to you.
**Implemented**, including waking when struck.

## Containers, settled

The Containers topic answers the question I left open: "If non-zero, the Wt. Fx
and Bulk Fx columns are used **instead of** the sum of the contents ... in
calculating the value reported to the parent." They are a **fixed reported
figure, not a multiplier** - "the weight of a 'pack of holding' is constant no
matter what you put inside". Bags' bulk fluctuates with contents; chests' bulk
is fixed. **Implemented**, with a Pack of Holding added.

## The belt is an inventory system, not a decoration

Only objects in your equipment slots **or on your belt** can be activated -
"Objects in your pack cannot be activated". Belts come in 2 and 3 slots
commonly, and a 10-slot **Utility Belt** is rare and precious. The manual's own
justification is the best argument for the mechanic: "Digging through your pack
for that scroll of teleportation while the Ancient Red Dragon is breathing down
your neck (literally) is a good recipe for roast adventurer."

Weapon, Belt and Ready-hand slots take any object type; every other slot is
type-restricted. Containers may not be nested circularly.

## Identification has four distinct mechanisms

- **Class identify**: identify one of a type and you recognise all others of
  that type ever after - though not how many charges a wand has left.
- **Identify on use**: using it tells you what it is.
- **Identify on wield**: most armour and weapons.
- The **Sage** identifies for a fee: drag the object into the sage's window and
  he quotes a price.

A popup always shows name, weight and bulk; an identified object also lists its
properties, each in three parts - **what you must do** (wield or activate),
**what it does**, and **how long it lasts** ("until removed", "for a period of
time", or "permanently").

Cursed items "may summon monsters, lower your attributes, or decrease your
prowess in combat", are usually disguised as enchanted, and **cannot be removed
until the curse is lifted**.

There is a lovely deliberate design note about the temple: Remove Curse is the
one service never greyed out, "since it would give the player hints about
unidentified objects to gray it".

## Attributes, precisely

- **Strength**: damage per hit, carrying capacity, and it gates what armour you
  can wear at all.
- **Intelligence**: mana, and a better chance of disarming traps.
- **Constitution**: hit points.
- **Dexterity**: armour value, chance to hit, and chance to disarm traps.

The chargen bars show three lines - an average person in the middle, and the
minimum and maximum you may start at. And the manual gives strategic advice
that is really a statement about the maths: "characters with above average
abilities in an area receive bonuses, so it is usually to your advantage to
improve your character's abilities in one area, rather than being equal in all
of them and not receiving bonuses from any of them." Specialising beats
spreading. **Implemented**: intelligence now contributes to disarming.

## Coinage

Four metals, all quoted in copper: silver is 10, gold is 100, and platinum is
1000 "quite rare" copper. Since a coin weighs a gram, this is also the answer
to carrying a fortune - a thousand copper is a kilogram, one platinum piece is
a gram. **Implemented.**

## Traps

"A known trap is **less likely** to go off" - less likely, not impossible. Ours
made a found trap perfectly safe. **Implemented** as a small chance, reduced by
dexterity. Searching may need several attempts, and disarming "you may have to
try more than once to be successful, and you run the risk of setting the trap
off". Levitation avoids the gravity-operated ones.

## Sites you can use

**Fountains** and **thrones** are site-specific verbs, and both "can have
beneficial or harmful effects, or may do nothing at all". Neither exists in
ours.

## Interface details worth copying

- **Drag the player icon to walk**; mouse movement aborts if you are attacked
  or hit a trap.
- **Double-click yourself** to take the stairs. Left click an adjacent door to
  open or close it, a monster to attack it.
- **Right click anything, anywhere** - dungeon, map or inventory - for a popup
  description. On a monster it gives the condition words. Capped at 10 lines,
  with "more ..." pointing you at the keyboard version.
- Targeting uses a **crosshair cursor** with a "Command Pending" message.
- **Shift-Enter** is the keyboard popup; **Tab** moves between inventory
  windows; objects move by Enter to pick up, move the cursor, Enter to drop.
- The description window keeps about **30 messages** of scrollback, and the
  three windows are resizable by dragging the dividers.
- Time exists on the status line to let you track spell durations and
  **item recharge** - some items work "once per day or once every few hours".
- You may **rename your character** mid-game, "adding such descriptions as you
  feel you deserve (the bold, the mighty)".
- Fast Map draws objects as a dagger, monsters as a frowning face, stairs as
  arrows, everything else as an asterisk.

## Still not adopted

The armour value ladder (task #27) and thieves (task #29). Both are recorded
above with reasons.
