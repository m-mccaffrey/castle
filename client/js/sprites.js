// All artwork in Stormhold is drawn here, in code, at build-up time: there are
// no image files to ship. Every creature, item and tile is composed from
// rectangles on a small pixel grid, then upscaled with smoothing off so it
// stays crisp. Original designs throughout.

export const GRID = 16;      // authoring grid for creatures and items
export const TILE_PX = 32;   // on-screen size of one map tile

const cache = new Map();

function canvas(w, h) {
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  const g = c.getContext('2d');
  g.imageSmoothingEnabled = false;
  return { c, g };
}

/** A tiny pixel-painting surface. */
class Pix {
  constructor(size = GRID) {
    const { c, g } = canvas(size, size);
    this.size = size;
    this.c = c;
    this.g = g;
  }
  px(x, y, col) { this.g.fillStyle = col; this.g.fillRect(x | 0, y | 0, 1, 1); }
  rect(x, y, w, h, col) { this.g.fillStyle = col; this.g.fillRect(x | 0, y | 0, w | 0, h | 0); }
  /** Filled ellipse, snapped to the pixel grid. */
  oval(cx, cy, rx, ry, col) {
    this.g.fillStyle = col;
    for (let y = Math.floor(cy - ry); y <= Math.ceil(cy + ry); y++) {
      for (let x = Math.floor(cx - rx); x <= Math.ceil(cx + rx); x++) {
        const dx = (x + 0.5 - cx) / rx, dy = (y + 0.5 - cy) / ry;
        if (dx * dx + dy * dy <= 1) this.g.fillRect(x, y, 1, 1);
      }
    }
  }
  line(x0, y0, x1, y1, col) {
    let dx = Math.abs(x1 - x0), dy = Math.abs(y1 - y0);
    const sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1;
    let err = dx - dy, x = x0, y = y0;
    for (let i = 0; i < 64; i++) {
      this.px(x, y, col);
      if (x === x1 && y === y1) break;
      const e2 = 2 * err;
      if (e2 > -dy) { err -= dy; x += sx; }
      if (e2 < dx) { err += dx; y += sy; }
    }
  }
  /** Trace a dark border around everything drawn so far. */
  outline(col = 'rgba(8,6,12,0.85)') {
    const img = this.g.getImageData(0, 0, this.size, this.size);
    const a = img.data;
    const solid = (x, y) => x >= 0 && y >= 0 && x < this.size && y < this.size &&
      a[(y * this.size + x) * 4 + 3] > 24;
    const edges = [];
    for (let y = 0; y < this.size; y++) {
      for (let x = 0; x < this.size; x++) {
        if (solid(x, y)) continue;
        if (solid(x - 1, y) || solid(x + 1, y) || solid(x, y - 1) || solid(x, y + 1)) edges.push([x, y]);
      }
    }
    for (const [x, y] of edges) this.px(x, y, col);
    return this;
  }
  /** Upscale to the final sprite size, nearest-neighbour. */
  bake(scale = TILE_PX / GRID) {
    const out = canvas(this.size * scale, this.size * scale);
    out.g.imageSmoothingEnabled = false;
    out.g.drawImage(this.c, 0, 0, this.size * scale, this.size * scale);
    return out.c;
  }
}

// --------------------------------------------------------------- helpers ---
function shade(hex, amount) {
  const m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  if (!m) return hex;
  const adj = (v) => Math.max(0, Math.min(255, Math.round(parseInt(v, 16) * amount)));
  const h = (v) => adj(v).toString(16).padStart(2, '0');
  return `#${h(m[1])}${h(m[2])}${h(m[3])}`;
}

const STEEL = '#b8c0cc';
const STEEL_D = '#7a828e';
const WOOD = '#8a6038';
const BONE = '#e4dcc4';

