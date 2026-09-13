import { T, isSolid } from '../../shared/constants.js';
import { RNG } from '../../shared/rng.js';

export class Level {
  constructor(w, h, depth, name) {
    this.w = w; this.h = h;
    this.depth = depth;
    this.name = name;
    this.tiles = new Uint8Array(w * h);   // terrain
    this.rooms = [];
    this.upAt = { x: 1, y: 1 };
    this.downAt = null;
    this.spawns = [];                     // monster spawn points chosen at gen time
    this.lootSpots = [];
    this.actors = new Map();              // id -> actor (players, monsters, npcs)
    this.items = new Map();               // id -> ground item
    this.projectiles = [];
    this.effects = [];                    // transient visuals (explosions, etc.)
    this.blocked = new Int32Array(w * h).fill(0); // actor occupancy, id or 0
  }

  idx(x, y) { return y * this.w + x; }
  inBounds(x, y) { return x >= 0 && y >= 0 && x < this.w && y < this.h; }
  get(x, y) { return this.inBounds(x, y) ? this.tiles[y * this.w + x] : T.VOID; }
  set(x, y, t) { if (this.inBounds(x, y)) this.tiles[y * this.w + x] = t; }

  /** Terrain-only passability. */
  passable(x, y) { return this.inBounds(x, y) && !isSolid(this.tiles[y * this.w + x]); }

  /** Passability including other creatures. `ignoreId` lets an actor ignore itself. */
  walkable(x, y, ignoreId = 0) {
    if (!this.passable(x, y)) return false;
    const occ = this.blocked[y * this.w + x];
    return occ === 0 || occ === ignoreId;
  }

  occupant(x, y) {
    if (!this.inBounds(x, y)) return null;
    const id = this.blocked[y * this.w + x];
    return id ? this.actors.get(id) || null : null;
  }

  place(actor) {
    this.actors.set(actor.id, actor);
    this.blocked[actor.y * this.w + actor.x] = actor.id;
  }

  remove(actor) {
    this.actors.delete(actor.id);
    const i = actor.y * this.w + actor.x;
    if (this.blocked[i] === actor.id) this.blocked[i] = 0;
  }

  moveActor(actor, nx, ny) {
    const oi = actor.y * this.w + actor.x;
    if (this.blocked[oi] === actor.id) this.blocked[oi] = 0;
    actor.px = actor.x; actor.py = actor.y;
    actor.x = nx; actor.y = ny;
    this.blocked[ny * this.w + nx] = actor.id;
  }

  /**
   * Nearest tile with open *terrain*, ignoring who is standing on it.
   * Loot uses this so a dropped item lands under your own feet.
   */
  findFloor(x, y, maxR = 14) {
    if (this.passable(x, y)) return { x, y };
    for (let r = 1; r <= maxR; r++) {
      for (let dy = -r; dy <= r; dy++) {
        for (let dx = -r; dx <= r; dx++) {
          if (Math.max(Math.abs(dx), Math.abs(dy)) !== r) continue;
          const nx = x + dx, ny = y + dy;
          if (this.passable(nx, ny)) return { x: nx, y: ny };
        }
      }
    }
    return { x, y };
  }

  /** Nearest walkable tile to (x,y), searched in expanding rings. */
  findFree(x, y, maxR = 14) {
    if (this.walkable(x, y)) return { x, y };
    for (let r = 1; r <= maxR; r++) {
      for (let dy = -r; dy <= r; dy++) {
        for (let dx = -r; dx <= r; dx++) {
          if (Math.max(Math.abs(dx), Math.abs(dy)) !== r) continue;
          const nx = x + dx, ny = y + dy;
          if (this.walkable(nx, ny)) return { x: nx, y: ny };
        }
      }
    }
    return { x, y };
  }
}

// --------------------------------------------------------------------------
//  Dungeon generation: scattered rooms, corridors, then a decoration pass.
// --------------------------------------------------------------------------

const THEMES = [
  { name: 'the Cellars',       minD: 1,  maxD: 3,  water: 0.15, rubble: 0.2 },
  { name: 'the Flooded Vaults', minD: 3,  maxD: 7,  water: 0.6,  rubble: 0.2 },
  { name: 'the Bone Gallery',  minD: 6,  maxD: 11, water: 0.1,  rubble: 0.5 },
  { name: 'the Deep Warrens',  minD: 10, maxD: 15, water: 0.25, rubble: 0.4 },
  { name: 'the Stormworks',    minD: 14, maxD: 20, water: 0.2,  rubble: 0.3 },
];

function themeFor(depth, rng) {
  const opts = THEMES.filter(t => depth >= t.minD && depth <= t.maxD);
  return opts.length ? rng.pick(opts) : THEMES[THEMES.length - 1];
}

