import { T, DIRS, chebyshev } from '../../shared/constants.js';
import { hasLOS } from '../../shared/fov.js';
import { resolveAttack, dirIndex } from './combat.js';

// ---------------------------------------------------------------- pathing --

class MinHeap {
  constructor() { this.a = []; }
  get size() { return this.a.length; }
  push(node) {
    const a = this.a;
    a.push(node);
    let i = a.length - 1;
    while (i > 0) {
      const p = (i - 1) >> 1;
      if (a[p].f <= a[i].f) break;
      [a[p], a[i]] = [a[i], a[p]];
      i = p;
    }
  }
  pop() {
    const a = this.a;
    const top = a[0];
    const last = a.pop();
    if (a.length) {
      a[0] = last;
      let i = 0;
      for (;;) {
        const l = i * 2 + 1, r = l + 1;
        let m = i;
        if (l < a.length && a[l].f < a[m].f) m = l;
        if (r < a.length && a[r].f < a[m].f) m = r;
        if (m === i) break;
        [a[m], a[i]] = [a[i], a[m]];
        i = m;
      }
    }
    return top;
  }
}

/**
 * A* from (sx,sy) to (tx,ty). Closed doors are passable at a small extra cost
 * so monsters will route through them and shoulder them open on arrival.
 * Returns an array of [x,y] steps (excluding the start), or null.
 */
export function findPath(level, sx, sy, tx, ty, opts = {}) {
  const maxNodes = opts.maxNodes ?? 900;
  const ignoreId = opts.ignoreId ?? 0;
  const w = level.w;
  const start = sy * w + sx, goal = ty * w + tx;
  if (start === goal) return [];

  const open = new MinHeap();
  const gScore = new Map([[start, 0]]);
  const cameFrom = new Map();
  const closed = new Set();
  const h = (x, y) => Math.max(Math.abs(x - tx), Math.abs(y - ty));
  open.push({ i: start, x: sx, y: sy, g: 0, f: h(sx, sy) });

  let expanded = 0;
  while (open.size && expanded < maxNodes) {
    const cur = open.pop();
    if (closed.has(cur.i)) continue;
    closed.add(cur.i);
    expanded++;

    if (cur.i === goal) {
      const path = [];
      let i = goal;
      while (i !== start) {
        const [px, py] = [i % w, (i / w) | 0];
        path.push([px, py]);
        i = cameFrom.get(i);
        if (i === undefined) return null;
      }
      return path.reverse();
    }

    for (const [dx, dy] of DIRS) {
      const nx = cur.x + dx, ny = cur.y + dy;
      if (!level.inBounds(nx, ny)) continue;
      const ni = ny * w + nx;
      if (closed.has(ni)) continue;

      const tile = level.tiles[ni];
      const isGoal = ni === goal;
      let cost = dx && dy ? 1.414 : 1;
      if (tile === T.WALL || tile === T.VOID || tile === T.TREE) continue;
      if (tile === T.DOOR) cost += 1.5;                       // shoulder it open
      if (tile === T.WATER || tile === T.RUBBLE) cost += 0.8;  // slow going
      // Don't cut a diagonal through a wall corner.
      if (dx && dy) {
        const a = level.tiles[cur.y * w + nx], b = level.tiles[ny * w + cur.x];
        const blockedA = a === T.WALL || a === T.VOID || a === T.TREE || a === T.DOOR;
        const blockedB = b === T.WALL || b === T.VOID || b === T.TREE || b === T.DOOR;
        if (blockedA && blockedB) continue;
      }
      const occ = level.blocked[ni];
      if (occ && occ !== ignoreId && !isGoal) cost += 4;       // route around crowds

      const g = cur.g + cost;
      if (g < (gScore.get(ni) ?? Infinity)) {
        gScore.set(ni, g);
        cameFrom.set(ni, cur.i);
        open.push({ i: ni, x: nx, y: ny, g, f: g + h(nx, ny) });
      }
    }
  }
  return null;
}

// -------------------------------------------------------------- behaviour --

function acquireTarget(world, level, m) {
  let best = null, bestD = Infinity;
  for (const a of level.actors.values()) {
    if (a.kind !== 'player' || a.dead || a.downed) continue;
    const d = chebyshev(a.x, a.y, m.x, m.y);
    if (d > m.aggro) continue;
    if (d < bestD && hasLOS(level, m.x, m.y, a.x, a.y, m.aggro + 2)) {
      bestD = d; best = a;
    }
  }
  return best;
}

function stepToward(world, level, m, tx, ty) {
  const now = world.now;
  // Reuse an existing path while it still points at the target.
  const stale = !m.path || !m.path.length || now - m.pathAt > 900 ||
    !m.pathGoal || m.pathGoal[0] !== tx || m.pathGoal[1] !== ty;

  if (stale) {
    m.path = findPath(level, m.x, m.y, tx, ty, { ignoreId: m.id });
    m.pathAt = now;
    m.pathGoal = [tx, ty];
  }

  let step = m.path && m.path.length ? m.path[0] : null;
  // Fall back to a greedy shove in the right direction if A* gave up.
  if (!step) {
    const dx = Math.sign(tx - m.x), dy = Math.sign(ty - m.y);
    const cands = [[dx, dy], [dx, 0], [0, dy]].filter(([a, b]) => a || b);
    for (const [a, b] of cands) {
      if (level.walkable(m.x + a, m.y + b, m.id)) { step = [m.x + a, m.y + b]; break; }
    }
    if (!step) return false;
  }

  const [nx, ny] = step;
  const tile = level.get(nx, ny);

  if (tile === T.DOOR) {                       // open it; that is this turn's action
    world.setTile(level, nx, ny, T.DOOR_OPEN);
    world.sound('door', nx, ny);
    m.nextMoveAt = world.now + m.moveTime();
    return true;
  }
  if (!level.walkable(nx, ny, m.id)) {
    m.path = null;                             // someone is in the way; re-plan
    return false;
  }

  m.facing = dirIndex(nx - m.x, ny - m.y);
  level.moveActor(m, nx, ny);
  if (m.path) m.path.shift();
  const slow = tile === T.WATER || tile === T.RUBBLE;
  m.nextMoveAt = world.now + m.moveTime(slow);
  return true;
}

