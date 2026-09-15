# Stormhold

A turn-based co-operative dungeon crawl for the family, played over the home
network. One computer hosts; everyone else joins from the same program. It runs
on Windows, macOS and a Raspberry Pi 400.

It is an original game written in the spirit of the early-90s Windows
shareware roguelikes: a town of seven trades, a staircase into twenty-five
floors of keep, a pack that fills up with things you cannot yet identify, and a
party that has to stay together.

```
   Aldershade
   ┌──────────────────────────────────────────────────────────┐
   │  Bolgar  Hesta  Pell        ▲ the keep gate       Ulric   │
   │                                                  Halli   │
   │                    the strongroom                        │
   └──────────────────────────────────────────────────────────┘
        twenty-five floors down, two things worth fearing
```

## Running it

You need Python 3.8 or newer. The only dependency is pygame.

**Windows** — double-click `play.bat`.
**macOS, Linux, Raspberry Pi** — run `./play.sh`.

Either script installs pygame the first time and then starts the game. If you
would rather do it by hand:

```sh
python -m pip install pygame-ce
python -m stormhold
```

### Playing together

One person clicks **Host a game**. The message log then shows the address the
others need, something like `192.168.1.24`. Everybody else starts the same
program, types that address into **Server address**, and clicks **Join a game**.

To leave a server running without a game window on it - handy on a Pi tucked
behind the telly:

```sh
python -m stormhold --serve
```

| Flag | What it does |
| --- | --- |
| `--serve` | Run a server with no game window. |
| `--port 7777` | Port to use. |
| `--seed 12345` | Fix the world seed, so the keep is the same every time. |
| `--save PATH` | Where to keep characters (default `data/party.json`). |
| `--fullscreen` | Start full screen. |

## How it plays

**It is turn-based.** Nothing in the keep moves until you do. There is no
timer, no twitch, and no penalty for thinking. A seven-year-old can take as
long as they like over a decision.

With several players the floor keeps one clock. Everyone's actions cost time
and slot into the same order, and the floor will run about two turns ahead of
somebody who has not moved yet before it stops and says **"Waiting for Mia…"**.
Pausing to think costs nobody anything. If a player genuinely wanders off, after
three quarters of a minute their character simply holds still and the rest of
the party carries on without them.

There is nothing to be fair about in town, so nobody ever waits there.

### Keys

| Key | Action |
| --- | --- |
| Arrows, numpad, or `W A S D` | Move. Walk into something to attack it. |
| Numpad `7 9 1 3` | The diagonals. |
| `5` or `.` | Wait one turn. |
| `G` or `,` | Pick up what is under you. |
| `I` | Pack: wear, wield, drink, read, drop. |
| `Z` | Cast a spell. |
| `F` | Fire a bow or crossbow at the nearest enemy. |
| `>` / `<` | Take a staircase you are standing on. |
| `C` | Character sheet. |
| `Enter` | Talk to the party. |
| Click the map | Step that way, or attack what you clicked. |
| `F1` | Help. `Esc` closes a window or opens the menu. |

### There are no character classes

You get four numbers and sixteen points to spread across them.

- **Strength** carries armour and swings it hard.
- **Dexterity** hits more often and is harder to hit.
- **Intelligence** is your mana and the spells you may learn.
- **Constitution** is health, and how fast it comes back.

Put it all in Strength and you are a warrior. Put it in Intelligence and buy
tomes and you are a mage. Nothing stops you changing your mind later; the
character you end up with is the one your choices made.

Magic is learned from books. The Gilded Retort sells tomes and they turn up in
the keep. Read one and the spell is yours for good - if you are experienced and
clever enough for it. There are twenty-seven spells across five schools.

### Weight is a real decision

Everything has a weight, including your gold: a hundred coins weigh a pound.
Carry too much and every step takes longer, which means every monster on the
floor gets more turns than you do. That is what the **strongroom** is for, and
why plate armour is not obviously better than leather.

### Things you find are not labelled

A potion is "a cloudy red potion" until you drink one or pay Ulric to identify
it, and which colour is which is shuffled every new world. Some rings are
cursed and will not come off until the temple breaks the binding. Weapons and
armour hide their enchantment until you learn it.

### Death

You die properly. You drop your pack where you fell, lose a fifth of the gold
you were carrying and a tenth of your experience, and wake on the temple floor
in Aldershade. The rest of the party fights on without you, and your pack is
still lying there if somebody can reach it.

## Town

| Who | What they do |
| --- | --- |
| Bolgar the Weaponsmith | Weapons, arrows and quarrels. |
| Hesta the Armourer | Armour, shields, helms and boots. |
| Pell's General Store | Packs, sacks, purses, belts, cloaks, boots. |
| The Gilded Retort | Potions, scrolls, and tomes to learn spells from. |
| Ulric the Sage | Tells you what a thing really is. |
| Temple of the Quiet Hour | Heals, cures, and breaks curses. |
| The Strongroom | Holds your gold so you do not have to carry it. |

The keep gate is at the head of the north road. It remembers the deepest floor
your party has reached, so you never re-walk ground you have cleared.

## Performance on a Pi 400

The game only redraws when something changes, and because it is turn-based
nothing changes unless somebody acts. All the artwork is drawn once at start-up
into 32-pixel tiles and blitted from there. A Pi 400 hosting for three players
spends almost all of its time idle.

## Where things are

```
stormhold/
  __main__.py        start here
  common/            constants, field of view, shared vocabulary
  game/
    world.py         the clock, the scheduler, and every action
    level.py         the keep, and Aldershade
    actors.py        characters and creatures
    items.py         weight, curses, identification
    spells.py        the spell list
    monsters.py      the bestiary
    combat.py        to-hit, damage, knockback
    ai.py            monster behaviour and pathfinding
  net/
    server.py        authoritative server
    client.py        socket client
    protocol.py      length-prefixed JSON
  ui/
    app.py           menus, character creation, the play screen
    art.py           every sprite, drawn in code
    palette.py       the sixteen colours and the dithering
    widgets.py       window chrome
tests/               33 tests
tools/contact_sheet.py   renders every sprite to one PNG
```

## The artwork

There are no image files. Every tile, creature and item is drawn at start-up
from rectangles, restricted to the sixteen VGA colours that a Windows 3.1 icon
was allowed, with ordered dithering for anything in between and a hard black
outline around everything. `python tools/contact_sheet.py sheet.png` renders
the lot to one picture.

## Tests

```sh
python -m unittest discover -s tests
```

Thirty-three tests covering every floor's connectivity, field of view,
pathfinding, encumbrance, the turn scheduler (including that the world does not
move on its own, that it waits for a player who has not acted, and that an
absent player cannot strand the party), combat maths, curses, identification,
death, shops and the wire protocol.

## A note on the inspiration

This was prompted by a copy of *Castle of the Winds* (Rick Saada, 1993). That
game is its author's work: nothing was taken from it, no resources were pulled
out of the binary, and none of its artwork, text, items, spells or creatures
appear here. What is borrowed is the shape of the thing - turn-based, class-
less, weight that matters, a town you keep coming back to - because that shape
is worth having again, and this one you can play with your kids in the next
room.

## Licence

MIT.