function overlaps(a, b, pad = 1) {
  return a.x - pad < b.x + b.w && a.x + a.w + pad > b.x &&
         a.y - pad < b.y + b.h && a.y + a.h + pad > b.y;
}

function carveRoom(level, r) {
  for (let y = r.y; y < r.y + r.h; y++) {
    for (let x = r.x; x < r.x + r.w; x++) level.set(x, y, T.FLOOR);
  }
}

function carveCorridor(level, ax, ay, bx, by, rng) {
  let x = ax, y = ay;
  const horizontalFirst = rng.chance(0.5);
  const stepX = () => { while (x !== bx) { x += x < bx ? 1 : -1; level.set(x, y, T.FLOOR); } };
  const stepY = () => { while (y !== by) { y += y < by ? 1 : -1; level.set(x, y, T.FLOOR); } };
  level.set(x, y, T.FLOOR);
  if (horizontalFirst) { stepX(); stepY(); } else { stepY(); stepX(); }
}

/** Wrap every floor tile that touches nothing with a wall so the map is sealed. */
function wallify(level) {
  for (let y = 0; y < level.h; y++) {
    for (let x = 0; x < level.w; x++) {
      if (level.get(x, y) !== T.VOID) continue;
      let touchesFloor = false;
      for (let dy = -1; dy <= 1 && !touchesFloor; dy++) {
        for (let dx = -1; dx <= 1; dx++) {
          const t = level.get(x + dx, y + dy);
          if (t !== T.VOID && t !== T.WALL) { touchesFloor = true; break; }
        }
      }
      if (touchesFloor) level.set(x, y, T.WALL);
    }
  }
}

/** A corridor tile pinched between two walls at a room edge becomes a door. */
function addDoors(level, rng) {
  for (const room of level.rooms) {
    const edges = [];
    for (let x = room.x - 1; x <= room.x + room.w; x++) {
      edges.push([x, room.y - 1], [x, room.y + room.h]);
    }
    for (let y = room.y - 1; y <= room.y + room.h; y++) {
      edges.push([room.x - 1, y], [room.x + room.w, y]);
    }
    for (const [x, y] of edges) {
      if (level.get(x, y) !== T.FLOOR) continue;
      const horiz = level.get(x - 1, y) === T.WALL && level.get(x + 1, y) === T.WALL;
      const vert = level.get(x, y - 1) === T.WALL && level.get(x, y + 1) === T.WALL;
      if ((horiz || vert) && rng.chance(0.72)) level.set(x, y, T.DOOR);
    }
  }
}

function decorate(level, theme, rng) {
  for (const room of level.rooms) {
    if (room.special) continue;
    const roll = rng.next();
    // Shallow water pool.
    if (roll < theme.water * 0.35 && room.w > 4 && room.h > 4) {
      const cx = room.x + (room.w >> 1), cy = room.y + (room.h >> 1);
      const rad = rng.int(1, Math.min(room.w, room.h) >> 1);
      for (let y = cy - rad; y <= cy + rad; y++) {
        for (let x = cx - rad; x <= cx + rad; x++) {
          if (level.get(x, y) === T.FLOOR && (x - cx) ** 2 + (y - cy) ** 2 <= rad * rad) {
            level.set(x, y, T.WATER);
          }
        }
      }
    } else if (roll < theme.water * 0.35 + 0.18 && room.w >= 5 && room.h >= 5) {
      // Pillars, inset one tile from the wall. The centre tile stays clear:
      // stairs, altars and boss spawns are all anchored there.
      for (let y = room.y + 1; y < room.y + room.h - 1; y += 2) {
        for (let x = room.x + 1; x < room.x + room.w - 1; x += 2) {
          if (x === room.cx && y === room.cy) continue;
          if (rng.chance(0.6)) level.set(x, y, T.WALL);
        }
      }
    }
    // Scattered rubble.
    if (rng.chance(theme.rubble)) {
      const n = rng.int(1, 5);
      for (let i = 0; i < n; i++) {
        const x = rng.int(room.x, room.x + room.w - 1);
        const y = rng.int(room.y, room.y + room.h - 1);
        if (level.get(x, y) === T.FLOOR) level.set(x, y, T.RUBBLE);
      }
    }
  }
}

/** Flood fill from a start tile; returns the set of reachable floor indices. */
export function reachable(level, sx, sy) {
  const seen = new Set();
  const stack = [[sx, sy]];
  seen.add(level.idx(sx, sy));
  while (stack.length) {
    const [x, y] = stack.pop();
    for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
      const nx = x + dx, ny = y + dy;
      if (!level.passable(nx, ny)) continue;
      const i = level.idx(nx, ny);
      if (seen.has(i)) continue;
      seen.add(i);
      stack.push([nx, ny]);
    }
  }
  return seen;
}