/** Weapon held in the right hand. */
function drawWeapon(p, kind, accent) {
  switch (kind) {
    case 'sword':
      p.rect(13, 3, 1, 7, STEEL);
      p.rect(12, 9, 3, 1, shade(WOOD, 0.9));
      p.rect(13, 10, 1, 2, WOOD);
      break;
    case 'axe':
      p.rect(13, 5, 1, 7, WOOD);
      p.rect(11, 3, 3, 3, STEEL);
      p.rect(11, 3, 1, 3, STEEL_D);
      break;
    case 'mace':
      p.rect(13, 6, 1, 6, WOOD);
      p.oval(13.5, 4.5, 2, 2, STEEL);
      break;
    case 'staff':
      p.rect(13, 2, 1, 11, WOOD);
      p.oval(13.5, 2, 1.8, 1.8, accent);
      p.px(13, 1, '#fff8e0');
      break;
    case 'bow':
      p.line(13, 3, 13, 11, WOOD);
      p.px(12, 4, WOOD); p.px(12, 10, WOOD);
      p.line(12, 4, 12, 10, '#e8e0c8');
      break;
    case 'claw':
      p.px(12, 10, BONE); p.px(13, 11, BONE); p.px(14, 10, BONE);
      break;
    case 'spear':
      p.rect(13, 2, 1, 11, WOOD);
      p.px(13, 1, STEEL); p.px(12, 2, STEEL); p.px(14, 2, STEEL);
      break;
  }
}

/**
 * The workhorse: one upright two-legged figure, parameterised enough to cover
 * every humanoid in the game from a kobold to the final boss.
 */
function humanoid(opts) {
  const {
    skin = '#c8a078', cloth = '#6a6a8a', accent = '#d8c060',
    eyes = '#ffe070', weapon = 'none', horns = false, hood = false,
    shield = false, bulk = 0, tatters = false, ribs = false, crown = false,
    glow = null, size = GRID,
  } = opts;
  const p = new Pix(size);
  const cx = 8;
  const bodyW = 6 + bulk;
  const bodyX = cx - (bodyW >> 1);

  if (glow) { p.g.globalAlpha = 0.35; p.oval(cx, 9, 7, 7, glow); p.g.globalAlpha = 1; }

  // legs
  if (tatters) {
    p.rect(bodyX, 12, bodyW, 2, cloth);
    for (let i = 0; i < bodyW; i += 2) p.px(bodyX + i, 14, shade(cloth, 0.7));
  } else {
    p.rect(cx - 3, 12, 2, 4, shade(cloth, 0.75));
    p.rect(cx + 1, 12, 2, 4, shade(cloth, 0.75));
    p.rect(cx - 3, 15, 2, 1, '#3a2e26');
    p.rect(cx + 1, 15, 2, 1, '#3a2e26');
  }

  // torso
  p.rect(bodyX, 7, bodyW, 5, cloth);
  p.rect(bodyX, 7, bodyW, 1, shade(cloth, 1.25));
  if (ribs) {
    for (let y = 8; y < 12; y += 2) p.rect(bodyX + 1, y, bodyW - 2, 1, shade(skin, 1.1));
  }
  // belt
  p.rect(bodyX, 11, bodyW, 1, accent);

  // arms
  p.rect(bodyX - 2, 7, 2, 4, skin);
  p.rect(bodyX + bodyW, 7, 2, 4, skin);

  // head
  const headW = 6, headX = cx - 3;
  p.rect(headX, 2, headW, 5, skin);
  if (hood) {
    p.rect(headX - 1, 1, headW + 2, 4, cloth);
    p.rect(headX, 4, headW, 2, shade(skin, 0.55));
  } else {
    p.rect(headX, 1, headW, 1, shade(skin, 0.8));
  }
  p.px(headX + 1, 4, eyes);
  p.px(headX + 4, 4, eyes);

  if (horns) {
    p.px(headX - 1, 1, BONE); p.px(headX - 1, 0, BONE);
    p.px(headX + headW, 1, BONE); p.px(headX + headW, 0, BONE);
  }
  if (crown) {
    p.rect(headX, 0, headW, 1, accent);
    p.px(headX, -1 + 1, accent);
    p.px(headX + 2, 0, '#fff0a0');
    p.px(headX + headW - 1, 0, accent);
  }
  if (shield) {
    p.rect(2, 7, 3, 5, STEEL_D);
    p.rect(2, 7, 3, 1, STEEL);
    p.px(3, 9, accent);
  }
  drawWeapon(p, weapon, accent);
  return p.outline();
}

