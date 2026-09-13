# Stormhold

A co-operative dungeon crawl for the family, built to be played over a home
network. One computer runs the keep; everyone else opens a web address. There is
nothing to install on the other machines — no client, no accounts, no internet.

It is a fresh, original game written in the spirit of the early-90s Windows
shareware roguelikes: a town with shops, a staircase down into a twenty-level
dungeon, a pack full of loot, and a party that has to stick together.

```
   ┌─ Aldershade ─────────────────────────────────────────────┐
   │  Doran the Smith   ▓▓▓▓   the keep gate   ▓▓▓▓  Sister   │
   │  Wren, Apothecary            ↓                   Halli   │
   └──────────────────────────────────────────────────────────┘
                twenty levels down, two bosses, one way home
```

## Running it

You need [Node.js](https://nodejs.org) 18 or newer on the machine that will host
the game. Nothing else — the server has **no dependencies at all**.

```sh
node server/index.js
```

It prints the addresses to use:

```
   ====================================================
     S T O R M H O L D   -   the keep is open
   ====================================================

   On this computer:      http://localhost:3000

   From other machines on the same network:
     en0        http://192.168.1.24:3000

   Open that address in any browser. Nothing to install.
```

Everyone else on the same wifi opens that `192.168.x.x` address in a browser —
a laptop, a tablet, an old iPad, whatever is in the house. Pick a name, pick a
class, and you are in the same dungeon.

### Options

| Flag | What it does |
| --- | --- |
| `--port=3000` | Port to listen on. |
| `--host=0.0.0.0` | Interface to bind. The default serves the whole network. |
| `--seed=12345` | Fix the world seed so the dungeon is the same every run. |
| `--help` | Print usage. |

Stop the server with `Ctrl+C`; every character is saved on the way out.

## Playing

| Key | Action |
| --- | --- |
| Arrows / `W A S D` | Move. Walk into a monster to attack it. |
| `Space` or click | Attack in the direction you face. Bows and staves fire. |
| `1` `2` `3` | Your three class abilities. |
| `E` or right-click | Stairs, shopkeepers, and helping a downed friend up. |
| `Q` | Drink the healing potion that best fits the wound. |
| `I` | Open your pack. Click an item to equip, drink or read it. |
| `M` | Show or hide the small map. |
| `Enter` | Chat with the party. |
| `F` | Full screen. |

On a tablet, a thumb-stick and buttons appear as soon as you touch the screen.

### The three classes

- **Warrior** — tough and fearless. *Cleave* hits everything around you,
  *Bulwark* halves incoming damage, *Charge* closes the gap and knocks a monster
  backwards.
- **Ranger** — quick, fights at range. *Volley* looses three arrows, *Snare*
  pins something in place, *Dash* leaps out of trouble.
- **Mage** — fragile, but throws fire and patches the party up. *Firebolt*
  bursts on impact, *Frost Nova* freezes everything nearby, *Mend* heals every
  friend around you.

### Co-operation is the point

- **Nobody dies alone.** At zero health you are *down*, not dead. A friend
  standing next to you holds `E` for three seconds and you are back up. You have
  just over a minute before it becomes permanent, so there is real tension
  without anyone losing an evening's progress.
- **Experience is shared** with everyone nearby, so there is no reason to steal
  kills from a younger sibling.
- **The party travels together.** Stand on the stairs and press `E`: it starts a
  five-second countdown and then moves *everyone on the level*, so nobody gets
  lost or left behind.
- **A wipe is not a disaster.** If the whole party goes down, Sister Halli drags
  you home to Aldershade and charges a tenth of your gold for the trouble.
- **The dungeon gets harder with more players** — monsters are tougher and more
  numerous with a bigger party, so three people is not three times as easy.

### Town

The keep gate is at the top of the road, north of the square.

- **Doran the Smith** — weapons and armour. His stock refreshes each time the
  party comes home, and gets better as you go deeper.
- **Wren the Apothecary** — potions and scrolls.
- **Sister Halli** — a full heal and cure, for coin.

### Going deep

Twenty levels. *The Warden of Ash* waits on level 10 and *Vaelrik, the
Storm-Bound* on level 20. Themes shift as you descend — the Cellars, the Flooded
Vaults, the Bone Gallery, the Deep Warrens, and finally the Stormworks. Some
levels hide a vault: a sealed room with far better loot and far worse company.

When you come back to town the keep gate remembers the deepest level your party
has reached, so you never have to walk back down through cleared floors.

## Characters are saved

Characters persist in `data/players.json`, keyed by name and class, and save on
disconnect, on shutdown, and every thirty seconds. Next time the server starts,
the lobby offers everyone their character back. Delete that file to start the
family over.

## Project layout

```
server/
  index.js        http + static files + the tick loop
  ws.js           a small RFC 6455 WebSocket server (this is why there are no deps)
  net.js          sessions, the wire protocol, per-player fog of war
  persist.js      character saves
  game/
    world.js      the simulation: turns, combat, loot, shops, descending
    level.js      dungeon generation and the town
    actors.js     players, monsters, derived stats
    ai.js         monster behaviour and A* pathfinding
    combat.js     to-hit, damage, knockback, status effects
    items.js      item tables, affixes, the loot generator
    monsters.js   the bestiary
shared/           code used by both sides: constants, protocol, rng, field of view
client/
  index.html      lobby and game shell
  css/style.css   the chrome
  js/
    main.js       boot and the frame loop
    render.js     canvas renderer, lighting, minimap
    sprites.js    every sprite, drawn in code — there are no image files
    ui.js         sidebar, pack, shops
    audio.js      all sound effects, synthesised in the browser
    input.js      keyboard, mouse, touch
    net.js        websocket client with reconnect
test/             unit and network tests
```

All artwork is drawn at runtime from rectangles on a pixel grid, and every sound
is synthesised with WebAudio, so the whole game is the source you see here.

## Tests

```sh
npm test
```

34 tests covering level connectivity at every depth, field of view,
pathfinding, combat maths, levelling, inventory and equipment, the revive and
party-wipe rules, descending together, shops, projectiles, fog of war, and the
WebSocket implementation (handshake, all three frame length encodings, UTF-8,
ordering, concurrent clients).

## Troubleshooting

**Other computers cannot connect.** The host's firewall is the usual culprit —
allow Node to accept incoming connections on the port. Make sure everyone is on
the same wifi, and that it is not a "guest" network, which usually blocks
devices from seeing each other.

**"Port 3000 is already in use."** Run `node server/index.js --port=3001`.

**The page looks stale after an update.** Reload with `Ctrl+Shift+R`.

**Someone's screen is frozen.** The client reconnects on its own within a few
seconds. If not, reload the page; the character is safe on the server.

## A note on the inspiration

This project was prompted by a copy of *Castle of the Winds* (Rick Saada, 1993).
That game is its author's work, and its art, text and names belong to him, so
nothing was taken from it: no resources were extracted from the binary, and none
of its content appears here. Stormhold is a new game with its own town, its own
bestiary, its own items and its own artwork, written because that *kind* of game
is worth having again — and this one lets you play it with your kids in the next
room.

## Licence

MIT.