/** Wall off anything the player could never reach, so no loot is stranded. */
function sealUnreachable(level, sx, sy) {
  const ok = reachable(level, sx, sy);
  for (let y = 0; y < level.h; y++) {
    for (let x = 0; x < level.w; x++) {
      const i = level.idx(x, y);
      if (level.passable(x, y) && !ok.has(i)) level.tiles[i] = T.WALL;
    }
  }
  return ok;
}

export function generateDungeon(depth, seed) {
  const rng = new RNG(seed ^ (depth * 0x9e3779b9));
  const theme = themeFor(depth, rng);
  // Levels grow slowly with depth so the early game is not a hike.
  const w = Math.min(88, 46 + Math.round(depth * 1.7));
  const h = Math.min(58, 32 + Math.round(depth * 0.9));
  const level = new Level(w, h, depth, `${theme.name}, level ${depth}`);
  level.theme = theme.name;

  // --- rooms ---------------------------------------------------------------
  const target = 10 + Math.floor(depth / 2) + rng.int(0, 4);
  let attempts = 0;
  while (level.rooms.length < target && attempts++ < 1200) {
    const rw = rng.int(4, 11), rh = rng.int(4, 8);
    const room = {
      x: rng.int(2, w - rw - 3),
      y: rng.int(2, h - rh - 3),
      w: rw, h: rh,
    };
    if (level.rooms.some(o => overlaps(room, o, 2))) continue;
    room.cx = room.x + (rw >> 1);
    room.cy = room.y + (rh >> 1);
    level.rooms.push(room);
    carveRoom(level, room);
  }

  if (level.rooms.length < 2) return generateDungeon(depth, seed + 1);

  // --- corridors: spanning tree, then a few loops so it is not a pure maze --
  const connected = [level.rooms[0]];
  const pending = level.rooms.slice(1);
  while (pending.length) {
    let best = null, bestD = Infinity, bestFrom = null;
    for (const a of connected) {
      for (const b of pending) {
        const d = (a.cx - b.cx) ** 2 + (a.cy - b.cy) ** 2;
        if (d < bestD) { bestD = d; best = b; bestFrom = a; }
      }
    }
    carveCorridor(level, bestFrom.cx, bestFrom.cy, best.cx, best.cy, rng);
    connected.push(best);
    pending.splice(pending.indexOf(best), 1);
  }
  const loops = 1 + Math.floor(level.rooms.length / 5);
  for (let i = 0; i < loops; i++) {
    const a = rng.pick(level.rooms), b = rng.pick(level.rooms);
    if (a !== b) carveCorridor(level, a.cx, a.cy, b.cx, b.cy, rng);
  }

  // --- a guarded treasure room ---------------------------------------------
  if (depth >= 2 && rng.chance(0.45)) {
    const vault = level.rooms[rng.int(1, level.rooms.length - 1)];
    vault.special = 'vault';
  }

  decorate(level, theme, rng);
  addDoors(level, rng);
  wallify(level);

  // --- stairs --------------------------------------------------------------
  const first = level.rooms[0];
  level.upAt = { x: first.cx, y: first.cy };
  level.set(first.cx, first.cy, T.STAIRS_UP);

  let far = level.rooms[1], farD = -1;
  for (const r of level.rooms.slice(1)) {
    const d = (r.cx - first.cx) ** 2 + (r.cy - first.cy) ** 2;
    if (d > farD) { farD = d; far = r; }
  }
  if (depth < 20) {
    level.downAt = { x: far.cx, y: far.cy };
    level.set(far.cx, far.cy, T.STAIRS_DOWN);
  } else {
    level.set(far.cx, far.cy, T.ALTAR);       // the bottom of the keep
    level.altarAt = { x: far.cx, y: far.cy };
  }
  far.special = far.special || 'end';

  const ok = sealUnreachable(level, first.cx, first.cy);

  // --- spawn + loot points -------------------------------------------------
  for (const room of level.rooms) {
    if (room === first) continue;               // never ambush the arrival room
    const density = room.special === 'vault' ? 0.09 : 0.035;
    const count = Math.max(1, Math.round(room.w * room.h * density));
    for (let i = 0; i < count; i++) {
      const x = rng.int(room.x, room.x + room.w - 1);
      const y = rng.int(room.y, room.y + room.h - 1);
      if (level.passable(x, y) && ok.has(level.idx(x, y))) {
        level.spawns.push({ x, y, elite: room.special === 'vault' });
      }
    }
    const lootCount = room.special === 'vault' ? rng.int(3, 5) : (rng.chance(0.55) ? rng.int(1, 2) : 0);
    for (let i = 0; i < lootCount; i++) {
      const x = rng.int(room.x, room.x + room.w - 1);
      const y = rng.int(room.y, room.y + room.h - 1);
      if (level.passable(x, y) && ok.has(level.idx(x, y))) {
        level.lootSpots.push({ x, y, rich: room.special === 'vault' });
      }
    }
  }

  level.isBossLevel = depth === 10 || depth === 20;
  if (level.isBossLevel) level.bossRoom = far;
  return level;
}