function stepAwayFrom(world, level, m, tx, ty) {
  const dx = Math.sign(m.x - tx), dy = Math.sign(m.y - ty);
  const cands = world.rng.shuffle([[dx, dy], [dx, 0], [0, dy], [dy, dx], [-dy, -dx]]);
  for (const [a, b] of cands) {
    if ((a || b) && level.walkable(m.x + a, m.y + b, m.id)) {
      m.facing = dirIndex(a, b);
      level.moveActor(m, m.x + a, m.y + b);
      m.nextMoveAt = world.now + m.moveTime();
      return true;
    }
  }
  return false;
}

function wander(world, level, m) {
  const rng = world.rng;
  if (!m.wanderDir || rng.chance(0.25)) m.wanderDir = rng.pick(DIRS);
  const [dx, dy] = m.wanderDir;
  if (level.walkable(m.x + dx, m.y + dy, m.id)) {
    m.facing = dirIndex(dx, dy);
    level.moveActor(m, m.x + dx, m.y + dy);
  } else {
    m.wanderDir = null;
  }
  // Idle monsters amble; they should not look like they are on patrol.
  m.nextMoveAt = world.now + m.moveTime() * 2.2;
}

/** One decision for one monster. Called only when the monster is off cooldown. */
export function thinkMonster(world, level, m) {
  const now = world.now;
  if (m.dead) return;

  if (m.hasEffect('snare')) { m.nextMoveAt = now + 200; return; }

  let target = m.target ? level.actors.get(m.target) : null;
  if (target && (target.dead || target.downed || target.kind !== 'player')) target = null;

  if (!target) {
    const found = acquireTarget(world, level, m);
    if (found) {
      m.target = found.id;
      target = found;
      if (!m.noticed) {
        m.noticed = true;
        world.sound('notice', m.x, m.y);
      }
    }
  }

  if (!target) {
    // Head for where the target was last seen before giving up entirely.
    if (m.lastSeen) {
      if (chebyshev(m.x, m.y, m.lastSeen.x, m.lastSeen.y) <= 1) m.lastSeen = null;
      else if (stepToward(world, level, m, m.lastSeen.x, m.lastSeen.y)) return;
    }
    m.target = null;
    m.noticed = false;
    wander(world, level, m);
    return;
  }

  const d = chebyshev(m.x, m.y, target.x, target.y);
  const los = hasLOS(level, m.x, m.y, target.x, target.y, 24);
  if (los) m.lastSeen = { x: target.x, y: target.y };
  else if (d > m.aggro + 6) { m.target = null; }

  // Wounded cowards break and run.
  if (m.ai === 'skittish' && m.hp < m.maxHp * 0.35 && d <= 5) {
    if (stepAwayFrom(world, level, m, target.x, target.y)) return;
  }

  // --- attack ------------------------------------------------------------
  if (d <= 1 && now >= m.nextAttackAt) {
    m.facing = dirIndex(target.x - m.x, target.y - m.y);
    m.nextAttackAt = now + m.atkSpeed;
    m.nextMoveAt = Math.max(m.nextMoveAt, now + Math.min(220, m.atkSpeed * 0.5));
    world.sound('swing', m.x, m.y);
    resolveAttack(world, m, target);
    return;
  }

  const wantsRange = m.ai === 'ranged' || m.ai === 'caster' || (m.ai === 'boss' && d > 1);
  if (wantsRange && los && d <= m.range && now >= m.nextAttackAt) {
    m.facing = dirIndex(target.x - m.x, target.y - m.y);
    m.nextAttackAt = now + m.atkSpeed;
    world.spawnProjectile({
      kind: m.tpl.projectile || 'bolt',
      x: m.x, y: m.y, tx: target.x, ty: target.y,
      ownerId: m.id, hostile: true,
      damage: m.rollDamage(world.rng),
      onHit: m.tpl.onHit,
      level,
    });
    world.sound('shoot', m.x, m.y);
    // Shooters shuffle to keep their distance rather than closing.
    if (d < 3) stepAwayFrom(world, level, m, target.x, target.y);
    else m.nextMoveAt = now + m.moveTime();
    return;
  }

  // --- boss specials -------------------------------------------------------
  if (m.ai === 'boss' && now >= m.nextSpecialAt && d <= 8) {
    m.nextSpecialAt = now + 7000;
    world.bossSpecial(level, m, target);
    return;
  }

  // Adjacent with the swing still on cooldown: hold the line, don't wander off.
  if (d <= 1 && m.ai !== 'skittish') { m.nextMoveAt = Math.max(m.nextMoveAt, now + 120); return; }

  // --- movement ------------------------------------------------------------
  if (now < m.nextMoveAt) return;

  if (m.ai === 'erratic' && world.rng.chance(0.35)) { wander(world, level, m); return; }

  // Shooters hold their ground at a comfortable distance.
  if (wantsRange && los && d >= 3 && d <= m.range) { m.nextMoveAt = now + m.moveTime(); return; }

  const goal = los ? target : m.lastSeen;
  if (goal) stepToward(world, level, m, goal.x, goal.y);
  else wander(world, level, m);
}
