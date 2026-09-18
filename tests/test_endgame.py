"""The keep can be finished, and not by accident.

A game nobody can complete is the worst bug there is, and the cheapest one
to miss: every test can pass while the last floor holds a creature with more
hit points than anything can chew through. This asks the two questions that
matter - is the lord of the keep there at all, and can a character who got
that far actually kill him.

The fight is modelled rather than played: spells, weapon swings and a belt
of healing, against his own numbers. It is not the real fight - he has his
own tricks - but it catches a boss who is unkillable or a pushover.
"""

import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from stormhold.common.constants import MAX_DEPTH, mana_cost                # noqa: E402
from stormhold.game import combat                                          # noqa: E402
from stormhold.game.items import Item                                      # noqa: E402
from stormhold.game.spells import SPELLS                                   # noqa: E402
from stormhold.game.world import World                                     # noqa: E402

FULL = ("platemail", "helm", "towershield", "gauntlets", "boots",
        "leggings", "cloak", "halberd", "amulet_ward", "ring_warding")


class TestTheKeepCanBeFinished(unittest.TestCase):

    def setUp(self):
        self.world = World(seed=4)
        self.level = self.world.get_level(MAX_DEPTH)

    def boss(self):
        return next((m for m in self.level.actors.values()
                     if getattr(m, "boss", False)), None)

    def champion(self, level_n, enchant, gear=FULL):
        p = self.world.add_player(f"Champion{level_n}",
                                  {"strength": 18, "dexterity": 16,
                                   "intelligence": 16, "constitution": 18})
        p.level = level_n
        for key in gear:
            item = Item(key, enchant=enchant)
            item.known = True
            p.equipment[item.slot] = item
        p.recalc()
        p.hp = p.max_hp
        p.spells.update(n for n, s in SPELLS.items() if s["level"] <= level_n)
        p.mana = p.max_mana
        return p

    def duel(self, p, boss, potions=0, trials=60):
        def best_spell(mana):
            best, most = None, 0
            for name in p.spells:
                spell = SPELLS[name]
                if "dmg" not in spell:
                    continue
                if mana_cost(spell["mana"], p.level, spell.get("level", 1)) > mana:
                    continue
                n, sides, per = spell["dmg"]
                avg = n * (sides + 1) / 2 + per * p.level
                if avg > most:
                    best, most = name, avg
            return best

        wins = 0
        for trial in range(trials):
            rng = random.Random(trial)
            php, mhp, mana, left = p.max_hp, boss.max_hp, p.max_mana, potions
            for _ in range(4000):
                if php <= 0 or mhp <= 0:
                    break
                if php < p.max_hp * 0.35 and left:
                    php = min(p.max_hp, php + max(24, int(p.max_hp * 0.6)))
                    left -= 1
                    continue
                spell = best_spell(mana)
                if spell:
                    s = SPELLS[spell]
                    mana -= mana_cost(s["mana"], p.level, s.get("level", 1))
                    n, sides, per = s["dmg"]
                    mhp -= sum(rng.randint(1, sides) for _ in range(n)) + per * p.level
                else:
                    hit, crit = combat.attack_roll(rng, p.to_hit, boss.armour_class)
                    if hit:
                        mhp -= p.damage_roll(rng) * (2 if crit else 1)
                if mhp <= 0:
                    break
                hit, crit = combat.attack_roll(rng, boss.to_hit, p.armour_class)
                if hit:
                    n, sides = boss.tpl["dmg"]
                    php -= sum(rng.randint(1, sides) for _ in range(n)) + boss.dmg_bonus
            wins += php > 0
        return wins / trials

    def test_the_last_floor_has_a_lord(self):
        boss = self.boss()
        self.assertIsNotNone(boss, f"nothing to beat on floor {MAX_DEPTH}")
        self.assertGreater(boss.max_hp, 200, "the last fight should be a fight")

    def test_a_character_who_got_there_and_brought_healing_can_win(self):
        p = self.champion(20, 1)
        self.assertGreater(self.duel(p, self.boss(), potions=6), 0.5,
                           "the keep cannot be finished")

    def test_and_a_finished_character_wins_comfortably(self):
        p = self.champion(25, 3)
        self.assertGreater(self.duel(p, self.boss()), 0.8)

    def test_but_not_halfway_through_the_keep_in_chain_mail(self):
        p = self.champion(14, 0, gear=("chainmail", "helm", "shield",
                                       "boots", "longsword"))
        self.assertLess(self.duel(p, self.boss(), potions=6), 0.2,
                        "the last fight should not be winnable at floor 14")


if __name__ == "__main__":
    unittest.main()
