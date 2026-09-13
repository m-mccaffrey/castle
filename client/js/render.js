// The renderer. Draws the remembered map, dims everything out of sight, tweens
// creatures between tiles, and layers on the torch-light that makes a dungeon
// feel like a dungeon.

import { T, SIGHT_DUNGEON, SIGHT_TOWN } from '../../shared/constants.js';
import { computeFOV } from '../../shared/fov.js';
import { SPRITES, TILE_PX, tileVariant, shade } from './sprites.js';

const TILE_SPRITE = {
  [T.FLOOR]: 'floor',
  [T.WALL]: 'wall',
  [T.DOOR]: 'door',
  [T.DOOR_OPEN]: 'door_open',
  [T.STAIRS_DOWN]: 'stairs_down',
  [T.STAIRS_UP]: 'stairs_up',
  [T.WATER]: 'water',
  [T.RUBBLE]: 'rubble',
  [T.GRASS]: 'grass',
  [T.ROAD]: 'road',
  [T.TREE]: 'tree',
  [T.SHOP_FLOOR]: 'shop_floor',
  [T.ALTAR]: 'altar',
  [T.BRIDGE]: 'bridge',
};

const FLOAT_COLORS = {
  damage: '#ffd86a', crit: '#ff9030', playerhurt: '#ff5a5a', heal: '#70e080',
  mana: '#70b0ff', gold: '#ffd040', xp: '#c0a0ff', miss: '#9a9a9a',
  burn: '#ff8030', poison: '#a0d040',
};

export class Renderer {
  constructor(canvas) {
    this.canvas = canvas;
    this.g = canvas.getContext('2d');
    this.g.imageSmoothingEnabled = false;

    this.map = null;                 // { w, h, tiles, known, depth, town }
    this.fov = new Set();
    this.fovKey = '';
    this.actors = new Map();         // id -> { ...server fields, rx, ry }
    this.items = [];
    this.projectiles = [];
    this.floats = [];
    this.effects = [];
    this.camera = { x: 0, y: 0, init: false };
    this.shake = 0;
    this.you = null;
    this.time = 0;
    this.showMinimap = true;
  }

  // ------------------------------------------------------------- map state --
  setLevel({ w, h, depth, name, town }) {
    this.map = {
      w, h, depth, name, town,
      tiles: new Uint8Array(w * h),
      known: new Uint8Array(w * h),
    };
    this.actors.clear();
    this.items = [];
    this.projectiles = [];
    this.floats = [];
    this.effects = [];
    this.fovKey = '';
    this.camera.init = false;
  }

  applyTiles(flat) {
    if (!this.map) return;
    for (let i = 0; i < flat.length; i += 3) {
      const x = flat[i], y = flat[i + 1], t = flat[i + 2];
      if (x < 0 || y < 0 || x >= this.map.w || y >= this.map.h) continue;
      const idx = y * this.map.w + x;
      this.map.tiles[idx] = t;
      this.map.known[idx] = 1;
    }
    this.fovKey = '';                // terrain changed; recompute lighting
  }

  /** Merge a server snapshot, keeping render positions for smooth movement. */
  applyState(snap) {
    this.you = snap.you;
    this.party = snap.party;
    this.descend = snap.descend;
    this.items = snap.items;
    this.projectiles = snap.proj;

    const seen = new Set();
    for (const a of snap.actors) {
      seen.add(a.id);
      const prev = this.actors.get(a.id);
      if (prev) {
        // Keep the old render position so the sprite glides to the new tile.
        Object.assign(prev, a);
        if (prev.tx !== a.x || prev.ty !== a.y) {
          prev.tx = a.x; prev.ty = a.y;
        }
      } else {
        this.actors.set(a.id, { ...a, rx: a.x, ry: a.y, tx: a.x, ty: a.y });
      }
    }
    for (const id of [...this.actors.keys()]) if (!seen.has(id)) this.actors.delete(id);
  }

  addFloat(f) {
    this.floats.push({ ...f, born: performance.now(), ox: (Math.random() - 0.5) * 0.5 });
    if (this.floats.length > 80) this.floats.shift();
  }