/** Four-legged creatures: rats, wolves, and the drake. */
function beast(opts) {
  const {
    fur = '#8a6a4a', eyes = '#ff6040', ears = true, tail = 'thin',
    wings = false, horns = false, big = false, size = GRID,
  } = opts;
  const p = new Pix(size);
  const top = big ? 5 : 7;
  const bodyH = big ? 6 : 4;

  if (wings) {
    p.g.globalAlpha = 0.9;
    p.rect(2, top - 3, 5, 4, shade(fur, 0.7));
    p.rect(9, top - 3, 5, 4, shade(fur, 0.7));
    p.g.globalAlpha = 1;
  }
  // body + head
  p.oval(7, top + bodyH / 2, 5, bodyH / 2 + 0.5, fur);
  p.oval(12, top + 1, 2.6, 2.4, shade(fur, 1.1));
  p.px(13, top, eyes);
  p.px(11, top, eyes);
  // snout
  p.px(14, top + 2, shade(fur, 0.75));
  if (ears) { p.px(11, top - 2, shade(fur, 0.8)); p.px(13, top - 2, shade(fur, 0.8)); }
  if (horns) { p.px(11, top - 2, BONE); p.px(13, top - 2, BONE); }
  // legs
  const legY = top + bodyH;
  for (const lx of [4, 6, 9, 11]) p.rect(lx, legY, 1, big ? 4 : 3, shade(fur, 0.8));
  // tail
  if (tail === 'thin') p.line(2, top + 2, 0, top, shade(fur, 0.7));
  else if (tail === 'bushy') { p.oval(2, top + 1, 2, 2, shade(fur, 0.85)); }
  return p.outline();
}

