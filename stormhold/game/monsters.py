"""The things that live under Aldershade.

speed is ticks per action: 100 is an ordinary pace, lower is quicker. A dire
wolf at 70 gets three moves to your two; a stone golem at 170 gives you time to
back away and think.
"""

# pack    : (min, max) of a group that turns up together - "when found in
#           numbers can be much more deadly"
# ammo    : a ranged attacker's supply. A manticore "can exhaust the spines on
#           its tail, though it will usually cease fire before such exhaustion"
# immune  : elements that do it no harm at all
# fearless: fights to the death and never flees ("a ant will fight to the death")
# element : what the creature is made of. It takes half damage from its own
#           element and half again from the opposite one.
MONSTERS = {
    # key: (name, sprite, min_d, max_d, freq, hp, ac, hit, dmg, speed, xp, ai, extras)
    # A fresh, unarmoured level-1 character with nothing but the starting
    # dagger died to this pack (2, 5) at dmg (1, 3) far more than a first
    # fight should: simulated over the real combat engine, an encounter
    # with the full pack of 5 killed such a character 5.6 times on average
    # (dying here means the temple, the pack dropped and a chunk of xp and
    # gold lost, not game over, but "almost impossible not to spend
    # several deaths on the first fight" is exactly what that number
    # predicts). Neither the pack size nor the damage range is sourced -
    # "when found in numbers can be much more deadly" gives no figures -
    # so both are ours to tune: halving the worst case to (1, 3) and the
    # top of the damage roll to 2 brings the same simulation's worst case
    # down to under half a death per encounter, with the typical one- or
    # two-rat meeting close to none.
    "cave_rat":       dict(name="Cave Rat",        sprite="cave_rat",        min_d=1,  max_d=5,  freq=10, hp=7,   ac=2,  hit=1,  dmg=(1, 2), speed=110, xp=4,   ai="skittish", pack=(1, 3)),
    "cave_bat":       dict(name="Cave Bat",         sprite="cave_bat",        min_d=1,  max_d=7,  freq=9,  hp=9,   ac=5,  hit=2,  dmg=(1, 4), speed=70,  xp=7,   ai="erratic", dodge=4),
    "kobold":         dict(name="Kobold",           sprite="kobold",          min_d=1,  max_d=7,  freq=10, hp=13,  ac=4,  hit=2,  dmg=(1, 5), speed=100, xp=9,   ai="melee"),
    "cellar_spider":  dict(name="Cellar Spider",    sprite="cellar_spider",   min_d=2,  max_d=9,  freq=9,  hp=17,  ac=5,  hit=4,  dmg=(1, 5), speed=90,  xp=15,  ai="melee", poison=3, fearless=True),
    # A goblin tribe can afford protection, and sometimes buys it.
    "goblin":         dict(name="Goblin", hires="shambler", hire_chance=0.25, sprite="goblin",          min_d=2,  max_d=9,  freq=11, hp=20,  ac=6,  hit=4,  dmg=(1, 6), speed=100, xp=14,  ai="melee", pack=(2, 4)),
    "goblin_archer":  dict(name="Goblin Archer",    sprite="goblin_archer",   min_d=3,  max_d=11, freq=8,  hp=17,  ac=5,  hit=5,  dmg=(1, 6), speed=100, xp=18,  ai="archer", ammo=12, rng=7, pack=(1, 2)),
    "skeleton":       dict(name="Rattling Bones",   sprite="skeleton",        min_d=3,  max_d=12, freq=10, hp=26,  ac=8,  hit=5,  dmg=(1, 8), speed=100, xp=23,  ai="melee", undead=True, fearless=True),
    "shambler":       dict(name="Shambler",         sprite="shambler",        min_d=3,  max_d=13, freq=9,  hp=40,  ac=6,  hit=4,  dmg=(2, 4), speed=150, xp=26,  ai="brute", undead=True),
    "dire_wolf":      dict(name="Dire Wolf",        sprite="dire_wolf",       min_d=4,  max_d=13, freq=10, hp=30,  ac=7,  hit=6,  dmg=(1, 9), speed=70,  xp=30,  ai="melee", pack=(2, 4)),
    "acid_pudding":   dict(name="Acid Pudding",     sprite="acid_pudding",    min_d=5,  max_d=14, freq=6,  hp=46,  ac=3,  hit=5,  dmg=(1, 8), speed=170, xp=34,  ai="brute", corrode=True),
    "cutpurse":       dict(name="Smirking Cutpurse", sprite="goblin",          min_d=3,  max_d=14, freq=6,  hp=30,  ac=10, hit=7,  dmg=(1, 5), speed=130, xp=40,  ai="melee", steals=True,
                          taunts=("You brought all this down here for me?",
                                  "Heavy, is it? Let me take some.",
                                  "The stairs are that way. Run along.",
                                  "I have had better off first-timers.")),
    "orc":            dict(name="Orc Raider",       sprite="orc",             min_d=5,  max_d=15, freq=11, hp=46,  ac=9,  hit=7,  dmg=(2, 5), speed=100, xp=40,  ai="melee"),
    "ash_cultist":    dict(name="Ash Cultist",      sprite="ash_cultist",     min_d=6,  max_d=16, freq=8,  hp=36,  ac=7,  hit=7,  dmg=(1, 8), speed=100, xp=46,  ai="caster", rng=7, bolt="fire", element="fire", immune=("fire",)),
    # Its poison is slow to take hold, which is what makes a cure worth
    # carrying: you have time to reach one, if you turn back now.
    "crypt_ghoul":    dict(name="Crypt Ghoul",      sprite="crypt_ghoul",     min_d=7,  max_d=16, freq=9,  hp=54,  ac=9,  hit=8,  dmg=(2, 6), speed=90,  xp=56,  ai="melee", poison=5, poison_delay=900, drain="body", undead=True),
    "ogre":           dict(name="Ogre",             sprite="ogre",            min_d=8,  max_d=18, freq=8,  hp=82,  ac=10, hit=8,  dmg=(3, 5), speed=130, xp=80,  ai="brute", knockback=2),
    "clockwork_sentry": dict(name="Clockwork Sentry", sprite="clockwork_sentry", min_d=9, max_d=19, freq=7, hp=70, ac=14, hit=9,  dmg=(2, 6), speed=120, xp=92,  ai="melee", construct=True, fearless=True),
    "pale_wraith":    dict(name="Pale Wraith",      sprite="pale_wraith",     min_d=10, max_d=20, freq=8,  hp=62,  ac=11, hit=10, dmg=(2, 7), speed=90,  xp=105, ai="erratic", drain="mana", undead=True),
    "moss_troll":     dict(name="Moss Troll",       sprite="moss_troll",      min_d=11, max_d=21, freq=8,  hp=130, ac=12, hit=10, dmg=(3, 6), speed=110, xp=150, ai="brute", regen=3),
    "storm_wisp":     dict(name="Storm Wisp",       sprite="storm_wisp",      min_d=12, max_d=22, freq=6,  hp=55,  ac=16, hit=11, dmg=(2, 8), speed=60,  xp=160, ai="erratic", bolt="spark", rng=5, immune=("lightning",)),
    # "Earth elementals can pass through rock", and what does not go round a
    # door goes through it.
    "stone_golem":    dict(name="Stone Golem",      sprite="stone_golem",     min_d=13, max_d=23, freq=7,  hp=185, ac=18, hit=11, dmg=(3, 7), speed=170, xp=195, ai="brute", knockback=2, construct=True, fearless=True, through_rock=True, breaks_doors=True),
    "storm_sorcerer": dict(name="Storm Sorcerer",   sprite="storm_sorcerer",  min_d=14, max_d=25, freq=7,  hp=95,  ac=12, hit=13, dmg=(2, 9), speed=100, xp=225, ai="caster", rng=9, bolt="spark"),
    "ember_drake":    dict(name="Ember Drake",      sprite="ember_drake",     min_d=16, max_d=25, freq=7,  hp=165, ac=15, hit=14, dmg=(3, 8), speed=80,  xp=290, ai="archer", ammo=12, rng=6, bolt="fire", element="fire", burn=True, immune=("fire",)),
    "iron_revenant":  dict(name="Iron Revenant",    sprite="iron_revenant",   min_d=18, max_d=25, freq=7,  hp=240, ac=19, hit=16, dmg=(4, 7), speed=100, xp=380, ai="melee", drain="mana", undead=True, fearless=True),

    # ---- the two that end a run -----------------------------------------
    "warden_of_ash": dict(
        name="The Warden of Ash", sprite="warden_of_ash", min_d=12, max_d=12, freq=0,
        # 340, not 560. At 560 the Warden was a wall a solo character could
        # not get past at all - 0% across twenty measured fights at the level
        # and gear you have on floor 12, which is the weakest a character is
        # relative to what is in front of them. At 340 it is a fight you win
        # about three times in five, whatever the size of the party.
        hp=340, ac=16, hit=13, dmg=(3, 8), speed=95, xp=1400, ai="boss",
        rng=7, bolt="fire", element="fire", burn=True, knockback=2,
        entry="Something enormous shifts in the dark, and the air turns to ash.",
    ),
    "vaelrik": dict(
        name="Vaelrik, the Storm-Bound", sprite="vaelrik", min_d=25, max_d=25, freq=0,
        hp=1500, ac=22, hit=19, dmg=(4, 9), speed=85, xp=7000, ai="boss",
        rng=9, bolt="spark", knockback=3, summons=("iron_revenant", "pale_wraith"),
        entry="Vaelrik rises from his broken throne. The storm answers him.",
    ),
}