  addEffect(e) {
    const particles = [];
    const n = e.kind === 'death' ? 14 : e.kind === 'slam' || e.kind === 'firestorm' ? 22 : 9;
    for (let i = 0; i < n; i++) {
      const a = Math.random() * Math.PI * 2;
      const sp = 0.02 + Math.random() * 0.06;
      particles.push({ x: 0, y: 0, vx: Math.cos(a) * sp, vy: Math.sin(a) * sp, life: 1 });
    }
    this.effects.push({ ...e, born: performance.now(), particles });
    if (this.effects.length > 40) this.effects.shift();
    if (e.kind === 'slam' || e.kind === 'death') this.shake = Math.min(8, this.shake + 3);
  }

  // ------------------------------------------------------------ lighting ----
  updateFOV() {
    if (!this.map || !this.you) return;
    const me = this.actors.get(this.you.id);
    const px = me ? me.x : 0, py = me ? me.y : 0;
    const key = `${px},${py},${this.map.depth}`;
    if (key === this.fovKey) return;
    this.fovKey = key;
    computeFOV(this.map, px, py, this.map.town ? SIGHT_TOWN : SIGHT_DUNGEON, this.fov);
  }

  // -------------------------------------------------------------- drawing ---
  resize() {
    const parent = this.canvas.parentElement;
    const w = Math.max(320, parent.clientWidth);
    const h = Math.max(240, parent.clientHeight);
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    if (this.canvas.width !== Math.floor(w * dpr) || this.canvas.height !== Math.floor(h * dpr)) {
      this.canvas.width = Math.floor(w * dpr);
      this.canvas.height = Math.floor(h * dpr);
      this.canvas.style.width = `${w}px`;
      this.canvas.style.height = `${h}px`;
      this.dpr = dpr;
      this.g.imageSmoothingEnabled = false;
    }
  }

