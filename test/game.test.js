import test from 'node:test';
import assert from 'node:assert/strict';

import { World } from '../server/game/world.js';
import { generateDungeon, generateTown, reachable } from '../server/game/level.js';
import { findPath } from '../server/game/ai.js';
import { computeFOV, hasLOS } from '../shared/fov.js';
import { makeItem, generateItem, describeItem } from '../server/game/items.js';
import { Player, makeMonster } from '../server/game/actors.js';
import { resolveAttack, applyDamage } from '../server/game/combat.js';
import { RNG } from '../shared/rng.js';
import { T, REVIVE_MS, DESCEND_MS, TOWN_DEPTH, xpForLevel, MAX_LEVEL } from '../shared/constants.js';

/** A world with a clock we control, so timing is deterministic. */
function makeWorld(seed = 1234) {
  const state = { now: 1_000_000 };
  const world = new World({ seed, clock: () => state.now });
  world.advance = (ms, step = 50) => {
    for (let t = 0; t < ms; t += step) { state.now += step; world.tick(); }
  };
  world.jump = (ms) => { state.now += ms; };
  return world;
}

// ---------------------------------------------------------------- levels --

test('every dungeon level is fully connected and has usable stairs', () => {
  for (let depth = 1; depth <= 20; depth++) {
    const level = generateDungeon(depth, 5150);
    const reach = reachable(level, level.upAt.x, level.upAt.y);
    let walkable = 0;
    for (let y = 0; y < level.h; y++) {
      for (let x = 0; x < level.w; x++) if (level.passable(x, y)) walkable++;
    }
    assert.equal(reach.size, walkable, `depth ${depth} has stranded tiles`);
    if (depth < 20) {
      assert.ok(level.downAt, `depth ${depth} has no down stairs`);
      assert.ok(reach.has(level.idx(level.downAt.x, level.downAt.y)),
        `depth ${depth} down stairs unreachable`);
    }
    assert.ok(level.spawns.length > 0 && level.lootSpots.length > 0);
  }
});

test('the town has shops, a spawn point and a way into the keep', () => {
  const town = generateTown(7);
  assert.equal(town.depth, TOWN_DEPTH);
  assert.equal(town.npcs.length, 3);
  assert.ok(town.downAt);
  assert.equal(town.get(town.downAt.x, town.downAt.y), T.STAIRS_DOWN);
  assert.ok(town.passable(town.spawnPoint.x, town.spawnPoint.y));
  const reach = reachable(town, town.spawnPoint.x, town.spawnPoint.y);
  assert.ok(reach.has(town.idx(town.downAt.x, town.downAt.y)), 'keep gate is walled off');
  for (const npc of town.npcs) {
    assert.ok(reach.has(town.idx(npc.x, npc.y)) || town.passable(npc.x, npc.y),
      `${npc.name} is unreachable`);
  }
});

test('pathfinding reaches every room and refuses impossible goals', () => {
  const level = generateDungeon(6, 99);
  const start = level.rooms[0];
  for (const room of level.rooms) {
    const path = findPath(level, start.cx, start.cy, room.cx, room.cy);
    assert.ok(path, `no path to room at ${room.cx},${room.cy}`);
    if (path.length) {
      const [ex, ey] = path[path.length - 1];
      assert.deepEqual([ex, ey], [room.cx, room.cy]);
    }
  }
  // A tile sealed in solid rock is not reachable.
  assert.equal(findPath(level, start.cx, start.cy, 0, 0), null);
});

// ------------------------------------------------------------------ fov ---

test('field of view is blocked by walls and is symmetric through open space', () => {
  const level = generateDungeon(2, 31);
  const room = level.rooms[0];
  const seen = new Set();
  computeFOV(level, room.cx, room.cy, 8, seen);
  assert.ok(seen.has(level.idx(room.cx, room.cy)), 'origin must be visible');
  for (const i of seen) {
    const x = i % level.w, y = (i / level.w) | 0;
    assert.ok(Math.max(Math.abs(x - room.cx), Math.abs(y - room.cy)) <= 8, 'saw past the radius');
  }
  // Line of sight cannot cross a wall tile.
  let wall = null;
  for (let y = 1; y < level.h - 1 && !wall; y++) {
    for (let x = 1; x < level.w - 1; x++) {
      if (level.get(x, y) === T.WALL && level.get(x - 1, y) === T.FLOOR && level.get(x + 1, y) === T.FLOOR) {
        wall = { x, y }; break;
      }
    }
  }
  if (wall) assert.equal(hasLOS(level, wall.x - 1, wall.y, wall.x + 1, wall.y), false);
});

