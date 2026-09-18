"""The world, and the clock that drives it.

Stormhold is turn-based. Nothing moves until somebody acts. Each floor keeps
its own clock measured in ticks, and every creature holds a time at which it
may act again. The scheduler repeatedly wakes whichever creature is due next.

With several players that raises the obvious question: what happens while one
of them is thinking? The answer here is that the floor's clock may run ahead of
a player who has not acted, but only by GRACE_TICKS - about two turns. Past
that the floor stops and reports who everyone is waiting for. A pause for
thought costs nobody anything; wandering off does not let the world run away.
"""

import random
import time

from ..common.constants import (
    SHOP_BUY_MARKUP, SHOP_SELL_RATE, JUNK_FLAT, condition_for, COINS, mana_cost,
    TICKS_PER_SECOND,
    T, DIRS, TOWN_DEPTH, MAX_DEPTH, DEEP_LIMIT, GRACE_TICKS, MOVE_COST, ATTACK_COST,
    CAST_COST, PICKUP_COST, DROP_COST, EQUIP_COST, QUAFF_COST, READ_COST,
    STAIRS_COST, REST_COST, FREE_COST, SIGHT_DUNGEON, SIGHT_TOWN, REGEN_TICKS,
    DEFAULT_DIFFICULTY, DIFFICULTIES, difficulty_factors,
    DEATH_GOLD_PENALTY, DEATH_XP_PENALTY, RESURRECT_HP_FRACTION,
    chebyshev, clamp, is_solid, STATS,
)
from ..common.fov import compute_fov, has_los, line_between
from .level import generate_dungeon, generate_town
from .actors import Player, NPC, make_monster, stat_bonus
from .items import (Item, Appearances, generate_item, generate_gold,
                    coin_metal, article, with_article, BASES)
from .monsters import spawn_table, MONSTERS
from .spells import SPELLS, can_learn, elemental_factor, starting_spell
from .traps import TRAPS, search_here, disarm_at, a_or_an
from . import combat, ai


