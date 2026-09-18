"""Play the game and check, after every single action, that it still adds up.

The bugs this project keeps shipping are not bugs in a feature. They are
drifts between two things that are supposed to agree:

  * what the server says you are carrying, and what the pack window draws
  * what the server says your hit points are, and what the status panel says
  * what the server has shown you of the floor, and what the map remembers
  * what a shop offers, and what it pays

Each of those was found by a person playing, not by a test, because every
test we had asked one question about one function. This asks the same short
list of questions after every action in a long game, which is the shape a
player's complaint actually has: "I did a load of things and then the
numbers were wrong."

    python3 tools/soak.py                 # one character, 600 actions
    python3 tools/soak.py --seeds 5 --actions 1500
    python3 tools/soak.py --seed 12 --verbose

It plays at about a second an action once a character starts dying and
walking back down, so a few hundred actions is a coffee and a few thousand
is a lunch. `tests/test_sync.py` runs the first sixty of it on every test
run; the long version is for before a release, or after touching anything
that both sides of the wire care about.

It plays through the real client: keys and clicks go through App.dispatch,
and every reading it checks comes from the window rather than the engine.
"""

import argparse
import os
import random
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame                                                     # noqa: E402

from stormhold.game.items import Item                             # noqa: E402
from tools.playtest import Session, free_port                                # noqa: E402
from tools import crawl as C                                      # noqa: E402


class Drift(Exception):
    """Two things that should agree, and do not."""


# --------------------------------------------------------------- the checks --
def carried(server_player, appearances):
    """What the server says is in the pack, as plain rows."""
    return sorted((i.key, i.qty) for i in server_player.inventory)


def shown(client_inventory):
    """What the pack window is drawing, as the same plain rows."""
    return sorted((i["key"], i["qty"])
                  for i in (client_inventory or {}).get("items", []))


def check_pack(s):
    p = s.me()
    mine = carried(p, None)
    theirs = shown(s.app.inventory)
    if mine != theirs:
        only_server = [r for r in mine if r not in theirs]
        only_client = [r for r in theirs if r not in mine]
        raise Drift(f"the pack window disagrees with the pack: "
                    f"carried but not shown {only_server}, "
                    f"shown but not carried {only_client}")


def check_worn(s):
    p = s.me()
    mine = {slot: (item.key if item else None)
            for slot, item in p.equipment.items()}
    theirs = {slot: (item["key"] if item else None) for slot, item
              in ((s.app.inventory or {}).get("equipment") or {}).items()}
    if theirs and mine != theirs:
        wrong = {k: (mine.get(k), theirs.get(k)) for k in mine
                 if mine.get(k) != theirs.get(k)}
        raise Drift(f"the paper doll disagrees with what is worn: {wrong}")


def check_vitals(s):
    p = s.me()
    you = s.app.play.you or {}
    if not you:
        return
    for label, mine, theirs in (("hit points", max(0, int(p.hp)), you.get("hp")),
                                ("mana", int(p.mana), you.get("mana")),
                                ("copper", p.copper, you.get("copper")),
                                ("level", p.level, you.get("level")),
                                ("depth", p.depth, you.get("depth"))):
        if theirs is not None and mine != theirs:
            raise Drift(f"the status panel says {label} is {theirs}, "
                        f"the game says {mine}")


def check_map(s):
    """Every square the server has shown this player must be on the client's
    map. This is the check the Lantern spell failed for its whole life."""
    play = s.app.play
    p = s.me()
    if play.map is None or play.map.depth != p.depth:
        return
    level = s.world.levels.get(p.depth)
    memory = s.world.memory_for(p, level)
    missing = sum(1 for i, seen in enumerate(memory)
                  if seen and not play.map.known[i])
    if missing:
        raise Drift(f"{missing} squares the game has shown you are not on "
                    f"the client's map")


def check_shop(s):
    """A price in a shop window is a promise. Check it against the till."""
    scene = s.app.scene
    if type(scene).__name__ != "StoreScene":
        return
    world, p = s.world, s.me()
    shop = scene.shop
    for row in scene.data.get("sell", []):
        item = p.find_item(row["id"])
        if item is None:
            continue
        would_pay = world.sell_offer(shop, item)
        if row.get("price") != would_pay:
            raise Drift(f"{shop} is offering {row['price']} for "
                        f"{item.key} and would pay {would_pay}")


CHECKS = (("pack", check_pack), ("worn", check_worn), ("vitals", check_vitals),
          ("map", check_map), ("shop", check_shop))


# ---------------------------------------------------------------- the play --
# Weighted so that most of the time is spent walking and fighting, which is
# what a player does, with the fiddly things sprinkled through it.
MOVES = [pygame.K_h, pygame.K_j, pygame.K_k, pygame.K_l,
         pygame.K_y, pygame.K_u, pygame.K_b, pygame.K_n]