// --------------------------------------------------------------- combat ---

test('damage is mitigated by armour, never below 1, and kills at zero', () => {
  const world = makeWorld();
  const m = makeMonster('kobold', 5, 5, 1);
  m.depth = 1;
  world.getLevel(1).place(m);
  m.armor = 30;
  const before = m.hp;
  const res = applyDamage(world, m, 5, null, {});
  assert.equal(res.dealt, 1, 'armour must not reduce a hit below 1');
  assert.equal(m.hp, before - 1);
  applyDamage(world, m, 9999, null, {});
  assert.ok(m.dead, 'monster should die at zero hp');
});

test('bulwark halves incoming damage', () => {
  const world = makeWorld();
  const p = world.addPlayer('Test', 'warrior');
  p.armor = 0;
  const plain = applyDamage(world, p, 40, null, {}).dealt;
  p.hp = p.maxHp;
  p.addEffect('bulwark', 5000, {}, world.now);
  const warded = applyDamage(world, p, 40, null, {}).dealt;
  assert.ok(warded < plain, `bulwark did nothing (${warded} vs ${plain})`);
  assert.equal(warded, Math.round(plain * 0.5));
});

test('a player kill awards xp and levels the character up', () => {
  const world = makeWorld();
  const p = world.addPlayer('Hero', 'warrior');
  world.movePlayerToDepth(p, 1);
  const level = world.getLevel(1);
  const spot = level.findFree(p.x + 1, p.y);
  const m = makeMonster('rat', spot.x, spot.y, 1);
  m.depth = 1;
  level.place(m);
  const xpBefore = p.xp;
  world.killActor(m, p);
  assert.ok(p.xp > xpBefore, 'no xp awarded');
  assert.equal(p.kills, 1);
  assert.ok(m.dead);
});

test('levelling stops at the cap and raises the right stats per class', () => {
  const mage = new Player('M', 'mage', 1, 1);
  const witsBefore = mage.wits;
  mage.addXp(xpForLevel(1) + 1);
  assert.equal(mage.level, 2);
  assert.ok(mage.wits > witsBefore, 'mage should gain wits');
  mage.addXp(10_000_000);
  assert.equal(mage.level, MAX_LEVEL, 'level cap not enforced');
});

// ------------------------------------------------------------ inventory ---

test('equipping swaps gear and updates derived stats', () => {
  const p = new Player('Geared', 'warrior', 1, 1);
  const armorBefore = p.armor;
  p.addItem(makeItem('plate'));
  p.equip(p.inventory[0].id);
  assert.ok(p.armor > armorBefore, 'armour did not improve');
  assert.equal(p.equipped.armor.key, 'plate');

  p.addItem(makeItem('leather'));
  const heavy = p.armor;
  p.equip(p.inventory.find(i => i.key === 'leather').id);
  assert.equal(p.equipped.armor.key, 'leather');
  assert.ok(p.armor < heavy, 'swapping down should lower armour');
  assert.ok(p.inventory.some(i => i.key === 'plate'), 'old armour should return to the pack');

  p.unequip('armor');
  assert.equal(p.equipped.armor, null);
});

test('consumables stack and are spent one at a time', () => {
  const p = new Player('Stacker', 'ranger', 1, 1);
  p.addItem(makeItem('potheal', null, null, 2));
  p.addItem(makeItem('potheal', null, null, 3));
  const stack = p.inventory.find(i => i.key === 'potheal');
  assert.equal(stack.qty, 5, 'potions should stack');
  p.removeItem(stack.id, 1);
  assert.equal(stack.qty, 4);
});

