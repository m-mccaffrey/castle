"""Striking things, and what happens when they strike back.

Armour class is the one defensive number: it decides whether a blow lands at
all, not how much it hurts. A well-armoured character is missed, not chipped.
"""

from ..common.constants import chebyshev


# Armour value is a chance to avoid a telling blow, not a damage soak: "A high
# armor value means monsters have a lesser chance of making a hit that inflicts
# damage." The original's ladder runs 0-54 for body armour in steps of six, with
# helmets and shields adding in threes, so a well-equipped character reaches the
# seventies - which is why the roll is a percentage rather than a d20.
HIT_BASE = 0.70          # an even fight against no armour at all
HIT_PER_SKILL = 0.02     # each point of the attacker's skill
HIT_PER_AV = 0.008       # each point of the defender's armour value
HIT_FLOOR = 0.05         # nothing is ever untouchable
HIT_CEILING = 0.95       # and nothing ever connects every time
CRIT_SHARE = 0.05        # the best-struck twentieth of blows tell double


def hit_chance(attacker_hit, defender_ac):
    """How often this attacker lands a telling blow on this defender."""
    p = HIT_BASE + HIT_PER_SKILL * attacker_hit - HIT_PER_AV * defender_ac
    return min(HIT_CEILING, max(HIT_FLOOR, p))


def attack_roll(rng, attacker_hit, defender_ac):
    """(landed, critical). Armour lowers the chance; it never soaks damage."""
    if rng.random() >= hit_chance(attacker_hit, defender_ac):
        return False, False
    return True, rng.random() < CRIT_SHARE


def melee(world, attacker, defender, cost_free=False):
    """One swing. Returns a short description of what happened."""
    rng = world.rng
    a_hit = attacker.to_hit
    hit, crit = attack_roll(rng, a_hit, defender.armour_class)

    if not hit:
        world.fx("miss", defender.x, defender.y, defender.depth)
        shield = (getattr(defender, "equipment", {}) or {}).get("shield")
        blocked = bool(shield) and rng.random() < 0.5
        text = (blow_message(rng, attacker, defender, 0, False, blocked=True)
                if blocked else miss_message(rng, attacker, defender))
        world.msg(text, "combat",
                  to=attacker if attacker.kind == "player" else defender)
        return False

    dmg = attacker.damage_roll(rng)
    if crit:
        dmg *= 2

    rider = None
    if attacker.kind == "monster":
        tpl = attacker.tpl
        if tpl.get("steals") and defender.kind == "player" and defender.copper:
            # "You feel a tug on your purse" ... "The Thief vanishes!"
            world.steal_from(attacker, defender)
            return
        if tpl.get("drain") and defender.kind == "player" and rng.random() < 0.3:
            rider = ("drain", tpl["drain"])
        elif tpl.get("poison"):
            # "Green dragons ... their poison is slow to take hold" - a
            # delayed poison does nothing for a while and then starts, which
            # is what makes carrying a cure worth the weight.
            if tpl.get("poison_delay"):
                rider = ("poison_later", tpl["poison"])
            else:
                rider = ("poisoned", tpl["poison"])
        elif tpl.get("burn"):
            rider = ("burning", 4)
    else:
        weapon = attacker.equipment.get("weapon")
        if weapon and weapon.base.get("burn"):
            rider = ("burning", 4)

    world.fx("hit", defender.x, defender.y, defender.depth)
    # Say what the swing did before the dying happens, so a boss's "falls!"
    # and the lines that follow it come after the blow that caused them.
    fatal = dmg >= defender.hp
    text = blow_message(rng, attacker, defender, dmg, fatal)
    if attacker.kind == "player":
        world.msg(text, "combat", to=attacker)
    elif defender.kind == "player":
        world.msg(text, "hurt", to=defender)
    # The swing has narrated its own kill, so kill() must not add "The Kobold
    # dies." underneath it.
    apply_damage(world, defender, dmg, attacker, crit=crit,
                 killed_by_a_blow=True)

    if rider and not defender.dead:
        name, power = rider
        if name == "drain":
            world.drain_player(defender, power, attacker)
        elif name == "poison_later":
            now = world.clock_for(defender.depth)
            delay = attacker.tpl.get("poison_delay", 400)
            defender.add_effect("poison_later", now + delay, power)
            if defender.kind == "player":
                world.msg("A cold numbness spreads from the wound.", "bad",
                          to=defender)
        else:
            defender.add_effect(name, world.clock_for(defender.depth) + 500, power)

    kb = attacker.tpl.get("knockback") if attacker.kind == "monster" else 0
    if kb and not defender.dead:
        knock_back(world, attacker, defender, kb)
    return True


