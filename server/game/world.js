import {
  T, DIRS, TICK_MS, MAX_DEPTH, TOWN_DEPTH, REVIVE_MS, BLEEDOUT_MS, DESCEND_MS,
  ABILITIES, chebyshev, clamp, SIGHT_DUNGEON, SIGHT_TOWN,
} from '../../shared/constants.js';
import { RNG } from '../../shared/rng.js';
import { generateDungeon, generateTown } from './level.js';
import { Player, makeMonster, NPC } from './actors.js';
import { computeFOV, hasLOS, lineTo } from '../../shared/fov.js';
import { thinkMonster, findPath } from './ai.js';
import {
  resolveAttack, applyDamage, healActor, enemiesNear, dirIndex, applyRider,
} from './combat.js';
import { generateItem, generateGold, makeItem, shopStock, describeItem } from './items.js';
import { spawnTableFor, MONSTERS } from './monsters.js';

const PROJ_SPEED = { arrow: 14, bolt: 11, fire: 10, magic: 13 };
const SIGHT_RADIUS = { dungeon: SIGHT_DUNGEON, town: SIGHT_TOWN };

let nextGroundId = 1;
let nextProjId = 1;

export class World {
  constructor(opts = {}) {
    this.seed = opts.seed ?? (Math.random() * 0x7fffffff) | 0;
    this.rng = new RNG(this.seed);
    // Injectable clock: the server passes Date.now, tests pass a virtual one.
    this.clock = opts.clock ?? (() => Date.now());
    this.levels = new Map();          // depth -> Level
    this.players = new Map();         // id -> Player
    this.now = this.clock();
    this.events = [];                 // drained by the net layer each tick
    this.partyDeepest = 1;
    this.difficulty = opts.difficulty ?? 1;
    this.shopCache = new Map();       // shop key -> stock
    this.town = this.getLevel(TOWN_DEPTH);
  }

  // ------------------------------------------------------------ levels ----
  getLevel(depth) {
    let lvl = this.levels.get(depth);
    if (lvl) return lvl;
    if (depth === TOWN_DEPTH) {
      lvl = generateTown(this.seed);
      for (const spec of lvl.npcs) {
        const npc = new NPC(spec, spec.x, spec.y);
        lvl.place(npc);
      }
    } else {
      lvl = generateDungeon(depth, this.seed);
      this.populate(lvl);
    }
    this.levels.set(depth, lvl);
    return lvl;
  }

  levelOf(actor) { return this.levels.get(actor.depth ?? 0) || null; }

  /** Fill a freshly generated level with monsters and loot. */
  populate(level) {
    const rng = this.rng;
    const table = spawnTableFor(level.depth);
    // Three people clearing a floor should not be three times as easy as one.
    const party = Math.max(1, this.players.size);
    const countMul = 1 + (party - 1) * 0.3;
    const toughMul = 1 + (party - 1) * 0.5;
    level.partySize = party;

    for (const spot of level.spawns) {
      if (!level.walkable(spot.x, spot.y)) continue;
      if (rng.next() > 0.88 * countMul) continue;      // leave some breathing room
      const key = rng.weighted(table);
      const elite = spot.elite || rng.chance(0.06 + level.depth * 0.004);
      const m = makeMonster(key, spot.x, spot.y, level.depth, elite);
      m.depth = level.depth;
      m.maxHp = Math.round(m.maxHp * toughMul);
      m.hp = m.maxHp;
      m.xpValue = Math.round(m.xpValue * (1 + (party - 1) * 0.25));
      level.place(m);
    }
    for (const spot of level.lootSpots) {
      if (!level.passable(spot.x, spot.y)) continue;
      if (rng.chance(0.42)) this.dropGold(level, spot.x, spot.y, generateGold(level.depth, rng));
      else this.dropItem(level, spot.x, spot.y, generateItem(level.depth, rng, spot.rich));
    }
    if (level.isBossLevel && level.bossRoom) {
      const key = level.depth >= 20 ? 'stormking' : 'warden';
      const { x, y } = level.findFree(level.bossRoom.cx, level.bossRoom.cy);
      const boss = makeMonster(key, x, y, level.depth);
      boss.depth = level.depth;
      boss.maxHp = Math.round(boss.maxHp * (1 + (party - 1) * 0.6));
      boss.hp = boss.maxHp;
      level.place(boss);
      level.boss = boss;
    }
  }

  // ------------------------------------------------------------ events ----
  // ctxDepth tags each event with the level it happened on so the net layer
  // can route it to the right clients. null means "tell everybody".
  float(x, y, text, kind = 'damage') { this.events.push({ t: 'float', x, y, text, kind, d: this.ctxDepth }); }
  sound(name, x, y) { this.events.push({ t: 'sound', name, x, y, d: this.ctxDepth }); }
  fx(kind, x, y, extra = {}) { this.events.push({ t: 'fx', kind, x, y, d: this.ctxDepth, ...extra }); }
  log(msg, kind = 'info', to = null) { this.events.push({ t: 'log', msg, kind, to, d: to ? null : this.ctxDepth }); }

  setTile(level, x, y, tile) {
    level.set(x, y, tile);
    this.events.push({ t: 'tile', depth: level.depth, x, y, tile });
    // Anyone who has already seen this tile should see it change.
    for (const p of this.players.values()) {
      if (p.depth !== level.depth) continue;
      const mem = p.memory.get(level.depth);
      if (mem && mem[y * level.w + x]) p.pendingTiles.push(x, y, tile);
    }
  }