// --------------------------------------------------------- the bestiary ----
const CREATURES = {
  // players
  warrior: () => humanoid({ skin: '#d8a878', cloth: '#c8503c', accent: '#e0c060', weapon: 'sword', shield: true }),
  ranger:  () => humanoid({ skin: '#d8a878', cloth: '#4a9c52', accent: '#8a6038', weapon: 'bow', hood: true }),
  mage:    () => humanoid({ skin: '#d8a878', cloth: '#5b7fd4', accent: '#a0d0f0', weapon: 'staff', hood: true }),

  // townsfolk
  smith:   () => humanoid({ skin: '#c89060', cloth: '#6a4a38', accent: '#c8a040', weapon: 'mace' }),
  apoth:   () => humanoid({ skin: '#e0b890', cloth: '#7a5a9a', accent: '#c0e070', hood: true }),
  priest:  () => humanoid({ skin: '#e8c8a0', cloth: '#e8e4d8', accent: '#d8c060', hood: true }),

  // dungeon
  rat:      () => beast({ fur: '#8a6a4a', eyes: '#ff7050', tail: 'thin' }),
  bat:      () => {
    const p = new Pix();
    p.g.globalAlpha = 0.95;
    p.rect(1, 5, 5, 3, '#6b5b8a'); p.rect(10, 5, 5, 3, '#6b5b8a');
    p.g.globalAlpha = 1;
    p.oval(8, 8, 2.6, 3, '#8272a8');
    p.px(7, 7, '#ffe070'); p.px(9, 7, '#ffe070');
    p.px(6, 4, '#6b5b8a'); p.px(10, 4, '#6b5b8a');
    return p.outline();
  },
  kobold:   () => humanoid({ skin: '#a8632c', cloth: '#5a4030', accent: '#c08040', weapon: 'spear', horns: true }),
  goblin:   () => humanoid({ skin: '#5f8a3a', cloth: '#4a3a28', accent: '#a06030', weapon: 'sword' }),
  gobarch:  () => humanoid({ skin: '#7aa84a', cloth: '#3a4a28', accent: '#8a6038', weapon: 'bow' }),
  spider:   () => {
    const p = new Pix();
    p.oval(8, 9, 4, 3.4, '#4a4a66');
    p.oval(8, 5.5, 2.4, 2, '#5a5a7a');
    p.px(7, 5, '#ff5050'); p.px(9, 5, '#ff5050');
    for (const [x0, y0, x1, y1] of [
      [4, 8, 1, 4], [4, 9, 0, 9], [4, 10, 1, 14],
      [12, 8, 15, 4], [12, 9, 16, 9], [12, 10, 15, 14],
    ]) p.line(x0, y0, x1, y1, '#3a3a52');
    return p.outline();
  },
  skeleton: () => humanoid({ skin: BONE, cloth: '#6a6458', accent: '#9a9488', weapon: 'sword', eyes: '#ff4040', ribs: true }),
  zombie:   () => humanoid({ skin: '#6e8a5a', cloth: '#4a4438', accent: '#5a5a4a', weapon: 'claw', eyes: '#c8e070' }),
  wolf:     () => beast({ fur: '#7a7a8a', eyes: '#ffd040', tail: 'bushy' }),
  orc:      () => humanoid({ skin: '#4f7a4a', cloth: '#5a3828', accent: '#b07030', weapon: 'axe', bulk: 2, eyes: '#ffb040' }),
  cultist:  () => humanoid({ skin: '#8a3a5a', cloth: '#6a1a2a', accent: '#d84060', hood: true, weapon: 'staff', eyes: '#ff5070' }),
  ghoul:    () => humanoid({ skin: '#9aa87a', cloth: '#3a3a2a', accent: '#6a6a4a', weapon: 'claw', eyes: '#d0ff80', tatters: true }),
  ogre:     () => humanoid({ skin: '#a07a4a', cloth: '#6a4a30', accent: '#8a5a30', weapon: 'mace', bulk: 4, eyes: '#ffd060' }),
  wraith:   () => humanoid({ skin: '#9fd8e8', cloth: '#2a4a60', accent: '#a0e8ff', hood: true, tatters: true, eyes: '#ffffff', glow: '#9fd8e8' }),
  troll:    () => humanoid({ skin: '#4a7a5a', cloth: '#3a4a30', accent: '#7a9a50', weapon: 'claw', bulk: 4, horns: true, eyes: '#c0ff90' }),
  golem:    () => {
    const p = new Pix();
    p.rect(3, 4, 10, 9, '#8a8a90');
    p.rect(3, 4, 10, 1, '#a8a8b0');
    p.rect(2, 6, 2, 5, '#7a7a82'); p.rect(12, 6, 2, 5, '#7a7a82');
    p.rect(4, 13, 3, 3, '#7a7a82'); p.rect(9, 13, 3, 3, '#7a7a82');
    p.px(6, 7, '#60d0ff'); p.px(9, 7, '#60d0ff');
    p.rect(5, 10, 6, 1, '#6a6a72');
    return p.outline();
  },
  sorcerer: () => humanoid({ skin: '#d8c8e8', cloth: '#6a5ad8', accent: '#c0a0ff', hood: true, weapon: 'staff', eyes: '#ffffff', glow: '#6a5ad8' }),
  drake:    () => beast({ fur: '#c8562c', eyes: '#ffe040', wings: true, horns: true, ears: false, big: true }),
  revenant: () => humanoid({ skin: '#b0b8c8', cloth: '#4a5260', accent: '#8a94a8', weapon: 'axe', bulk: 2, eyes: '#50e0ff', ribs: true }),

  // bosses (authored larger, so they loom)
  warden: () => humanoid({
    size: 24, skin: '#e0703c', cloth: '#5a2018', accent: '#ffb040',
    weapon: 'mace', bulk: 6, horns: true, eyes: '#fff080', glow: '#ff6020',
  }),
  stormking: () => humanoid({
    size: 24, skin: '#c8c0e8', cloth: '#3a2a7a', accent: '#b0a0ff',
    weapon: 'sword', bulk: 5, crown: true, eyes: '#ffffff', glow: '#7d6ae8',
  }),
};