  draw(dt) {
    this.time += dt;
    const g = this.g;
    const W = this.canvas.width, H = this.canvas.height;

    g.fillStyle = '#0a0908';
    g.fillRect(0, 0, W, H);
    if (!this.map || !this.you) return;

    this.updateFOV();

    // Tween creatures toward their server tile.
    const lerp = Math.min(1, dt * 13);
    for (const a of this.actors.values()) {
      a.rx += ((a.tx ?? a.x) - a.rx) * lerp;
      a.ry += ((a.ty ?? a.y) - a.ry) * lerp;
      if (Math.abs(a.rx - a.tx) < 0.01) a.rx = a.tx;
      if (Math.abs(a.ry - a.ty) < 0.01) a.ry = a.ty;
    }

    const me = this.actors.get(this.you.id);
    const focusX = me ? me.rx : this.map.w / 2;
    const focusY = me ? me.ry : this.map.h / 2;

    const scale = this.dpr || 1;
    const tile = TILE_PX * scale;
    const viewW = W / tile, viewH = H / tile;

    if (!this.camera.init) {
      this.camera.x = focusX; this.camera.y = focusY; this.camera.init = true;
    } else {
      const k = Math.min(1, dt * 7);
      this.camera.x += (focusX - this.camera.x) * k;
      this.camera.y += (focusY - this.camera.y) * k;
    }

    // Keep the camera inside the map unless the map is smaller than the screen.
    let camX = this.camera.x, camY = this.camera.y;
    if (this.map.w > viewW) camX = Math.max(viewW / 2, Math.min(this.map.w - viewW / 2, camX));
    else camX = this.map.w / 2;
    if (this.map.h > viewH) camY = Math.max(viewH / 2, Math.min(this.map.h - viewH / 2, camY));
    else camY = this.map.h / 2;

    let shakeX = 0, shakeY = 0;
    if (this.shake > 0.1) {
      shakeX = (Math.random() - 0.5) * this.shake * scale;
      shakeY = (Math.random() - 0.5) * this.shake * scale;
      this.shake *= Math.max(0, 1 - dt * 6);
    }

    const originX = W / 2 - camX * tile + shakeX;
    const originY = H / 2 - camY * tile + shakeY;
    const sx = (wx) => originX + wx * tile;
    const sy = (wy) => originY + wy * tile;

    const x0 = Math.max(0, Math.floor(camX - viewW / 2) - 1);
    const x1 = Math.min(this.map.w - 1, Math.ceil(camX + viewW / 2) + 1);
    const y0 = Math.max(0, Math.floor(camY - viewH / 2) - 1);
    const y1 = Math.min(this.map.h - 1, Math.ceil(camY + viewH / 2) + 1);

    // --- terrain ---------------------------------------------------------
    for (let y = y0; y <= y1; y++) {
      for (let x = x0; x <= x1; x++) {
        const i = y * this.map.w + x;
        if (!this.map.known[i]) continue;
        const t = this.map.tiles[i];
        if (t === T.VOID) continue;
        const list = SPRITES.tiles[TILE_SPRITE[t]];
        const img = tileVariant(list, x, y);
        if (!img) continue;
        const dx = sx(x), dy = sy(y);
        g.drawImage(img, dx, dy, tile, tile);
        if (!this.fov.has(i)) {
          // Remembered, but not currently in sight.
          g.fillStyle = 'rgba(6,8,16,0.62)';
          g.fillRect(dx, dy, tile, tile);
        }
      }
    }

    // --- ground loot ------------------------------------------------------
    const bob = Math.sin(this.time * 3) * 0.06;
    for (const it of this.items) {
      if (it.x < x0 || it.x > x1 || it.y < y0 || it.y > y1) continue;
      const img = it.gold ? SPRITES.items.gold : SPRITES.items[it.icon] || SPRITES.items.gold;
      if (!img) continue;
      // A glint under anything better than ordinary.
      if (it.tier >= 3) {
        g.save();
        g.globalAlpha = 0.35 + Math.sin(this.time * 5) * 0.15;
        g.fillStyle = it.tier >= 4 ? '#ffd060' : '#90d0ff';
        g.beginPath();
        g.arc(sx(it.x + 0.5), sy(it.y + 0.6), tile * 0.42, 0, Math.PI * 2);
        g.fill();
        g.restore();
      }
      g.drawImage(img, sx(it.x), sy(it.y + bob), tile, tile);
    }

    // --- creatures --------------------------------------------------------
    const sorted = [...this.actors.values()].sort((a, b) => a.ry - b.ry);
    for (const a of sorted) {
      if (a.rx < x0 - 2 || a.rx > x1 + 2 || a.ry < y0 - 2 || a.ry > y1 + 2) continue;
      this.drawActor(g, a, sx, sy, tile, scale);
    }

    // --- projectiles ------------------------------------------------------
    for (const p of this.projectiles) {
      const img = SPRITES.projectiles[p.k] || SPRITES.projectiles.bolt;
      if (!img) continue;
      g.save();
      g.translate(sx(p.x + 0.5), sy(p.y + 0.5));
      g.rotate(p.a);
      g.drawImage(img, -tile / 2, -tile / 2, tile, tile);
      g.restore();
    }

    // --- effects ----------------------------------------------------------
    this.drawEffects(g, sx, sy, tile);

    // --- torchlight -------------------------------------------------------
    if (!this.map.town) {
      const cx = sx(focusX + 0.5), cy = sy(focusY + 0.5);
      const radius = 9 * tile;
      const grad = g.createRadialGradient(cx, cy, tile * 1.5, cx, cy, radius);
      grad.addColorStop(0, 'rgba(0,0,0,0)');
      grad.addColorStop(0.55, 'rgba(4,4,10,0.18)');
      grad.addColorStop(1, 'rgba(2,2,6,0.78)');
      g.fillStyle = grad;
      g.fillRect(0, 0, W, H);
    }

    // --- floating text ----------------------------------------------------
    this.drawFloats(g, sx, sy, tile, scale);

    if (this.showMinimap) this.drawMinimap(g, W, H, scale);
  }

