"""Characters and creatures.

There are no classes. A character is four numbers, whatever they are carrying,
and whatever spells they have found the books for. A heavily armoured character
who put everything into Strength plays like a warrior; one who put it into
Intelligence and bought tomes plays like a mage. Nothing enforces it.
"""

import random

from ..common.constants import (
    movement_speed, COPPER_GRAMS, COPPER_CC, COINS,
    STATS, START_STAT, MAX_LEVEL, CARRY_PER_STRENGTH, encumbrance_for,
    xp_for_level, clamp, SLOTS, RING_SLOTS, TICKS_PER_TURN,
    BODY_BULK_CAPACITY, CARRY_BASE, START_COPPER, BARE_HANDS_WEIGHT, BARE_HANDS_BULK,
)
from .items import Item
from .monsters import MONSTERS, scaled

_next_actor_id = [1]


def new_actor_id():
    _next_actor_id[0] += 1
    return _next_actor_id[0]


def stat_bonus(value):
    """Classic modifier curve: 10 is average and worth nothing."""
    return (value - 10) // 2


class Actor:
    def __init__(self, x=0, y=0):
        self.id = new_actor_id()
        self.x = x
        self.y = y
        self.depth = 0
        self.hp = 1
        self.max_hp = 1
        self.dead = False
        self.facing = 4
        self.next_at = 0            # game time at which it may act again
        self.effects = {}           # name -> expiry tick
        self.kind = "actor"
        self.name = "?"

    # -------------------------------------------------------------- effects -
    def add_effect(self, name, until, value=None):
        cur = self.effects.get(name)
        payload = (until, value)
        if cur is None or cur[0] < until:
            self.effects[name] = payload

    def has(self, name):
        return name in self.effects

    def effect_value(self, name, default=0):
        e = self.effects.get(name)
        return default if e is None else (e[1] if e[1] is not None else default)

    def expire_effects(self, now):
        gone = [k for k, (until, _) in self.effects.items() if until <= now]
        for k in gone:
            del self.effects[k]
        return gone