// -------------------------------------------------------------- item icons -
const ITEMS = {
  sword: () => { const p = new Pix(); p.rect(7, 2, 2, 9, STEEL); p.rect(5, 10, 6, 1, '#a07838'); p.rect(7, 11, 2, 3, WOOD); return p.outline(); },
  axe:   () => { const p = new Pix(); p.rect(7, 3, 2, 11, WOOD); p.rect(4, 2, 5, 5, STEEL); p.rect(4, 2, 1, 5, STEEL_D); return p.outline(); },
  mace:  () => { const p = new Pix(); p.rect(7, 6, 2, 8, WOOD); p.oval(8, 4, 3.2, 3.2, STEEL); p.px(6, 3, '#e0e8f0'); return p.outline(); },
  dagger:() => { const p = new Pix(); p.rect(7, 4, 2, 6, STEEL); p.rect(5, 9, 6, 1, '#a07838'); p.rect(7, 10, 2, 3, WOOD); return p.outline(); },
  bow:   () => { const p = new Pix(); p.line(5, 2, 5, 13, WOOD); p.px(6, 3, WOOD); p.px(6, 12, WOOD); p.line(7, 3, 7, 12, '#e8e0c8'); p.rect(8, 7, 6, 1, '#d8d0b8'); return p.outline(); },
  staff: () => { const p = new Pix(); p.rect(7, 4, 2, 11, WOOD); p.oval(8, 3, 3, 3, '#70c0ff'); p.px(7, 2, '#ffffff'); return p.outline(); },
  armor: () => { const p = new Pix(); p.rect(4, 3, 8, 9, STEEL_D); p.rect(4, 3, 8, 1, STEEL); p.rect(3, 4, 1, 5, STEEL_D); p.rect(12, 4, 1, 5, STEEL_D); p.rect(6, 6, 4, 4, '#6a727e'); return p.outline(); },
  robe:  () => { const p = new Pix(); p.rect(5, 3, 6, 3, '#6a7ad0'); p.rect(4, 6, 8, 7, '#5b7fd4'); p.rect(4, 12, 8, 1, '#4a68b0'); p.rect(7, 6, 2, 6, '#8098e0'); return p.outline(); },
  ring:  () => { const p = new Pix(); p.oval(8, 9, 4, 4, '#d8b040'); p.g.clearRect(6, 7, 4, 4); p.oval(8, 4, 1.8, 1.8, '#70e0ff'); return p.outline(); },
  amulet:() => { const p = new Pix(); p.line(4, 3, 8, 8, '#c8a040'); p.line(12, 3, 8, 8, '#c8a040'); p.oval(8, 10, 3, 3.4, '#d84060'); p.px(7, 9, '#ff90a0'); return p.outline(); },
  potion_red:    () => potion('#d83048', '#ff8090'),
  potion_blue:   () => potion('#3060d8', '#80a0ff'),
  potion_green:  () => potion('#30a850', '#80e090'),
  potion_yellow: () => potion('#d8b030', '#ffe880'),
  scroll:() => { const p = new Pix(); p.rect(4, 3, 8, 10, '#e8dcb8'); p.rect(4, 3, 8, 1, '#c8bc98'); p.rect(3, 2, 10, 2, '#b8a478'); p.rect(3, 12, 10, 2, '#b8a478'); for (let y = 6; y < 12; y += 2) p.rect(6, y, 5, 1, '#8a7a58'); return p.outline(); },
  gold:  () => { const p = new Pix(); p.oval(6, 10, 3, 2.4, '#d8a830'); p.oval(10, 11, 3, 2.4, '#d8a830'); p.oval(8, 7, 3.2, 2.6, '#f0c850'); p.px(7, 6, '#fff0a0'); return p.outline(); },
};

