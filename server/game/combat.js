import { DIRS, chebyshev } from '../../shared/constants.js';

/**
 * One attack, attacker -> target. `world` supplies rng and the event sinks
 * (floating text, sounds, log lines) so this module stays free of transport
 * concerns.
 */
export function resolveAttack(world, attacker, target, opts = {}) {
  if (!target || target.dead) return { hit: false };
  const rng = world.rng;

  const acc = (attacker.accuracy ?? 0) + (opts.accBonus ?? 0);
  const roll = rng.int(1, 20);
  const targetNumber = 10 + Math.floor((target.armor ?? 0) * 0.5);
  const crit = roll === 20;

  if (!crit && roll + acc < targetNumber) {
    world.float(target.x, target.y, 'miss', 'miss');
    world.sound('miss', target.x, target.y);
    return { hit: false };
  }

  let dmg = opts.damage ?? attacker.rollDamage(rng);
  if (opts.mult) dmg = Math.round(dmg * opts.mult);
  if (crit) dmg = Math.round(dmg * 2);

  const result = applyDamage(world, target, dmg, attacker, {
    kind: crit ? 'crit' : 'hit',
    element: opts.element,
  });

  // Weapon riders: burning, chilling, poison.
  const rider = opts.onHit ?? attacker.equipped?.weapon?.onHit ?? attacker.tpl?.onHit;
  if (rider && !target.dead && result.dealt > 0) {
    applyRider(world, target, rider, attacker);
  }

  const steal = attacker.equipped?.weapon?.lifesteal;
  if (steal && result.dealt > 0 && attacker.hp < attacker.maxHp) {
    const healed = Math.max(1, Math.round(result.dealt * steal));
    attacker.hp = Math.min(attacker.maxHp, attacker.hp + healed);
    world.float(attacker.x, attacker.y, `+${healed}`, 'heal');
  }

  const kb = opts.knockback ?? attacker.tpl?.knockback ?? 0;
  if (kb && !target.dead) knockback(world, attacker, target, kb);

  world.sound(crit ? 'crit' : (attacker.kind === 'player' ? 'hit' : 'hurt'), target.x, target.y);
  return { hit: true, crit, ...result };
}

export function applyRider(world, target, rider, source) {
  const now = world.now;
  if (rider.type === 'burn') {
    target.addEffect('burn', rider.ms, { dmg: rider.dmg, nextTick: now + 500, src: source?.id }, now);
  } else if (rider.type === 'poison') {
    target.addEffect('poison', rider.ms, { dmg: rider.dmg, nextTick: now + 700, src: source?.id }, now);
  } else if (rider.type === 'chill') {
    target.addEffect('chill', rider.ms, { slow: rider.slow ?? 0.5 }, now);
  } else if (rider.type === 'snare') {
    target.addEffect('snare', rider.ms, {}, now);
  }
}

/** Damage after mitigation. Returns { dealt, killed }. */
export function applyDamage(world, target, amount, source, opts = {}) {
  if (target.dead) return { dealt: 0, killed: false };

  let dmg = amount;
  if (!opts.trueDamage) {
    dmg -= Math.floor((target.armor ?? 0) / 3);
    if (target.hasEffect('bulwark')) dmg = Math.round(dmg * 0.5);
    if (target.hasEffect('ward')) dmg = Math.round(dmg * 0.5);
    dmg = Math.max(1, dmg);
  }

  target.hp -= dmg;
  world.float(target.x, target.y, String(dmg),
    opts.kind === 'crit' ? 'crit' : (target.kind === 'player' ? 'playerhurt' : 'damage'));

  // Anything that gets hit turns on its attacker.
  if (target.kind === 'monster' && source && source.kind === 'player') {
    target.target = source.id;
    target.lastSeen = { x: source.x, y: source.y };
  }

  if (target.hp <= 0) {
    world.killActor(target, source);
    return { dealt: dmg, killed: true };
  }
  return { dealt: dmg, killed: false };
}

export function healActor(world, target, amount) {
  if (target.dead || target.hp >= target.maxHp) return 0;
  const healed = Math.min(amount, target.maxHp - target.hp);
  target.hp += healed;
  world.float(target.x, target.y, `+${healed}`, 'heal');
  return healed;
}

/** Shove `target` directly away from `from` by up to `tiles` squares. */
export function knockback(world, from, target, tiles) {
  const level = world.levelOf(target);
  if (!level) return;
  let dx = Math.sign(target.x - from.x);
  let dy = Math.sign(target.y - from.y);
  if (dx === 0 && dy === 0) return;
  for (let i = 0; i < tiles; i++) {
    const nx = target.x + dx, ny = target.y + dy;
    if (!level.walkable(nx, ny, target.id)) break;
    level.moveActor(target, nx, ny);
  }
}

/** Every hostile actor within `radius` tiles of (x, y). */
export function enemiesNear(level, x, y, radius, forPlayer = true) {
  const out = [];
  for (const a of level.actors.values()) {
    if (a.dead) continue;
    if (forPlayer && a.kind !== 'monster') continue;
    if (!forPlayer && a.kind !== 'player') continue;
    if (!forPlayer && a.downed) continue;
    if (chebyshev(a.x, a.y, x, y) <= radius) out.push(a);
  }
  return out;
}

/** Facing index (into DIRS) that best matches a delta. */
export function dirIndex(dx, dy) {
  if (dx === 0 && dy === 0) return 4;
  let best = 0, bestDot = -Infinity;
  const len = Math.hypot(dx, dy);
  const ux = dx / len, uy = dy / len;
  for (let i = 0; i < DIRS.length; i++) {
    const [ex, ey] = DIRS[i];
    const el = Math.hypot(ex, ey);
    const dot = (ex / el) * ux + (ey / el) * uy;
    if (dot > bestDot) { bestDot = dot; best = i; }
  }
  return best;
}