  // ------------------------------------------------------------ players ---
  addPlayer(name, cls, save) {
    const town = this.getLevel(TOWN_DEPTH);
    const spot = town.findFree(town.spawnPoint.x, town.spawnPoint.y);
    const p = new Player(name, cls, spot.x, spot.y);
    if (save) p.loadSave(save);
    if (!p.equipped.weapon && !save) {
      p.equipped.weapon = makeItem(p.def.startWeapon);
      p.equipped.armor = makeItem(p.def.startArmor);
      p.addItem(makeItem('potheal', null, null, 2));
      p.recalc();
      p.hp = p.maxHp; p.mana = p.maxMana;
    }
    p.depth = TOWN_DEPTH;
    this.players.set(p.id, p);
    town.place(p);
    this.partyDeepest = Math.max(this.partyDeepest, p.deepest || 1);
    this.updateFOV(p, true);
    return p;
  }

  removePlayer(id) {
    const p = this.players.get(id);
    if (!p) return;
    const level = this.levels.get(p.depth);
    if (level) level.remove(p);
    this.players.delete(id);
  }

  playersOn(depth) {
    return [...this.players.values()].filter(p => p.depth === depth);
  }

  // ------------------------------------------------------------- input ----
  setInput(p, dx, dy) {
    p.input.dx = clamp(dx | 0, -1, 1);
    p.input.dy = clamp(dy | 0, -1, 1);
    if (dx || dy) {
      p.facing = dirIndex(p.input.dx, p.input.dy);
      if (p.reviving) this.cancelRevive(p);
    }
  }

  /** Called from the tick loop when a player's move cooldown is up. */
  tryMove(p) {
    const { dx, dy } = p.input;
    if (!dx && !dy) return;
    const level = this.levels.get(p.depth);
    if (!level) return;

    const nx = p.x + dx, ny = p.y + dy;
    if (!level.inBounds(nx, ny)) return;
    const tile = level.get(nx, ny);

    // Bump a closed door to open it.
    if (tile === T.DOOR) {
      this.setTile(level, nx, ny, T.DOOR_OPEN);
      this.sound('door', nx, ny);
      p.nextMoveAt = this.now + 150;
      return;
    }

    const occ = level.occupant(nx, ny);
    if (occ && occ.kind === 'monster' && !occ.dead) {
      this.playerMelee(p, occ);
      return;
    }
    if (occ && occ.kind === 'npc') {
      this.openShop(p, occ);
      p.nextMoveAt = this.now + 250;
      return;
    }
    if (!level.walkable(nx, ny, p.id)) return;

    // Don't let a diagonal squeeze through a wall corner.
    if (dx && dy && !level.passable(p.x + dx, p.y) && !level.passable(p.x, p.y + dy)) return;

    level.moveActor(p, nx, ny);
    const slow = tile === T.WATER || tile === T.RUBBLE;
    p.nextMoveAt = this.now + p.moveTime(slow);
    if (slow) this.sound('splash', nx, ny);
    else this.sound('step', nx, ny);
    this.pickupAt(p, level);
    this.updateFOV(p);
  }

  playerMelee(p, target) {
    if (this.now < p.nextAttackAt) return;
    p.facing = dirIndex(target.x - p.x, target.y - p.y);
    p.nextAttackAt = this.now + p.attackTime();
    p.nextMoveAt = Math.max(p.nextMoveAt, this.now + 120);
    this.sound('swing', p.x, p.y);
    this.fx('slash', target.x, target.y, { color: p.color });
    resolveAttack(this, p, target);
  }

  /** Primary attack: melee for a bare/melee weapon, a shot for bows and staves. */
  primaryAttack(p) {
    if (p.downed || this.now < p.nextAttackAt) return;
    const level = this.levels.get(p.depth);
    if (!level) return;
    const w = p.equipped.weapon;
    const [fx, fy] = DIRS[p.facing];

    if (w?.ranged) {
      const cost = w.magic ? (w.manaCost || 0) : 0;
      if (cost && p.mana < cost) {
        this.log('Not enough mana.', 'warn', p.id);
        this.sound('deny', p.x, p.y);
        p.nextAttackAt = this.now + 300;
        return;
      }
      p.mana -= cost;
      p.nextAttackAt = this.now + p.attackTime();
      // Aim at the nearest enemy roughly ahead, else straight forward.
      const aim = this.aimAssist(level, p, fx, fy, 10) || { x: p.x + fx * 10, y: p.y + fy * 10 };
      this.spawnProjectile({
        kind: w.magic ? 'magic' : 'arrow',
        x: p.x, y: p.y, tx: aim.x, ty: aim.y,
        ownerId: p.id, hostile: false,
        damage: p.rollDamage(this.rng),
        onHit: w.onHit, lifesteal: w.lifesteal,
        level,
      });
      this.sound('shoot', p.x, p.y);
      return;
    }

    // Melee swing at whatever is in front.
    const tx = p.x + fx, ty = p.y + fy;
    const occ = level.occupant(tx, ty);
    p.nextAttackAt = this.now + p.attackTime();
    this.sound('swing', p.x, p.y);
    this.fx('slash', tx, ty, { color: p.color });
    if (occ && occ.kind === 'monster' && !occ.dead) resolveAttack(this, p, occ);
  }

  /** Nudge a shot toward a nearby enemy so kids can actually hit things. */
  aimAssist(level, p, fx, fy, range) {
    let best = null, bestScore = -Infinity;
    const flen = Math.hypot(fx, fy) || 1;
    for (const a of level.actors.values()) {
      if (a.kind !== 'monster' || a.dead) continue;
      const dx = a.x - p.x, dy = a.y - p.y;
      const d = Math.hypot(dx, dy);
      if (d > range || d === 0) continue;
      const dot = ((dx / d) * (fx / flen) + (dy / d) * (fy / flen));
      if (dot < 0.55) continue;                        // must be broadly ahead
      if (!hasLOS(level, p.x, p.y, a.x, a.y, range + 2)) continue;
      const score = dot * 2 - d * 0.05;
      if (score > bestScore) { bestScore = score; best = a; }
    }
    return best ? { x: best.x, y: best.y } : null;
  }

