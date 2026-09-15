# How hard is the keep?

Measured with `tools/balance.py`, which calls the game's own combat code
rather than a model of it. A death counts as a loss even though the temple
hands the character back, because in the middle of a fight it is one.

There are two measurements here, and the difference between them is the
whole point.

- **Toe to toe** (the default): stand and swing until one side is down. No
  potions, no spells, no retreating up a corridor, no doors to shut. This is
  the worst case, not the game.
- **Played properly** (`--play`): the same fight, with the spells a character
  of that level could have learned and a belt of potions, all of it going
  through `do_player_action` so it obeys the game's own rules - real mana
  costs, real ranges, real elemental resistances.

## Toe to toe, one person, gear at +4 on everything

    floor  lvl   hp   AV    1 foe  2 foes  3 foes  typical resident
        1    2   23   14    100%   100%   100%  Cave Rat
        3    4   31   14    100%   100%    98%  Cave Rat
        5    6   45   35    100%    95%    65%  Goblin
        8    9   60   47    100%    92%    20%  Rattling Bones
       11   12   76   65    100%    70%     5%  Orc Raider
       14   15   91   62    100%    48%     0%  Clockwork Sentry
       17   18  107   63     60%     0%     0%  Moss Troll
       20   21  123   81    100%    12%     0%  Storm Sorcerer
       23   24  138   81      5%     0%     0%  Iron Revenant
       25   25  168   82     18%     0%     0%  Iron Revenant

## Played properly, one person, gear at only +2

Spark and Fireball, three healing potions and two mana potions:

    floor    1 foe  2 foes  3 foes  typical resident
        1     100%   100%   100%  Cave Rat
        5     100%   100%   100%  Goblin
       11     100%   100%   100%  Orc Raider
       14     100%   100%   100%  Clockwork Sentry
       17     100%    95%    25%  Moss Troll
       20     100%   100%    95%  Storm Sorcerer
       23     100%    15%     0%  Iron Revenant
       25     100%    35%     0%  Iron Revenant

Floor 23 goes from 5% to 100% against a single Iron Revenant, on *worse*
gear. The gap between the two tables is not a rounding error; it is the
difference between the game as it is and the game as an earlier version of
this file measured it.

## What changed the answer

**A character's weapon damage barely grows.** It is the weapon's dice plus a
Strength bonus plus the enchantment, so the best realistic swing is about
fourteen. Levels buy accuracy and hit points, never weapon damage.

**Spell damage grows with every level.** `_act_cast` sets `power = p.level`,
and every attack spell has a per-level term: Sunburst is `5d8 + 1.4 x level`,
which is 57 at level 25 against that fourteen. Spells are the only damage in
the game that keeps up with `scaled()`, which adds 9% to a creature's hit
points for every floor below its home floor.

So the answer to "can one person finish the keep" is really "can one person
get the books", which is why `generate_item` now drops them. Before that,
the only spell books in the world were the four on the magic shop's shelf -
restocked each visit, four of thirty-six spells - while the character
creation screen told the player they would find them in the keep.

Two gates worth knowing about: Sunburst needs Intelligence 19 and character
creation caps a stat at 18, so it wants a Ring of Wit; and packs of three
deep-floor creatures are still lethal, which is what corridors and doorways
are for and what this instrument cannot measure.

## The two bosses

Played properly, at +2 gear with three healing and two mana potions:

    party of 1   party of 2   party of 4
    The Warden of Ash (floor 12)
          0%          50%         100%
    Vaelrik, the Storm-Bound (floor 25)
          0%          20%         100%

Solo they stay out of reach. At +4 gear with eight of each potion the Warden
comes in at 10%; Vaelrik needs +6 gear and ten of each to reach 25%, and +6
is past what the item tables generate. Hit-and-run is the obvious answer and
it is not modelled here. Both bosses act faster than an unhasted character
(the Warden's speed is 95 and Vaelrik's 85 against a character's 100, and a
lower number is a shorter turn), so walking away from one does not work -
but Haste halves a character's action cost, which would. That is untested.

Both bosses are, as measured, party fights. Whether that is right is a
design decision - this file only says what is true today.

## Regenerating these

    python3 tools/balance.py --difficulty Intermediate --enchant 4 --party 1
    python3 tools/balance.py --play --difficulty Intermediate --enchant 2 --trials 20
