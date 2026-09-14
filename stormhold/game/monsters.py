"""The things that live under Aldershade.

speed is ticks per action: 100 is an ordinary pace, lower is quicker. A dire
wolf at 70 gets three moves to your two; a stone golem at 170 gives you time to
back away and think.
"""

MONSTERS = {
    # key: (name, sprite, min_d, max_d, freq, hp, ac, hit, dmg, speed, xp, ai, extras)
    "cave_rat":       dict(name="Cave Rat",        sprite="cave_rat",        min_d=1,  max_d=5,  freq=10, hp=7,   ac=2,  hit=1,  dmg=(1, 3), speed=110, xp=4,   ai="skittish"),
    "cave_bat":       dict(name="Cave Bat",         sprite="cave_bat",        min_d=1,  max_d=7,  freq=9,  hp=9,   ac=5,  hit=2,  dmg=(1, 4), speed=70,  xp=7,   ai="erratic"),
    "kobold":         dict(name="Kobold",           sprite="kobold",          min_d=1,  max_d=7,  freq=10, hp=13,  ac=4,  hit=2,  dmg=(1, 5), speed=100, xp=9,   ai="melee"),
    "cellar_spider":  dict(name="Cellar Spider",    sprite="cellar_spider",   min_d=2,  max_d=9,  freq=9,  hp=17,  ac=5,  hit=4,  dmg=(1, 5), speed=90,  xp=15,  ai="melee", poison=3),
    "goblin":         dict(name="Goblin",           sprite="goblin",          min_d=2,  max_d=9,  freq=11, hp=20,  ac=6,  hit=4,  dmg=(1, 6), speed=100, xp=14,  ai="melee"),
    "goblin_archer":  dict(name="Goblin Archer",    sprite="goblin_archer",   min_d=3,  max_d=11, freq=8,  hp=17,  ac=5,  hit=5,  dmg=(1, 6), speed=100, xp=18,  ai="archer", rng=7),
    "skeleton":       dict(name="Rattling Bones",   sprite="skeleton",        min_d=3,  max_d=12, freq=10, hp=26,  ac=8,  hit=5,  dmg=(1, 8), speed=100, xp=23,  ai="melee", undead=True),
    "shambler":       dict(name="Shambler",         sprite="shambler",        min_d=3,  max_d=13, freq=9,  hp=40,  ac=6,  hit=4,  dmg=(2, 4), speed=150, xp=26,  ai="brute", undead=True),
    "dire_wolf":      dict(name="Dire Wolf",        sprite="dire_wolf",       min_d=4,  max_d=13, freq=10, hp=30,  ac=7,  hit=6,  dmg=(1, 9), speed=70,  xp=30,  ai="melee"),
    "acid_pudding":   dict(name="Acid Pudding",     sprite="acid_pudding",    min_d=5,  max_d=14, freq=6,  hp=46,  ac=3,  hit=5,  dmg=(1, 8), speed=170, xp=34,  ai="brute", corrode=True),
    "orc":            dict(name="Orc Raider",       sprite="orc",             min_d=5,  max_d=15, freq=11, hp=46,  ac=9,  hit=7,  dmg=(2, 5), speed=100, xp=40,  ai="melee"),
    "ash_cultist":    dict(name="Ash Cultist",      sprite="ash_cultist",     min_d=6,  max_d=16, freq=8,  hp=36,  ac=7,  hit=7,  dmg=(1, 8), speed=100, xp=46,  ai="caster", rng=7, bolt="fire"),
    "crypt_ghoul":    dict(name="Crypt Ghoul",      sprite="crypt_ghoul",     min_d=7,  max_d=16, freq=9,  hp=54,  ac=9,  hit=8,  dmg=(2, 6), speed=90,  xp=56,  ai="melee", poison=5, drain="hp", undead=True),
    "ogre":           dict(name="Ogre",             sprite="ogre",            min_d=8,  max_d=18, freq=8,  hp=82,  ac=10, hit=8,  dmg=(3, 5), speed=130, xp=80,  ai="brute", knockback=2),
    "clockwork_sentry": dict(name="Clockwork Sentry", sprite="clockwork_sentry", min_d=9, max_d=19, freq=7, hp=70, ac=14, hit=9,  dmg=(2, 6), speed=120, xp=92,  ai="melee", construct=True),
    "pale_wraith":    dict(name="Pale Wraith",      sprite="pale_wraith",     min_d=10, max_d=20, freq=8,  hp=62,  ac=11, hit=10, dmg=(2, 7), speed=90,  xp=105, ai="erratic", drain="stat", undead=True),
    "moss_troll":     dict(name="Moss Troll",       sprite="moss_troll",      min_d=11, max_d=21, freq=8,  hp=130, ac=12, hit=10, dmg=(3, 6), speed=110, xp=150, ai="brute", regen=3),
    "storm_wisp":     dict(name="Storm Wisp",       sprite="storm_wisp",      min_d=12, max_d=22, freq=6,  hp=55,  ac=16, hit=11, dmg=(2, 8), speed=60,  xp=160, ai="erratic", bolt="spark", rng=5),
    "stone_golem":    dict(name="Stone Golem",      sprite="stone_golem",     min_d=13, max_d=23, freq=7,  hp=185, ac=18, hit=11, dmg=(3, 7), speed=170, xp=195, ai="brute", knockback=2, construct=True),
    "storm_sorcerer": dict(name="Storm Sorcerer",   sprite="storm_sorcerer",  min_d=14, max_d=25, freq=7,  hp=95,  ac=12, hit=13, dmg=(2, 9), speed=100, xp=225, ai="caster", rng=9, bolt="spark"),
    "ember_drake":    dict(name="Ember Drake",      sprite="ember_drake",     min_d=16, max_d=25, freq=7,  hp=165, ac=15, hit=14, dmg=(3, 8), speed=80,  xp=290, ai="archer", rng=6, bolt="fire", burn=True),
    "iron_revenant":  dict(name="Iron Revenant",    sprite="iron_revenant",   min_d=18, max_d=25, freq=7,  hp=240, ac=19, hit=16, dmg=(4, 7), speed=100, xp=380, ai="melee", drain="stat", undead=True),

    # ---- the two that end a run -----------------------------------------
    "warden_of_ash": dict(
        name="The Warden of Ash", sprite="warden_of_ash", min_d=12, max_d=12, freq=0,
        hp=560, ac=16, hit=13, dmg=(3, 8), speed=95, xp=1400, ai="boss",
        rng=7, bolt="fire", burn=True, knockback=2,
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


def spawn_table(depth):
    """Which creatures can turn up on this floor, and how often."""
    out = []
    for key, m in MONSTERS.items():
        if m["freq"] <= 0 or not (m["min_d"] <= depth <= m["max_d"]):
            continue
        mid = (m["min_d"] + m["max_d"]) / 2.0
        falloff = 1.0 / (1.0 + abs(depth - mid) * 0.18)
        out.append((key, m["freq"] * falloff))
    return out or [("cave_rat", 1.0)]


def scaled(template, depth):
    """Creatures met deeper than their home floor have had longer to grow."""
    over = max(0, depth - template["min_d"])
    return dict(
        hp=int(template["hp"] * (1 + over * 0.09)),
        ac=template["ac"] + over // 3,
        hit=template["hit"] + int(over * 0.4),
        dmg_bonus=int(over * 0.5),
        xp=int(template["xp"] * (1 + over * 0.14)),
    )