class World:
    def __init__(self, seed=None, difficulty=DEFAULT_DIFFICULTY):
        self.seed = seed if seed is not None else random.randrange(1 << 30)
        # The original's four settings. Whoever opens the keep chooses it, and
        # it applies to everything living in it, because the party shares the
        # floors they are fighting on.
        # A name that is not one of the four is a mistake in whatever built
        # this world, and it used to pass silently as Intermediate: a whole
        # afternoon's measurements of "Hard" were measurements of the
        # default, because the setting is called Difficult. Anything
        # arriving over the wire is sanitised by the server before it gets
        # here, so this can afford to be blunt.
        known = [label for label, _sym, _t, _x in DIFFICULTIES]
        if difficulty not in known:
            raise ValueError(f"no such difficulty {difficulty!r}; "
                             f"it is one of {', '.join(known)}")
        self.difficulty = difficulty
        self.rng = random.Random(self.seed)
        self.appearances = Appearances(self.seed)
        self.levels = {}
        self.players = {}
        self.events = []
        self.party_deepest = 1
        self.shop_stock = {}
        self.get_level(TOWN_DEPTH)

    # ====================================================== levels ==========
    def get_level(self, depth):
        level = self.levels.get(depth)
        if level is not None:
            return level
        if depth == TOWN_DEPTH:
            level = generate_town(self.seed)
            for spec in level.npcs:
                npc = NPC(spec)
                npc.depth = depth
                level.place(npc)
        else:
            level = generate_dungeon(depth, self.seed)
            self.populate(level)
        level.clock = 0
        level.waiting_on = None
        self.levels[depth] = level
        return level

    def clock_for(self, depth):
        level = self.levels.get(depth)
        return level.clock if level else 0

    def populate(self, level):
        rng = self.rng
        table = spawn_table(level.depth)
        party = max(1, len(self.players))
        count_mult = 1 + (party - 1) * 0.3
        tough_mult = 1 + (party - 1) * 0.45

        # How many creatures a floor holds. This was 85% of however many
        # spawn points the map generator happened to put down, from the
        # first floor to the twenty-fifth: thirteen on floor one against a
        # character with twenty-two hit points and a dagger, and then
        # twenty-six on floor three because that map had more room. One at a
        # time none of the early creatures can beat you - measured, a fresh
        # character wins every duel on floor one - so what killed people was
        # arithmetic, and a floor that doubles because of its shape is a
        # cliff nobody chose. A count, ramped with depth and capped, gives
        # the curve the floors are supposed to have.
        wanted = int(min(24, 6 + 1.1 * level.depth) * count_mult)
        spots = [(x, y, vault) for x, y, vault in level.spawns
                 if level.walkable(x, y)]
        rng.shuffle(spots)

        for x, y, vault in spots[:wanted]:
            key = self._weighted(table)
            m = self.spawn(key, x, y, level.depth)
            m.max_hp = int(m.max_hp * tough_mult)
            m.hp = m.max_hp
            m.xp_value = int(m.xp_value * (1 + (party - 1) * 0.22))
            level.place(m)
            # "when found in numbers can be much more deadly" - rats, wolves,
            # dogs and goblins arrive as a pack, not as a single specimen.
            # "Goblin tribes are sometimes able to hire a larger monster to
            # act as a guard" - a pack that turns up with something worse
            # standing behind it.
            hire = m.tpl.get("hires")
            # ...but it cannot hire something from further down than this.
            # A Shambler lives from floor 3; standing one behind a goblin
            # pack on floor 2 put a creature a whole band out of place in
            # front of a character with nineteen hit points.
            if hire and MONSTERS[hire]["min_d"] > level.depth:
                hire = None
            if hire and rng.random() < m.tpl.get("hire_chance", 0.25):
                spot = level.find_free(x, y, max_r=4)
                if spot:
                    guard = self.spawn(hire, spot[0], spot[1], level.depth)
                    guard.max_hp = int(guard.max_hp * tough_mult)
                    guard.hp = guard.max_hp
                    level.place(guard)

            pack = m.tpl.get("pack")
            if pack:
                # The first floor a creature lives on gets a scouting party,
                # not the whole pack. Full strength arrives once you are
                # three floors into its range. Measured against the game's
                # own combat code, four dire wolves in the open on floor 4
                # is a 0% fight for the character you would be; two is a
                # fight you can lose and learn from.
                low, high = pack
                over = max(0, level.depth - m.tpl["min_d"])
                if over < 3:
                    high = low + (high - low) * over // 3
                    low = max(1, low - 1) if over == 0 else low
                for _ in range(rng.randint(low - 1, max(low - 1, high - 1))):
                    spot = level.find_free(x, y, max_r=3)
                    if not spot:
                        break
                    mate = self.spawn(key, spot[0], spot[1], level.depth)
                    mate.max_hp = int(mate.max_hp * tough_mult)
                    mate.hp = mate.max_hp
                    level.place(mate)

        for x, y, rich in level.loot_spots:
            if not level.passable(x, y):
                continue
            if rng.random() < 0.42:
                level.add_ground_item(x, y, self._gold_item(generate_gold(level.depth, rng), level.depth))
            else:
                level.add_ground_item(x, y, generate_item(level.depth, rng, rich))

        if level.boss_key:
            bx, by = level.find_floor(level.boss_room["cx"], level.boss_room["cy"])
            boss = self.spawn(level.boss_key, bx, by, level.depth)
            # A boss facing a party is outnumbered in the one currency that
            # decides a fight: actions. Four people get four swings to its
            # one, so health alone cannot keep up - at half again per head a
            # party of four walked over both bosses while one person could
            # not touch either. It also hits harder and moves faster against
            # a crowd, which is the only thing that holds the odds steady
            # from one player to four.
            crowd = party - 1
            boss.max_hp = int(boss.max_hp * (1 + crowd * 0.9))
            boss.hp = boss.max_hp
            boss.dmg_bonus = getattr(boss, "dmg_bonus", 0) + crowd * 2
            boss.speed = max(40, int(boss.speed / (1 + crowd * 0.2)))
            level.place(boss)
            level.boss = boss

    def spawn(self, key, x, y, depth, rng=None):
        """Make a creature at this world's difficulty."""
        tough, worth = difficulty_factors(self.difficulty)
        return make_monster(key, x, y, depth, rng or self.rng, tough, worth)

    def _weighted(self, pairs):
        total = sum(w for _, w in pairs)
        r = self.rng.random() * total
        for value, w in pairs:
            r -= w
            if r <= 0:
                return value
        return pairs[-1][0]

    def _gold_item(self, amount, depth=0):
        it = Item("coins")
        it.gold_amount = amount
        it.metal = coin_metal(depth, self.rng)
        worth = dict(COINS)[it.metal]
        # round the value to whole coins of that metal
        it.gold_amount = max(worth, (amount // worth) * worth)
        it.base = dict(it.base, name=f"{it.metal} pieces")
        return it

    # ====================================================== events ==========
    def msg(self, text, kind="info", to=None, depth=None):
        self.events.append({"t": "msg", "text": text, "kind": kind,
                            "to": to.id if to is not None else None,
                            "depth": depth})

    def float_text(self, x, y, depth, text, kind):
        self.events.append({"t": "float", "x": x, "y": y, "depth": depth,
                            "text": text, "kind": kind})

    def fx(self, kind, x, y, depth):
        self.events.append({"t": "fx", "kind": kind, "x": x, "y": y, "depth": depth})

    def sound(self, name, x, y, depth):
        self.events.append({"t": "snd", "name": name, "x": x, "y": y, "depth": depth})

    def set_tile(self, level, x, y, tile):
        level.set(x, y, tile)
        self.events.append({"t": "tile", "depth": level.depth, "x": x, "y": y, "tile": tile})
        for p in self.players.values():
            if p.depth != level.depth:
                continue
            mem = p.memory.get(level.depth)
            if mem and mem[y * level.w + x]:
                p.pending_tiles.extend((x, y, tile))

    # ====================================================== players =========
    def add_player(self, name, stats=None, colour=0, save=None, spell=None):
        town = self.get_level(TOWN_DEPTH)
        p = Player(name, stats, colour)
        if save:
            p.load_save(save)
        else:
            self.give_starting_kit(p)
            p.spells.add(starting_spell(spell))
        p.depth = TOWN_DEPTH
        p.x, p.y = town.find_free(*town.spawn_point)
        p.next_at = town.clock
        self.players[p.id] = p
        town.place(p)
        self.party_deepest = max(self.party_deepest, p.deepest or 1)
        self.update_fov(p, force=True)
        return p

    def give_starting_kit(self, p):
        """A dagger, a pack, a purse and a belt - the rest you buy.

        The original starts you with a dagger, a pack and a purse and 1500
        copper, which is the point: a suit of leather armour costs 1050 and a
        short sword 1470, so your first decision is which one you can afford.
        Handing out a sword and armour for free made that starting purse
        meaningless, and left the character at 84% of capacity before leaving
        town.

        The belt is in the kit because of a rule of ours, not the original's
        shop list: nothing in the pack can be drunk, so without a belt a
        healing potion is an ornament. Leather, a belt and a potion came to
        more than the starting purse, so a new character walked down the
        stairs in a dagger with nothing to drink and died on the first floor
        three times running.
        """
        for key in ("dagger", "pack", "purse", "belt"):
            it = Item(key)
            it.known = True
            p.equipment[it.slot] = it
        self.appearances.identify("potion_heal")
        p.recalc()
        p.hp, p.mana = p.max_hp, p.max_mana

    def remove_player(self, pid):
        p = self.players.pop(pid, None)
        if not p:
            return
        level = self.levels.get(p.depth)
        if level:
            level.remove(p)

    def players_on(self, depth):
        return [p for p in self.players.values() if p.depth == depth]

    # ====================================================== scheduler =======
    # Looking at things, tidying your pack and haggling in a shop are not
    # actions in the world: they take no game time, so they must not give
    # anything down there a free turn.
    FREE_ACTIONS = frozenset({
        "examine", "sort", "rename", "buy", "sell", "service",
    })

    def submit(self, player, action):
        """Queue a player's chosen action, then let the floor run."""
        if player.dead:
            return
        action = self.clean_action(action)
        level = self.levels.get(player.depth)
        if level is not None and action.get("a") in self.FREE_ACTIONS:
            self.do_player_action(level, player, action)
            return
        player.pending = action
        self.run_level(player.depth)

    def run_level(self, depth, max_actions=800):
        """Advance one floor until it needs a decision from somebody."""
        level = self.levels.get(depth)
        if level is None:
            return
        level.waiting_on = None

        # Waiting on a companion only matters where something is hunting you.
        # On a cleared floor - and in town - people come and go as they please.
        threatened = any(a.kind == "monster" and not a.dead
                         for a in level.actors.values())

        for _ in range(max_actions):
            ready = None
            blocked = None
            for a in list(level.actors.values()):
                if a.dead or a.kind == "npc":
                    continue
                if a.kind == "player" and a.pending is None and not a.resting:
                    if threatened:
                        if blocked is None or a.next_at < blocked.next_at:
                            blocked = a
                    else:
                        # Nothing can hurt them, so do not let them hold the
                        # floor up - and do not let them bank turns either.
                        if a.next_at < level.clock:
                            a.next_at = level.clock
                    continue
                if ready is None or a.next_at < ready.next_at:
                    ready = a

            if ready is None:
                self._set_waiting(level, blocked.id if blocked else None)
                return

            # Do not let the floor run further than GRACE_TICKS ahead of
            # somebody who still owes us an action.
            if blocked is not None and ready.next_at - blocked.next_at > GRACE_TICKS:
                self._set_waiting(level, blocked.id)
                return

            level.clock = max(level.clock, ready.next_at)
            was_on = ready.depth
            cost = self.act(level, ready)
            if cost is None:
                cost = MOVE_COST
            if ready.kind == "player":
                # Each floor keeps its own clock so that a party can share a
                # turn order, but the character's own clock is the one they
                # see: it used to restart at zero every time they took the
                # stairs.
                ready.elapsed = getattr(ready, "elapsed", 0) + max(1, int(cost))
            if ready.depth != was_on:
                # Taking the stairs moved them to another floor, which already
                # set their next action time against that floor's clock. This
                # floor's clock means nothing to them now.
                continue
            ready.next_at = level.clock + max(1, int(cost))
            self.after_action(level, ready)

        self._set_waiting(level, None)

    def _set_waiting(self, level, actor_id):
        if level.waiting_on != actor_id:
            level.waiting_on = actor_id
            level.waiting_since = time.time() if actor_id else None

    def nudge_idle(self, idle_seconds=45.0):
        """Let the party carry on when somebody has genuinely wandered off.

        The floor waits for whoever is thinking, which is right - but a child
        who goes to find a snack should not strand everybody else. After a
        while that character simply holds still, taking a turn at a time, and
        the game goes on without them.
        """
        nudged = []
        now = time.time()
        for level in self.levels.values():
            waiting = getattr(level, "waiting_on", None)
            since = getattr(level, "waiting_since", None)
            if not waiting or since is None or now - since < idle_seconds:
                continue
            player = self.players.get(waiting)
            if player is None or player.pending is not None:
                continue
            if not player.idle_noted:
                player.idle_noted = True
                self.msg(f"{player.name} is standing still.", "info", depth=level.depth)
            # Hold still, a turn at a time, until the floor is no longer
            # waiting on them. One turn is rarely enough: they may be several
            # behind, and the party should not crawl forward a second at a time.
            for _ in range(40):
                player.pending = {"a": "wait"}
                self.run_level(level.depth)
                if level.waiting_on != player.id or player.dead:
                    break
            level.waiting_since = now
            nudged.append(player.id)
        return nudged

    def act(self, level, actor):
        if actor.kind == "monster":
            return ai.take_turn(self, level, actor)
        if actor.kind == "player" and actor.resting and actor.pending is None:
            # Carry on resting without being asked, until healed or disturbed.
            for_mana = actor.resting == "mana"
            # "Rest until player is fully healed" and "Rest until player's
            # mana is restored" are two commands with two conditions. Resting
            # used to wait for both, so `r` sat you in the open long after
            # you were healed, waiting on mana it recovers at half the rate
            # the other command does.
            done = (actor.mana >= actor.max_mana if for_mana
                    else actor.hp >= actor.max_hp)
            if done:
                actor.resting = False
                self.msg("You wake, clear-headed." if for_mana else "You feel rested.",
                         "good", to=actor)
            elif not for_mana and combat.enemies_in_sight(self, level, actor, 8):
                # Resting breaks the moment something comes into view; sleep is
                # deeper and breaks only when something actually hits you,
                # which combat handles.
                actor.resting = False
                self.msg("Something disturbs your rest.", "bad", to=actor)
            else:
                actor.pending = {"a": "wait"}
        action = actor.pending
        actor.pending = None
        if action is None:
            return MOVE_COST
        if actor.kind == "player" and action.get("a") != "wait":
            actor.idle_noted = False
            # Anything except settling down interrupts a rest - but the rest
            # and sleep commands themselves obviously must not.
            if action.get("a") not in ("rest", "sleep"):
                actor.resting = False
        if action is None:
            return MOVE_COST
        return self.do_player_action(level, actor, action)

    def after_action(self, level, actor):
        """Per-action upkeep: burning, poison, natural healing, expiry."""
        now = level.clock
        for name in list(actor.effects.keys()):
            until, value = actor.effects[name]
            if name in ("burning", "poisoned") and not actor.dead:
                combat.apply_damage(self, actor, max(1, value or 2), None)
                self.fx(name, actor.x, actor.y, level.depth)
                if actor.dead:
                    return
        # A delayed poison does not wear off when its timer runs out - that
        # is the moment it takes hold.
        creeping = actor.effect_value("poison_later", 0)
        gone = actor.expire_effects(now)
        if "poison_later" in gone and not actor.dead:
            actor.add_effect("poisoned", now + 600, creeping or 3)
            self.msg("The numbness turns to fire. The poison has taken hold.",
                     "bad", to=actor)
        for name in gone:
            if name == "poison_later":
                continue
            if actor.kind == "player":
                self.msg(f"Your {name.replace('_', ' ')} fades.", "info", to=actor)

        if actor.kind == "player" and not actor.dead:
            self.recharge_items(actor)
            # Slow natural recovery, measured in ticks rather than turns so
            # that dawdling in heavy armour does not heal you faster.
            actor.regen_credit = getattr(actor, "regen_credit", 0) + MOVE_COST
            if actor.regen_credit >= REGEN_TICKS:
                actor.regen_credit = 0
                con = actor.stat("constitution")
                if actor.hp < actor.max_hp:
                    actor.hp = min(actor.max_hp, actor.hp + 1 + max(0, stat_bonus(con)))
                if actor.mana < actor.max_mana:
                    # Sleeping restores mana at twice the waking rate.
                    gain = 2 if actor.resting == "mana" else 1
                    actor.mana = min(actor.max_mana, actor.mana + gain)

    # ====================================================== vision ==========
    def steal_from(self, thief, victim):
        """Take coin from the purse and go. The bank is why this is survivable."""
        level = self.levels.get(victim.depth)
        take = min(victim.copper, max(1, int(victim.copper * 0.25)))
        if not take or not victim.spend(take):
            return
        thief.stolen = getattr(thief, "stolen", 0) + take
        self.msg("You feel a tug on your purse!", "bad", to=victim)
        spot = level.find_free(thief.x, thief.y, max_r=30) if level else None
        if spot:
            level.move_actor(thief, *spot)
            thief.target_id = None
            self.msg(f"The {thief.name} vanishes!", "bad", to=victim)
        self.events.append({"t": "inv", "to": victim.id})

    def transmogrify(self, level, m, caster=None):
        """Turn one creature into another, keeping how hurt it was.

        "Note that the 'injuredness' of a monster is preserved, so a Red Dragon
        that has lost half its hit points and is transformed into a Hill Giant
        will have half the normal hit points of a Hill Giant."
        """
        share = m.hp / max(1, m.max_hp)
        table = spawn_table(level.depth)
        key = self._weighted(table)
        was = m.name
        fresh = self.spawn(key, m.x, m.y, level.depth)
        level.remove(m)
        fresh.hp = max(1, int(fresh.max_hp * share))
        level.place(fresh)
        self.msg(f"The {was} twists and becomes a {fresh.name}.", "good",
                 to=caster)
        return fresh

    def within_reach(self, p, item):
        """Can this be activated where it is? Worn slots and the belt only."""
        if item in p.equipment.values():
            return True
        for worn in (p.equipment.get("waist"), p.equipment.get("quiver")):
            if worn is not None and item in getattr(worn, "contents", []):
                return True
        # equipping something out of the pack is always allowed; it is only
        # activation that the belt gates
        return bool(item.slot)

    def recharge_items(self, p):
        """Charged items come back on a clock: "(Once every N hours)"."""
        now = self.clock_for(p.depth)
        for item in list(p.inventory) + [i for i in p.equipment.values() if i]:
            hours = item.base.get("recharge_hours")
            if not hours:
                continue
            full = item.base.get("charges", (0, 0))[1]
            if item.charges >= full:
                item.recharge_at = None
                continue
            due = getattr(item, "recharge_at", None)
            if due is None:
                item.recharge_at = now + hours * 3600 * TICKS_PER_SECOND
            elif now >= due:
                item.charges += 1
                item.recharge_at = now + hours * 3600 * TICKS_PER_SECOND
                self.msg(f"Your {item.name(self.appearances)} hums as it "
                         f"gathers power again.", "info", to=p)

    def memory_for(self, p, level):
        mem = p.memory.get(level.depth)
        if mem is None:
            mem = bytearray(level.w * level.h)
            p.memory[level.depth] = mem
        return mem

    def light_radius(self, p, level):
        """How far you see.

        The original has no light sources at all - no torches, no lanterns,
        no fuel to track. You simply see, and the Light spell reveals a room
        or a stretch of corridor. So this is a flat radius, widened only by
        magic.
        """
        if level.is_town:
            return SIGHT_TOWN
        base = SIGHT_DUNGEON
        if p.has("truesight"):
            base += 6
        return base

    def update_fov(self, p, force=False):
        level = self.levels.get(p.depth)
        if level is None:
            return
        key = (p.x, p.y, p.depth, self.light_radius(p, level))
        if not force and getattr(p, "_fov_key", None) == key:
            return
        p._fov_key = key
        compute_fov(level, p.x, p.y, key[3], p.fov)
        mem = self.memory_for(p, level)
        for i in p.fov:
            if not mem[i]:
                mem[i] = 1
                p.pending_tiles.extend((i % level.w, i // level.w, level.tiles[i]))

    def resend_level(self, p):
        """Queue every tile this player remembers, for a fresh client map."""
        level = self.levels.get(p.depth)
        if level is None:
            return
        mem = self.memory_for(p, level)
        p.pending_tiles = []
        for i, seen in enumerate(mem):
            if seen:
                p.pending_tiles.extend((i % level.w, i // level.w, level.tiles[i]))

    # ====================================================== actions =========
    # The fields a verb may treat as numbers. Anything arriving from a client
    # is only a suggestion: a string, a list or None must not reach int().
    NUMERIC_FIELDS = ("id", "x", "y", "dx", "dy", "qty", "amount", "npc",
                      "target", "slotn")

    @classmethod
    def clean_action(cls, action):
        """Make one client's action safe to act on.

        Every verb used to coerce its own arguments, so a client sending
        {"id": "not a number"} raised out of the verb. Coercing once, at the
        door, is the only place it can be done exactly once.
        """
        if not isinstance(action, dict):
            return {"a": None}
        out = {}
        for key, value in action.items():
            if not isinstance(key, str):
                continue
            if key in cls.NUMERIC_FIELDS:
                try:
                    out[key] = int(value)
                except (TypeError, ValueError):
                    continue            # as if it had not been sent
            elif isinstance(value, (str, int, float, bool)) or value is None:
                out[key] = value
        return out

    def do_player_action(self, level, p, action):
        """Carry out one chosen action. Returns the ticks it cost."""
        action = self.clean_action(action)
        kind = action.get("a")
        handler = getattr(self, f"_act_{kind}", None)
        if handler is None:
            return FREE_COST
        return handler(level, p, action)

    # ---- movement --------------------------------------------------------
    def _act_move(self, level, p, action):
        dx = clamp(int(action.get("dx", 0)), -1, 1)
        dy = clamp(int(action.get("dy", 0)), -1, 1)
        if dx == 0 and dy == 0:
            return self._act_wait(level, p, action)

        p.facing = ai._dir_index(dx, dy)
        nx, ny = p.x + dx, p.y + dy
        if not level.in_bounds(nx, ny):
            return FREE_COST

        tile = level.get(nx, ny)
        if tile == T.DOOR:
            self.set_tile(level, nx, ny, T.DOOR_OPEN)
            self.sound("door", nx, ny, level.depth)
            self.msg("You open the door.", "info", to=p)
            return p.action_cost(MOVE_COST, moving=True) or MOVE_COST

        other = level.actor_at(nx, ny)
        if other is not None and other.kind == "monster" and not other.dead:
            combat.melee(self, p, other)
            self.sound("swing", p.x, p.y, level.depth)
            return p.action_cost(ATTACK_COST, attacking=True) or ATTACK_COST
        if other is not None and other.kind == "npc":
            self.events.append({"t": "shop", "to": p.id, "npc": other.id,
                                "shop": other.shop, "name": other.name})
            return FREE_COST
        if other is not None:
            self.msg(f"{other.name} is in the way.", "info", to=p)
            return FREE_COST

        if not level.walkable(nx, ny, p.id):
            return FREE_COST
        if dx and dy and is_solid(level.get(p.x + dx, p.y)) and is_solid(level.get(p.x, p.y + dy)):
            # Silence here reads as a dropped keypress. The rule is real and
            # it costs fights, so say it.
            self.msg("You cannot squeeze diagonally between two walls.",
                     "info", to=p)
            return FREE_COST

        cost = p.action_cost(MOVE_COST, moving=True)
        if cost is None:
            self.msg("You are carrying far too much to move. Drop something, "
                     "or bank your copper in town.", "warn", to=p)
            return FREE_COST

        level.move_actor(p, nx, ny)
        if tile in (T.WATER, T.RUBBLE):
            cost = int(cost * 1.5)
        self.update_fov(p)
        self.spring_trap(level, p)
        self.describe_floor(level, p)
        return cost

    def spring_trap(self, level, p, forced=False):
        """Walk onto something you did not find and it goes off."""
        spot = (p.x, p.y)
        trap = level.traps.get(spot)
        if not trap or not trap["armed"]:
            return False
        if trap["found"] and not forced:
            # "A known trap is less likely to go off" - less likely, not
            # never. A careless step still finds the trigger sometimes, and
            # being nimble helps you avoid it.
            dodge = 6 + max(0, stat_bonus(p.stat("dexterity")))
            if self.rng.randint(1, max(2, dodge)) != 1:
                return False
            self.msg("You misjudge your step and catch the trigger anyway.",
                     "bad", to=p)
        info = TRAPS[trap["kind"]]
        trap["found"] = True
        trap["armed"] = False
        level.traps.pop(spot, None)

        # "Levitation ... will prevent you from falling into pits and trap
        # doors." Anything that works by dropping you, or dropping on you,
        # misses a character who is not standing on the floor.
        if info.get("gravity") and p.has("levitating"):
            self.msg("You drift over it, feet clear of the stones.",
                     "good", to=p)
            return True

        self.msg(info["desc"], "bad", to=p)
        self.fx("blast", p.x, p.y, level.depth)
        self.sound("slam", p.x, p.y, level.depth)
        n, sides = info["dmg"]
        if n:
            dmg = sum(self.rng.randint(1, sides) for _ in range(n))
            combat.apply_damage(self, p, dmg, None)
        now = level.clock
        if info.get("poison"):
            p.add_effect("poisoned", now + 500, info["poison"])
        if info.get("burn"):
            p.add_effect("burning", now + 400, info["burn"])
        if info.get("hold"):
            p.add_effect("held", now + 300)
        if info.get("stun"):
            p.next_at += 200
        if info.get("slow"):
            p.add_effect("slowed", now + 400)
            self.msg("Your limbs grow heavy.", "bad", to=p)
        if info.get("teleport"):
            spot = level.find_free(p.x, p.y, max_r=30, ignore_id=p.id)
            if spot:
                level.move_actor(p, *spot)
                self.update_fov(p, force=True)
                self.msg("The floor twists away, and you are somewhere else.",
                         "bad", to=p)
        if info.get("trapdoor"):
            # No damage at all - it simply puts you a floor deeper, wherever
            # that floor happens to be, which is the worse outcome.
            self.msg("You land hard, a floor further down.", "bad", to=p)
            self.move_player_to(p, p.depth + 1)
            return True
        if info.get("animate"):
            raised = 0
            for _ in range(self.rng.randint(2, 4)):
                free = level.find_free(p.x, p.y, max_r=4, ignore_id=p.id)
                if not free:
                    break
                key = self._weighted(spawn_table(level.depth))
                m = self.spawn(key, free[0], free[1], level.depth)
                m.target_id = p.id
                m.last_seen = (p.x, p.y)
                level.place(m)
                raised += 1
            if raised:
                self.msg(f"{raised} of them climb to their feet around you.",
                         "bad", to=p)
        if info.get("alarm"):
            roused = 0
            for a in level.actors.values():
                if a.kind == "monster" and not a.dead and a.target_id is None:
                    a.target_id = p.id
                    a.last_seen = (p.x, p.y)
                    roused += 1
            if roused:
                self.msg(f"{roused} things below start moving toward you.", "bad", to=p)
        return True

    def describe_floor(self, level, p):
        pile = level.items_at(p.x, p.y)
        if not pile:
            return
        names = [i.name(self.appearances) for i in pile]
        if len(names) == 1:
            # "You see Purse here." wants an article; "3 Potions" and
            # "Gauntlets" do not.
            self.msg(f"You see {with_article(names[0])} here.", "loot", to=p)
        else:
            self.msg(f"You see several things here: {', '.join(names)}.", "loot", to=p)

    def _act_wait(self, level, p, action):
        return p.action_cost(REST_COST) or REST_COST

    def _act_search(self, level, p, action):
        """Take a turn to look at the walls and floor around you."""
        found = search_here(self, level, p, self.rng)
        if found:
            for line in found:
                self.msg(line, "good", to=p)
            self.sound("notice", p.x, p.y, level.depth)
        else:
            self.msg("You search, and find nothing.", "info", to=p)
        return p.action_cost(REST_COST) or REST_COST

    def _act_disarm(self, level, p, action):
        """Try to defuse a trap you have already found, next to you or underfoot."""
        best = None
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                spot = (p.x + dx, p.y + dy)
                trap = level.traps.get(spot)
                if trap and trap["found"] and trap["armed"]:
                    best = spot
                    break
            if best:
                break
        if best is None:
            self.msg("There is no trap here that you have found.", "info", to=p)
            return FREE_COST
        acted, message = disarm_at(self, level, p, best, self.rng)
        self.msg(message, "good" if "disarm" in message else "warn", to=p)
        if "set the" in message:
            was = (p.x, p.y)
            p.x, p.y = best
            self.spring_trap(level, p, forced=True)
            p.x, p.y = was
        return p.action_cost(REST_COST) or REST_COST

    def _act_freehand(self, level, p, action):
        """Put your weapon away, so you have a hand free."""
        if p.equipment.get("weapon") is None:
            self.msg("Your hands are already empty.", "info", to=p)
            return FREE_COST
        ok, message = p.unequip("weapon")
        self.msg(message, "info" if ok else "warn", to=p)
        self.events.append({"t": "inv", "to": p.id})
        return (p.action_cost(EQUIP_COST) or EQUIP_COST) if ok else FREE_COST

    def _act_rest(self, level, p, action):
        """Sit still until you are mended, or until something interrupts."""
        if combat.enemies_in_sight(self, level, p, 8):
            self.msg("Not with something watching you.", "warn", to=p)
            return FREE_COST
        if p.hp >= p.max_hp:
            # Rest is for wounds; mana is what the other command is for.
            self.msg("You are already rested." if p.mana >= p.max_mana else
                     "You are unhurt. Sleep if it is mana you want.",
                     "info", to=p)
            return FREE_COST
        p.resting = True
        self.msg("You sit down to rest.", "info", to=p)
        return p.action_cost(REST_COST) or REST_COST

    def _act_examine(self, level, p, action):
        """Look at something without touching it. Costs nothing."""
        tx, ty = int(action.get("x", p.x)), int(action.get("y", p.y))
        if (ty * level.w + tx) not in p.fov:
            self.msg("You cannot see that from here.", "info", to=p)
            return FREE_COST

        other = level.actor_at(tx, ty)
        if other is not None and not other.dead:
            if other.kind == "monster":
                state = condition_for(other.hp / max(1, other.max_hp))
            self.msg(
                f"{other.name}: {state}." if other.kind == "monster"
                else f"{other.name}, level {getattr(other, 'level', 1)}.", "info", to=p)
            return FREE_COST

        pile = level.items_at(tx, ty)
        if pile:
            for it in pile:
                self.msg(f"{it.name(self.appearances)} - {it.describe(self.appearances)}.",
                         "loot", to=p)
            return FREE_COST

        trap = level.traps.get((tx, ty))
        if trap and trap["found"]:
            self.msg(f"{a_or_an(TRAPS[trap['kind']]['name']).capitalize()}, still armed.",
                     "warn", to=p)
            return FREE_COST

        tile = level.get(tx, ty)
        names = {T.FLOOR: "bare floor", T.WALL: "solid wall", T.DOOR: "a closed door",
                 T.DOOR_OPEN: "an open doorway", T.STAIRS_DOWN: "stairs leading down",
                 T.STAIRS_UP: "stairs leading up", T.WATER: "shallow water",
                 T.RUBBLE: "broken rubble", T.GRASS: "grass", T.ROAD: "a paved road",
                 T.TREE: "a tree", T.SHOP_FLOOR: "a shop floor", T.ALTAR: "an altar",
                 T.FOUNTAIN: "a fountain", T.THRONE: "a throne"}
        self.msg(f"You see {names.get(tile, 'nothing of interest')}.", "info", to=p)
        return FREE_COST

    def _act_open(self, level, p, action):
        """Open a door beside you, or the one you name."""
        for spot in self._adjacent(p, action):
            if level.get(*spot) == T.DOOR:
                self.set_tile(level, spot[0], spot[1], T.DOOR_OPEN)
                self.sound("door", spot[0], spot[1], level.depth)
                self.msg("You open the door.", "info", to=p)
                self.update_fov(p, force=True)
                return p.action_cost(MOVE_COST, moving=True) or MOVE_COST
        self.msg("There is nothing here to open.", "info", to=p)
        return FREE_COST

    def _act_close(self, level, p, action):
        """Shut a door beside you. Useful for putting something between you
        and whatever is following."""
        for spot in self._adjacent(p, action):
            if level.get(*spot) != T.DOOR_OPEN:
                continue
            if level.actor_at(*spot) is not None:
                self.msg("Something is standing in the doorway.", "warn", to=p)
                return FREE_COST
            if level.items_at(*spot):
                self.msg("Something on the floor is blocking the door.", "warn", to=p)
                return FREE_COST
            self.set_tile(level, spot[0], spot[1], T.DOOR)
            self.sound("door", spot[0], spot[1], level.depth)
            self.msg("You close the door.", "info", to=p)
            self.update_fov(p, force=True)
            return p.action_cost(MOVE_COST, moving=True) or MOVE_COST
        self.msg("There is nothing here to close.", "info", to=p)
        return FREE_COST

    def _adjacent(self, p, action):
        """The tiles to try for a door verb: the one aimed at, else all neighbours."""
        if "x" in action and "y" in action:
            return [(int(action["x"]), int(action["y"]))]
        return [(p.x + dx, p.y + dy) for dx, dy in DIRS]

    def _act_sleep(self, level, p, action):
        """Sleep until your mana comes back.

        A deeper thing than resting, and the original is precise about the
        difference: "You regenerate mana at twice the normal rate, but it is
        only interrupted when a monster attacks you, not when they come into
        view." So you may lie down with something already watching.
        """
        if p.mana >= p.max_mana:
            self.msg("Your mana is already full.", "info", to=p)
            return FREE_COST
        p.resting = "mana"
        self.msg("You settle down to sleep.", "info", to=p)
        return p.action_cost(REST_COST) or REST_COST

    def _act_run(self, level, p, action):
        """Travel in one direction until something worth stopping for appears.

        The original has an option called "Stop Running on Special Sites",
        which is the whole idea: running is for crossing ground you have
        already cleared, and it gives way the moment the floor gets interesting.
        """
        dx = clamp(int(action.get("dx", 0)), -1, 1)
        dy = clamp(int(action.get("dy", 0)), -1, 1)
        if not dx and not dy:
            return FREE_COST

        def open_ways(x, y):
            return sum(1 for ax, ay in DIRS if level.passable(x + ax, y + ay))

        total = 0
        prev_ways = open_ways(p.x, p.y)
        for step in range(40):
            if combat.enemies_in_sight(self, level, p, 7):
                if step == 0:
                    self.msg("Not with something in sight.", "warn", to=p)
                break
            nx, ny = p.x + dx, p.y + dy
            if not level.walkable(nx, ny, p.id) or level.get(nx, ny) == T.DOOR:
                break
            before = p.hp
            total += self._act_move(level, p, {"dx": dx, "dy": dy}) or 0
            if p.hp < before or p.dead:
                break
            tile = level.get(p.x, p.y)
            if tile in (T.STAIRS_DOWN, T.STAIRS_UP, T.DOOR_OPEN, T.ALTAR):
                break
            if level.items_at(p.x, p.y):
                break
            trap = level.traps.get((p.x, p.y))
            if trap and trap["found"]:
                break
            # A junction is only interesting in a corridor. In open ground
            # every tile has eight ways out, and stopping at each one would
            # make running useless exactly where it is most wanted.
            ways = open_ways(p.x, p.y)
            if prev_ways <= 3 and ways > prev_ways and step > 0:
                break
            prev_ways = ways
        return total or (p.action_cost(MOVE_COST, moving=True) or MOVE_COST)

    # ---- fighting --------------------------------------------------------
    def _act_attack(self, level, p, action):
        dx = clamp(int(action.get("dx", 0)), -1, 1)
        dy = clamp(int(action.get("dy", 0)), -1, 1)
        if dx or dy:
            p.facing = ai._dir_index(dx, dy)
        fx, fy = DIRS[p.facing]
        target = level.actor_at(p.x + fx, p.y + fy)
        self.sound("swing", p.x, p.y, level.depth)
        if target is not None and target.kind == "monster" and not target.dead:
            combat.melee(self, p, target)
        else:
            self.msg("You swing at nothing.", "info", to=p)
        return p.action_cost(ATTACK_COST, attacking=True) or ATTACK_COST

    # ---- objects ---------------------------------------------------------
    # "This command generally puts everything on the floor into the player's
    # pack. The special case is if the object is a pack, purse, or belt, and
    # the player isn't wearing one, the object goes in the appropriate
    # inventory slot."
    WEARS_ITSELF = {"pack": "pack", "purse": "purse", "waist": "waist"}

    def _act_pickup(self, level, p, action):
        pile = list(level.items_at(p.x, p.y))
        if not pile:
            self.msg("There is nothing here to pick up.", "info", to=p)
            return FREE_COST

        took = 0
        for item in pile:
            if item.kind == "coins":
                metal = getattr(item, "metal", "copper")
                worth = dict(COINS)[metal]
                n = max(1, item.gold_amount // worth)
                p.gain_coins(metal, n)
                level.take_ground_item(p.x, p.y, item)
                self.msg(f"You pick up {n} {metal} pieces "
                         f"(worth {item.gold_amount} copper).", "loot", to=p)
                self.sound("gold", p.x, p.y, level.depth)
                took += 1
                continue

            # A pack you are not wearing goes on rather than in - there is
            # nothing to put it in, which is the whole point of finding one.
            slot = self.WEARS_ITSELF.get(item.slot)
            if slot and p.equipment.get(slot) is None:
                level.take_ground_item(p.x, p.y, item)
                p.equipment[slot] = item
                p.recalc()
                self.msg(f"You put on {with_article(item.name(self.appearances))}.",
                         "loot", to=p)
                self.sound("pickup", p.x, p.y, level.depth)
                took += 1
                continue

            ok, why = p.room_for(item)
            if not ok or not p.add_item(item):
                self.msg(why if not ok else "Your pack is full.", "warn", to=p)
                break                       # and leave the rest where it lies
            level.take_ground_item(p.x, p.y, item)
            self.msg(f"You pick up {with_article(item.name(self.appearances))}.",
                     "loot", to=p)
            self.sound("pickup", p.x, p.y, level.depth)
            took += 1

        if not took:
            return FREE_COST
        self.events.append({"t": "inv", "to": p.id})
        return p.action_cost(PICKUP_COST) or PICKUP_COST

    def _act_drop(self, level, p, action):
        """Put something on the floor, from wherever it is.

        This used to insist the thing was loose in the pack. Select a potion
        off your belt, or the sword in your hand, press Drop - which the
        window offers, enabled - and nothing happened and nothing was said.
        """
        item = p.find_item(int(action.get("id", 0)))
        if item is None:
            self.msg("You are not carrying that.", "warn", to=p)
            return FREE_COST

        if item not in p.inventory:
            worn_slot = next((slot for slot, w in p.equipment.items() if w is item),
                             None)
            if worn_slot is not None:
                ok, why = p.unequip(worn_slot)
                if not ok:
                    self.msg(why, "warn", to=p)     # cursed things stay on
                    return FREE_COST
                # unequip puts it in the pack; take it straight back out so
                # a full pack cannot swallow the drop.
                if item in p.inventory:
                    p.inventory.remove(item)
            else:
                holder = next((w for w in p.equipment.values()
                               if w and item in (w.contents or [])), None)
                if holder is None:
                    self.msg("You are not carrying that.", "warn", to=p)
                    return FREE_COST
                holder.contents.remove(item)
            p.recalc()
            level.add_ground_item(p.x, p.y, item)
            self.msg(f"You drop {item.name(self.appearances)}.", "info", to=p)
            self.events.append({"t": "inv", "to": p.id})
            return p.action_cost(DROP_COST) or DROP_COST

        dropped = p.remove_item(item, int(action.get("qty", item.qty)))
        level.add_ground_item(p.x, p.y, dropped)
        self.msg(f"You drop {dropped.name(self.appearances)}.", "info", to=p)
        # Without this the thing stayed in the window after it hit the floor,
        # which is the same fault picking things up had: the pack you are
        # looking at is the last one the server described, not the one you
        # are carrying.
        self.events.append({"t": "inv", "to": p.id})
        return p.action_cost(DROP_COST) or DROP_COST

    def _act_equip(self, level, p, action):
        item = p.find_item(int(action.get("id", 0)))
        if item is None:
            return FREE_COST
        was_known = item.known
        ok, message = p.equip(item, action.get("slot"))
        self.msg(message, "info" if ok else "warn", to=p)
        if ok and not was_known:
            # "Most armor and weapons are marked as identify on wield. If you
            # actually use the object, you'll find out whether or not it's
            # enchanted." The curse is how you find out the hard way.
            item.known = True
            self.appearances.identify(item.key)
            if item.cursed:
                self.msg(f"A chill runs up your arm. The "
                         f"{item.name(self.appearances)} fastens itself to you "
                         f"- it is cursed.", "bad", to=p)
            elif item.enchant:
                self.msg(f"You can feel the enchantment on it "
                         f"({item.enchant:+d}).", "good", to=p)
        self.events.append({"t": "inv", "to": p.id})
        return (p.action_cost(EQUIP_COST) or EQUIP_COST) if ok else FREE_COST

    def _act_unequip(self, level, p, action):
        ok, message = p.unequip(action.get("slot", ""))
        self.msg(message, "info" if ok else "warn", to=p)
        self.events.append({"t": "inv", "to": p.id})
        return (p.action_cost(EQUIP_COST) or EQUIP_COST) if ok else FREE_COST

    def _act_use(self, level, p, action):
        item = p.find_item(int(action.get("id", 0)))
        if item is None:
            return FREE_COST
        if not self.within_reach(p, item):
            # "The Activate menu allows you to use objects you are carrying
            # about your person, either in one of the inventory slots or on
            # your belt (Objects in your pack cannot be activated)."
            self.msg("That is buried in your pack. Put it on your belt if you "
                     "want it to hand.", "warn", to=p)
            return FREE_COST
        kind = item.kind
        if kind == "potion":
            return self.quaff(level, p, item)
        if kind == "scroll":
            return self.read_scroll(level, p, item, action)
        if item.spell:
            return self.read_book(level, p, item)
        if item.slot:
            return self._act_equip(level, p, {"id": item.id})
        self.msg("You are not sure what to do with that.", "info", to=p)
        return FREE_COST

    def quaff(self, level, p, item):
        use = item.base.get("use")
        power = item.base.get("power", 0)
        now = level.clock
        self.appearances.identify(item.key)
        self.sound("drink", p.x, p.y, level.depth)
        name = item.base["name"]

        if use == "heal":
            got = combat.heal(self, p, power)
            self.msg(f"You drink the {name}. You feel better ({got} healed).", "good", to=p)
        elif use == "mana":
            p.mana = min(p.max_mana, p.mana + power)
            self.msg(f"You drink the {name}. Your head clears.", "good", to=p)
        elif use == "haste":
            p.add_effect("haste", now + power * 10)
            self.msg("Everything around you seems to slow down.", "good", to=p)
        elif use == "might":
            p.add_effect("might", now + power * 10)
            self.msg("Your arms feel like oak.", "good", to=p)
        elif use == "cure":
            for bad in ("poisoned", "burning", "slowed", "afraid"):
                p.effects.pop(bad, None)
            self.msg("A clean warmth runs through you.", "good", to=p)
        elif use == "levitate":
            # "Levitation ... will prevent you from falling into pits and
            # trap doors."
            p.add_effect("levitating", now + power * 10)
            self.msg("Your feet leave the flagstones.", "good", to=p)
        elif use == "sight":
            p.add_effect("truesight", now + power * 10)
            self.update_fov(p, force=True)
            self.msg("The dark loosens its grip.", "good", to=p)
        elif use == "poison":
            p.add_effect("poisoned", now + 600, 4)
            self.msg("That was a mistake. Your stomach turns.", "bad", to=p)
        p.consume(item, 1)
        p.recalc()
        self.events.append({"t": "inv", "to": p.id})
        return p.action_cost(QUAFF_COST) or QUAFF_COST

    def read_scroll(self, level, p, item, action):
        use = item.base.get("use")
        if use == "identify" and self.needs_a_target(
                p, action, "Choose something for the scroll to name."):
            return FREE_COST
        if use == "enchant" and self.needs_a_target(
                p, action, "Choose a weapon or a piece of armour to enchant.",
                want="worn"):
            return FREE_COST

        now = level.clock
        self.appearances.identify(item.key)
        self.sound("magic", p.x, p.y, level.depth)
        consumed = True

        if use == "map":
            self.reveal_level(p, level)
            self.msg("The plan of this floor unfolds in your mind.", "good", to=p)
        elif use == "identify":
            target = p.find_item(int(action.get("target", 0)))
            if target is None:
                self.msg("Nothing to identify. Pick an item first.", "warn", to=p)
                consumed = False
            else:
                target.known = True
                self.appearances.identify(target.key)
                self.msg(f"It is {target.name(self.appearances)}.", "good", to=p)
        elif use == "recall":
            self.msg(f"{p.name} tears open the way home.", "good", depth=level.depth)
            for ally in self.players_on(level.depth):
                self.move_player_to(ally, TOWN_DEPTH)
        elif use == "blink":
            spot = self.random_safe_spot(level, p)
            if spot:
                level.move_actor(p, *spot)
                self.update_fov(p, force=True)
                self.msg("The world lurches, and you are somewhere else.", "good", to=p)
            else:
                consumed = False
        elif use == "uncurse":
            freed = 0
            for slot, worn in p.equipment.items():
                if worn and worn.cursed:
                    worn.cursed = False
                    freed += 1
            self.msg("A weight lifts." if freed else "Nothing here is cursed.",
                     "good" if freed else "info", to=p)
        elif use == "enchant":
            target = p.find_item(int(action.get("target", 0)))
            if target is None or not target.slot:
                self.msg("Choose a weapon or piece of armour to enchant.", "warn", to=p)
                consumed = False
            else:
                target.enchant += 1
                target.known = True
                if target.cursed and target.enchant >= 0:
                    target.cursed = False
                p.recalc()
                self.msg(f"Your {target.base['name']} glows. It is now {target.name(self.appearances)}.", "good", to=p)
        elif use == "firestorm":
            self.fx("firestorm", p.x, p.y, level.depth)
            power = item.base.get("power", 25)
            for m in combat.enemies_near(level, p.x, p.y, 3):
                combat.apply_damage(self, m, power + self.rng.randint(0, 8), p)
            self.msg("Fire roars outward.", "good", to=p)
        elif use == "fear":
            for m in combat.enemies_near(level, p.x, p.y, 6):
                m.add_effect("afraid", now + 400)
            self.msg("A wave of dread rolls out from you.", "good", to=p)

        if consumed:
            p.consume(item, 1)
            self.events.append({"t": "inv", "to": p.id})
            return p.action_cost(READ_COST) or READ_COST
        return FREE_COST

    def read_book(self, level, p, item):
        spell = item.spell
        ok, why = can_learn(spell, p.level, p.stat("intelligence"))
        if not ok:
            self.msg(why, "warn", to=p)
            return FREE_COST
        if spell in p.spells:
            self.msg(f"You already know {spell}.", "info", to=p)
            return FREE_COST
        p.spells.add(spell)
        p.consume(item, 1)
        self.msg(f"You study the tome. {spell} is yours.", "good", to=p)
        self.sound("levelup", p.x, p.y, level.depth)
        self.events.append({"t": "inv", "to": p.id})
        return p.action_cost(READ_COST * 2) or READ_COST

    def reveal_level(self, p, level):
        mem = self.memory_for(p, level)
        for i in range(len(mem)):
            if level.tiles[i] == T.VOID or mem[i]:
                continue
            mem[i] = 1
            p.pending_tiles.extend((i % level.w, i // level.w, level.tiles[i]))

    def random_safe_spot(self, level, p):
        for _ in range(200):
            x = self.rng.randint(1, level.w - 2)
            y = self.rng.randint(1, level.h - 2)
            if not level.walkable(x, y, p.id):
                continue
            if combat.enemies_near(level, x, y, 4):
                continue
            return (x, y)
        return None

    # ---- spells ----------------------------------------------------------
    def apply_slow(self, m, now):
        """Slow stacks, but with diminishing returns.

        The original: "a monster will move at 1/2, then 1/3, then 1/4, then
        1/5 ... of its normal speed" - so each further casting adds one to the
        divisor rather than halving again.
        """
        step = m.slow_steps = getattr(m, "slow_steps", 0) + 1
        m.add_effect("slowed", now + 6000)        # ten minutes of game time
        m.slow_divisor = step + 1

    # Things that cannot happen until you have named an object. Asking first
    # costs nothing; the alternative is what Revelation used to do, which was
    # to take the mana, say "Choose something in your pack first" and leave
    # you no way to choose anything.
    def needs_a_target(self, p, action, prompt, want=None):
        if action.get("target"):
            return False
        self.events.append({"t": "pick", "to": p.id, "prompt": prompt,
                            "want": want, "action": dict(action)})
        return True

    def _act_cast(self, level, p, action):
        name = action.get("spell")
        spell = SPELLS.get(name)
        if spell is None or name not in p.spells:
            self.msg("You do not know that spell.", "warn", to=p)
            return FREE_COST
        if spell.get("identify") and self.needs_a_target(
                p, action, f"{name}: choose something to learn about."):
            return FREE_COST

        # The original lets you overdraw: "You don't have enough mana. Casting
        # this spell may damage your health. Continue?" - you pay the shortfall
        # in hit points instead of being refused.
        cost = mana_cost(spell["mana"], p.level, spell.get("level", 1))
        shortfall = max(0, cost - int(p.mana))
        if shortfall and not action.get("confirm_overdraw"):
            self.events.append({
                "t": "ask", "to": p.id, "key": "confirm_overdraw",
                "text": f"You have not the mana for {name}. Casting it will "
                        f"cost you {shortfall} hit points instead. Go on?",
                "action": dict(action)})
            return FREE_COST

        tx = int(action.get("x", p.x))
        ty = int(action.get("y", p.y))
        rng_limit = spell.get("rng", 0)
        if rng_limit and chebyshev(p.x, p.y, tx, ty) > rng_limit:
            self.msg("That is beyond your reach.", "warn", to=p)
            return FREE_COST

        p.mana = max(0, p.mana - cost)
        if shortfall:
            p.hp -= shortfall
            self.msg("The spell tears at you as you force it out.", "bad", to=p)
            if p.hp <= 0:
                self.kill(p)
                return p.action_cost(spell.get("cast_ticks", CAST_COST))
        now = level.clock
        self.sound("magic", p.x, p.y, level.depth)
        power = p.level

        # --- damage -------------------------------------------------------
        if spell.get("dmg"):
            n, s, per = spell["dmg"]
            def roll():
                return sum(self.rng.randint(1, s) for _ in range(n)) + int(per * power)

            targets = []
            if spell.get("burst"):
                radius = spell["burst"]
                centre = (p.x, p.y) if rng_limit == 0 else (tx, ty)
                self.fx("blast", centre[0], centre[1], level.depth)
                targets = combat.enemies_near(level, centre[0], centre[1], radius)
            elif spell.get("pierce"):
                for (cx, cy) in line_between(p.x, p.y, tx, ty):
                    if is_solid(level.get(cx, cy)):
                        break
                    self.fx("bolt", cx, cy, level.depth)
                    occ = level.actor_at(cx, cy)
                    if occ is not None and occ.kind == "monster" and not occ.dead:
                        targets.append(occ)
            elif spell.get("chain"):
                first = level.actor_at(tx, ty)
                if first is not None and first.kind == "monster":
                    targets.append(first)
                    for extra in combat.enemies_near(level, tx, ty, 4):
                        if extra not in targets and len(targets) < spell["chain"]:
                            targets.append(extra)
            else:
                occ = level.actor_at(tx, ty)
                if occ is not None and occ.kind == "monster" and not occ.dead:
                    targets.append(occ)
                for (cx, cy) in line_between(p.x, p.y, tx, ty):
                    self.fx("bolt", cx, cy, level.depth)

            if not targets:
                self.msg("Your magic finds nothing.", "info", to=p)
            narrated = 0
            for m in targets:
                dmg = roll()
                if spell.get("undead_bonus") and m.tpl.get("undead"):
                    dmg = int(dmg * 1.5)
                # "The monster on the target square takes full damage, and
                # those on the eight adjoining squares take half damage."
                if spell.get("burst") and (m.x, m.y) != (tx, ty):
                    dmg = max(1, dmg // 2)
                dmg = max(1, int(dmg * elemental_factor(spell.get("element"),
                                                        m.tpl)))
                self.fx("hit", m.x, m.y, level.depth)
                # A spell used to say only "You cast Spark." and leave you to
                # guess what it did. Three lines is enough for a Fireball;
                # past that it is a wall of text.
                if narrated < 3:
                    self.msg(combat.blow_message(
                        self.rng, p, m, dmg, dmg >= m.hp,
                        style=spell.get("element", "blast")), "combat", to=p)
                    narrated += 1
                combat.apply_damage(self, m, dmg, p, killed_by_a_blow=narrated <= 3)
                if not m.dead:
                    if spell.get("burn"):
                        m.add_effect("burning", now + 400, 4)
                    if spell.get("slow"):
                        self.apply_slow(m, now)
            if len(targets) > narrated:
                rest = len(targets) - narrated
                self.msg(f"...and {rest} other{'' if rest == 1 else 's'} "
                         f"caught in it.", "combat", to=p)

        # --- healing ------------------------------------------------------
        if spell.get("heal_flat") or spell.get("heal_full"):
            def heal_amount(who):
                if spell.get("heal_full"):
                    return who.max_hp
                return max(spell["heal_flat"],
                           int(spell.get("heal_frac", 0) * who.max_hp))
            amount = heal_amount(p)
            if spell.get("party"):
                for ally in combat.players_near(level, p.x, p.y, spell.get("rng", 4)):
                    combat.heal(self, ally, heal_amount(ally))
                    self.fx("heal", ally.x, ally.y, level.depth)
                self.msg(f"You cast {name}. Everyone nearby is mended.", "good", to=p)
            else:
                target = level.actor_at(tx, ty)
                if target is None or target.kind != "player":
                    target = p
                got = combat.heal(self, target, heal_amount(target))
                self.fx("heal", target.x, target.y, level.depth)
                # Say what it did, as the potions do. "You cast Mend Wounds."
                # tells you nothing about whether it was worth the mana.
                who = "you" if target is p else target.name
                if got:
                    self.msg(f"Warmth closes the wounds on {who} "
                             f"({got} healed).", "good", to=p)
                else:
                    self.msg(f"There is nothing on {who} left to mend.",
                             "info", to=p)

        # --- everything else ----------------------------------------------
        if spell.get("cure"):
            lifted = [bad for bad in ("poisoned", "burning", "afraid", "slowed",
                                      "poison_later")
                      if p.effects.pop(bad, None) is not None]
            # It used to cure in silence, which looked exactly like a spell
            # that had failed.
            if lifted:
                self.msg("The sickness goes out of you.", "good", to=p)
            else:
                self.msg("Nothing ails you.", "info", to=p)
        if spell.get("light"):
            # "Cast in a hallway, it will light the 3x3 square region around
            # the target square. In a room, however, the entire room is lit."
            room = next((r for r in level.rooms
                         if r["x"] <= tx < r["x"] + r["w"]
                         and r["y"] <= ty < r["y"] + r["h"]), None)
            mem = self.memory_for(p, level)

            def light(xx, yy):
                """Remember a square, and queue it for the client.

                Setting the memory bit alone was not enough, and was worse
                than doing nothing: update_fov only sends a tile when the
                bit is *not* already set, so a square lit this way could
                never be sent again. Lantern said "Light fills the room",
                took the mana, and the room stayed black for the rest of
                the game unless you left the floor and came back.
                """
                if not level.in_bounds(xx, yy):
                    return
                i = level.idx(xx, yy)
                if not mem[i]:
                    mem[i] = 1
                    p.pending_tiles.extend((xx, yy, level.tiles[i]))

            if room:
                for yy in range(room["y"], room["y"] + room["h"]):
                    for xx in range(room["x"], room["x"] + room["w"]):
                        light(xx, yy)
                self.msg("Light fills the room.", "good", to=p)
            else:
                for yy in range(ty - 1, ty + 2):
                    for xx in range(tx - 1, tx + 2):
                        light(xx, yy)
                self.msg("A pool of light spreads around you.", "good", to=p)

        if spell.get("sleep"):
            occ = level.actor_at(tx, ty)
            if occ is not None and occ.kind == "monster" and not occ.dead:
                occ.add_effect("asleep", now + spell["sleep"] * 10)
                occ.target_id = None
                self.msg(f"The {occ.name} slumps where it stands.", "good", to=p)
            else:
                self.msg("Nothing there to lull.", "info", to=p)

        if spell.get("transmogrify"):
            occ = level.actor_at(tx, ty)
            if occ is not None and occ.kind == "monster" and not occ.dead:
                self.transmogrify(level, occ, p)
            else:
                self.msg("Nothing there to reshape.", "info", to=p)

        if spell.get("resist"):
            el = spell["resist"]
            stacks = getattr(p, "resist_stacks", None)
            if stacks is None:
                stacks = p.resist_stacks = {}
            stacks[el] = stacks.get(el, 0) + 1
            p.add_effect(f"resist_{el}", now + spell.get("dur", 90) * 10)
            self.msg(f"You cast {name}. "
                     + ("You are warded twice over." if stacks[el] > 1
                        else f"{el.title()} will find you harder to hurt."),
                     "good", to=p)
        if spell.get("ac"):
            dur = spell.get("dur", 40) * 10
            key = "stoneskin" if name == "Stoneskin" else "shield_spell"
            if spell.get("party"):
                for ally in combat.players_near(level, p.x, p.y, spell.get("rng", 4)):
                    ally.add_effect(key, now + dur, spell["ac"])
            else:
                p.add_effect(key, now + dur, spell["ac"])
            self.msg(f"You cast {name}.", "good", to=p)
        if spell.get("halve"):
            p.add_effect("sanctuary", now + spell.get("dur", 30) * 10)
            self.msg("A stillness settles over you.", "good", to=p)
        if spell.get("haste"):
            p.add_effect("haste", now + spell.get("dur", 40) * 10)
            self.msg("You quicken.", "good", to=p)
        if spell.get("feather"):
            p.add_effect("feather", now + spell.get("dur", 90) * 10)
            self.msg("Your burden stops mattering.", "good", to=p)
        if spell.get("truesight"):
            p.add_effect("truesight", now + spell.get("dur", 60) * 10)
            self.update_fov(p, force=True)
            self.msg("The dark thins, and the walls give up what they hide.",
                     "good", to=p)
        if spell.get("detect"):
            p.add_effect(f"detect_{spell['detect']}", now + spell.get("dur", 80) * 10)
            self.msg(f"You sense the {spell['detect']} on this floor.", "good", to=p)
        if spell.get("reveal"):
            self.reveal_level(p, level)
            self.msg("The whole floor lies open in your mind.", "good", to=p)
        if spell.get("clairvoyance"):
            radius = spell["clairvoyance"]
            mem = self.memory_for(p, level)
            found = 0
            for y in range(max(0, p.y - radius), min(level.h, p.y + radius + 1)):
                for x in range(max(0, p.x - radius), min(level.w, p.x + radius + 1)):
                    i = level.idx(x, y)
                    if level.tiles[i] != T.VOID and not mem[i]:
                        mem[i] = 1
                        p.pending_tiles.extend((x, y, level.tiles[i]))
                    secret = level.secrets.get((x, y))
                    if secret and not secret["found"]:
                        secret["found"] = True
                        self.set_tile(level, x, y, T.DOOR)
                        found += 1
                    trap = level.traps.get((x, y))
                    if trap and not trap["found"]:
                        trap["found"] = True
                        found += 1
            self.msg("The ground around you comes clear." +
                     (f" {found} things were hiding in it." if found else ""),
                     "good", to=p)
        if spell.get("find_traps"):
            # Certain inside the radius, and a fading chance beyond it.
            sure = spell["find_traps"]
            found = 0
            for (x, y), trap in level.traps.items():
                if trap["found"]:
                    continue
                gap = chebyshev(x, y, p.x, p.y)
                if gap <= sure or self.rng.random() < sure / max(1, gap * 2):
                    trap["found"] = True
                    found += 1
            self.msg(f"You sense {found} trap{'' if found == 1 else 's'}."
                     if found else "Nothing underfoot is waiting for you.",
                     "good" if found else "info", to=p)
        if spell.get("identify"):
            target = p.find_item(int(action.get("target", 0)))
            if target is not None:
                target.known = True
                self.appearances.identify(target.key)
                self.msg(f"It is {target.name(self.appearances)}.", "good", to=p)
            else:
                self.msg("Choose something in your pack first.", "warn", to=p)
        if spell.get("blink"):
            # "Phase Door ... transports the player to a random location from 5
            # to 10 squares from his or her current position"; Teleport moves
            # you "at least 10 squares".
            lo, hi = spell["blink"]
            spot = self.random_spot_between(level, p, lo, hi)
            if spot:
                level.move_actor(p, *spot)
                self.update_fov(p, force=True)
                self.msg("You blink away.", "good", to=p)
        if spell.get("passwall"):
            fx, fy = DIRS[p.facing]
            opened = 0
            for step in range(1, 4):
                cx, cy = p.x + fx * step, p.y + fy * step
                if level.get(cx, cy) == T.WALL:
                    self.set_tile(level, cx, cy, T.FLOOR)
                    opened += 1
            self.msg("Stone flows aside." if opened else "There is no wall there.",
                     "good" if opened else "warn", to=p)
        if spell.get("recall"):
            # The original's Rune of Return works both ways: "From inside the
            # mine ... the spell will return the player to the ground level ...
            # From ground level ... the spell teleports the player to the
            # deepest place the player has visited so far." That second half is
            # the whole point - you do not fight back down every time.
            if level.is_town:
                target = max(1, p.deepest or 1)
                if target <= TOWN_DEPTH:
                    self.msg("You have not yet been anywhere to return to.",
                             "info", to=p)
                else:
                    self.msg(f"{p.name} steps back into the deep.", "good",
                             depth=level.depth)
                    for ally in self.players_on(level.depth):
                        self.move_player_to(ally, target)
            else:
                self.msg(f"{p.name} opens the road home.", "good", depth=level.depth)
                for ally in self.players_on(level.depth):
                    self.move_player_to(ally, TOWN_DEPTH)

        p.recalc()
        return p.action_cost(spell.get("cast_ticks", CAST_COST)) or CAST_COST

    # ---- stairs ----------------------------------------------------------
    # Drinking and sitting: "can have beneficial or harmful effects, or may do
    # nothing at all". The gamble is the mechanic - you take it when you are
    # desperate, and sometimes it is worse than being desperate.
    def summon_near(self, level, p, n=2):
        """Something notices you. Used by thrones, and by cursed items."""
        table = spawn_table(level.depth)
        called = 0
        for _ in range(n):
            spot = level.find_free(p.x + self.rng.randint(-4, 4),
                                   p.y + self.rng.randint(-4, 4), 6)
            if not spot or not level.walkable(*spot):
                continue
            m = self.spawn(self._weighted(table), spot[0], spot[1], level.depth)
            m.target_id = p.id
            level.place(m)
            called += 1
        if called:
            self.msg("Something has been waiting for a sitter. It comes.",
                     "bad", to=p)
        return called

    def _act_fountain(self, level, p, action):
        if level.get(p.x, p.y) != T.FOUNTAIN:
            self.msg("There is no fountain here.", "info", to=p)
            return FREE_COST
        roll = self.rng.random()
        if roll < 0.30:
            combat.heal(self, p, max(4, p.max_hp // 4))
            self.msg("The water is cold and clean. You feel better.", "good", to=p)
        elif roll < 0.45:
            p.mana = p.max_mana
            self.msg("The water sings on your tongue. Your magic returns.",
                     "good", to=p)
        elif roll < 0.60:
            self.msg("The water is brackish and does nothing at all.", "info", to=p)
        elif roll < 0.80:
            p.add_effect("poisoned", level.clock + 500, 3)
            self.msg("The water is foul. Your stomach turns.", "bad", to=p)
        else:
            self.drain_player(p, "body")
        return p.action_cost(QUAFF_COST) or QUAFF_COST

    def _act_throne(self, level, p, action):
        if level.get(p.x, p.y) != T.THRONE:
            self.msg("There is no throne here.", "info", to=p)
            return FREE_COST
        roll = self.rng.random()
        if roll < 0.25:
            got = self.rng.randint(200, 900) * max(1, p.depth)
            p.gain_coins("gold", max(1, got // 100))
            self.msg(f"A hidden compartment springs open. {got} copper of gold.",
                     "loot", to=p)
        elif roll < 0.40:
            stat = self.rng.choice(list(STATS))
            p.stats[stat] = min(25, p.stats[stat] + 1)
            p.recalc()
            self.msg(f"Something old and approving settles on you. "
                     f"Your {stat} improves.", "good", to=p)
        elif roll < 0.60:
            self.msg("You sit. Nothing whatever happens.", "info", to=p)
        elif roll < 0.80:
            self.summon_near(level, p)
        else:
            self.drain_player(p, "body")
        return p.action_cost(REST_COST) or REST_COST

    def _act_stairs(self, level, p, action):
        tile = level.get(p.x, p.y)
        if tile == T.STAIRS_DOWN:
            target = max(1, self.party_deepest) if level.is_town else p.depth + 1
            if target > DEEP_LIMIT:
                self.msg("There is nothing deeper than this.", "info", to=p)
                return FREE_COST
            self.msg(f"{p.name} goes down.", "info", depth=level.depth)
            self.move_player_to(p, target)
            return p.action_cost(STAIRS_COST) or STAIRS_COST
        if tile == T.STAIRS_UP:
            target = p.depth - 1
            if target < TOWN_DEPTH:
                return FREE_COST
            self.msg(f"{p.name} climbs up.", "info", depth=level.depth)
            self.move_player_to(p, target)
            return p.action_cost(STAIRS_COST) or STAIRS_COST
        self.msg("There are no stairs here.", "info", to=p)
        return FREE_COST

    def move_player_to(self, p, depth):
        old = self.levels.get(p.depth)
        if old:
            old.remove(p)
        level = self.get_level(depth)
        going_down = depth > p.depth
        anchor = level.up_at if going_down else (level.down_at or level.spawn_point or level.up_at)
        p.depth = depth
        p.x, p.y = level.find_free(anchor[0], anchor[1], 12)
        p.next_at = level.clock
        p.pending = None
        level.place(p)
        if depth > 0:
            p.deepest = max(p.deepest, depth)
            self.party_deepest = max(self.party_deepest, depth)
        if depth == TOWN_DEPTH:
            self.shop_stock.clear()
        self.update_fov(p, force=True)
        self.resend_level(p)
        self.events.append({"t": "level", "to": p.id})
        if level.boss_key and getattr(level, "boss", None) and not level.boss.dead:
            entry = level.boss.tpl.get("entry")
            if entry:
                self.msg(entry, "bad", to=p)

    # ---- monsters acting -------------------------------------------------
    def resisted(self, target, element, dmg):
        """Damage after the target's resistances, which stack multiplicatively."""
        if not element:
            return dmg
        stacks = getattr(target, "resist_stacks", {}).get(element, 0)
        if target.has(f"resist_{element}"):
            stacks = max(1, stacks)
        return max(1, int(dmg * (0.5 ** stacks))) if stacks else dmg

    def random_spot_between(self, level, p, lo, hi):
        """A free square between lo and hi paces away, if there is one."""
        over = None            # nearest candidate that is at least far enough
        for _ in range(120):
            spot = self.random_safe_spot(level, p)
            if not spot:
                continue
            d = chebyshev(p.x, p.y, spot[0], spot[1])
            if lo <= d <= hi:
                return spot
            if d >= lo and (over is None or d < over[1]):
                over = (spot, d)
        return over[0] if over else None

    def monster_ranged(self, level, m, target):
        kind = m.tpl.get("bolt", "spark")
        for (cx, cy) in line_between(m.x, m.y, target.x, target.y):
            if is_solid(level.get(cx, cy)):
                return
            self.fx("bolt", cx, cy, level.depth)
            if (cx, cy) == (target.x, target.y):
                break
        self.sound("shoot", m.x, m.y, level.depth)
        hit, crit = combat.attack_roll(self.rng, m.to_hit, target.armour_class)
        style = "shoot" if m.tpl.get("ammo") else "blast"
        if not hit:
            self.msg(combat.ranged_miss_message(self.rng, m, target),
                     "combat", to=target)
            return
        dmg = m.damage_roll(self.rng)
        # A player's resistances halve elemental damage, and stack: "casting
        # two Resist Cold spells cuts the damage from White Dragon breath to
        # 1/4 its normal value."
        dmg = self.resisted(target, kind, dmg)
        dealt = dmg * (2 if crit else 1)
        self.msg(combat.blow_message(self.rng, m, target, dealt,
                                     dealt >= target.hp, style=style),
                 "hurt", to=target)
        combat.apply_damage(self, target, dealt, m, crit=crit,
                            killed_by_a_blow=True)
        if m.tpl.get("burn") and not target.dead:
            target.add_effect("burning", level.clock + 400, 4)

    def boss_special(self, level, m, target):
        roll = self.rng.random()
        if m.tpl.get("summons") and roll < 0.4:
            self.msg(f"{m.name} calls for his guard!", "bad", depth=level.depth)
            for _ in range(2):
                sx, sy = level.find_free(m.x + self.rng.randint(-3, 3),
                                         m.y + self.rng.randint(-3, 3), 6)
                if not level.walkable(sx, sy):
                    continue
                key = self.rng.choice(m.tpl["summons"])
                add = self.spawn(key, sx, sy, level.depth)
                add.next_at = level.clock + 100
                add.target_id = target.id
                level.place(add)
                self.fx("blast", sx, sy, level.depth)
            return
        self.msg(f"{m.name} brings the ground up under you!", "bad", depth=level.depth)
        self.fx("blast", m.x, m.y, level.depth)
        self.sound("slam", m.x, m.y, level.depth)
        for victim in combat.players_near(level, m.x, m.y, 3):
            combat.apply_damage(self, victim, m.damage_roll(self.rng) + 4, m)
            if not victim.dead:
                combat.knock_back(self, m, victim, m.tpl.get("knockback", 1))

    # ---- death -----------------------------------------------------------
    def kill(self, target, source=None, announce=True):
        if target.dead:
            return
        level = self.levels.get(target.depth)
        target.dead = True

        if target.kind == "monster":
            target.hp = 0
            if level:
                level.remove(target)
                self.fx("death", target.x, target.y, level.depth)
                self.sound("die", target.x, target.y, level.depth)
                if self.rng.random() < (1.0 if target.boss else 0.35):
                    drops = 5 if target.boss else 1
                    for _ in range(drops):
                        level.add_ground_item(target.x, target.y,
                                              generate_item(target.depth, self.rng, target.boss))
                if self.rng.random() < (1.0 if target.boss else 0.5):
                    mult = 10 if target.boss else 1
                    level.add_ground_item(target.x, target.y,
                                          self._gold_item(generate_gold(target.depth, self.rng) * mult,
                                                          target.depth))
            nearby = [p for p in self.players_on(target.depth)
                      if not p.dead and chebyshev(p.x, p.y, target.x, target.y) <= 12]
            if nearby:
                share = max(1, int(target.xp_value / max(1, len(nearby) * 0.8)))
                for p in nearby:
                    for lvl in p.add_xp(share):
                        self.msg(f"{p.name} reaches level {lvl}.", "good", depth=target.depth)
                        self.sound("levelup", p.x, p.y, target.depth)
            if source is not None and source.kind == "player":
                source.kills += 1
            if announce:
                # A blow that killed it has already said so, in better words.
                self.msg(f"The {target.name} dies.", "kill", depth=target.depth)
            if target.boss:
                self.msg(f"{target.name} falls!", "good", depth=target.depth)
                self.uncover_the_deep(level)
                if target.key == "vaelrik":
                    self.msg("The storm over Aldershade breaks. The keep is yours.",
                             "good", depth=target.depth)
                    for p in self.players_on(target.depth):
                        p.won = True
            return

        # --- a player has died ---------------------------------------------
        self.msg(f"{target.name} has been killed!", "bad", depth=target.depth)
        self.sound("death", target.x, target.y, target.depth)
        if level:
            # You drop what you were carrying where you fell. Your worn gear
            # comes with you; the pack does not.
            for item in list(target.inventory):
                level.add_ground_item(target.x, target.y, item)
            target.inventory.clear()
            if target.copper > 0:
                lost = int(target.copper * DEATH_GOLD_PENALTY)
                if lost:
                    level.add_ground_item(target.x, target.y, self._gold_item(lost))
                    target.copper -= lost
            level.remove(target)

        target.deaths += 1
        target.xp = max(0, int(target.xp * (1 - DEATH_XP_PENALTY)))
        target.effects.clear()
        target.dead = False
        target.recalc()
        target.hp = max(1, int(target.max_hp * RESURRECT_HP_FRACTION))
        target.mana = target.max_mana // 2
        # Say it before moving them: the arrival message must not come first.
        self.events.append({"t": "died", "to": target.id})
        self.msg("You wake on the flagstones of the temple. Your pack is gone, "
                 "and so is some of what you knew.", "bad", to=target)
        self.move_player_to(target, TOWN_DEPTH)
        self.events.append({"t": "inv", "to": target.id})

    def _act_stow(self, level, p, action):
        """Move something from the pack onto a belt or into the quiver.

        Without this the belt was unreachable: nothing in the game ever put
        anything on one, and since "objects in your pack cannot be
        activated", no potion, scroll or wand could ever be used at all.
        """
        item = p.find_item(int(action.get("id", 0)))
        if item is None:
            return FREE_COST
        slot = action.get("slot", "waist")
        holder = p.equipment.get(slot)
        if holder is None or holder.contents is None:
            self.msg("You are not wearing anything that would hold it.",
                     "warn", to=p)
            return FREE_COST
        if holder.base.get("wands_only") and not item.base.get("charges"):
            self.msg(f"The {holder.name(self.appearances)} is for wands.",
                     "warn", to=p)
            return FREE_COST
        if holder.base.get("coins_only"):
            self.msg("That is for coin.", "warn", to=p)
            return FREE_COST
        slots = holder.base.get("belt_slots")
        if slots is not None and len(holder.contents) >= slots:
            self.msg(f"The {holder.name(self.appearances)} is full.",
                     "warn", to=p)
            return FREE_COST
        # One goes on the belt, so weigh one - not the six in your pack.
        # Weighing the lot meant a stack of potions could never be reached
        # for at all: the belt refused the whole armful and you drank none
        # of it.
        unit = self.unit_of(item)
        if (sum(i.weight for i in holder.contents) + unit.weight
                > holder.base.get("capacity", 0)
                or sum(i.bulk for i in holder.contents) + unit.bulk
                > holder.base.get("bulk_capacity", 0)):
            self.msg(f"That will not fit in the "
                     f"{holder.name(self.appearances)}.", "warn", to=p)
            return FREE_COST

        moved = p.remove_item(item, 1)
        if moved is None:
            return FREE_COST
        holder.contents.append(moved)
        p.recalc()
        self.msg(f"You put {with_article(moved.name(self.appearances))} on your "
                 f"{holder.name(self.appearances)}.", "info", to=p)
        self.events.append({"t": "inv", "to": p.id})
        return p.action_cost(EQUIP_COST) or EQUIP_COST

    def _act_unstow(self, level, p, action):
        """Take something back off the belt and into the pack."""
        wanted = int(action.get("id", 0))
        for slot in ("waist", "quiver"):
            holder = p.equipment.get(slot)
            for item in list(getattr(holder, "contents", None) or []):
                if item.id != wanted:
                    continue
                ok, why = p.room_for(item)
                if not ok:
                    self.msg(why, "warn", to=p)
                    return FREE_COST
                holder.contents.remove(item)
                p.inventory.append(item)
                p.recalc()
                self.msg(f"You put {with_article(item.name(self.appearances))} "
                         f"back in your pack.", "info", to=p)
                self.events.append({"t": "inv", "to": p.id})
                return p.action_cost(EQUIP_COST) or EQUIP_COST
        return FREE_COST

    def _act_sort(self, level, p, action):
        """Tidy the pack. Costs nothing: it is your own pack."""
        p.sort_pack(self.appearances)
        self.msg("You tidy your pack.", "info", to=p)
        self.events.append({"t": "inv", "to": p.id})
        return FREE_COST

    def _act_callme(self, level, p, action):
        """Rename the character.

        "You may rename your character during the game, adding such
        descriptions as you feel you deserve (the bold, the mighty)."
        """
        raw = str(action.get("name", ""))
        clean = "".join(ch for ch in raw if ch.isprintable()).strip()[:24]
        if not clean or clean == p.name:
            return FREE_COST
        taken = {q.name.lower() for q in self.players.values() if q is not p}
        if clean.lower() in taken:
            self.msg(f"Somebody in the keep is already called {clean}.",
                     "warn", to=p)
            return FREE_COST
        was = p.name
        p.name = clean
        self.msg(f"{was} will be known as {clean} from here on.", "good",
                 depth=p.depth)
        self.events.append({"t": "renamed", "to": p.id, "was": was,
                            "name": clean})
        return FREE_COST

    def _act_rename(self, level, p, action):
        """Let a player call a thing whatever they like."""
        item = p.find_item(int(action.get("id", 0)))
        if item is None:
            return FREE_COST
        raw = str(action.get("name", ""))
        clean = "".join(ch for ch in raw if ch.isprintable()).strip()[:24]
        old = item.name(self.appearances)
        item.custom_name = clean or None
        if clean:
            self.msg(f"You will call it {clean} from now on.", "info", to=p)
        else:
            self.msg(f"It goes back to being {item.name(self.appearances)}.", "info", to=p)
        self.events.append({"t": "inv", "to": p.id})
        return FREE_COST

    # ====================================================== shops ===========
    # The temple's price list. Restoration costs the most because being
    # drained is the worst thing that can quietly happen to a character.
    TEMPLE_SERVICES = (
        ("heal_minor",   "Heal Minor Wounds",        500),
        ("heal_medium",  "Heal Medium Wounds",       900),
        ("heal_major",   "Heal Major Wounds",       1400),
        ("heal_full",    "Heal",                    2500),
        ("uncurse",      "Remove Curse",            2500),
        ("cure_poison",  "Neutralize Poison",       1800),
        ("rune_return",  "Rune of Return",          1000),
        ("restore_strength",     "Restore Strength",     3000),
        ("restore_intelligence", "Restore Intelligence", 3000),
        ("restore_constitution", "Restore Constitution", 3000),
        ("restore_dexterity",    "Restore Dexterity",    3000),
        ("restore_hp",   "Restore Drained Hit Points", 3000),
    )

    # What each kind of undead takes from you, from the original's bestiary:
    # a wight's touch drains "strength, constitution, and dexterity"; a wraith
    # drains "the magical powers of men they encounter, or if that fails as
    # well, drain the intelligence from their minds"; a vampire drains hit
    # points "in such a manner that the victim will not recover without the aid
    # of special enchantment".
    BODY_STATS = ("strength", "constitution", "dexterity")

    def uncover_the_deep(self, level):
        """The stairs behind the throne, once the last boss is down.

        The story ends on floor 25 for anybody who wants it to. For anybody
        who does not, this is the way on: everything below is built from the
        same tables, scaled by depth, so a character who has been levelled to
        the ceiling has somewhere left to go - and anything added to those
        tables later turns up down there without starting again.
        """
        spot = getattr(level, "deep_stairs_at", None)
        if spot is None or level.down_at is not None:
            return
        x, y = spot
        if not level.in_bounds(x, y) or is_solid(level.get(x, y)):
            spot = level.find_floor(x, y)
            if spot is None:
                return
            x, y = spot
        level.down_at = (x, y)
        self.set_tile(level, x, y, T.STAIRS_DOWN)
        self.msg("Behind the throne, a stair goes down into the dark. "
                 "Nobody has ever written down what is under here.",
                 "good", depth=level.depth)

    def drain_player(self, player, kind, source=None):
        """Something took a piece of you that will not simply grow back."""
        lost = 0
        if kind in ("hp", "maxhp"):
            lost = player.drain_hp(self.rng.randint(2, 5))
            if lost:
                self.msg(f"You feel weaker. ({lost} hit points drained)", "bad", to=player)
        elif kind == "mana":
            take = min(int(player.mana), self.rng.randint(2, 6))
            if take:
                player.mana -= take
                lost = take
                self.msg("Your magic is drawn out of you.", "bad", to=player)
            else:
                # "or if that fails as well, drain the intelligence"
                lost = player.drain_stat("intelligence", 1)
                if lost:
                    self.msg("It takes the sharpness from your mind.", "bad", to=player)
        elif kind == "mind":
            lost = player.drain_stat("intelligence", 1)
            if lost:
                self.msg("It takes the sharpness from your mind.", "bad", to=player)
        else:
            stat = self.rng.choice(self.BODY_STATS if kind == "body"
                                   else list(STATS))
            lost = player.drain_stat(stat, 1)
            if lost:
                self.msg(f"You feel your {stat} ebbing away.", "bad", to=player)
        if lost:
            self.fx("death", player.x, player.y, player.depth)
            self.events.append({"t": "inv", "to": player.id})

    def temple_services(self, p):
        """Which services are worth offering this character, and what they cost."""
        out = []
        for key, label, price in self.TEMPLE_SERVICES:
            useful = True
            if key.startswith("heal") and p.hp >= p.max_hp:
                useful = False
            elif key == "cure_poison" and not p.has("poisoned"):
                useful = False
            elif key == "uncurse":
                # Deliberately always offered. The original explains why: it is
                # "always available since it would give the player hints about
                # unidentified objects to gray it". Greying it out would tell
                # you for free whether anything you are wearing is cursed.
                useful = True
            elif key.startswith("restore_") and key != "restore_hp":
                stat = key.split("_", 1)[1]
                useful = p.drained.get(stat, 0) > 0
            elif key == "restore_hp":
                useful = p.drained_hp > 0
            out.append({"key": key, "label": label, "price": price,
                        "useful": useful, "afford": p.copper >= price})
        return out

    def buy_service(self, p, key):
        price = dict((k, v) for k, _l, v in self.TEMPLE_SERVICES).get(key)
        if price is None:
            return
        if p.copper < price:
            self.msg(f"That costs {price} copper. You have {p.copper}.", "warn", to=p)
            self.sound("deny", p.x, p.y, p.depth)
            return

        healed = {"heal_minor": 0.25, "heal_medium": 0.5,
                  "heal_major": 0.75, "heal_full": 1.0}.get(key)
        if healed is not None:
            if p.hp >= p.max_hp:
                self.msg("You are not hurt.", "info", to=p)
                return
            p.copper -= price
            combat.heal(self, p, int(p.max_hp * healed) if healed < 1 else p.max_hp)
            if healed >= 1.0:
                p.mana = p.max_mana
            self.sound("heal", p.x, p.y, p.depth)
            self.msg("The sisters lay hands on you.", "good", to=p)
        elif key == "cure_poison":
            p.copper -= price
            for bad in ("poisoned", "burning"):
                p.effects.pop(bad, None)
            self.msg("The sickness is drawn out of you.", "good", to=p)
        elif key == "uncurse":
            cursed = [i for i in p.equipment.values() if i and i.cursed]
            if not cursed:
                self.msg("Nothing you carry is cursed.", "info", to=p)
                return
            p.copper -= price
            for item in cursed:
                item.cursed = False
            self.msg("The binding breaks.", "good", to=p)
        elif key == "rune_return":
            scroll = Item("scroll_teleport")
            scroll.known = True
            ok, why = p.room_for(scroll)
            if not ok:
                self.msg(why, "warn", to=p)
                return
            p.copper -= price
            p.add_item(scroll)
            self.appearances.identify("scroll_teleport")
            self.msg("They cut a rune of return for you.", "good", to=p)
        elif key == "restore_hp":
            if not p.drained_hp:
                self.msg("Nothing has been taken from you.", "info", to=p)
                return
            p.copper -= price
            back = p.restore_hp_drain()
            self.msg(f"You are made whole again. ({back} hit points restored)",
                     "good", to=p)
        elif key.startswith("restore_"):
            stat = key.split("_", 1)[1]
            if not p.drained.get(stat):
                self.msg(f"Your {stat} is not diminished.", "info", to=p)
                return
            p.copper -= price
            back = p.restore_stat(stat)
            self.msg(f"Your {stat} returns to you. ({back} restored)", "good", to=p)
        else:
            return

        p.recalc()
        self.events.append({"t": "inv", "to": p.id})

    def stock_for(self, shop):
        """What a trader has on the shelves. Restocked when the party comes home."""
        cached = self.shop_stock.get(shop)
        if cached is not None:
            return cached
        rng = random.Random(self.rng.randrange(1 << 30))
        depth = max(1, self.party_deepest)
        items = []

        # The staples are always on the shelf. A shuffled pool of seven can
        # leave a trade with nothing basic in it, and a character who cannot
        # buy a sword or a coat before going down is finished before the
        # first floor: one run in three ended with a dagger and no armour
        # because of what the dice did in town.
        if shop == "weaponsmith":
            for key in ("dagger", "shortsword", "longsword"):
                staple = Item(key)
                staple.known = True
                items.append(staple)
            pool = [k for k, b in BASES.items()
                    if b.get("slot") == "weapon" and b.get("depth", 0) <= depth + 2
                    and k not in ("dagger", "shortsword", "longsword")]
            rng.shuffle(pool)
            for key in pool[:5]:
                it = Item(key, enchant=1 if rng.random() < 0.25 else 0)
                it.known = True
                items.append(it)
        elif shop == "armourer":
            for key in ("cap", "leather", "buckler"):
                staple = Item(key)
                staple.known = True
                items.append(staple)
            pool = [k for k, b in BASES.items()
                    if b.get("slot") in ("torso", "head", "shield", "arms", "feet", "legs", "back", "waist")
                    and b.get("depth", 0) <= depth + 2
                    and k not in ("cap", "leather", "buckler")]
            rng.shuffle(pool)
            for key in pool[:6]:
                it = Item(key, enchant=1 if rng.random() < 0.2 else 0)
                it.known = True
                items.append(it)
        elif shop == "general":
            # What the original's general store had on the shelf: containers,
            # belts sized in slots, and the soft gear the armourer doesn't
            # bother with. No light sources - the original has none.
            for key in ("pack", "sack", "purse", "belt", "belt3",
                        "cloak", "boots"):
                items.append(Item(key))
        elif shop == "magic":
            for key in ("potion_heal", "potion_mana", "scroll_map", "scroll_ident", "scroll_teleport"):
                it = Item(key, qty=2)
                it.known = True
                items.append(it)
            extra = [k for k, b in BASES.items()
                     if b.get("kind") in ("potion", "scroll") and b.get("depth", 0) <= depth + 1
                     and not b.get("bad")]
            rng.shuffle(extra)
            for key in extra[:3]:
                it = Item(key)
                it.known = True
                items.append(it)
            from .spells import spells_for_sale, make_tome
            for name in spells_for_sale(depth, rng, 4):
                items.append(make_tome(name))
        elif shop == "temple":
            for key in ("potion_heal", "potion_cure", "scroll_uncurse"):
                it = Item(key, qty=2)
                it.known = True
                items.append(it)

        self.shop_stock[shop] = items
        return items

    # "The Junk Store ... will buy anything, for market price (if it's less
    # than 25 C.P.), or for 25 C.P. if it's cursed or worthless. Anything sold
    # to this store is gone for good."
    JUNK_FLAT = JUNK_FLAT

    def junk_price(self, item):
        """Nan buys anything, and always badly.

        The original's rule exactly: market price when that is under 25, and
        a flat 25 otherwise - so she pays the same twenty-five for a suit of
        plate as for a cursed ring. This once paid a tenth of the value on
        the grounds that offering the same for a quarrel and a breastplate
        was insulting. It is meant to be: she is where you dump what no
        trade will take, and the armourer at four fifths is where a
        breastplate goes.
        """
        value = item.value()
        if item.cursed or value <= 0:
            return self.JUNK_FLAT
        return value if value < self.JUNK_FLAT else self.JUNK_FLAT

    # What each trade will take off your hands. "Shops refuse junk:
    # 'We don't buy those...', 'We don't buy worthless items!'"
    SHOP_TAKES = {
        "weaponsmith": ("weapon",),
        "armourer": ("armour",),
        "general": ("container", "armour"),
        "magic": ("potion", "scroll", "book", "ring", "amulet", "wand"),
        "sage": ("potion", "scroll", "book", "ring", "amulet", "wand"),
        "temple": ("potion", "scroll"),
    }

    @staticmethod
    def trade_of(item):
        """Which trade an object belongs to."""
        base = item.base
        if base.get("slot") == "weapon":
            return "wand" if base.get("charges") else "weapon"
        if base.get("kind") == "container":
            return "container"
        if base.get("slot"):
            return "armour"
        return base.get("kind") or "oddment"

    def shop_refusal(self, shop, item):
        """Why this trade will not take it, or None if they will."""
        # value() floors at one, and that floor is exactly where a ruined
        # thing lands: a Rusty -3 Dagger is worth less than nothing before
        # the floor catches it.
        if item.value() <= 1 or item.kind == "coins":
            return "We don't buy worthless items!"
        if shop == "junk":
            return None                       # Nan takes anything
        takes = self.SHOP_TAKES.get(shop)
        if takes is None:
            return None
        if self.trade_of(item) not in takes:
            return "We don't buy those..."
        return None

    @staticmethod
    def unit_of(item):
        """One of whatever this is: a lot of three potions sells singly."""
        if item.stackable and item.qty > 1:
            one = Item(item.key, qty=1)
            one.known = item.known
            return one
        return item

    def sell_offer(self, shop, item):
        """What a shop will actually hand over for something.

        There is one of these because there used to be two: the window
        quoted `shop_price(selling=True)` for every shop alike while the sale
        paid `junk_price` at Nan's. She offered you 129 copper for a sword
        and gave you twenty-five, and the only thing wrong with the sale was
        that nobody had told the window.
        """
        if self.shop_refusal(shop, item):
            return 0            # she will not take it; do not put a price on it
        return (self.junk_price(item) if shop == "junk"
                else self.shop_price(item, selling=True))

    def shop_price(self, item, selling=False):
        value = item.value()
        return (max(1, int(value * SHOP_SELL_RATE)) if selling
                else max(1, int(value * SHOP_BUY_MARKUP)))

    def _act_buy(self, level, p, action):
        shop = action.get("shop")
        stock = self.stock_for(shop)
        item = next((i for i in stock if i.id == int(action.get("id", 0))), None)
        if item is None:
            self.msg("That is not on the shelf.", "warn", to=p)
            return FREE_COST
        # Work out what is actually leaving the shelf before pricing it. One
        # drag out of a stack of two potions buys one potion, so the lot's
        # price is neither what you are charged nor what you should be
        # refused on: with 300 copper and a 425 lot of two, the shop turned
        # away a customer who could afford a potion, and when it did sell it
        # quoted 425 and took 212.
        take = item
        if item.stackable and item.qty > 1:
            take = Item(item.key, qty=1)
            take.known = True
        price = self.shop_price(take)
        if p.copper < price:
            self.msg("You don't have enough money!", "warn", to=p)
            return FREE_COST
        if take is item:
            stock.remove(item)
        else:
            item.qty -= 1
        ok, why = p.room_for(take)
        if not ok:
            self.msg(why, "warn", to=p)
            if take is not item:
                item.qty += 1
            else:
                stock.append(item)
            return FREE_COST
        if not p.add_item(take):
            self.msg("Your pack is full.", "warn", to=p)
            return FREE_COST
        p.copper -= price
        self.appearances.identify(take.key)
        self.msg(f"You buy {with_article(take.name(self.appearances))} "
                 f"for {price} copper.", "loot", to=p)
        # Bought straight onto the body: wear it, or stow it if the slot it
        # was dropped on is a belt or a quiver.
        wear = action.get("wear")
        if wear:
            # Hand it to the verbs that already know the rules, rather than
            # writing a second, slightly different set of them here.
            if take.slot == wear or (take.slot in ("ring_left", "ring_right")
                                     and wear in ("ring_left", "ring_right")):
                self._act_equip(level, p, {"id": take.id, "slot": wear})
            elif wear == "free_hand" and take.slot is None:
                # Nothing has to be worn to unlock the free hand - that is
                # the whole point of it - so this needs no "is something
                # already there to hold it" check the belt and quiver do.
                self._act_equip(level, p, {"id": take.id, "slot": wear})
            elif p.equipment.get(wear) is not None:
                self._act_stow(level, p, {"id": take.id, "slot": wear})
            else:
                self.msg(f"You have nothing on your {wear} to put that in, "
                         f"so it is in your pack.", "info", to=p)
        self.sound("buy", p.x, p.y, level.depth)
        self.events.append({"t": "inv", "to": p.id})
        self.events.append({"t": "shop", "to": p.id, "npc": action.get("npc"),
                            "shop": shop, "name": action.get("name", "")})
        return FREE_COST

    def _act_sell(self, level, p, action):
        item = p.find_item(int(action.get("id", 0)))
        if item is None or item not in p.inventory:
            # It used to fail in silence, so dragging something a shop will
            # not take looked exactly like the game ignoring you.
            self.msg("You are not carrying that.", "warn", to=p)
            return FREE_COST
        shop = action.get("shop")
        refusal = self.shop_refusal(shop, item)
        if refusal:
            self.msg(refusal, "warn", to=p)
            return FREE_COST
        price = self.sell_offer(shop, item)
        p.remove_item(item, item.qty)
        p.copper += price
        if shop == "junk":
            self.msg(f"Nan takes {item.name(self.appearances)} off your hands "
                     f"for {price} copper. You will not see it again.",
                     "loot", to=p)
        else:
            self.msg(f"You sell {with_article(item.name(self.appearances))} "
                     f"for {price} copper.",
                     "loot", to=p)
        self.sound("gold", p.x, p.y, level.depth)
        self.events.append({"t": "inv", "to": p.id})
        self.events.append({"t": "shop", "to": p.id, "npc": action.get("npc"),
                            "shop": action.get("shop"), "name": action.get("name", "")})
        return FREE_COST

    def _act_service(self, level, p, action):
        """The temple, the sage and the strongroom."""
        what = action.get("what")

        if what and (what.startswith("heal_") or what.startswith("restore_")
                     or what in ("cure_poison", "rune_return")
                     or (what == "uncurse" and action.get("temple"))):
            self.buy_service(p, what)
            self.events.append({"t": "shop", "to": p.id, "npc": action.get("npc"),
                                "shop": "temple", "name": action.get("name", "")})
            return FREE_COST

        if what == "identify":
            item = p.find_item(int(action.get("id", 0)))
            if item is None:
                return FREE_COST
            price = 60 + p.level * 10
            if p.copper < price:
                self.msg(f"Ulric wants {price} copper for that.", "warn", to=p)
                return FREE_COST
            p.copper -= price
            item.known = True
            self.appearances.identify(item.key)
            self.msg(f"Ulric turns it over. It is {item.name(self.appearances)}.", "good", to=p)
            self.events.append({"t": "inv", "to": p.id})

        elif what == "heal":
            price = 30 + p.level * 12
            if p.copper < price:
                self.msg(f"The offering is {price} copper.", "warn", to=p)
                return FREE_COST
            p.copper -= price
            p.hp = p.max_hp
            p.mana = p.max_mana
            for bad in ("poisoned", "burning", "slowed", "afraid"):
                p.effects.pop(bad, None)
            self.msg("You are made whole again.", "good", to=p)
            self.sound("heal", p.x, p.y, level.depth)

        elif what == "uncurse":
            price = 150 + p.level * 20
            if p.copper < price:
                self.msg(f"That rite costs {price} copper.", "warn", to=p)
                return FREE_COST
            freed = [w for w in p.equipment.values() if w and w.cursed]
            if not freed:
                self.msg("Nothing you carry is cursed.", "info", to=p)
                return FREE_COST
            p.copper -= price
            for w in freed:
                w.cursed = False
            self.msg("The binding breaks.", "good", to=p)

        elif what == "deposit":
            amount = max(0, min(int(action.get("amount", 0)), p.copper))
            p.copper -= amount
            p.bank += amount
            self.msg(f"You deposit {amount} copper. The strongroom holds {p.bank}.", "info", to=p)

        elif what == "withdraw":
            amount = max(0, min(int(action.get("amount", 0)), p.bank))
            p.bank -= amount
            p.copper += amount
            self.msg(f"You withdraw {amount} copper.", "info", to=p)

        self.events.append({"t": "inv", "to": p.id})
        # ...and the counter itself, or nothing on it changes while you are
        # standing there. Deposit a hundred copper and the panel went on
        # saying what it said before: the money had moved, the log said so,
        # and all three figures on screen were stale until you shut the
        # window and opened it again. The sage had the same fault one step
        # milder - his offer for a thing he had just identified was still
        # the price he would have paid while it was unknown.
        if action.get("shop") or what in ("identify", "deposit", "withdraw",
                                          "heal", "uncurse"):
            self.events.append({"t": "shop", "to": p.id,
                                "npc": action.get("npc"),
                                "shop": action.get("shop") or
                                        ("bank" if what in ("deposit", "withdraw")
                                         else "sage" if what == "identify"
                                         else "temple"),
                                "name": action.get("name", "")})
        return FREE_COST

    # ====================================================== snapshot ========
    def snapshot_for(self, viewer):
        """Everything this character can see, ready to put on the wire."""
        level = self.levels.get(viewer.depth)
        if level is None:
            return None

        detect_mon = viewer.has("detect_monsters")
        detect_item = viewer.has("detect_items")

        actors = []
        for a in level.actors.values():
            if a.dead:
                continue
            visible = (a.y * level.w + a.x) in viewer.fov
            if not visible and a.kind == "player":
                visible = True                      # companions are always on the map
            if not visible and a.kind == "monster" and detect_mon:
                visible = True
            if not visible:
                continue
            entry = {
                "id": a.id, "k": a.kind, "x": a.x, "y": a.y, "f": a.facing,
                "hp": max(0, int(a.hp)), "mhp": a.max_hp, "n": a.name,
            }
            if a.kind == "player":
                entry["c"] = a.colour
                entry["lv"] = a.level
                weapon = a.equipment.get("weapon")
                entry["w"] = weapon.base.get("icon") if weapon else None
                entry["sh"] = bool(a.equipment.get("shield"))
                entry["hm"] = bool(a.equipment.get("head"))
                entry["rb"] = bool(a.equipment.get("torso") and
                                   a.equipment["torso"].key == "robe")
            else:
                entry["s"] = a.sprite
                if getattr(a, "boss", False):
                    entry["bo"] = 1
            if a.effects:
                entry["fx"] = list(a.effects.keys())
            actors.append(entry)

        items = []
        for (x, y), pile in level.ground.items():
            if not pile:
                continue
            if (y * level.w + x) not in viewer.fov and not detect_item:
                continue
            top = pile[-1]
            items.append({"x": x, "y": y, "icon": top.base.get("icon", "gold"),
                          "n": top.name(self.appearances), "many": len(pile) > 1})

        hazards = [{"x": x, "y": y, "kind": t["kind"]}
                   for (x, y), t in level.traps.items()
                   if t["found"] and (y * level.w + x) in viewer.fov]

        return {
            "clock": level.clock,
            "depth": viewer.depth,
            "traps": hazards,
            "waiting": level.waiting_on,
            "actors": actors,
            "items": items,
            "you": self.self_view(viewer),
            "party": [{"id": p.id, "n": p.name, "hp": max(0, int(p.hp)), "mhp": p.max_hp,
                       "lv": p.level, "d": p.depth, "c": p.colour}
                      for p in self.players.values()],
        }

    def self_view(self, p):
        enc_name, enc_mult = p.encumbrance
        weight = p.carried_weight
        return {
            "id": p.id, "name": p.name, "level": p.level, "xp": p.xp,
            "hp": max(0, int(p.hp)), "max_hp": p.max_hp,
            "mana": int(p.mana), "max_mana": p.max_mana,
            "copper": p.copper, "bank": p.bank, "depth": p.depth,
            "ac": p.armour_class, "to_hit": p.to_hit,
            "stats": {k: p.stat(k) for k in p.stats},
            "base_stats": dict(p.stats),
            "weight": weight, "capacity": p.capacity,
            "bulk": p.carried_bulk, "bulk_capacity": p.bulk_capacity,
            "encumbrance": enc_name, "speed": p.speed_percent(),
            "move_speed": p.move_speed_percent(),
            "effects": {k: v[0] for k, v in p.effects.items()},
            "spells": sorted(p.spells),
            "spell_costs": {n: mana_cost(SPELLS[n]["mana"], p.level,
                                         SPELLS[n].get("level", 1))
                            for n in p.spells if n in SPELLS},
            "deepest": p.deepest, "kills": p.kills, "deaths": p.deaths,
            "clock": getattr(p, "elapsed", 0),
        }

    def inventory_view(self, p):
        pack_w, pack_b = p.pack_load()
        max_w, max_b = p.pack_limits()
        return {
            "items": [self.item_view(i) for i in p.inventory],
            "equipment": {slot: (self.item_view(i) if i else None)
                          for slot, i in p.equipment.items()},
            "copper": p.copper, "bank": p.bank,
            "weight": p.carried_weight, "capacity": p.capacity,
            "bulk": p.carried_bulk, "bulk_capacity": p.bulk_capacity,
            "pack_weight": pack_w, "pack_max_weight": max_w,
            "pack_bulk": pack_b, "pack_max_bulk": max_b,
            "pack_name": p.pack.name(self.appearances) if p.pack else "Your hands",
            "encumbrance": p.encumbrance[0],
            # What is on the belt and in the quiver, which is the only place
            # anything can be reached from in a hurry.
            "stowed": {slot: [self.item_view(i)
                              for i in (getattr(p.equipment.get(slot), "contents", None) or [])]
                       for slot in ("waist", "quiver")},
        }

    def item_view(self, item, shop=False):
        return {
            "id": item.id, "key": item.key,
            "name": item.name(self.appearances, shop=shop),
            "icon": self.appearances.icon_for(item.key, item.base),
            "desc": item.describe(self.appearances),
            "slot": item.slot, "kind": item.kind, "qty": item.qty,
            "weight": item.weight, "bulk": item.bulk, "value": item.value(),
            "custom": bool(item.custom_name),
            "cursed": item.cursed and item.known,
            "spell": item.spell,
            # How many things this will hold to hand. The window could not
            # draw a belt's empty slots without it, so an empty belt showed
            # nothing at all and there was no sign the slots existed.
            "slots": item.base.get("belt_slots"),
        }

    def shop_view(self, p, shop, npc_id, name):
        stock = self.stock_for(shop)
        return {
            "shop": shop, "npc": npc_id, "name": name,
            # The price of one, because one is what a drag buys.
            "stock": [dict(self.item_view(i, shop=True),
                           price=self.shop_price(self.unit_of(i)))
                      for i in stock],
            # Each row carries the refusal as well as the price, so the
            # window can say "We don't buy those..." at the moment you drag
            # the thing in, rather than offering you 960 copper for a sword
            # the armourer was never going to take.
            "sell": [dict(self.item_view(i), price=self.sell_offer(shop, i),
                          refusal=self.shop_refusal(shop, i))
                     for i in p.inventory],
            "copper": p.copper, "bank": p.bank,
            "services": self.temple_services(p) if shop == "temple" else [],
            "drained": {k: v for k, v in p.drained.items() if v},
            "drained_hp": p.drained_hp,
            "heal_price": 30 + p.level * 12,
            "identify_price": 60 + p.level * 10,
            "uncurse_price": 150 + p.level * 20,
        }