// --------------------------------------------------------------------------
//  The town: a fixed, friendly layout. This is where the party starts, sells
//  loot, heals up, and regroups after a wipe.
// --------------------------------------------------------------------------

function building(level, x, y, w, h, doorSide, doorOffset) {
  for (let j = y; j < y + h; j++) {
    for (let i = x; i < x + w; i++) {
      const edge = i === x || j === y || i === x + w - 1 || j === y + h - 1;
      level.set(i, j, edge ? T.WALL : T.SHOP_FLOOR);
    }
  }
  let door;
  if (doorSide === 'south') door = { x: x + doorOffset, y: y + h - 1 };
  else if (doorSide === 'north') door = { x: x + doorOffset, y };
  else if (doorSide === 'west') door = { x, y: y + doorOffset };
  else door = { x: x + w - 1, y: y + doorOffset };
  level.set(door.x, door.y, T.DOOR_OPEN);
  return door;
}

export function generateTown(seed = 1) {
  const rng = new RNG(seed ^ 0xbeef);
  const w = 48, h = 34;
  const level = new Level(w, h, 0, 'Aldershade');
  level.isTown = true;
  level.theme = 'town';

  // Grass field inside a ring of trees.
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const border = x < 2 || y < 2 || x >= w - 2 || y >= h - 2;
      level.set(x, y, border ? T.TREE : T.GRASS);
    }
  }
  // Ragged treeline so the edge does not look ruled with a pencil.
  for (let i = 0; i < 90; i++) {
    const x = rng.int(2, w - 3), y = rng.int(2, h - 3);
    const edgeDist = Math.min(x - 2, y - 2, w - 3 - x, h - 3 - y);
    if (edgeDist <= 1 && rng.chance(0.7)) level.set(x, y, T.TREE);
  }

  // Roads: one north-south to the keep gate, one east-west through the square.
  const roadX = w >> 1, roadY = h >> 1;
  for (let y = 3; y < h - 3; y++) { level.set(roadX, y, T.ROAD); level.set(roadX + 1, y, T.ROAD); }
  for (let x = 4; x < w - 4; x++) { level.set(x, roadY, T.ROAD); level.set(x, roadY + 1, T.ROAD); }

  // Town square: a paved plaza with a well at its heart.
  for (let y = roadY - 3; y <= roadY + 4; y++) {
    for (let x = roadX - 4; x <= roadX + 5; x++) level.set(x, y, T.ROAD);
  }
  level.set(roadX, roadY, T.WATER);
  level.set(roadX + 1, roadY, T.WATER);
  level.set(roadX, roadY + 1, T.WATER);
  level.set(roadX + 1, roadY + 1, T.WATER);

  // The keep gate at the top of the road: the way down.
  level.downAt = { x: roadX, y: 4 };
  level.set(roadX, 4, T.STAIRS_DOWN);
  level.set(roadX + 1, 4, T.ROAD);
  for (let x = roadX - 4; x <= roadX + 5; x++) {
    level.set(x, 2, T.WALL);
    level.set(x, 3, x === roadX || x === roadX + 1 ? T.ROAD : T.WALL);
  }

  // Shops. Each door faces the road so nobody gets lost looking for the smith.
  const smith = building(level, 6, 8, 10, 7, 'east', 3);
  const apoth = building(level, 6, 20, 10, 7, 'east', 3);
  const temple = building(level, w - 17, 12, 11, 9, 'west', 4);

  // Paths from each shop door to the main road.
  for (let x = smith.x + 1; x <= roadX; x++) level.set(x, smith.y, T.ROAD);
  for (let x = apoth.x + 1; x <= roadX; x++) level.set(x, apoth.y, T.ROAD);
  for (let x = temple.x - 1; x >= roadX; x--) level.set(x, temple.y, T.ROAD);

  level.npcs = [
    { kind: 'smith',  x: 10, y: 11,      name: 'Doran the Smith',   shop: 'smith' },
    { kind: 'apoth',  x: 10, y: 23,      name: 'Wren the Apothecary', shop: 'apoth' },
    { kind: 'priest', x: w - 12, y: 16,  name: 'Sister Halli',      shop: 'temple' },
  ];

  level.spawnPoint = { x: roadX, y: roadY + 4 };
  level.upAt = level.spawnPoint;

  // Decorative touches around the plaza.
  for (const [x, y] of [[roadX - 6, roadY - 5], [roadX + 7, roadY - 5], [roadX - 6, roadY + 6], [roadX + 7, roadY + 6]]) {
    if (level.get(x, y) === T.GRASS) level.set(x, y, T.TREE);
  }
  return level;
}
