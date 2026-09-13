"""Striking things, and what happens when they strike back.

Armour class is the one defensive number: it decides whether a blow lands at
all, not how much it hurts. A well-armoured character is missed, not chipped.
"""

from ..common.constants import chebyshev


def attack_roll(rng, attacker_hit, defender_ac):
    """d20 against 10 + AC - to-hit. A natural 20 always lands, a 1 never does."""
    roll = rng.randint(1, 20)
    if roll == 1:
        return False, False
    if roll == 20:
        return True, True
    target = 10 + defender_ac - attacker_hit
    return roll >= target, False


def melee(world, attacker, defender, cost_free=False):
    """One swing. Returns a short description of what happened."""
    rng = world.rng
    a_hit = attacker.to_hit
    hit, crit = attack_roll(rng, a_hit, defender.armour_class)

    a_name = attacker.name
    d_name = defender.name

    if not hit:
        world.fx("miss", defender.x, defender.y, defender.depth)
        if attacker.kind == "player":
            world.msg(f"You miss the {d_name}.", "combat", to=attacker)
        else:
            world.msg(f"The {a_name} misses you.", "combat", to=defender)
        return False

    dmg = attacker.damage_roll(rng)
    if crit:
        dmg *= 2

    rider = None
    if attacker.kind == "monster":
        tpl = attacker.tpl
        if tpl.get("poison"):
            rider = ("poisoned", tpl["poison"])
        elif tpl.get("drain"):
            rider = ("drained", 1)
        elif tpl.get("burn"):
            rider = ("burning", 4)
    else:
        weapon = attacker.equipment.get("weapon")
        if weapon and weapon.base.get("burn"):
            rider = ("burning", 4)

    world.fx("hit", defender.x, defender.y, defender.depth)
    apply_damage(world, defender, dmg, attacker, crit=crit)

    verb = "hit" if not crit else "land a solid blow on"
    if attacker.kind == "player":
        world.msg(f"You {verb} the {d_name} for {dmg}.", "combat", to=attacker)
    if defender.kind == "player":
        world.msg(f"The {a_name} hits you for {dmg}.", "hurt", to=defender)

    if rider and not defender.dead:
        name, power = rider
        defender.add_effect(name, world.clock_for(defender.depth) + 500, power)

    kb = attacker.tpl.get("knockback") if attacker.kind == "monster" else 0
    if kb and not defender.dead:
        knock_back(world, attacker, defender, kb)
    return True


def apply_damage(world, target, amount, source=None, crit=False):
    if target.dead:
        return 0
    if target.has("sanctuary"):
        amount = max(1, amount // 2)
    target.hp -= amount
    world.float_text(target.x, target.y, target.depth, str(amount),
                     "crit" if crit else ("hurt" if target.kind == "player" else "damage"))
    if target.kind == "monster" and source is not None and source.kind == "player":
        target.target_id = source.id
        target.last_seen = (source.x, source.y)
    if target.hp <= 0:
        world.kill(target, source)
        return amount
    return amount


def heal(world, target, amount):
    if target.dead:
        return 0
    healed = min(amount, target.max_hp - target.hp)
    if healed <= 0:
        return 0
    target.hp += healed
    world.float_text(target.x, target.y, target.depth, f"+{healed}", "heal")
    return healed


def knock_back(world, source, target, tiles):
    level = world.levels.get(target.depth)
    if not level:
        return
    dx = (target.x > source.x) - (target.x < source.x)
    dy = (target.y > source.y) - (target.y < source.y)
    if dx == 0 and dy == 0:
        return
    for _ in range(tiles):
        nx, ny = target.x + dx, target.y + dy
        if not level.walkable(nx, ny, target.id):
            break
        level.move_actor(target, nx, ny)


def enemies_near(level, x, y, radius):
    return [a for a in level.actors.values()
            if a.kind == "monster" and not a.dead
            and chebyshev(a.x, a.y, x, y) <= radius]


def players_near(level, x, y, radius):
    return [a for a in level.actors.values()
            if a.kind == "player" and not a.dead
            and chebyshev(a.x, a.y, x, y) <= radius]