  // --------------------------------------------------------- projectiles --
  spawnProjectile(spec) {
    const dx = spec.tx - spec.x, dy = spec.ty - spec.y;
    const len = Math.hypot(dx, dy) || 1;
    const p = {
      id: nextProjId++,
      kind: spec.kind,
      x: spec.x, y: spec.y,
      dx: dx / len, dy: dy / len,
      speed: PROJ_SPEED[spec.kind] ?? 12,
      ownerId: spec.ownerId,
      hostile: !!spec.hostile,
      damage: spec.damage,
      onHit: spec.onHit,
      lifesteal: spec.lifesteal,
      burst: spec.burst || 0,
      traveled: 0,
      maxRange: spec.maxRange ?? 12,
    };
    spec.level.projectiles.push(p);
    return p;
  }

  stepProjectiles(level, dt) {
    const keep = [];
    for (const pr of level.projectiles) {
      const step = pr.speed * dt;
      const substeps = Math.max(1, Math.ceil(step / 0.5));
      let alive = true;
      for (let s = 0; s < substeps && alive; s++) {
        pr.x += pr.dx * (step / substeps);
        pr.y += pr.dy * (step / substeps);
        pr.traveled += step / substeps;
        const tx = Math.round(pr.x), ty = Math.round(pr.y);

        if (!level.passable(tx, ty)) { this.burstProjectile(level, pr, tx, ty); alive = false; break; }
        if (pr.traveled >= pr.maxRange) { this.burstProjectile(level, pr, tx, ty); alive = false; break; }

        const occ = level.occupant(tx, ty);
        if (occ && occ.id !== pr.ownerId && !occ.dead) {
          const validTarget = pr.hostile ? (occ.kind === 'player' && !occ.downed) : occ.kind === 'monster';
          if (validTarget) {
            const owner = level.actors.get(pr.ownerId);
            resolveAttack(this, owner ?? { accuracy: 6, kind: pr.hostile ? 'monster' : 'player' }, occ, {
              damage: pr.damage,
              onHit: pr.onHit,
            });
            this.burstProjectile(level, pr, tx, ty);
            alive = false;
          }
        }
      }
      if (alive) keep.push(pr);
    }
    level.projectiles = keep;
  }

  burstProjectile(level, pr, x, y) {
    this.fx(pr.kind === 'fire' ? 'firehit' : pr.kind === 'magic' || pr.kind === 'bolt' ? 'magichit' : 'hit', x, y);
    if (pr.burst > 0) {
      for (const a of level.actors.values()) {
        const valid = pr.hostile ? a.kind === 'player' && !a.downed : a.kind === 'monster';
        if (valid && !a.dead && chebyshev(a.x, a.y, x, y) <= pr.burst) {
          applyDamage(this, a, Math.round(pr.damage * 0.6), level.actors.get(pr.ownerId), { element: pr.kind });
        }
      }
    }
  }

  /** Serialisable projectile view for the client. */
  projectileJSON(level) {
    return level.projectiles.map(p => ({
      id: p.id, k: p.kind,
      x: Math.round(p.x * 10) / 10, y: Math.round(p.y * 10) / 10,
      a: Math.round(Math.atan2(p.dy, p.dx) * 100) / 100,
    }));
  }

