# How hard is the keep?

Measured with `tools/balance.py`, which calls the game's own combat code
rather than a model of it. A character is dressed the way somebody who got
that deep plausibly would be, stands toe to toe, and fights until one side is
down. No potions, no spells, no retreating up a corridor, no doors to shut.
A death counts as a loss even though the temple hands the character back,
because in the middle of a fight it is one.

Read these as the worst case, not as how hard the game plays. A person
retreats, drinks, casts and shuts doors, and all four of those are missing
here. What the numbers are good for is comparing floors with each other, and
comparing party sizes.

## One person, gear at +4 on everything

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

In plain, unenchanted gear the same character is at 35% on floor 17, 2% on
floor 20 and 0% from floor 23 down.

## The two bosses

    party of 1   party of 2   party of 3   party of 4
    The Warden of Ash (floor 12)
          0%          15%          80%         100%
    Vaelrik, the Storm-Bound (floor 25)
          0%           0%          15%          95%

## What this says

The keep is tuned as a game for three or four. Solo it is comfortable to
about floor 14, demands near-perfect gear from floor 17, and the last
stretch and both bosses cannot be won alone at any equipment level we can
actually generate - the best gear the item tables produce is about +4.

Two reasons, and they compound:

- **A character's damage barely grows.** It is the weapon's dice plus a
  Strength bonus plus the enchantment, so the best realistic swing is around
  fourteen. Levels buy accuracy and hit points, never damage.
- **Creatures' hit points grow steeply.** `scaled()` adds 9% per floor below
  a creature's home floor, on top of bases that already reach 240, so an Iron
  Revenant met at floor 23 has about 350 and Vaelrik has 1500.

Whether that is a problem depends on what the game is for. For a family of
three or four playing together it is roughly right and the bosses are real
events. For one person, or a parent testing alone, the back half is a wall.

Nothing here has been re-tuned. The numbers are written down so the decision
can be made deliberately.

## Regenerating these

    python3 tools/balance.py --difficulty Intermediate --enchant 4 --party 1
    python3 tools/balance.py --party 3 --trials 25