class Player(Actor):
    def __init__(self, name, stats=None, colour=0):
        super().__init__()
        self.kind = "player"
        self.name = name
        self.colour = colour
        self.stats = dict.fromkeys(STATS, START_STAT)
        if stats:
            self.stats.update({k: v for k, v in stats.items() if k in STATS})
        self.level = 1
        self.xp = 0
        self.coins = {"copper": START_COPPER, "silver": 0, "gold": 0,
                      "platinum": 0}
        self.bank = 0
        self.equipment = {s: None for s in SLOTS}
        self.inventory = []
        self.spells = set()
        self.deepest = 0
        self.deaths = 0
        self.kills = 0
        # Drain is not an effect that wears off. It is damage to the character
        # that only the temple can undo, which is what the temple is for.
        self.drained = {k: 0 for k in STATS}
        self.drained_hp = 0

        self.memory = {}            # depth -> bytearray of seen tiles
        self.fov = set()
        self.pending_tiles = []
        self.pending = None         # the action the scheduler is waiting for
        self.idle_noted = False
        self.elapsed = 0            # this character's own clock, in ticks
        self.resting = False

        self.recalc()
        self.hp = self.max_hp
        self.mana = self.max_mana

    # ------------------------------------------------------------ derived ---
    def stat(self, name):
        """Base stat, less anything drained out of you, plus what gear adds."""
        value = self.stats.get(name, 10) - self.drained.get(name, 0)
        for item in self.equipment.values():
            if not item:
                continue
            bonus = item.base.get("bonus")
            if bonus and bonus[0] == name:
                value += bonus[1]
        if name == "strength" and self.has("might"):
            value += 4
        return max(1, value)

    def recalc(self):
        con = self.stat("constitution")
        intel = self.stat("intelligence")
        self.max_hp = 8 + con + (self.level - 1) * (2 + max(1, con // 4))
        self.max_mana = intel + (self.level - 1) * max(1, intel // 4)
        for item in self.equipment.values():
            if not item:
                continue
            self.max_hp += item.base.get("hp_bonus", 0)
            self.max_mana += item.base.get("mana_bonus", 0)
        self.max_hp = max(1, self.max_hp - self.drained_hp)
        self.max_mana = max(0, self.max_mana)
        self.hp = min(getattr(self, "hp", self.max_hp), self.max_hp)
        self.mana = min(getattr(self, "mana", self.max_mana), self.max_mana)

    @property
    def armour_class(self):
        ac = stat_bonus(self.stat("dexterity"))
        for item in self.equipment.values():
            if item:
                ac += item.ac()
        ac += self.effect_value("shield_spell", 0)
        ac += self.effect_value("stoneskin", 0)
        return ac

    @property
    def to_hit(self):
        bonus = self.level // 2 + stat_bonus(self.stat("dexterity"))
        weapon = self.equipment.get("weapon")
        if weapon:
            bonus += weapon.to_hit()
        return bonus

    def damage_roll(self, rng):
        weapon = self.equipment.get("weapon")
        if weapon and weapon.base.get("dmg"):
            n, s = weapon.damage()
            dmg = sum(rng.randint(1, s) for _ in range(n)) + weapon.enchant
        else:
            dmg = rng.randint(1, 3)          # bare hands
        dmg += stat_bonus(self.stat("strength"))
        return max(1, dmg)

    # ------------------------------------------------------------- money ---
    @property
    def copper(self):
        """What the purse is worth, in copper. Prices are all quoted in it."""
        return sum(n * worth for (metal, worth) in COINS
                   for n in (self.coins.get(metal, 0),))

    @copper.setter
    def copper(self, value):
        """Set the purse to a plain value. Used at creation and by saves."""
        self.coins = {"copper": max(0, int(value)), "silver": 0, "gold": 0,
                      "platinum": 0}

    @property
    def coin_count(self):
        """How many actual coins you are carrying. This is what weighs."""
        return sum(self.coins.values())

    def gain_coins(self, metal, n):
        self.coins[metal] = self.coins.get(metal, 0) + int(n)

    def spend(self, amount):
        """Pay a price, breaking larger coins into change as needed.

        Coins are not silently consolidated - a purse of copper stays a purse
        of copper, and keeps weighing what it weighs. That is the whole point
        of finding platinum in the deep levels.
        """
        if amount > self.copper:
            return False
        left = int(amount)
        for metal, worth in COINS:                    # smallest first
            take = min(self.coins.get(metal, 0), left // worth)
            self.coins[metal] -= take
            left -= take * worth
        if left:                                      # break one bigger coin
            for metal, worth in reversed(COINS):
                if worth > left and self.coins.get(metal, 0):
                    self.coins[metal] -= 1
                    change = worth - left
                    left = 0
                    for m2, w2 in reversed(COINS):
                        n, change = divmod(change, w2)
                        self.coins[m2] = self.coins.get(m2, 0) + n
                    break
        return left == 0

    # -------------------------------------------------------- encumbrance ---
    @property
    def carried_weight(self):
        w = sum(i.weight for i in self.inventory)
        w += sum(i.weight for i in self.equipment.values() if i)
        w += self.coin_count * COPPER_GRAMS   # every coin weighs a gram
        return w

    @property
    def carried_bulk(self):
        """Bulk strapped to you, not worn by you.

        Armour conforms to the body and does not count; a pack, a purse and
        anything carried loose in your hands does.
        """
        # Things stowed in a pack press down against each other, so what is
        # inside counts for half. The pack and purse themselves count in full.
        b = sum(i.bulk for i in self.inventory) // 2
        for slot in ("pack", "purse"):
            worn = self.equipment.get(slot)
            if worn:
                b += worn.base.get("bulk", 0)
        b += self.coin_count * COPPER_CC
        return b

    @property
    def capacity(self):
        return self.stat("strength") * CARRY_PER_STRENGTH + CARRY_BASE

    @property
    def bulk_capacity(self):
        return BODY_BULK_CAPACITY

    @property
    def pack(self):
        """The container the loose items live in, if you are wearing one."""
        return self.equipment.get("pack")

    def belt_has_room(self, item=None):
        """A belt holds a fixed number of things, not a weight."""
        belt = self.equipment.get("waist")
        if belt is None:
            return False
        slots = belt.base.get("belt_slots")
        if not slots:
            return False
        return len(getattr(belt, "contents", []) or []) < slots

    def pack_limits(self):
        """(weight, bulk) the pack can hold - or what two hands can, without one."""
        pack = self.pack
        if pack is None:
            return BARE_HANDS_WEIGHT, BARE_HANDS_BULK
        return (pack.base.get("capacity", 12000),
                pack.base.get("bulk_capacity", 50000))

    def pack_load(self):
        """(weight, bulk) currently in the pack."""
        return (sum(i.weight for i in self.inventory),
                sum(i.bulk for i in self.inventory))

    def room_for(self, item):
        """Can this go in the pack? Returns (ok, reason)."""
        max_w, max_b = self.pack_limits()
        used_w, used_b = self.pack_load()
        if used_w + item.weight > max_w:
            where = "your pack" if self.pack else "your hands"
            return False, f"There is no more room in {where} for that weight."
        if used_b + item.bulk > max_b:
            where = "your pack" if self.pack else "your hands"
            return False, f"That is too bulky to fit in {where}."
        return True, ""

    @property
    def encumbrance(self):
        """Whichever is worse, the load or the bulk."""
        if self.has("feather"):
            return "Unencumbered", 1.0
        by_weight = encumbrance_for(self.carried_weight, self.capacity)
        by_bulk = encumbrance_for(self.carried_bulk, self.bulk_capacity)
        for tier in (by_weight, by_bulk):
            if tier[1] is None:
                return tier
        return by_weight if by_weight[1] >= by_bulk[1] else by_bulk

    def speed_percent(self):
        """Overall speed: how fast every action goes. Load does not enter."""
        cost = self.action_cost(TICKS_PER_TURN)
        if cost is None:
            return 0
        return max(1, int(round(100.0 * TICKS_PER_TURN / cost)))

    def move_speed_percent(self):
        """Movement speed, which load alone drives. None means stuck.

        The original's manual is explicit that the two are separate: "movement
        speed (or slowness) doesn't affect other actions, so you can cast
        spells at the same rate no matter how heavily loaded you are."
        """
        return movement_speed(self.carried_weight, self.capacity)

    def action_cost(self, base, moving=False, attacking=False):
        """How long an action takes. Only movement pays for what you carry."""
        # Overall speed starts at 100% and only magic moves it. A fresh
        # character in the original reads "100% / 200%" whatever their
        # Dexterity; we were scaling every action by Dex and printing 135%.
        cost = float(base)
        if self.has("haste"):
            cost *= 0.5
        if self.has("slowed"):
            cost *= 2.0
        if moving:
            mv = self.move_speed_percent()
            if mv is None:
                return None                   # too loaded to move at all
            cost *= 100.0 / mv
        if attacking:
            # A heavy weapon is slow to swing. It does not make you slower at
            # reading, resting or walking, which is what it used to do - and
            # what made the status line read 125% with a dagger in hand.
            weapon = self.equipment.get("weapon")
            if weapon:
                cost *= weapon.base.get("speed", 100) / 100.0
        return max(10, int(cost))

    # ------------------------------------------------------------ progress --
    def drain_stat(self, name, amount=1):
        """Permanently sap an attribute. Never below three."""
        floor = 3
        current = self.stats.get(name, 10) - self.drained.get(name, 0)
        amount = min(amount, max(0, current - floor))
        if amount <= 0:
            return 0
        self.drained[name] = self.drained.get(name, 0) + amount
        self.recalc()
        return amount

    def drain_hp(self, amount=1):
        amount = min(amount, max(0, self.max_hp - 5))
        if amount <= 0:
            return 0
        self.drained_hp += amount
        self.recalc()
        self.hp = min(self.hp, self.max_hp)
        return amount

    def restore_stat(self, name):
        lost = self.drained.get(name, 0)
        self.drained[name] = 0
        self.recalc()
        return lost

    def restore_hp_drain(self):
        lost = self.drained_hp
        self.drained_hp = 0
        self.recalc()
        return lost

    @property
    def is_drained(self):
        return self.drained_hp > 0 or any(self.drained.values())

    def add_xp(self, amount):
        self.xp += amount
        gained = []
        while self.level < MAX_LEVEL and self.xp >= xp_for_level(self.level):
            self.level += 1
            before_hp, before_mana = self.max_hp, self.max_mana
            self.recalc()
            self.hp += self.max_hp - before_hp
            # "Your mana is restored every time your player goes up a level in
            # power" - not topped up by the increase, filled.
            self.mana = self.max_mana
            gained.append(self.level)
        return gained

    # ----------------------------------------------------------- inventory --
    def add_item(self, item, force=False):
        if not force:
            ok, _ = self.room_for(item)
            if not ok:
                return False
        if item.stackable:
            for slot in self.inventory:
                if slot.key == item.key and slot.stackable and not slot.custom_name:
                    slot.qty += item.qty
                    return True
        if len(self.inventory) >= 40:
            return False
        self.inventory.append(item)
        return True

    def sort_pack(self, appearances=None):
        """Group the pack the way a tidy person would: by what things are.

        Within a type the things you know come first and the ones you have
        not identified fall to the end, which is what the original's Sort
        Pack does and what makes the command worth pressing.
        """
        order = {"weapon": 0, "armour": 1, "container": 2, "potion": 3,
                 "scroll": 4, "book": 5,
                 "ring": 8, "amulet": 9, "treasure": 10, "coins": 11}

        def key(item):
            kind = item.kind
            if item.slot in ("torso", "head", "shield", "arms", "feet",
                             "legs", "back", "waist", "bracers"):
                kind = "armour"
            elif item.slot == "weapon":
                kind = "weapon"
            unknown = not item.known
            if appearances is not None and item.base.get("kind") in (
                    "potion", "scroll", "ring", "amulet"):
                unknown = not appearances.is_known(item.key)
            return (order.get(kind, 12), unknown,
                    item.name(appearances).lower())

        self.inventory.sort(key=key)

    def find_item(self, item_id):
        for it in self.inventory:
            if it.id == item_id:
                return it
        for it in self.equipment.values():
            if it and it.id == item_id:
                return it
        # things tucked into a worn container - the belt, chiefly
        for it in self.equipment.values():
            for inner in getattr(it, "contents", []) or []:
                if inner.id == item_id:
                    return inner
        return None

    def remove_item(self, item, qty=1):
        if item not in self.inventory:
            return None
        if item.stackable and item.qty > qty:
            item.qty -= qty
            clone = Item(item.key, qty=qty)
            return clone
        self.inventory.remove(item)
        return item

    def equip(self, item, prefer_slot=None):
        """Put something on. Returns (ok, message).

        prefer_slot lets the player drop a ring onto the hand they meant.
        """
        slot = item.slot
        if not slot:
            return False, f"You cannot wear {item.name()}."
        req = item.base.get("str_req")
        if req and self.stat("strength") < req:
            return False, f"You are not strong enough to use that (needs Strength {req})."
        if slot in RING_SLOTS:
            if prefer_slot in RING_SLOTS:
                slot = prefer_slot
            else:
                slot = "ring_left" if self.equipment["ring_left"] is None else "ring_right"
        current = self.equipment.get(slot)
        if current and current.cursed:
            current.known = True
            return False, f"You cannot remove the {current.name()} - it is stuck fast."
        if current:
            self.inventory.append(current)
        if item in self.inventory:
            self.inventory.remove(item)
        self.equipment[slot] = item
        self.recalc()
        if item.cursed:
            item.known = True
            return True, f"You put on {item.name()}. A chill runs up your arm - it is cursed."
        return True, f"You are now using {item.name()}."

    def unequip(self, slot):
        item = self.equipment.get(slot)
        if not item:
            return False, "Nothing there."
        if item.cursed:
            item.known = True
            return False, f"The {item.name()} will not come off."
        if slot != "pack":
            ok, why = self.room_for(item)
            if not ok:
                return False, why
        self.equipment[slot] = None
        self.inventory.append(item)
        self.recalc()
        return True, f"You put away {item.name()}."

    def ammo_for(self, weapon):
        want = weapon.base.get("missile")
        if not want:
            return None
        for it in self.inventory:
            if it.base.get("ammo") == want and it.qty > 0:
                return it
        return None

    # ---------------------------------------------------------------- save --
    def to_save(self):
        return {
            "name": self.name, "colour": self.colour, "stats": self.stats,
            "level": self.level, "xp": self.xp, "coins": dict(self.coins),
            "bank": self.bank,
            "hp": self.hp, "mana": self.mana,
            "inventory": [i.to_dict() for i in self.inventory],
            "equipment": {k: (v.to_dict() if v else None) for k, v in self.equipment.items()},
            "spells": sorted(self.spells),
            "deepest": self.deepest, "deaths": self.deaths, "kills": self.kills,
            "drained": self.drained, "drained_hp": self.drained_hp,
            "elapsed": self.elapsed,
        }

    def load_save(self, d):
        self.stats.update(d.get("stats", {}))
        self.colour = d.get("colour", self.colour)
        self.level = d.get("level", 1)
        self.xp = d.get("xp", 0)
        if "coins" in d:
            self.coins = dict(d["coins"])
        else:
            self.copper = d.get("copper", START_COPPER)
        self.bank = d.get("bank", 0)
        self.inventory = [Item.from_dict(x) for x in d.get("inventory", [])]
        self.equipment = {s: None for s in SLOTS}
        for slot, raw in (d.get("equipment") or {}).items():
            if raw and slot in self.equipment:
                self.equipment[slot] = Item.from_dict(raw)
        self.spells = set(d.get("spells", []))
        self.deepest = d.get("deepest", 0)
        self.deaths = d.get("deaths", 0)
        self.kills = d.get("kills", 0)
        self.drained = {k: d.get("drained", {}).get(k, 0) for k in STATS}
        self.drained_hp = d.get("drained_hp", 0)
        self.elapsed = d.get("elapsed", 0)
        self.recalc()
        self.hp = clamp(d.get("hp", self.max_hp), 1, self.max_hp)
        self.mana = clamp(d.get("mana", self.max_mana), 0, self.max_mana)


class Monster(Actor):
    def __init__(self, key, x, y, depth, rng, tough=1.0, worth=1.0):
        super().__init__(x, y)
        tpl = MONSTERS[key]
        s = scaled(tpl, depth, tough, worth)
        self.kind = "monster"
        self.key = key
        self.tpl = tpl
        self.name = tpl["name"]
        self.sprite = tpl["sprite"]
        self.depth = depth
        self.max_hp = self.hp = s["hp"]
        self.armour_class = s["ac"]
        self.to_hit = s["hit"]
        self.dmg_bonus = s["dmg_bonus"]
        self.xp_value = s["xp"]
        self.speed = tpl["speed"]
        self.ai = tpl["ai"]
        self.boss = key in ("warden_of_ash", "vaelrik")
        self.target_id = None
        self.last_seen = None
        self.path = None
        self.path_goal = None

    def damage_roll(self, rng):
        n, s = self.tpl["dmg"]
        return max(1, sum(rng.randint(1, s) for _ in range(n)) + self.dmg_bonus)

    def action_cost(self, base, moving=False):
        # Monsters carry nothing, so movement costs them no more than anything
        # else; the argument exists so callers can treat them alike.
        cost = base * self.speed / 100.0
        if self.has("slowed"):
            # 1/2, then 1/3, then 1/4 ... each further slowing helps less
            cost *= getattr(self, "slow_divisor", 2)
        if self.has("haste"):
            cost *= 0.5
        return max(10, int(cost))


def make_monster(key, x, y, depth, rng, tough=1.0, worth=1.0):
    return Monster(key, x, y, depth, rng, tough, worth)


class NPC(Actor):
    def __init__(self, spec):
        super().__init__(spec["x"], spec["y"])
        self.kind = "npc"
        self.name = spec["name"]
        self.sprite = spec["sprite"]
        self.shop = spec["shop"]
        self.max_hp = self.hp = 1
        self.next_at = 1 << 60          # townsfolk never take a turn