  // ---------------------------------------------------------- abilities ---
  useAbility(p, slot) {
    if (p.downed) return;
    const key = p.def.abilities[slot];
    if (!key) return;
    const ab = ABILITIES[key];
    const ready = p.abilityReady[key] ?? 0;
    if (this.now < ready) { this.sound('deny', p.x, p.y); return; }
    if (p.mana < ab.cost) {
      this.log('Not enough mana.', 'warn', p.id);
      this.sound('deny', p.x, p.y);
      return;
    }
    const level = this.levels.get(p.depth);
    if (!level) return;

    p.mana -= ab.cost;
    p.abilityReady[key] = this.now + ab.cd;
    p.nextAttackAt = Math.max(p.nextAttackAt, this.now + 250);
    const [fx, fy] = DIRS[p.facing];

    switch (key) {
      case 'cleave': {
        this.fx('cleave', p.x, p.y, { color: p.color });
        this.sound('cleave', p.x, p.y);
        for (const m of enemiesNear(level, p.x, p.y, 1)) {
          resolveAttack(this, p, m, { mult: 1.5, accBonus: 2 });
        }
        break;
      }
      case 'bulwark': {
        p.addEffect('bulwark', 6000, {}, this.now);
        this.fx('shield', p.x, p.y, { color: '#c8b048' });
        this.sound('buff', p.x, p.y);
        this.log(`${p.name} braces behind their shield.`, 'ability');
        break;
      }
      case 'charge': {
        this.sound('charge', p.x, p.y);
        let hit = null, steps = 0;
        for (let i = 1; i <= ABILITIES.charge.range; i++) {
          const nx = p.x + fx * i, ny = p.y + fy * i;
          if (!level.passable(nx, ny)) break;
          const occ = level.occupant(nx, ny);
          if (occ && occ.kind === 'monster' && !occ.dead) { hit = occ; break; }
          if (occ) break;
          steps = i;
        }
        if (steps > 0) {
          level.moveActor(p, p.x + fx * steps, p.y + fy * steps);
          this.fx('dashtrail', p.x, p.y, { color: p.color });
        }
        if (hit) {
          resolveAttack(this, p, hit, { mult: 1.8, accBonus: 3, knockback: 2 });
        }
        this.updateFOV(p);
        break;
      }
      case 'volley': {
        this.sound('shoot', p.x, p.y);
        const spread = [-0.35, 0, 0.35];
        const baseAngle = Math.atan2(fy, fx);
        const aim = this.aimAssist(level, p, fx, fy, 9);
        const angle = aim ? Math.atan2(aim.y - p.y, aim.x - p.x) : baseAngle;
        for (const off of spread) {
          const a = angle + off;
          this.spawnProjectile({
            kind: 'arrow', x: p.x, y: p.y,
            tx: p.x + Math.cos(a) * 9, ty: p.y + Math.sin(a) * 9,
            ownerId: p.id, hostile: false,
            damage: Math.round(p.rollDamage(this.rng) * 0.8),
            maxRange: 9, level,
          });
        }
        break;
      }
      case 'snare': {
        const aim = this.aimAssist(level, p, fx, fy, ABILITIES.snare.range);
        const target = aim ? level.occupant(aim.x, aim.y) : null;
        if (target && target.kind === 'monster') {
          target.addEffect('snare', 3000, {}, this.now);
          this.fx('snare', target.x, target.y);
          this.sound('snare', target.x, target.y);
          this.log(`${p.name} pins ${target.name} in place.`, 'ability');
        } else {
          this.log('Nothing in your sights.', 'warn', p.id);
          p.mana += ab.cost;
          p.abilityReady[key] = this.now + 400;
        }
        break;
      }
      case 'dash': {
        this.sound('dash', p.x, p.y);
        let steps = 0;
        for (let i = 1; i <= ABILITIES.dash.range; i++) {
          const nx = p.x - fx * i, ny = p.y - fy * i;
          if (!level.walkable(nx, ny, p.id)) break;
          steps = i;
        }
        if (steps) {
          level.moveActor(p, p.x - fx * steps, p.y - fy * steps);
          this.fx('dashtrail', p.x, p.y, { color: p.color });
          this.updateFOV(p);
        }
        p.addEffect('haste', 2000, {}, this.now);
        break;
      }
      case 'firebolt': {
        this.sound('fireball', p.x, p.y);
        const aim = this.aimAssist(level, p, fx, fy, ABILITIES.firebolt.range)
          || { x: p.x + fx * 10, y: p.y + fy * 10 };
        this.spawnProjectile({
          kind: 'fire', x: p.x, y: p.y, tx: aim.x, ty: aim.y,
          ownerId: p.id, hostile: false,
          damage: Math.round(p.rollDamage(this.rng) * 1.5),
          onHit: { type: 'burn', dmg: 5, ms: 3000 },
          burst: 1, maxRange: ABILITIES.firebolt.range, level,
        });
        break;
      }
      case 'frostnova': {
        this.sound('frost', p.x, p.y);
        this.fx('frostnova', p.x, p.y);
        for (const m of enemiesNear(level, p.x, p.y, ABILITIES.frostnova.range)) {
          applyDamage(this, m, Math.round(p.rollDamage(this.rng) * 0.9), p, { element: 'frost' });
          if (!m.dead) applyRider(this, m, { type: 'chill', slow: 0.55, ms: 4000 }, p);
        }
        break;
      }
      case 'mend': {
        this.sound('heal', p.x, p.y);
        this.fx('heal', p.x, p.y);
        const amount = 22 + p.stat('wits') * 3 + p.level * 2;
        for (const ally of this.playersOn(p.depth)) {
          if (ally.downed) continue;
          if (chebyshev(ally.x, ally.y, p.x, p.y) > ABILITIES.mend.range) continue;
          healActor(this, ally, amount);
          if (ally.id !== p.id) this.fx('heal', ally.x, ally.y);
        }
        break;
      }
    }
  }

  // --------------------------------------------------------- ground loot --
  dropItem(level, x, y, item) {
    const spot = level.findFloor(x, y, 6);
    const g = { id: nextGroundId++, x: spot.x, y: spot.y, item, gold: 0 };
    level.items.set(g.id, g);
    return g;
  }

  dropGold(level, x, y, amount) {
    const spot = level.findFloor(x, y, 6);
    const g = { id: nextGroundId++, x: spot.x, y: spot.y, item: null, gold: amount };
    level.items.set(g.id, g);
    return g;
  }

  pickupAt(p, level) {
    for (const g of level.items.values()) {
      if (g.x !== p.x || g.y !== p.y) continue;
      if (g.gold) {
        p.gold += g.gold;
        this.float(p.x, p.y, `+${g.gold}g`, 'gold');
        this.sound('gold', p.x, p.y);
        level.items.delete(g.id);
      } else if (g.item) {
        if (p.addItem(g.item)) {
          this.log(`${p.name} picks up ${g.item.name}.`, 'loot');
          this.sound('pickup', p.x, p.y);
          level.items.delete(g.id);
          this.pushInventory(p);
        } else {
          this.log('Your pack is full.', 'warn', p.id);
        }
      }
    }
  }

  itemsJSON(level) {
    return [...level.items.values()].map(g => ({
      id: g.id, x: g.x, y: g.y,
      gold: g.gold || 0,
      icon: g.item?.icon || null,
      name: g.item?.name || `${g.gold} gold`,
      tier: g.item?.tier || 1,
    }));
  }