test('max-hp gear keeps current hp within bounds', () => {
  const p = new Player('Vigor', 'warrior', 1, 1);
  p.addItem(makeItem('amuletvigor'));
  p.equip(p.inventory[0].id);
  const maxWithAmulet = p.maxHp;
  p.hp = p.maxHp;
  p.unequip('trinket');
  assert.ok(p.maxHp < maxWithAmulet);
  assert.ok(p.hp <= p.maxHp, 'hp must be clamped when max hp drops');
});

test('generated loot is always well-formed', () => {
  const rng = new RNG(8);
  for (let depth = 1; depth <= 20; depth++) {
    for (let i = 0; i < 60; i++) {
      const it = generateItem(depth, rng, i % 5 === 0);
      assert.ok(it.name && it.name.length > 0);
      assert.ok(Number.isFinite(it.value) && it.value > 0, `bad value on ${it.name}`);
      assert.ok(typeof describeItem(it) === 'string');
      if (it.type === 'weapon') assert.ok(it.dmg[0] > 0 && it.dmg[1] > 1);
    }
  }
});

// --------------------------------------------------------------- co-op ----

test('a downed player can be revived by a friend standing over them', () => {
  const world = makeWorld();
  const a = world.addPlayer('Parent', 'warrior');
  const b = world.addPlayer('Kid', 'mage');
  world.movePlayerToDepth(a, 1);
  world.movePlayerToDepth(b, 1);
  const level = world.getLevel(1);
  // Put them next to each other.
  const spot = level.findFree(a.x + 1, a.y);
  level.moveActor(b, spot.x, spot.y);

  applyDamage(world, b, 99999, null, {});
  assert.equal(b.downed, true, 'should be downed, not dead');
  assert.equal(world.players.has(b.id), true);

  world.interact(a);
  assert.ok(a.reviving, 'revive channel did not start');
  // Mashing the key must not restart the channel.
  world.advance(1000);
  world.interact(a);
  world.interact(a);
  world.advance(REVIVE_MS);
  assert.equal(b.downed, false, 'revive never completed');
  assert.ok(b.hp > 0);
});

test('moving cancels a revive in progress', () => {
  const world = makeWorld();
  const a = world.addPlayer('Parent', 'warrior');
  const b = world.addPlayer('Kid', 'ranger');
  world.movePlayerToDepth(a, 1);
  world.movePlayerToDepth(b, 1);
  const level = world.getLevel(1);
  const spot = level.findFree(a.x + 1, a.y);
  level.moveActor(b, spot.x, spot.y);
  applyDamage(world, b, 99999, null, {});
  world.interact(a);
  assert.ok(a.reviving);
  world.setInput(a, 1, 0);
  assert.equal(a.reviving, null, 'walking away should cancel the revive');
});

test('a total party wipe sends everyone home to town with a gold penalty', () => {
  const world = makeWorld();
  const a = world.addPlayer('A', 'warrior');
  const b = world.addPlayer('B', 'mage');
  world.movePlayerToDepth(a, 3);
  world.movePlayerToDepth(b, 3);
  a.gold = 1000; b.gold = 500;
  applyDamage(world, a, 99999, null, {});
  applyDamage(world, b, 99999, null, {});
  assert.equal(a.depth, TOWN_DEPTH, 'wiped party should be back in town');
  assert.equal(b.depth, TOWN_DEPTH);
  assert.equal(a.gold, 900, 'expected a 10% gold penalty');
  assert.equal(a.downed, false);
  assert.ok(a.hp > 0);
});

test('calling the party down moves everyone together after the countdown', () => {
  const world = makeWorld();
  const a = world.addPlayer('A', 'warrior');
  const b = world.addPlayer('B', 'ranger');
  world.movePlayerToDepth(a, 1);
  world.movePlayerToDepth(b, 1);
  const level = world.getLevel(1);
  // Stand the caller on the stairs; leave the other one across the level.
  level.moveActor(a, level.downAt.x, level.downAt.y);
  world.interact(a);
  assert.ok(level.descendUntil, 'countdown did not start');
  world.advance(DESCEND_MS + 200);
  assert.equal(a.depth, 2, 'caller did not descend');
  assert.equal(b.depth, 2, 'the rest of the party was left behind');
});