  drawActor(g, a, sx, sy, tile, scale) {
    const key = a.k === 'player' ? a.s : a.s;
    const img = SPRITES.creatures[key] || SPRITES.creatures.kobold;
    const big = a.bo ? 1.5 : a.el ? 1.18 : 1;
    const w = tile * big, h = tile * big;
    const dx = sx(a.rx + 0.5) - w / 2;
    const dy = sy(a.ry + 0.5) - h / 2;

    // Shadow grounds the sprite on the floor.
    g.save();
    g.globalAlpha = 0.3;
    g.fillStyle = '#000';
    g.beginPath();
    g.ellipse(sx(a.rx + 0.5), sy(a.ry + 0.92), tile * 0.3 * big, tile * 0.12 * big, 0, 0, Math.PI * 2);
    g.fill();
    g.restore();

    if (a.dn) {
      // Downed: lying on the floor, rotated.
      g.save();
      g.translate(sx(a.rx + 0.5), sy(a.ry + 0.6));
      g.rotate(Math.PI / 2);
      g.globalAlpha = 0.75;
      g.drawImage(img, -w / 2, -h / 2, w, h);
      g.restore();
    } else {
      g.save();
      if (a.fx?.includes('chill')) g.globalAlpha = 0.92;
      // Flip so the sprite faces the way it is moving.
      const facingLeft = a.f >= 5 && a.f <= 7;
      if (facingLeft) {
        g.translate(dx + w, dy);
        g.scale(-1, 1);
        g.drawImage(img, 0, 0, w, h);
      } else {
        g.drawImage(img, dx, dy, w, h);
      }
      g.restore();

      // Status tints.
      if (a.fx?.length) this.drawStatus(g, a, sx, sy, tile);
    }

    // Health bar: monsters only when hurt, players always.
    const hurt = a.hp < a.mhp;
    if ((a.k === 'monster' && hurt) || a.k === 'player') {
      const bw = tile * 0.7, bh = Math.max(3, 3 * scale);
      const bx = sx(a.rx + 0.5) - bw / 2;
      const by = dy - bh - 2 * scale;
      g.fillStyle = 'rgba(0,0,0,0.7)';
      g.fillRect(bx - 1, by - 1, bw + 2, bh + 2);
      const frac = Math.max(0, Math.min(1, a.hp / a.mhp));
      g.fillStyle = a.k === 'player' ? (a.id === this.you?.id ? '#60c860' : '#50a0e0')
                                     : frac > 0.5 ? '#c04040' : '#e07030';
      g.fillRect(bx, by, bw * frac, bh);
    }

    // Names: party members and anything unusual.
    if (a.k === 'player' || a.bo || a.el) {
      g.font = `${Math.round(10 * scale)}px "Courier New", monospace`;
      g.textAlign = 'center';
      g.fillStyle = 'rgba(0,0,0,0.8)';
      const label = a.dn ? `${a.n} (down!)` : a.n;
      const ly = dy - 8 * scale;
      g.fillText(label, sx(a.rx + 0.5) + 1, ly + 1);
      g.fillStyle = a.bo ? '#ff9060' : a.el ? '#ffd060' : (a.c || '#e0e0e0');
      g.fillText(label, sx(a.rx + 0.5), ly);
    }

    // Revive progress ring.
    if (a.rp != null) {
      const cx = sx(a.rx + 0.5), cy = sy(a.ry + 0.5);
      g.save();
      g.strokeStyle = '#70e080';
      g.lineWidth = 3 * scale;
      g.beginPath();
      g.arc(cx, cy, tile * 0.55, -Math.PI / 2, -Math.PI / 2 + (a.rp / 100) * Math.PI * 2);
      g.stroke();
      g.restore();
    }
  }

  drawStatus(g, a, sx, sy, tile) {
    const cx = sx(a.rx + 0.5), cy = sy(a.ry + 0.5);
    const tint = {
      burn: 'rgba(255,110,30,0.28)', poison: 'rgba(150,210,60,0.26)',
      chill: 'rgba(120,200,255,0.3)', snare: 'rgba(200,180,90,0.22)',
      haste: 'rgba(255,240,140,0.18)', fury: 'rgba(255,90,90,0.2)',
      bulwark: 'rgba(200,180,90,0.22)', ward: 'rgba(160,200,255,0.2)',
    };
    for (const fx of a.fx) {
      const col = tint[fx];
      if (!col) continue;
      g.fillStyle = col;
      g.beginPath();
      g.arc(cx, cy, tile * 0.45, 0, Math.PI * 2);
      g.fill();
    }
  }