function potion(body, shine) {
  const p = new Pix();
  p.rect(7, 2, 2, 2, '#9a9488');
  p.rect(6, 4, 4, 1, '#b8b2a6');
  p.oval(8, 9, 3.6, 4.2, body);
  p.px(6, 7, shine);
  p.rect(6, 11, 5, 1, shade(body, 0.7));
  return p.outline();
}

// ------------------------------------------------------------- projectiles -
const PROJECTILES = {
  arrow: () => { const p = new Pix(); p.rect(2, 7, 10, 1, WOOD); p.px(12, 7, STEEL); p.px(11, 6, STEEL); p.px(11, 8, STEEL); p.px(3, 6, '#e8e0c8'); p.px(3, 8, '#e8e0c8'); return p; },
  bolt:  () => { const p = new Pix(); p.oval(8, 7.5, 3.4, 2, '#8a70ff'); p.oval(8, 7.5, 2, 1.2, '#d8c8ff'); p.px(3, 7, '#6a50d0'); return p; },
  fire:  () => { const p = new Pix(); p.oval(8, 7.5, 3.6, 2.6, '#ff6020'); p.oval(8, 7.5, 2.2, 1.6, '#ffc040'); p.px(8, 7, '#fff8d0'); p.px(3, 7, '#c83010'); return p; },
  magic: () => { const p = new Pix(); p.oval(8, 7.5, 3, 2.2, '#40c8ff'); p.oval(8, 7.5, 1.6, 1.2, '#e0f8ff'); return p; },
};

// ------------------------------------------------------------------ tiles --
// Tiles are drawn straight at TILE_PX with a few deterministic variants each,
// so large stone floors do not look like graph paper.
function tileVariants(name, count, draw) {
  const list = [];
  for (let v = 0; v < count; v++) {
    const { c, g } = canvas(TILE_PX, TILE_PX);
    draw(g, v, TILE_PX);
    list.push(c);
  }
  return list;
}

// A cheap deterministic hash so every variant looks the same on every machine.
function vrand(seed) {
  let t = (seed * 2654435761) >>> 0;
  t ^= t >>> 15; t = Math.imul(t, 2246822507); t ^= t >>> 13;
  return ((t >>> 0) % 1000) / 1000;
}

function speckle(g, size, seed, colors, count) {
  for (let i = 0; i < count; i++) {
    const r1 = vrand(seed * 97 + i * 3);
    const r2 = vrand(seed * 131 + i * 7 + 1);
    const r3 = vrand(seed * 17 + i * 11 + 2);
    g.fillStyle = colors[Math.floor(r3 * colors.length)];
    const s = r3 > 0.8 ? 3 : 2;
    g.fillRect(Math.floor(r1 * (size - s)), Math.floor(r2 * (size - s)), s, s);
  }
}