  // ------------------------------------------------------------- items ----
  useItem(p, itemId) {
    const it = p.inventory.find(i => i.id === itemId);
    if (!it) return;
    if (it.slot) { this.equipItem(p, itemId); return; }
    if (!it.use) return;
    const level = this.levels.get(p.depth);
    let consumed = true;

    switch (it.use) {
      case 'heal': {
        if (p.hp >= p.maxHp) { this.log('You are already at full health.', 'warn', p.id); return; }
        healActor(this, p, it.power);
        this.sound('drink', p.x, p.y);
        break;
      }
      case 'mana': {
        if (p.mana >= p.maxMana) { this.log('Your mana is already full.', 'warn', p.id); return; }
        p.mana = Math.min(p.maxMana, p.mana + it.power);
        this.float(p.x, p.y, `+${it.power}`, 'mana');
        this.sound('drink', p.x, p.y);
        break;
      }
      case 'haste': p.addEffect('haste', it.power, {}, this.now); this.sound('buff', p.x, p.y); break;
      case 'fury':  p.addEffect('fury', it.power, {}, this.now);  this.sound('buff', p.x, p.y); break;
      case 'ward':  p.addEffect('ward', it.power, {}, this.now);  this.sound('buff', p.x, p.y); break;
      case 'map': {
        this.revealLevel(p, level);
        this.sound('magic', p.x, p.y);
        this.log('The layout of the level floods into your mind.', 'ability', p.id);
        break;
      }
      case 'teleport': {
        const spot = this.randomSafeSpot(level, p);
        if (spot) {
          level.moveActor(p, spot.x, spot.y);
          this.fx('blink', p.x, p.y);
          this.sound('blink', p.x, p.y);
          this.updateFOV(p);
        } else consumed = false;
        break;
      }
      case 'firestorm': {
        this.fx('firestorm', p.x, p.y);
        this.sound('fireball', p.x, p.y);
        for (const m of enemiesNear(level, p.x, p.y, 3)) {
          applyDamage(this, m, it.power + p.level * 2, p, { element: 'fire' });
          if (!m.dead) applyRider(this, m, { type: 'burn', dmg: 5, ms: 3000 }, p);
        }
        break;
      }
      case 'recall': {
        if (p.depth === TOWN_DEPTH) { this.log('You are already in town.', 'warn', p.id); return; }
        this.log(`${p.name} tears open a road home. The party is pulled to Aldershade.`, 'good');
        for (const ally of this.playersOn(p.depth)) this.movePlayerToDepth(ally, TOWN_DEPTH);
        this.sound('magic', p.x, p.y);
        break;
      }
      default: consumed = false;
    }

    if (consumed) {
      p.removeItem(itemId, 1);
      this.pushInventory(p);
    }
  }

  equipItem(p, itemId) {
    const res = p.equip(itemId);
    if (res) {
      this.sound('equip', p.x, p.y);
      this.log(`${p.name} equips ${res.equipped.name}.`, 'loot');
      this.pushInventory(p);
    }
  }

  unequipItem(p, slot) {
    if (p.unequip(slot)) { this.sound('equip', p.x, p.y); this.pushInventory(p); }
  }

  dropInventoryItem(p, itemId) {
    const level = this.levels.get(p.depth);
    const it = p.removeItem(itemId, 1);
    if (!it || !level) return;
    this.dropItem(level, p.x, p.y, it);
    this.sound('drop', p.x, p.y);
    this.pushInventory(p);
  }

  pushInventory(p) {
    this.events.push({ t: 'inv', to: p.id });
  }

  randomSafeSpot(level, p) {
    for (let i = 0; i < 200; i++) {
      const x = this.rng.int(1, level.w - 2), y = this.rng.int(1, level.h - 2);
      if (!level.walkable(x, y, p.id)) continue;
      if (enemiesNear(level, x, y, 4).length) continue;
      return { x, y };
    }
    return null;
  }

  revealLevel(p, level) {
    const mem = this.memoryFor(p, level);
    for (let y = 0; y < level.h; y++) {
      for (let x = 0; x < level.w; x++) {
        const i = y * level.w + x;
        if (level.tiles[i] === T.VOID) continue;
        if (!mem[i]) { mem[i] = 1; p.pendingTiles.push(x, y, level.tiles[i]); }
      }
    }
  }

  // ------------------------------------------------------------- shops ----
  openShop(p, npc) {
    if (!npc.shop) return;
    let stock = this.shopCache.get(npc.shop);
    if (!stock) {
      stock = shopStock(npc.shop, this.rng, this.partyDeepest);
      this.shopCache.set(npc.shop, stock);
    }
    this.events.push({ t: 'shopopen', to: p.id, npcId: npc.id, shop: npc.shop, name: npc.name });
    p.openShopId = npc.id;
  }

  buy(p, npcId, itemId) {
    const level = this.levels.get(p.depth);
    const npc = level?.actors.get(npcId);
    if (!npc || !npc.shop || chebyshev(npc.x, npc.y, p.x, p.y) > 2) {
      this.log('You are too far from the shopkeeper.', 'warn', p.id);
      return;
    }
    if (npc.shop === 'temple' && itemId === 'heal') {
      const cost = 25 + p.level * 8;
      if (p.gold < cost) { this.log('You cannot afford that blessing.', 'warn', p.id); this.sound('deny', p.x, p.y); return; }
      p.gold -= cost;
      p.hp = p.maxHp; p.mana = p.maxMana;
      p.effects = p.effects.filter(e => ['haste', 'fury', 'ward'].includes(e.type));
      this.sound('heal', p.x, p.y);
      this.fx('heal', p.x, p.y);
      this.log(`${p.name} is made whole again.`, 'good');
      this.pushInventory(p);
      return;
    }
    const stock = this.shopCache.get(npc.shop) || [];
    const idx = stock.findIndex(i => i.id === itemId);
    if (idx < 0) return;
    const it = stock[idx];
    if (p.gold < it.value) { this.log('You cannot afford that.', 'warn', p.id); this.sound('deny', p.x, p.y); return; }
    if (!p.addItem(it)) { this.log('Your pack is full.', 'warn', p.id); return; }
    p.gold -= it.value;
    stock.splice(idx, 1);
    this.sound('buy', p.x, p.y);
    this.log(`${p.name} buys ${it.name}.`, 'loot');
    this.pushInventory(p);
    this.events.push({ t: 'shopopen', to: p.id, npcId: npc.id, shop: npc.shop, name: npc.name });
  }

  sell(p, npcId, itemId) {
    const level = this.levels.get(p.depth);
    const npc = level?.actors.get(npcId);
    if (!npc || !npc.shop) return;
    const it = p.inventory.find(i => i.id === itemId);
    if (!it) return;
    const price = Math.max(1, Math.floor(it.value * 0.45));
    p.removeItem(itemId, 1);
    p.gold += price;
    this.sound('gold', p.x, p.y);
    this.log(`${p.name} sells ${it.name} for ${price} gold.`, 'loot');
    this.pushInventory(p);
  }

  shopStockJSON(shop) {
    const stock = this.shopCache.get(shop) || [];
    return stock.map(i => ({ ...i, desc: describeItem(i) }));
  }