  drawEffects(g, sx, sy, tile) {
    const now = performance.now();
    this.effects = this.effects.filter((e) => {
      const age = (now - e.born) / 1000;
      const life = e.kind === 'death' ? 0.6 : 0.45;
      if (age > life) return false;
      const k = 1 - age / life;
      const colors = {
        slash: e.color || '#ffffff', death: e.color || '#c04040',
        firehit: '#ff8030', firestorm: '#ff7020', burn: '#ff8030',
        magichit: '#70c0ff', frostnova: '#a0e0ff', heal: '#70e080',
        blink: '#c0a0ff', levelup: '#ffe070', slam: '#ffb060',
        cleave: '#ffffff', snare: '#d8c060', dashtrail: e.color || '#ffffff',
        shield: '#ffd860', poison: '#a0d040', hit: '#ffd86a',
      };
      const col = colors[e.kind] || '#ffffff';

      if (e.kind === 'slash' || e.kind === 'cleave') {
        g.save();
        g.globalAlpha = k * 0.85;
        g.strokeStyle = col;
        g.lineWidth = 3;
        g.beginPath();
        const r = tile * (e.kind === 'cleave' ? 0.95 : 0.5) * (1.4 - k * 0.4);
        g.arc(sx(e.x + 0.5), sy(e.y + 0.5), r, 0, Math.PI * 2);
        g.stroke();
        g.restore();
        return true;
      }

      if (e.kind === 'frostnova' || e.kind === 'firestorm' || e.kind === 'slam') {
        g.save();
        g.globalAlpha = k * 0.5;
        g.fillStyle = col;
        g.beginPath();
        g.arc(sx(e.x + 0.5), sy(e.y + 0.5), tile * 3.2 * (1 - k), 0, Math.PI * 2);
        g.fill();
        g.restore();
        return true;
      }

      g.save();
      g.globalAlpha = k;
      g.fillStyle = col;
      for (const p of e.particles) {
        p.x += p.vx; p.y += p.vy;
        const size = Math.max(2, tile * 0.12 * k);
        g.fillRect(sx(e.x + 0.5 + p.x) - size / 2, sy(e.y + 0.5 + p.y) - size / 2, size, size);
      }
      g.restore();
      return true;
    });
  }

  drawFloats(g, sx, sy, tile, scale) {
    const now = performance.now();
    g.textAlign = 'center';
    this.floats = this.floats.filter((f) => {
      const age = (now - f.born) / 1000;
      if (age > 1.1) return false;
      const rise = age * 1.3;
      const alpha = age < 0.8 ? 1 : 1 - (age - 0.8) / 0.3;
      const big = f.kind === 'crit' || f.kind === 'playerhurt';
      g.save();
      g.globalAlpha = Math.max(0, alpha);
      g.font = `bold ${Math.round((big ? 16 : 13) * scale)}px "Courier New", monospace`;
      const x = sx(f.x + 0.5 + f.ox), y = sy(f.y + 0.2 - rise);
      g.fillStyle = 'rgba(0,0,0,0.85)';
      g.fillText(f.text, x + 1.5, y + 1.5);
      g.fillStyle = FLOAT_COLORS[f.kind] || '#ffffff';
      g.fillText(f.text, x, y);
      g.restore();
      return true;
    });
  }

  drawMinimap(g, W, H, scale) {
    if (!this.map) return;
    const maxPx = 150 * scale;
    const cell = Math.max(1, Math.floor(Math.min(maxPx / this.map.w, maxPx / this.map.h)));
    const mw = this.map.w * cell, mh = this.map.h * cell;
    const ox = W - mw - 12 * scale, oy = 12 * scale;

    g.save();
    g.fillStyle = 'rgba(10,10,14,0.78)';
    g.fillRect(ox - 3, oy - 3, mw + 6, mh + 6);
    g.strokeStyle = '#6a6458';
    g.lineWidth = scale;
    g.strokeRect(ox - 3, oy - 3, mw + 6, mh + 6);

    for (let y = 0; y < this.map.h; y++) {
      for (let x = 0; x < this.map.w; x++) {
        const i = y * this.map.w + x;
        if (!this.map.known[i]) continue;
        const t = this.map.tiles[i];
        if (t === T.VOID) continue;
        let col = '#4a4640';
        if (t === T.WALL) col = '#2a2824';
        else if (t === T.TREE) col = '#2e4226';
        else if (t === T.WATER) col = '#22405e';
        else if (t === T.GRASS) col = '#3a5030';
        else if (t === T.ROAD || t === T.SHOP_FLOOR) col = '#5e5549';
        else if (t === T.STAIRS_DOWN) col = '#ffd060';
        else if (t === T.STAIRS_UP) col = '#80c0ff';
        else if (t === T.DOOR || t === T.DOOR_OPEN) col = '#7a5838';
        else if (t === T.ALTAR) col = '#b0a0ff';
        g.fillStyle = col;
        g.fillRect(ox + x * cell, oy + y * cell, cell, cell);
      }
    }
    // Party dots, then you on top.
    for (const p of this.party ?? []) {
      g.fillStyle = p.id === this.you?.id ? '#70ff70' : '#60b0ff';
      const s = Math.max(2, cell + 1);
      g.fillRect(ox + p.x * cell - 1, oy + p.y * cell - 1, s, s);
    }
    g.restore();
  }
}