function buildTiles() {
  const t = {};
  t.floor = tileVariants('floor', 4, (g, v, s) => {
    g.fillStyle = '#3a3630'; g.fillRect(0, 0, s, s);
    g.fillStyle = '#423e37'; g.fillRect(0, 0, s, 2); g.fillRect(0, 0, 2, s);
    speckle(g, s, v + 1, ['#332f2a', '#474338', '#2e2a26'], 9);
  });
  t.shop_floor = tileVariants('shop_floor', 2, (g, v, s) => {
    g.fillStyle = '#52433a'; g.fillRect(0, 0, s, s);
    g.fillStyle = '#5e4d42'; g.fillRect(2, 2, s - 4, s - 4);
    speckle(g, s, v + 40, ['#4a3c34', '#63544a'], 5);
  });
  t.wall = tileVariants('wall', 3, (g, v, s) => {
    g.fillStyle = '#5a5650'; g.fillRect(0, 0, s, s);
    g.fillStyle = '#6e6a62'; g.fillRect(0, 0, s, 4);           // lit top edge
    g.fillStyle = '#413d38'; g.fillRect(0, s - 4, s, 4);       // shadowed base
    g.strokeStyle = '#4a4640'; g.lineWidth = 1;
    // brick courses, offset on alternate rows
    for (let y = 6; y < s; y += 8) {
      g.beginPath(); g.moveTo(0, y + 0.5); g.lineTo(s, y + 0.5); g.stroke();
      const off = ((y / 8) % 2) ? 0 : s / 2;
      g.beginPath(); g.moveTo(off + 0.5, y + 0.5); g.lineTo(off + 0.5, y + 8.5); g.stroke();
    }
    speckle(g, s, v + 70, ['#535049', '#625e57'], 4);
  });
  t.grass = tileVariants('grass', 4, (g, v, s) => {
    g.fillStyle = '#3c5a32'; g.fillRect(0, 0, s, s);
    for (let i = 0; i < 14; i++) {
      const r1 = vrand(v * 53 + i * 5), r2 = vrand(v * 91 + i * 9 + 3);
      g.fillStyle = r2 > 0.6 ? '#46682e' : '#35502c';
      g.fillRect(Math.floor(r1 * (s - 2)), Math.floor(r2 * (s - 3)), 2, 3);
    }
  });
  t.road = tileVariants('road', 3, (g, v, s) => {
    g.fillStyle = '#6a6054'; g.fillRect(0, 0, s, s);
    g.fillStyle = '#756b5d'; g.fillRect(1, 1, s - 2, s - 2);
    speckle(g, s, v + 11, ['#5e554a', '#807567'], 7);
  });
  t.tree = tileVariants('tree', 3, (g, v, s) => {
    g.fillStyle = '#3c5a32'; g.fillRect(0, 0, s, s);
    g.fillStyle = '#5a4028'; g.fillRect(s / 2 - 3, s - 12, 6, 12);
    g.fillStyle = '#2e5228';
    g.beginPath(); g.arc(s / 2, s / 2 - 3, 11 + vrand(v) * 2, 0, Math.PI * 2); g.fill();
    g.fillStyle = '#3a6630';
    g.beginPath(); g.arc(s / 2 - 3, s / 2 - 6, 6, 0, Math.PI * 2); g.fill();
  });
  t.water = tileVariants('water', 4, (g, v, s) => {
    g.fillStyle = '#1f3f5e'; g.fillRect(0, 0, s, s);
    g.fillStyle = '#2a5478';
    for (let y = 4; y < s; y += 9) {
      const off = Math.floor(vrand(v * 31 + y) * 8);
      g.fillRect(off, y, s - off - 4, 2);
    }
    g.fillStyle = '#3f7aa8'; g.fillRect(4 + v * 3, 6, 5, 1);
  });
  t.rubble = tileVariants('rubble', 3, (g, v, s) => {
    g.fillStyle = '#3a3630'; g.fillRect(0, 0, s, s);
    for (let i = 0; i < 8; i++) {
      const r1 = vrand(v * 61 + i * 13), r2 = vrand(v * 23 + i * 7);
      g.fillStyle = ['#5a5650', '#6a665e', '#4a4640'][i % 3];
      const w = 3 + Math.floor(r1 * 4);
      g.fillRect(Math.floor(r1 * (s - w)), Math.floor(r2 * (s - w)), w, w - 1);
    }
  });
  t.door = tileVariants('door', 1, (g, v, s) => {
    g.fillStyle = '#3a3630'; g.fillRect(0, 0, s, s);
    g.fillStyle = '#6a4a2a'; g.fillRect(3, 1, s - 6, s - 2);
    g.fillStyle = '#7a5838'; g.fillRect(5, 3, s - 10, s - 6);
    g.fillStyle = '#4a3420';
    for (let y = 5; y < s - 4; y += 7) g.fillRect(5, y, s - 10, 1);
    g.fillStyle = '#d8b040'; g.fillRect(s - 9, s / 2 - 1, 3, 3);
  });
  t.door_open = tileVariants('door_open', 1, (g, v, s) => {
    g.fillStyle = '#2e2a26'; g.fillRect(0, 0, s, s);
    g.fillStyle = '#6a4a2a'; g.fillRect(0, 0, 4, s); g.fillRect(s - 4, 0, 4, s);
    g.fillStyle = '#3a3630'; g.fillRect(4, 0, s - 8, s);
  });
  t.stairs_down = tileVariants('stairs_down', 1, (g, v, s) => {
    g.fillStyle = '#2a2724'; g.fillRect(0, 0, s, s);
    for (let i = 0; i < 4; i++) {
      const inset = i * 4;
      g.fillStyle = ['#5a5650', '#4e4a44', '#423e38', '#36322d'][i];
      g.fillRect(inset, inset, s - inset * 2, 4);
    }
    g.fillStyle = '#161412'; g.fillRect(14, 16, s - 28, s - 18);
  });
  t.stairs_up = tileVariants('stairs_up', 1, (g, v, s) => {
    g.fillStyle = '#3a3630'; g.fillRect(0, 0, s, s);
    for (let i = 0; i < 4; i++) {
      g.fillStyle = ['#36322d', '#454139', '#545046', '#636055'][i];
      g.fillRect(2, s - 8 - i * 6, s - 4, 6);
    }
  });
  t.altar = tileVariants('altar', 1, (g, v, s) => {
    g.fillStyle = '#3a3630'; g.fillRect(0, 0, s, s);
    g.fillStyle = '#6a6478'; g.fillRect(5, 10, s - 10, 14);
    g.fillStyle = '#8a84a0'; g.fillRect(3, 7, s - 6, 4);
    g.fillStyle = '#b0a0ff'; g.fillRect(12, 13, 8, 2);
  });
  t.bridge = tileVariants('bridge', 2, (g, v, s) => {
    g.fillStyle = '#1f3f5e'; g.fillRect(0, 0, s, s);
    g.fillStyle = '#6a4a2a'; g.fillRect(0, 2, s, s - 4);
    g.fillStyle = '#7a5838';
    for (let x = 1; x < s; x += 6) g.fillRect(x, 3, 4, s - 6);
  });
  return t;
}

// ------------------------------------------------------------------- init --
export const SPRITES = { creatures: {}, items: {}, projectiles: {}, tiles: {} };

export function buildSprites() {
  if (cache.has('built')) return SPRITES;
  for (const [name, fn] of Object.entries(CREATURES)) {
    const p = fn();
    // Bosses are authored on a bigger grid; keep the same pixel scale.
    SPRITES.creatures[name] = p.bake(TILE_PX / GRID);
  }
  for (const [name, fn] of Object.entries(ITEMS)) SPRITES.items[name] = fn().bake(TILE_PX / GRID);
  for (const [name, fn] of Object.entries(PROJECTILES)) SPRITES.projectiles[name] = fn().bake(TILE_PX / GRID);
  SPRITES.tiles = buildTiles();
  cache.set('built', true);
  return SPRITES;
}

/** Pick a stable variant for a tile position so the map does not shimmer. */
export function tileVariant(list, x, y) {
  if (!list || !list.length) return null;
  return list[Math.floor(vrand(x * 73856093 ^ y * 19349663) * list.length) % list.length];
}

export { shade };