  // ------------------------------------------------------- death & revival -
  killActor(target, source) {
    if (target.dead) return;
    const level = this.levels.get(target.depth ?? 0);

    if (target.kind === 'monster') {
      target.dead = true;
      target.hp = 0;
      if (level) {
        level.remove(target);
        this.fx('death', target.x, target.y, { color: target.color });
        this.sound(target.boss ? 'bossdie' : 'die', target.x, target.y);

        // Loot. Bosses and elites are worth the trip.
        const rng = this.rng;
        const lootChance = target.boss ? 1 : target.elite ? 0.75 : 0.3;
        if (rng.chance(lootChance)) {
          const drops = target.boss ? 5 : target.elite ? 2 : 1;
          for (let i = 0; i < drops; i++) {
            this.dropItem(level, target.x, target.y, generateItem(target.depth, rng, target.boss || target.elite));
          }
        }
        if (rng.chance(target.boss ? 1 : 0.55)) {
          const mult = target.boss ? 12 : target.elite ? 3 : 1;
          this.dropGold(level, target.x, target.y, generateGold(target.depth, rng) * mult);
        }
      }

      // XP is shared with everyone nearby, so nobody has to steal kills.
      const nearby = this.playersOn(target.depth).filter(
        p => !p.downed && chebyshev(p.x, p.y, target.x, target.y) <= 14);
      const share = nearby.length ? Math.ceil(target.xpValue / Math.max(1, nearby.length * 0.75)) : 0;
      for (const p of nearby) {
        const levels = p.addXp(share);
        this.float(p.x, p.y, `+${share}xp`, 'xp');
        for (const lv of levels) {
          this.log(`${p.name} reaches level ${lv}!`, 'good');
          this.sound('levelup', p.x, p.y);
          this.fx('levelup', p.x, p.y, { color: p.color });
        }
      }
      if (source?.kind === 'player') source.kills++;
      if (target.boss) {
        this.log(`${target.name} falls!`, 'good');
        if (target.key === 'stormking') {
          this.log('The storm over Aldershade breaks. The keep is yours. Well played!', 'good');
          for (const p of this.playersOn(target.depth)) p.won = true;
        }
      } else {
        this.log(`${target.name} is slain.`, 'kill');
      }
      return;
    }

    if (target.kind === 'player') {
      if (target.downed) {                     // bled out
        this.wipeOrSendHome(target);
        return;
      }
      target.downed = true;
      target.hp = 0;
      target.input.dx = 0; target.input.dy = 0;
      target.bleedUntil = this.now + BLEEDOUT_MS;
      this.cancelRevive(target);
      this.sound('down', target.x, target.y);
      this.fx('death', target.x, target.y, { color: target.color });
      this.log(`${target.name} has gone down! Stand over them and press E to help them up.`, 'bad');

      const level = this.levels.get(target.depth);
      const standing = this.playersOn(target.depth).filter(p => !p.downed);
      if (level && !standing.length) this.partyWipe(target.depth);
    }
  }

  /** Someone bled out with friends still fighting: they wake up in town. */
  wipeOrSendHome(p) {
    p.downed = false;
    p.bleedUntil = 0;
    const lost = Math.floor(p.gold * 0.1);
    p.gold -= lost;
    p.hp = Math.max(1, Math.round(p.maxHp * 0.35));
    p.mana = Math.round(p.maxMana * 0.5);
    p.effects = [];
    this.movePlayerToDepth(p, TOWN_DEPTH);
    this.log(`${p.name} wakes on the temple floor in Aldershade${lost ? `, ${lost} gold lighter` : ''}.`, 'bad');
    this.sound('revive', p.x, p.y);
  }

  partyWipe(depth) {
    this.log('The whole party is down. Sister Halli drags you all back to Aldershade.', 'bad');
    for (const p of this.playersOn(depth)) {
      p.downed = false;
      p.bleedUntil = 0;
      const lost = Math.floor(p.gold * 0.1);
      p.gold -= lost;
      p.hp = Math.max(1, Math.round(p.maxHp * 0.35));
      p.mana = Math.round(p.maxMana * 0.5);
      p.effects = [];
      this.movePlayerToDepth(p, TOWN_DEPTH);
    }
  }

  beginRevive(p, target) {
    p.reviving = { id: target.id, until: this.now + REVIVE_MS };
    target.reviveProgress = 0;
    this.log(`${p.name} is helping ${target.name} up...`, 'info');
    this.sound('channel', p.x, p.y);
  }

  cancelRevive(p) {
    if (p.reviving) {
      const t = this.players.get(p.reviving.id);
      if (t) t.reviveProgress = 0;
      p.reviving = null;
    }
  }

  finishRevive(p, target) {
    target.downed = false;
    target.bleedUntil = 0;
    target.reviveProgress = 0;
    target.hp = Math.max(1, Math.round(target.maxHp * 0.45));
    target.effects = [];
    p.reviving = null;
    this.sound('revive', target.x, target.y);
    this.fx('heal', target.x, target.y);
    this.log(`${target.name} is back on their feet!`, 'good');
  }

