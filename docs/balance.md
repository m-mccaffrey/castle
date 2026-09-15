# How hard is the keep?

Three instruments, in increasing order of realism and decreasing order of
how often you can afford to run them.

- **`tools/balance.py --play`** — one fight, through the game's own combat
  code, with the spells and potions a character could own.
- **`tools/balance.py --floors`** — the worst knot of creatures the level
  generator actually puts on each floor, against the character you would
  actually be there, fought in the open and fought in a doorway.
- **`tools/campaign.py`** — the whole keep, floor by floor, every decision
  going through `World.submit`, so the monster AI, the ranged attacks, the
  boss specials, the traps, the wandering monsters and the shared floor
  clock are all the real ones. Nothing in it models the game; it plays it.

A death counts as a loss even though the temple hands the character back,
because in the middle of a fight it is one.

## What a character actually is, floor by floor

Two things had been guessed, and both guesses were wrong in ways that made
every other number wrong.

**Level.** The old assumption was `level = depth + 1`. Counting the
experience the generator actually puts on the floors above, and sharing it
the way `kill` does, a solo character is level 15 on floor 12 and hits the
level cap on floor 21. A party of four is about three levels behind that per
head - not the nine you would expect, because experience is shared at
`xp / (heads x 0.8)` and a bigger party meets half again as many creatures.

**Gear.** There used to be a hand-written table of what seemed about right.
Set it low and the early floors looked impossible; set it high and the whole
keep looked like a walk. Both happened, a few hours apart. `equip_like` now
spends a real purse - the copper the floors above this one actually contain,
seventy per cent of it, the rest going on potions, the temple, and what you
drop when you die - at the shop's real prices, covering every slot before
upgrading any.

## The worst knot on each floor, one person, Intermediate

Not the typical resident: the typical resident is not what kills you. The
worst knot on each of fifteen generated floors, and the median of those.

    floor  lvl    hp   AV   open  doorway  what is standing there
        1    1    19    3   100%     100%  2x cave bat, cave rat
        2    2    23   10    58%     100%  2x goblin
        3    4    31   11    50%     100%  3x goblin, shambler
        4    5    35   20   100%     100%  3x cutpurse, goblin
        5    6    45   28    75%     100%  4x goblin
        7    8    55   67   100%     100%  5x goblin, shambler
        9   10    65   76    92%     100%  4x dire wolf
       11   12    76   79   100%     100%  4x dire wolf
       13   15    91   79   100%     100%  4x dire wolf
       15   18   107   80   100%     100%  1x stone golem
       17   21   122   98   100%     100%  2x stone golem, storm wisp
       19   24   137   98    92%     100%  2x ember drake
       21   28   158   98   100%     100%  2x ember drake, iron revenant
       23   30   168   98   100%     100%  2x iron revenant, stone golem
       25   30   198   99    33%      33%  2x storm sorcerer, Vaelrik

The gap between the two columns is the whole game. A doorway turns every
fight in the keep from a mobbing into a duel, because it decides how many of
them get to swing at you each turn. It is the one thing a person does that a
number does not, and it is why a table of "toe to toe in the open" - which is
what this file used to contain - said the back half of the keep was
unwinnable when it is not.

## What was changed, and why

**Packs arrive as scouting parties on the floor they first live on.** A
creature met at its minimum depth used to turn up at full pack strength. Four
dire wolves in the open on floor 4, against the character you are on floor 4,
measured 0% across fifteen fights. Full strength now arrives once you are
three floors into the creature's range. Floors 1-5 went from 0-13% in the
open to 58-100%.

**Nothing hires a guard from below its own floor.** Goblins can hire a
Shambler, and a Shambler lives from floor 3 down - so a goblin pack on floor 2
came with a creature a whole band out of place, in front of a character with
nineteen hit points.

**The Warden of Ash lost two hundred hit points**, 560 to 340. At 560 it was
0% for one person across twenty fights - a hard gate at floor 12, which is
where a character is at their weakest relative to what is in front of them.
The floor-12 boss was harder than the floor-25 one.

**A boss now scales against a party in more than health.** It used to gain
half its health again per extra person, and nothing else. But a boss is
outnumbered in the currency that decides a fight, which is actions: four
people get four swings to its one. Four walked over both bosses while one
person could not touch either. It now gains 90% health, +2 damage and a
shorter turn per extra head, which is what holds the odds steady.

    boss                      party 1   party 2   party 3   party 4
    The Warden of Ash (12)        67%       79%       67%       62%
    Vaelrik (25)                  79%       75%       62%       96%

Read those as upper bounds: `fight_well` does not model the summoned guard
or the ground-slam, and both bosses have them.

## Can any number of people finish it?

Yes, and a bigger party has an easier time of it. `populate` puts half again
as many creatures on a floor per extra person and makes each 45% tougher, but
those are spread over the whole floor while the party arrives at each fight
together. Against the worst knot on a floor, parties of two and up are at
or near 100% everywhere.

The cost of a bigger party is pace, not danger: shared experience puts each
head about three levels behind a solo character at the same depth.

For a family that wants more bite than that, the difficulty setting is the
dial, and it has real range. On floor 3, against the same knot, in the open:

    Easy 92%    Intermediate 50%    Difficult 0%

## What is not measured

- `fight_well` fights in a clear space. It does not model summons, boss
  ground-slams, knockback, poison ticking between fights, or a corridor that
  bends.
- The campaign simulator is an average player, not a good one: it does not
  lure, does not read a scroll when things go wrong, and buys spell books
  last. It currently gets a solo character to about floor 3 and a party of
  four to about floor 5 before the deaths mount up. That is a floor under the
  game's difficulty, not a ceiling - the fight tables above are the ceiling,
  and the truth is between them.
- Nothing here measures whether the game is *fun*, which is the only
  question that actually matters and the only one a person has to answer.

## Regenerating these

    python3 tools/balance.py --floors --party 1 --trials 15
    python3 tools/balance.py --floors --party 0        # one table per size
    python3 tools/balance.py --bosses --trials 24
    python3 tools/balance.py --play --enchant 2
    python3 tools/campaign.py --all-parties --runs 2 --depth 8