BOSSES = ("warden_of_ash", "vaelrik")


def deepest_band():
    """The creatures that live on the last floor anything is written for.

    Below that the keep keeps going, so it keeps sending these - older and
    bigger every floor, which is what `scaled` is for. Working it out from
    the table rather than naming the creatures means a new deep monster
    added later joins the band without anybody remembering to come back
    here.
    """
    floor = max(m["max_d"] for m in MONSTERS.values() if m["freq"] > 0)
    return [(key, m["freq"]) for key, m in MONSTERS.items()
            if m["freq"] > 0 and m["max_d"] >= floor]


def spawn_table(depth):
    """Which creatures can turn up on this floor, and how often."""
    out = []
    for key, m in MONSTERS.items():
        if m["freq"] <= 0 or not (m["min_d"] <= depth <= m["max_d"]):
            continue
        mid = (m["min_d"] + m["max_d"]) / 2.0
        falloff = 1.0 / (1.0 + abs(depth - mid) * 0.18)
        out.append((key, m["freq"] * falloff))
    # Past the written floors the deep sends what it has. Falling through to
    # a cave rat - which is what used to happen the moment you went below the
    # deepest `max_d` - would have made floor 26 the easiest in the keep.
    return out or deepest_band()


def scaled(template, depth, tough=1.0, worth=1.0):
    """Creatures met deeper than their home floor have had longer to grow.

    `tough` and `worth` are the difficulty setting: how hard the creature is
    and what killing it is worth.
    """
    over = max(0, depth - template["min_d"])
    return dict(
        hp=max(1, int(template["hp"] * (1 + over * 0.09) * tough)),
        ac=template["ac"] + over // 3,
        hit=template["hit"] + int(over * 0.4),
        dmg_bonus=int(over * 0.5 + (tough - 1.0) * 2),
        xp=max(1, int(template["xp"] * (1 + over * 0.14) * worth)),
    )