VERBS = [pygame.K_g, pygame.K_s, pygame.K_o, pygame.K_c, pygame.K_i,
         pygame.K_x, pygame.K_m, pygame.K_v, pygame.K_f, pygame.K_d,
         pygame.K_z, pygame.K_r, pygame.K_ESCAPE, pygame.K_RETURN]


class Soak:
    def __init__(self, seed, actions, verbose=False, port=None):
        port = port or free_port()
        self.rng = random.Random(seed)
        self.seed, self.actions, self.verbose = seed, actions, verbose
        self.s = Session(seed=seed, port=port, size=(1280, 800))
        C.make_character(self.s, spell="Spark", difficulty="Intermediate")
        # Start underground. Wandering at random almost never finds the
        # stairs out of town, and the floor the bugs turn up on is the first
        # one down.
        # A character with an empty pack cannot exercise a pack check, and
        # a fresh one is nearly empty, so kit out first the way the crawl
        # bot does - it is what a player does before going down anyway.
        try:
            C.kit_out(self.s)
        except Exception:                                     # noqa: BLE001
            pass
        C.dive_back(self.s, 1)
        self.s.settle(1.0)
        self.faults = []
        self.done = 0

    def step(self):
        """One thing a player might do."""
        # Walking at random almost never lands on a thing, and a soak that
        # never picks anything up never exercises the pack - which is where
        # every drift reported from play has been so far.
        here = self.s.world.levels[self.s.me().depth].items_at(
            self.s.me().x, self.s.me().y)
        if here:
            self.s.key(pygame.K_g)
            return "get what is underfoot"
        if self.rng.random() < 0.10:
            found = self.walk_to_something()
            if found:
                return found
        # Dying sends you back to the temple, and a character wandering the
        # town square is not exercising anything. Go back down.
        if self.s.me().depth == 0 and self.rng.random() < 0.25:
            # Walk to the stairs rather than calling the crawl bot's
            # dive_back, which rests to nine tenths of full first and turns
            # one action into a minute of wall clock.
            return self.find_the_stairs()
        roll = self.rng.random()
        if roll < 0.62:
            key = self.rng.choice(MOVES)
            shift = pygame.KMOD_LSHIFT if self.rng.random() < 0.12 else 0
            self.s.key(key, mod=shift)
            return f"walk {pygame.key.name(key)}"
        if roll < 0.90:
            key = self.rng.choice(VERBS)
            self.s.key(key)
            return f"press {pygame.key.name(key)}"
        if roll < 0.93:
            return self.fiddle_with_the_pack()
        if roll < 0.95:
            # Click somewhere on the map, the way a mouse player moves.
            view = self.s.app.play.viewport(self.s.app.screen)
            pos = (self.rng.randrange(view.x, view.right),
                   self.rng.randrange(view.y, view.bottom))
            self.s.click(pos)
            return f"click the map at {pos}"
        return self.find_the_stairs()

    def fiddle_with_the_pack(self):
        """Open the pack and move something about.

        Dropping and picking back up is the exact motion that showed the
        window and the game disagreeing, so the soak has to do it rather
        than wait to stumble over loot.
        """
        self.s.key(pygame.K_i)
        self.s.settle(0.3)
        scene = self.s.app.scene
        if type(scene).__name__ != "PackScene":
            return "tried to open the pack and got somewhere else"
        scene.draw(self.s.app.screen)
        # Everything the window will let you select: loose in the pack, on
        # the belt, and worn. Only looking at the pack is how a Drop button
        # that was broken for the belt and for the body went unnoticed.
        cells = list(scene.cell_rects) + list(scene.stow_rects)
        cells += [(rect, worn) for slot, rect in scene.slot_rects.items()
                  if (worn := scene.equipment().get(slot))]
        if not cells:
            self.s.key(pygame.K_ESCAPE)
            return "opened an empty pack"
        rect, item = self.rng.choice(cells)
        scene.selected = item
        scene.draw(self.s.app.screen)
        what = self.rng.choice(("drop", "use", "sort"))
        for button in scene.buttons:
            if button.action == what and button.enabled:
                before = self.fingerprint()
                said = len(self.s.app.play.messages)
                self.s.click(button.rect.center)
                self.s.settle(0.4)
                # An enabled button must do something or say why not. Both
                # of the last two bugs reported from play were this: Drop
                # was offered for a potion on your belt, did nothing, and
                # said nothing, which reads as a broken game rather than a
                # rule. Nothing about the pack window can tell you which.
                if (self.fingerprint() == before
                        and len(self.s.app.play.messages) == said):
                    self.s.key(pygame.K_ESCAPE)
                    raise Drift(f"the pack's {what.title()} button was enabled "
                                f"for {item['name']}, and pressing it changed "
                                f"nothing and said nothing")
                self.s.key(pygame.K_ESCAPE)
                return f"{what} {item['name']} from the pack"
        self.s.key(pygame.K_ESCAPE)
        return f"opened the pack and could not {what}"

    def fingerprint(self):
        """Everything the character is carrying, as one comparable value."""
        p = self.s.me()

        def one(item):
            return (item.id, item.key, item.qty, item.enchant,
                    tuple((c.id, c.qty) for c in (getattr(item, "contents", None) or [])))
        return (tuple(one(i) for i in p.inventory),
                tuple((slot, one(i) if i else None)
                      for slot, i in sorted(p.equipment.items())),
                p.copper, p.bank, int(p.hp), int(p.mana), p.x, p.y, p.depth)

    def walk_to_something(self):
        """Head for the nearest thing the window is actually showing.

        Not the nearest thing on the floor: the client can only route over
        squares it has seen, so aiming at an item in unexplored ground fails
        every time and the soak never picks anything up.
        """
        play = self.s.app.play
        me = play.me()
        if not me or not play.items:
            return None
        spot = min(((i["x"], i["y"]) for i in play.items),
                   key=lambda xy: max(abs(xy[0] - me["x"]), abs(xy[1] - me["y"])))
        if not self.s.walk_to(*spot, limit=40):
            return None
        self.s.key(pygame.K_g)
        return f"walk to the things at {spot} and get them"

    def find_the_stairs(self):
        """Walk to the way down and take it, so the soak sees more than one
        floor. Random steps find a staircase about never."""
        from stormhold.common.constants import T
        p = self.s.me()
        level = self.s.world.levels.get(p.depth)
        if level is None:
            return "nothing"
        spot = next(((x, y) for y in range(level.h) for x in range(level.w)
                     if level.get(x, y) == T.STAIRS_DOWN), None)
        if spot is None:
            return "looked for stairs and found none"
        self.s.walk_to(*spot, limit=120)
        self.s.key(pygame.K_PERIOD, mod=pygame.KMOD_LSHIFT)
        return f"walk to the stairs at {spot} and go down"

    def run(self):
        for n in range(self.actions):
            what = "?"
            try:
                what = self.step()
                self.s.settle(0.25)
            except Drift as drift:
                self.note(n, "a control", str(drift))
                continue
            except Exception:                                 # noqa: BLE001
                self.note(n, what, "the game raised:\n" + traceback.format_exc())
                break
            self.done = n + 1
            if self.s.me().dead:
                self.s.settle(1.0)
            for name, check in CHECKS:
                try:
                    check(self.s)
                except Drift as drift:
                    self.note(n, what, f"[{name}] {drift}")
                except Exception:                             # noqa: BLE001
                    self.note(n, what,
                              f"[{name}] the check itself broke:\n"
                              + traceback.format_exc())
            if self.verbose and n % 50 == 0:
                p = self.s.me()
                print(f"    {n:>4}  floor {p.depth}  hp {int(p.hp)}/{p.max_hp}  "
                      f"{len(p.inventory)} things  {p.copper} cp", flush=True)
        return self.faults

    def note(self, n, what, message):
        # One report per kind of drift: a divergence that is not repaired
        # repeats on every action after it and would bury everything else.
        key = message.split("\n")[0][:60]
        if any(k == key for k, _, _, _ in self.faults):
            return
        self.faults.append((key, self.seed, n, f"after {what}: {message}"))
        print(f"  ** seed {self.seed} action {n}: {message}", flush=True)

    def close(self):
        try:
            self.s.close()
        except Exception:                                     # noqa: BLE001
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=1)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--actions", type=int, default=600)
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--port", type=int, default=None,
                    help="base port, for when one is already in use")
    args = ap.parse_args()

    seeds = ([args.seed] if args.seed is not None
             else list(range(1, args.seeds + 1)))
    all_faults, played = [], 0
    for i, seed in enumerate(seeds):
        print(f"\n-- seed {seed}: {args.actions} actions "
              f"------------------------------")
        base = args.port
        soak = Soak(seed, args.actions, args.verbose,
                    port=(base + i) if base else None)
        try:
            all_faults += soak.run()
            played += soak.done
        finally:
            soak.close()
        print(f"   played {soak.done} actions, {len(soak.faults)} kinds of drift")

    print(f"\n{played} actions over {len(seeds)} character(s), "
          f"{len(all_faults)} kinds of drift")
    for _, seed, n, message in all_faults:
        print(f"  seed {seed} action {n}: {message.splitlines()[0]}")
    return 1 if all_faults else 0


if __name__ == "__main__":
    sys.exit(main())