test('xp from a kill is shared with nearby party members', () => {
  const world = makeWorld();
  const a = world.addPlayer('A', 'warrior');
  const b = world.addPlayer('B', 'mage');
  world.movePlayerToDepth(a, 2);
  world.movePlayerToDepth(b, 2);
  const level = world.getLevel(2);
  level.moveActor(b, ...Object.values(level.findFree(a.x + 2, a.y)));
  const spot = level.findFree(a.x + 1, a.y);
  const m = makeMonster('goblin', spot.x, spot.y, 2);
  m.depth = 2;
  level.place(m);
  world.killActor(m, a);
  assert.ok(a.xp > 0 && b.xp > 0, 'both party members should earn xp');
});

// ---------------------------------------------------------------- shops ---

test('buying costs gold, selling pays out, and you cannot overspend', () => {
  const world = makeWorld();
  const p = world.addPlayer('Shopper', 'warrior');
  const town = world.getLevel(TOWN_DEPTH);
  const smith = [...town.actors.values()].find(a => a.shop === 'smith');
  const spot = town.findFree(smith.x + 1, smith.y);
  town.moveActor(p, spot.x, spot.y);

  world.openShop(p, smith);
  const stock = world.shopCache.get('smith');
  assert.ok(stock.length > 0);

  const cheapest = stock.reduce((a, b) => (a.value <= b.value ? a : b));
  p.gold = cheapest.value;
  world.buy(p, smith.id, cheapest.id);
  assert.equal(p.gold, 0, 'gold was not deducted');
  assert.ok(p.inventory.some(i => i.id === cheapest.id), 'item not delivered');

  // Broke now: the next purchase must fail.
  const remaining = world.shopCache.get('smith')[0];
  if (remaining) {
    const packBefore = p.inventory.length;
    world.buy(p, smith.id, remaining.id);
    assert.equal(p.inventory.length, packBefore, 'bought something with no gold');
  }

  world.sell(p, smith.id, cheapest.id);
  assert.ok(p.gold > 0, 'selling paid nothing');
  assert.equal(p.inventory.some(i => i.id === cheapest.id), false);
});

test('you cannot shop from across the map', () => {
  const world = makeWorld();
  const p = world.addPlayer('Sneak', 'mage');
  const town = world.getLevel(TOWN_DEPTH);
  const smith = [...town.actors.values()].find(a => a.shop === 'smith');
  world.openShop(p, smith);
  const stock = world.shopCache.get('smith');
  p.gold = 100000;
  const packBefore = p.inventory.length;
  world.buy(p, smith.id, stock[0].id);   // player is at the town spawn, far away
  assert.equal(p.inventory.length, packBefore, 'bought an item from out of range');
});

// ---------------------------------------------------- items in the world --

test('walking over loot picks it up, and gold is added straight to the purse', () => {
  const world = makeWorld();
  const p = world.addPlayer('Looter', 'ranger');
  world.movePlayerToDepth(p, 1);
  const level = world.getLevel(1);
  world.dropGold(level, p.x, p.y, 77);
  const goldBefore = p.gold;
  world.pickupAt(p, level);
  assert.equal(p.gold, goldBefore + 77);

  const sword = makeItem('longsword');
  world.dropItem(level, p.x, p.y, sword);
  world.pickupAt(p, level);
  assert.ok(p.inventory.some(i => i.id === sword.id), 'item was not picked up');
});

test('a healing potion heals and is consumed', () => {
  const world = makeWorld();
  const p = world.addPlayer('Drinker', 'warrior');
  world.movePlayerToDepth(p, 1);
  p.hp = 5;
  p.inventory = [];
  p.addItem(makeItem('potheal'));
  const potion = p.inventory[0];
  world.useItem(p, potion.id);
  assert.ok(p.hp > 5, 'potion did not heal');
  assert.equal(p.inventory.length, 0, 'potion was not consumed');
});