  // ---------------------------------------------------------- interaction -
  interact(p) {
    if (p.downed) return;
    const level = this.levels.get(p.depth);
    if (!level) return;

    // 1. A friend on the floor next to you always comes first. Mashing the key
    //    must not restart the channel, or the revive never finishes.
    if (p.reviving) {
      const cur = this.players.get(p.reviving.id);
      if (cur && cur.downed && chebyshev(cur.x, cur.y, p.x, p.y) <= 1) return;
      this.cancelRevive(p);
    }
    for (const ally of this.playersOn(p.depth)) {
      if (ally.id === p.id || !ally.downed) continue;
      if (chebyshev(ally.x, ally.y, p.x, p.y) <= 1) { this.beginRevive(p, ally); return; }
    }

    // 2. A shopkeeper within reach.
    for (const a of level.actors.values()) {
      if (a.kind === 'npc' && chebyshev(a.x, a.y, p.x, p.y) <= 1) { this.openShop(p, a); return; }
    }

    // 3. Stairs under your feet.
    const tile = level.get(p.x, p.y);
    if (tile === T.STAIRS_DOWN) {
      if (level.descendUntil) { this.log('The party is already on its way down.', 'info', p.id); return; }
      const target = p.depth === TOWN_DEPTH ? Math.max(1, this.partyDeepest) : p.depth + 1;
      if (target > MAX_DEPTH) { this.log('There is nothing deeper than this.', 'info', p.id); return; }
      level.descendUntil = this.now + DESCEND_MS;
      level.descendTo = target;
      this.sound('stairs', p.x, p.y);
      this.log(`${p.name} calls the party down to level ${target}. Gather up! (${Math.round(DESCEND_MS / 1000)}s)`, 'good');
      return;
    }
    if (tile === T.STAIRS_UP) {
      const target = p.depth - 1;
      if (target < TOWN_DEPTH) return;
      level.descendUntil = this.now + DESCEND_MS;
      level.descendTo = target;
      this.sound('stairs', p.x, p.y);
      this.log(`${p.name} calls the party back up to ${target === TOWN_DEPTH ? 'Aldershade' : `level ${target}`}. (${Math.round(DESCEND_MS / 1000)}s)`, 'good');
      return;
    }
    if (tile === T.ALTAR) {
      this.log('The shattered throne of Vaelrik. Nothing stirs here now.', 'info', p.id);
      return;
    }
    this.log('Nothing to do here.', 'info', p.id);
  }

  movePlayerToDepth(p, depth) {
    const old = this.levels.get(p.depth);
    if (old) old.remove(p);
    const level = this.getLevel(depth);
    const anchor = depth > p.depth ? (level.upAt || level.spawnPoint)
                                   : (level.downAt || level.spawnPoint || level.upAt);
    const spot = level.findFree(anchor.x, anchor.y, 10);
    p.depth = depth;
    p.x = spot.x; p.y = spot.y; p.px = spot.x; p.py = spot.y;
    p.nextMoveAt = this.now + 300;
    p.input.dx = 0; p.input.dy = 0;
    this.cancelRevive(p);
    level.place(p);
    if (depth > 0) {
      p.deepest = Math.max(p.deepest, depth);
      this.partyDeepest = Math.max(this.partyDeepest, depth);
    }
    if (depth === TOWN_DEPTH) {
      // Fresh stock whenever the party comes home.
      this.shopCache.clear();
    }
    this.updateFOV(p, true);
    this.resendLevel(p);
    this.events.push({ t: 'level', to: p.id });
  }

  /**
   * Queue every tile this player remembers on their current level. Needed
   * whenever the client resets its map: a fresh join, or revisiting a level.
   */
  resendLevel(p) {
    const level = this.levels.get(p.depth);
    if (!level) return;
    const mem = this.memoryFor(p, level);
    p.pendingTiles.length = 0;
    for (let i = 0; i < mem.length; i++) {
      if (mem[i]) p.pendingTiles.push(i % level.w, (i / level.w) | 0, level.tiles[i]);
    }
  }

  // --------------------------------------------------------------- vision -
  memoryFor(p, level) {
    let mem = p.memory.get(level.depth);
    if (!mem) { mem = new Uint8Array(level.w * level.h); p.memory.set(level.depth, mem); }
    return mem;
  }

  updateFOV(p, force = false) {
    const level = this.levels.get(p.depth);
    if (!level) return;
    if (!force && p.fovAt === `${p.x},${p.y}`) return;
    p.fovAt = `${p.x},${p.y}`;
    const radius = level.isTown ? SIGHT_RADIUS.town : SIGHT_RADIUS.dungeon;
    computeFOV(level, p.x, p.y, radius, p.fov);
    const mem = this.memoryFor(p, level);
    for (const i of p.fov) {
      if (!mem[i]) {
        mem[i] = 1;
        p.pendingTiles.push(i % level.w, (i / level.w) | 0, level.tiles[i]);
      }
    }
  }

  // ---------------------------------------------------------- boss moves --
  bossSpecial(level, boss, target) {
    const roll = this.rng.next();
    if (boss.key === 'stormking' && roll < 0.4 && boss.tpl.summons) {
      const n = 2;
      this.log(`${boss.name} calls his guard!`, 'bad');
      this.sound('summon', boss.x, boss.y);
      for (let i = 0; i < n; i++) {
        const spot = level.findFree(boss.x + this.rng.int(-3, 3), boss.y + this.rng.int(-3, 3), 6);
        if (!level.walkable(spot.x, spot.y)) continue;
        const key = this.rng.pick(boss.tpl.summons);
        const m = makeMonster(key, spot.x, spot.y, level.depth);
        m.depth = level.depth;
        m.target = target.id;
        level.place(m);
        this.fx('blink', spot.x, spot.y);
      }
      return;
    }
    if (roll < 0.7) {
      // Ground slam: everything close gets hurt and shoved.
      this.fx('slam', boss.x, boss.y, { color: boss.color });
      this.sound('slam', boss.x, boss.y);
      for (const p of enemiesNear(level, boss.x, boss.y, 3, false)) {
        applyDamage(this, p, boss.rollDamage(this.rng) + 6, boss, {});
        if (!p.dead && !p.downed) {
          const dx = Math.sign(p.x - boss.x), dy = Math.sign(p.y - boss.y);
          const nx = p.x + dx * 2, ny = p.y + dy * 2;
          if (level.walkable(nx, ny, p.id)) level.moveActor(p, nx, ny);
        }
      }
      return;
    }
    // Fan of bolts.
    this.sound('shoot', boss.x, boss.y);
    const base = Math.atan2(target.y - boss.y, target.x - boss.x);
    for (const off of [-0.5, -0.25, 0, 0.25, 0.5]) {
      const a = base + off;
      this.spawnProjectile({
        kind: boss.tpl.projectile || 'bolt',
        x: boss.x, y: boss.y,
        tx: boss.x + Math.cos(a) * 10, ty: boss.y + Math.sin(a) * 10,
        ownerId: boss.id, hostile: true,
        damage: Math.round(boss.rollDamage(this.rng) * 0.7),
        onHit: boss.tpl.onHit, maxRange: 11, level,
      });
    }
  }

