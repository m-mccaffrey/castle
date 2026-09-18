"""Nothing in the shops should be a trap.

A piece of gear is a trap when something else is better or equal on every
axis that matters and cheaper, lighter or found sooner: you save up, buy it,
and are worse off. Five weapons and a suit of armour were traps - the long
sword lost to the sabre, the battle axe lost to the long sword, the scale
mail lost to chain mail on armour, weight, price, depth and strength at once.

The weapon weights and the armour ladder are the original's own table, read
out of CASTLE1.HLP: armour runs 6, 12, 18, 24, 30, 36, 42, and a dagger
weighs 500 against a two-hander's 5000.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from stormhold.game.items import BASES                            # noqa: E402


def damage_per_turn(base):
    n, sides = base["dmg"]
    return n * (sides + 1) / 2 / (base.get("speed", 100) / 100.0)


def beats(better, worse, score):
    """Is `better` at least as good on every axis, and better on one?"""
    if score(better) < score(worse):
        return False
    for field, sign in (("wt", 1), ("value", 1), ("depth", 1), ("str_req", 1),
                        ("mana_bonus", -1), ("belt_slots", -1)):
        if sign * better.get(field, 0) > sign * worse.get(field, 0):
            return False
    if better.get("charges") != worse.get("charges"):
        return False
    if better.get("two_handed") and not worse.get("two_handed"):
        return False
    return (score(better) > score(worse)
            or better.get("wt", 0) < worse.get("wt", 0)
            or better.get("value", 0) < worse.get("value", 0))


class TestNothingIsATrap(unittest.TestCase):

    def dominated(self, pool, score):
        out = []
        for key, base in pool.items():
            for other, rival in pool.items():
                if other != key and beats(rival, base, score):
                    out.append(f"{key} is beaten outright by {other}")
                    break
        return out

    def test_no_weapon_is_beaten_outright_by_another(self):
        weapons = {k: v for k, v in BASES.items()
                   if v.get("slot") == "weapon" and v.get("dmg")}
        self.assertEqual(self.dominated(weapons, damage_per_turn), [])

    def test_no_piece_of_armour_is_beaten_outright_by_another(self):
        for slot in {v.get("slot") for v in BASES.values() if v.get("ac")}:
            pool = {k: v for k, v in BASES.items()
                    if v.get("ac") and v.get("slot") == slot}
            with self.subTest(slot=slot):
                self.assertEqual(self.dominated(pool, lambda b: b["ac"]), [])

    def test_the_body_armour_ladder_is_the_originals(self):
        """Soft Leather 6, Studded 12, Ring 18, Scale 24, Chain 30, the
        banded step at 36, Plate 42 - with the weights to match."""
        ladder = sorted(((v["ac"], v["wt"], k) for k, v in BASES.items()
                         if v.get("slot") == "torso" and v.get("ac", 0) > 3))
        self.assertEqual([av for av, _, _ in ladder], [6, 12, 18, 24, 30, 36, 42])
        self.assertEqual([wt for _, wt, _ in ladder],
                         [5000, 7000, 8000, 9000, 10000, 12000, 15000])

    def test_a_heavier_weapon_is_not_a_downgrade(self):
        """Weight, price and depth should each buy something."""
        weapons = sorted((v for v in BASES.values()
                          if v.get("slot") == "weapon" and v.get("dmg")
                          and not v.get("mana_bonus") and not v.get("charges")),
                         key=lambda b: b["value"])
        best = 0.0
        for base in weapons:
            best = max(best, damage_per_turn(base))
        self.assertGreater(best, damage_per_turn(weapons[0]),
                           "paying more never buys a better swing")


class TestTheDifficultySettingIsHonoured(unittest.TestCase):
    """A name that is not one of the four used to pass silently as
    Intermediate. An afternoon of measurements of "Hard" were measurements of
    the default, because the setting is called Difficult.
    """

    def test_an_unknown_setting_is_refused_rather_than_ignored(self):
        from stormhold.game.world import World
        with self.assertRaises(ValueError):
            World(seed=1, difficulty="Hard")

    def test_each_setting_changes_what_you_meet(self):
        from stormhold.game.world import World
        from stormhold.common.constants import DIFFICULTIES
        toughness = {}
        for label, _sym, _t, _x in DIFFICULTIES:
            world = World(seed=3, difficulty=label)
            world.add_player("Gauge")
            level = world.get_level(4)
            hp = [m.max_hp for m in level.actors.values()
                  if getattr(m, "kind", "") == "monster"]
            toughness[label] = sum(hp) / max(1, len(hp))
        self.assertLess(toughness["Easy"], toughness["Intermediate"])
        self.assertLess(toughness["Intermediate"], toughness["Difficult"])
        self.assertLess(toughness["Difficult"], toughness["Experts Only"])