test('a scroll of recall pulls the whole party back to town', () => {
  const world = makeWorld();
  const a = world.addPlayer('A', 'mage');
  const b = world.addPlayer('B', 'warrior');
  world.movePlayerToDepth(a, 5);
  world.movePlayerToDepth(b, 5);
  a.addItem(makeItem('scrrecall'));
  world.useItem(a, a.inventory.find(i => i.key === 'scrrecall').id);
  assert.equal(a.depth, TOWN_DEPTH);
  assert.equal(b.depth, TOWN_DEPTH, 'party member left behind');
});

// ---------------------------------------------------------- projectiles ---

test('a projectile travels, hits a monster and stops', () => {
  const world = makeWorld();
  const p = world.addPlayer('Archer', 'ranger');
  world.movePlayerToDepth(p, 1);
  const level = world.getLevel(1);
  // Find a clear run of floor to shoot along.
  let from = null;
  for (const room of level.rooms) {
    if (room.w >= 5) { from = { x: room.x + 1, y: room.y + 1 }; break; }
  }
  assert.ok(from, 'no room wide enough for the test');
  level.moveActor(p, from.x, from.y);
  const target = makeMonster('rat', from.x + 3, from.y, 1);
  target.depth = 1;
  target.maxHp = target.hp = 500;          // survive the hit so we can measure
  level.place(target);

  world.spawnProjectile({
    kind: 'arrow', x: p.x, y: p.y, tx: target.x, ty: target.y,
    ownerId: p.id, hostile: false, damage: 10, level,
  });
  assert.equal(level.projectiles.length, 1);
  for (let i = 0; i < 40 && level.projectiles.length; i++) world.stepProjectiles(level, 0.05);
  assert.equal(level.projectiles.length, 0, 'projectile never resolved');
  assert.ok(target.hp < 500 || target.dead, 'projectile did no damage');
});

test('projectiles stop at walls instead of flying through them', () => {
  const world = makeWorld();
  const p = world.addPlayer('Caster', 'mage');
  world.movePlayerToDepth(p, 1);
  const level = world.getLevel(1);
  world.spawnProjectile({
    kind: 'fire', x: p.x, y: p.y, tx: p.x + 40, ty: p.y,
    ownerId: p.id, hostile: false, damage: 10, maxRange: 40, level,
  });
  for (let i = 0; i < 400 && level.projectiles.length; i++) world.stepProjectiles(level, 0.05);
  assert.equal(level.projectiles.length, 0, 'projectile escaped the level');
});

// ------------------------------------------------------------- snapshot ---

test('a snapshot only contains what the viewer can actually see', () => {
  const world = makeWorld();
  const p = world.addPlayer('Watcher', 'warrior');
  world.movePlayerToDepth(p, 4);
  world.updateFOV(p, true);
  const snap = world.snapshotFor(p);
  assert.ok(snap, 'no snapshot produced');
  const level = world.getLevel(4);
  for (const a of snap.actors) {
    if (a.k === 'player') continue;
    assert.ok(p.fov.has(a.y * level.w + a.x), `leaked a hidden ${a.n} at ${a.x},${a.y}`);
  }
  assert.equal(snap.you.id, p.id);
  assert.ok(Array.isArray(snap.party));
});

test('the world survives a long unattended run with monsters and players', () => {
  const world = makeWorld(2026);
  const p = world.addPlayer('Idle', 'warrior');
  world.movePlayerToDepth(p, 8);
  world.advance(60_000);                       // a full minute of simulation
  assert.ok(Number.isFinite(p.hp) && p.hp <= p.maxHp);
  assert.ok(Number.isFinite(p.mana) && p.mana <= p.maxMana);
  for (const level of world.levels.values()) {
    for (const a of level.actors.values()) {
      assert.ok(Number.isFinite(a.hp), `${a.name} has non-finite hp`);
      assert.ok(a.x >= 0 && a.y >= 0 && a.x < level.w && a.y < level.h,
        `${a.name} escaped the map at ${a.x},${a.y}`);
    }
  }
});