def apply_damage(world, target, amount, source=None, crit=False,
                 killed_by_a_blow=False):
    if target.dead:
        return 0
    if target.has("sanctuary"):
        amount = max(1, amount // 2)
    if getattr(target, "resting", False):
        # Being struck wakes you from anything, sleep included.
        target.resting = False
        world.msg("You are woken by the blow!", "bad", to=target)
    target.hp -= amount
    world.float_text(target.x, target.y, target.depth, str(amount),
                     "crit" if crit else ("hurt" if target.kind == "player" else "damage"))
    if target.kind == "monster" and source is not None and source.kind == "player":
        target.target_id = source.id
        target.last_seen = (source.x, source.y)
    if target.hp <= 0:
        world.kill(target, source, announce=not killed_by_a_blow)
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


def enemies_in_sight(world, level, player, radius):
    """The creatures this player can actually see.

    "Not with something in sight" was being decided by distance alone, so a
    creature around a corner stopped you resting while the same creature was
    "nothing in sight to shoot at". Sight is what the messages claim, so
    sight is what they should ask about.
    """
    world.update_fov(player)
    return [a for a in enemies_near(level, player.x, player.y, radius)
            if (a.y * level.w + a.x) in player.fov]


def players_near(level, x, y, radius):
    return [a for a in level.actors.values()
            if a.kind == "player" and not a.dead
            and chebyshev(a.x, a.y, x, y) <= radius]


# ---------------------------------------------------------------------------
#  What a blow reads like
#
#  The original never prints a damage number in the log. It prints a sentence
#  built from the weapon in your hand, where the blow landed, and how hard it
#  was, and the reference notes this is "the single most copyable thing in the
#  game for feel, and it costs nothing but a message table". So here is the
#  table. The number still floats over the target for anyone who wants it.
# ---------------------------------------------------------------------------

WEAPON_CLASS = {
    "dagger": "pierce", "shortsword": "slash", "sabre": "slash",
    "longsword": "slash", "broadsword": "slash", "greatsword": "slash",
    "mace": "crush", "warhammer": "crush", "quarterstaff": "crush",
    "runestaff": "crush", "club": "crush",
    "axe": "chop", "halberd": "chop",
    "spear": "pierce", "shortbow": "shoot", "longbow": "shoot",
    "crossbow": "shoot", "wand": "blast",
}

PLACES = ("in the arm", "in the chest", "in the head", "in the leg",
          "on the flank")

# by weapon class: (a graze, an ordinary blow, a solid blow, a crushing blow)
STRIKES = {
    "slash":  ("{A} slash{s} {D}, opening a bloodless cut.",
               "{A} hit{s} {D} {where}!",
               "{A} deal{s} {D} a solid blow!",
               "{A} deal{s} {D} a crushing blow!"),
    "chop":   ("{A} chop{s} at {D} and catch{es} nothing but hide.",
               "{A} chop{s} {D} {where}!",
               "{A} deal{s} {D} a solid blow!",
               "{A} sink{s} the blade into {D} to the haft!"),
    "crush":  ("{A} clip{s} {D} a glancing blow.",
               "{A} smash{es} {D} {where}!",
               "{A} deal{s} {D} a solid blow!",
               "{A} deal{s} {D} a crushing blow!"),
    "pierce": ("{A} prick{s} {D}, no deeper than a thorn.",
               "{A} stab{s} {D} {where}!",
               "{A} run{s} {D} through the guard!",
               "{A} drive{s} the point home to the hilt!"),
    "shoot":  ("{A} graze{s} {D} in passing.",
               "{A} hit{s} {D} {where}!",
               "{A} put{s} a shaft deep into {D}!",
               "{A} nail{s} {D} clean through!"),
    "fire":   ("{A} scorch{es} {D}.",
               "{A} sear{s} {D} {where}!",
               "{A} set{s} {D} alight!",
               "{A} engulf{s} {D} in fire!"),
    "cold":   ("{A} chill{s} {D}.",
               "{A} rime{s} {D} {where} with frost!",
               "{A} freeze{s} {D} to the bone!",
               "{A} encase{s} {D} in ice!"),
    "lightning": ("{A} spark{s} against {D}.",
               "{A} jolt{s} {D} {where}!",
               "{A} arc{s} clean through {D}!",
               "{A} blast{s} {D} off {their} feet!"),
    "blast":  ("{A} scorch{es} {D}.",
               "{A} sear{s} {D} {where}!",
               "{A} blast{s} {D} off {their} feet!",
               "{A} engulf{s} {D} in fire!"),
    "fist":   ("{A} cuff{s} {D} without much conviction.",
               "{A} strike{s} {D} {where}!",
               "{A} deal{s} {D} a solid blow!",
               "{A} deal{s} {D} a crushing blow!"),
}

KILLS = {
    "slash":  ("{A} slash{es} through {Dp} throat with a neat lunge and slice.",
               "{A} deal{s} {D} a final murderous cut."),
    "chop":   ("{A} chop{s} open {Dp} chest, splintering ribs.",
               "{A} take{s} {D} apart at the shoulder."),
    "crush":  ("{A} crush{es} {Dp} skull into jelly.",
               "{A} pound{s} {D} until it stops moving."),
    "pierce": ("{A} run{s} {D} through, and {Dsub} fold{Ds} around the blade.",
               "{A} put{s} the point through {Dp} heart."),
    "shoot":  ("{A} drop{s} {D} where {Dsub} stand{Ds}.",
               "{A} put{s} the last shaft through {D}."),
    "blast":  ("{A} burn{s} {D} to a cinder.",
               "Nothing much is left of {D}."),
    "fire":   ("{A} burn{s} {D} to a cinder.",
               "{D} goes up like dry kindling."),
    "cold":   ("{D} freezes solid and cracks apart.",
               "{A} still{s} {D} where it stands."),
    "lightning": ("{A} blast{s} {D} apart.",
               "{D} comes apart in a crack of light."),
    "fist":   ("{A} beat{s} {D} down, and {Dsub} {Ddo} not get up.",
               "{A} finish{es} {D} off bare-handed."),
}

MISSES = ("{A} miss{es} {D}.",
          "{A} miss{es} {D} by a league!",
          "{A} swing{s} at air as {D} dance{Ds} back.")

BLOCK = "{A} smash{es} into {Dp} shield, striking sparks."


def _conjugate(text, you, defender_is_you=False):
    """Second person for whoever is "you", third for everyone else.

    The attacker and the defender are conjugated separately: "The Kobold
    swings at air as you dance back" needs both in one sentence.
    """
    text = text.replace("{Ds}", "" if defender_is_you else "s")
    if you:
        return (text.replace("{s}", "").replace("{es}", "")
                    .replace("{their}", "their"))
    return (text.replace("{s}", "s").replace("{es}", "es")
                .replace("{their}", "its"))


def weapon_class(actor):
    """What sort of blow this attacker deals."""
    if actor.kind != "player":
        return "fist"
    weapon = actor.equipment.get("weapon")
    if weapon is None:
        return "fist"
    return WEAPON_CLASS.get(weapon.key, "crush")


def _name_of(actor):
    """Bosses are named, not described: Vaelrik, not the Vaelrik."""
    if getattr(actor, "boss", False):
        return actor.name
    return f"the {actor.name}"


def _leading(name):
    """Capitalise the first letter and leave the rest of the name alone."""
    return name[:1].upper() + name[1:]


def blow_message(rng, attacker, defender, dmg, killed, blocked=False,
                 style=None):
    """One sentence for one blow, from the attacker's point of view.

    `style` overrides the weapon in hand, for the blows that are not swings:
    an arrow, a bolt of fire, a spell.
    """
    you = attacker.kind == "player"
    A = "You" if you else _leading(_name_of(attacker))
    D = "you" if defender.kind == "player" else _name_of(defender)
    Dp = "your" if defender.kind == "player" else f"{_name_of(defender)}'s"
    # A second mention of the defender wants a pronoun, and "you" takes a
    # different verb from "it": "you do not get up", "it does not get up".
    Dsub = "you" if defender.kind == "player" else "it"
    Ddo = "do" if defender.kind == "player" else "does"
    style = style or weapon_class(attacker)

    if blocked:
        text = BLOCK
    elif killed:
        text = rng.choice(KILLS[style])
    else:
        share = dmg / max(1, defender.max_hp)
        rung = 0 if share < 0.08 else 1 if share < 0.25 else 2 if share < 0.5 else 3
        text = STRIKES[style][rung]
    return _conjugate(text, you, defender.kind == "player").format(
        A=A, D=D, Dp=Dp, Dsub=Dsub, Ddo=Ddo, where=rng.choice(PLACES))


MISSES_RANGED = ("{A} shot goes wide of {D}.",
                 "{A} shot whistles past {D}.",
                 "{A} shot buries itself in the stone beside {D}.")


def ranged_miss_message(rng, attacker, defender):
    """A shot that misses is not a swing that misses."""
    you = attacker.kind == "player"
    A = "Your" if you else f"{_leading(_name_of(attacker))}'s"
    D = "you" if defender.kind == "player" else _name_of(defender)
    return rng.choice(MISSES_RANGED).format(A=A, D=D)


def miss_message(rng, attacker, defender):
    you = attacker.kind == "player"
    A = "You" if you else _leading(_name_of(attacker))
    D = "you" if defender.kind == "player" else _name_of(defender)
    Dp = "your" if defender.kind == "player" else f"{_name_of(defender)}'s"
    Dsub = "you" if defender.kind == "player" else "it"
    return _conjugate(rng.choice(MISSES), you, defender.kind == "player").format(
        A=A, D=D, Dp=Dp, Dsub=Dsub, Ddo="do" if Dsub == "you" else "does",
        where="")