  // ----------------------------------------------------------------- tick -
  tick() {
    const prev = this.now;
    this.now = this.clock();
    const dt = Math.min(0.25, (this.now - prev) / 1000);

    // Only simulate levels that somebody is standing on.
    const activeDepths = new Set([...this.players.values()].map(p => p.depth));

    for (const depth of activeDepths) {
      const level = this.levels.get(depth);
      if (!level) continue;
      this.ctxDepth = depth;

      for (const p of this.playersOn(depth)) this.tickPlayer(p, level, dt);

      for (const a of [...level.actors.values()]) {
        if (a.kind !== 'monster' || a.dead) continue;
        this.tickEffects(a, dt);
        if (a.dead) continue;
        if (a.tpl.regen && a.hp < a.maxHp) a.hp = Math.min(a.maxHp, a.hp + a.tpl.regen * dt);
        if (this.now >= a.nextMoveAt || this.now >= a.nextAttackAt) thinkMonster(this, level, a);
      }

      this.stepProjectiles(level, dt);
      this.tickDescend(level);
    }
    this.ctxDepth = null;
  }

  tickPlayer(p, level, dt) {
    this.tickEffects(p, dt);

    if (p.downed) {
      if (this.now >= p.bleedUntil) this.killActor(p, null);
      return;
    }

    // Regeneration: brisk in town, a trickle in the dark.
    const inTown = level.isTown;
    const hpRate = (inTown ? 6 : 0.30 + p.stat('might') * 0.025);
    const manaRate = (inTown ? 8 : 0.60 + p.stat('wits') * 0.07);
    if (p.hp < p.maxHp) p.hp = Math.min(p.maxHp, p.hp + hpRate * dt);
    if (p.mana < p.maxMana) p.mana = Math.min(p.maxMana, p.mana + manaRate * dt);

    // Revive channel.
    if (p.reviving) {
      const target = this.players.get(p.reviving.id);
      if (!target || !target.downed || chebyshev(target.x, target.y, p.x, p.y) > 1) {
        this.cancelRevive(p);
      } else {
        target.reviveProgress = clamp(1 - (p.reviving.until - this.now) / REVIVE_MS, 0, 1);
        if (this.now >= p.reviving.until) this.finishRevive(p, target);
      }
    }

    if (this.now >= p.nextMoveAt) this.tryMove(p);
  }

  tickEffects(a, dt) {
    if (!a.effects.length) return;
    for (const e of a.effects) {
      if ((e.type === 'burn' || e.type === 'poison') && this.now >= (e.nextTick ?? 0)) {
        e.nextTick = this.now + (e.type === 'burn' ? 500 : 700);
        const src = e.src ? (this.players.get(e.src) ?? null) : null;
        applyDamage(this, a, e.dmg, src, { trueDamage: true, kind: e.type });
        this.fx(e.type === 'burn' ? 'burn' : 'poison', a.x, a.y);
        if (a.dead) return;
      }
    }
    a.expireEffects(this.now);
  }

  tickDescend(level) {
    if (!level.descendUntil) return;
    if (this.now < level.descendUntil) return;
    const to = level.descendTo;
    level.descendUntil = 0;
    level.descendTo = null;
    const travellers = this.playersOn(level.depth);
    if (!travellers.length) return;
    for (const p of travellers) {
      this.movePlayerToDepth(p, to);
      this.sound('stairs', p.x, p.y);
    }
    const dest = this.levels.get(to);
    this.log(to === TOWN_DEPTH ? 'The party climbs back into the daylight of Aldershade.'
                               : `The party descends into ${dest?.name ?? `level ${to}`}.`, 'good');
    if (dest?.isBossLevel && dest.boss && !dest.boss.dead) {
      this.log(dest.boss.tpl.title || 'Something enormous waits here.', 'bad');
    }
  }

  // ------------------------------------------------------------ snapshot --
  /** Everything `viewer` can currently see, ready to serialise. */
  snapshotFor(viewer) {
    const level = this.levels.get(viewer.depth);
    if (!level) return null;
    const actors = [];
    for (const a of level.actors.values()) {
      if (a.dead) continue;
      const i = a.y * level.w + a.x;
      const visible = viewer.fov.has(i) || a.kind === 'player';
      if (!visible) continue;
      const e = {
        id: a.id, k: a.kind, x: a.x, y: a.y, f: a.facing,
        hp: Math.ceil(a.hp), mhp: a.maxHp,
        s: a.sprite || a.cls, c: a.color, n: a.name,
      };
      if (a.kind === 'player') {
        e.dn = a.downed ? 1 : 0;
        e.lv = a.level;
        if (a.reviveProgress > 0) e.rp = Math.round(a.reviveProgress * 100);
      }
      if (a.elite) e.el = 1;
      if (a.boss) e.bo = 1;
      if (a.effects.length) e.fx = a.effects.map(x => x.type);
      actors.push(e);
    }

    const items = this.itemsJSON(level).filter(g => viewer.fov.has(g.y * level.w + g.x));

    return {
      t: this.now,
      actors,
      items,
      proj: this.projectileJSON(level),
      you: viewer.toSelfJSON(),
      party: this.playersOn(viewer.depth).map(p => ({
        id: p.id, name: p.name, cls: p.cls, lv: p.level,
        hp: Math.ceil(p.hp), mhp: p.maxHp, dn: p.downed ? 1 : 0,
        x: p.x, y: p.y,
      })),
      descend: level.descendUntil ? { at: level.descendUntil, to: level.descendTo } : null,
      depth: viewer.depth,
    };
  }
}
