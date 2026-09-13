// Session handling: turns socket traffic into world commands, and the world's
// events back into per-player packets. Each client only ever learns about what
// its own character can see.

import { C, S, encode, decode } from '../shared/protocol.js';
import { CLASSES, chebyshev, TICK_MS, PROTOCOL_VERSION } from '../shared/constants.js';
import { describeItem } from './game/items.js';

const MAX_NAME = 14;
const MAX_CHAT = 160;
const MSG_BUDGET = 240;            // messages per second before we hang up
const TILES_PER_PACKET = 1200;     // tile triples per TILES message
const HEAR_RADIUS = 15;            // you hear things you cannot see

const CONTROL_CHARS = /[\x00-\x1f\x7f]/g;
const CHAT_COLORS = ['#e8d8a0', '#a0d8e8', '#d8a0e8', '#a0e8b0', '#e8a0a0', '#e8c0a0'];

function cleanName(raw) {
  const s = String(raw ?? '')
    .replace(CONTROL_CHARS, '')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, MAX_NAME);
  return s.length ? s : 'Adventurer';
}

function cleanChat(raw) {
  return String(raw ?? '')
    .replace(CONTROL_CHARS, '')
    .trim()
    .slice(0, MAX_CHAT);
}

class Session {
  constructor(conn, id) {
    this.conn = conn;
    this.id = id;
    this.player = null;
    this.msgCount = 0;
    this.budgetAt = Date.now();
    this.colorIdx = id % CHAT_COLORS.length;
    this.joinedAt = Date.now();
  }

  send(type, data) { this.conn.send(encode(type, data)); }
  get name() { return this.player?.name ?? `#${this.id}`; }
}

export class NetServer {
  constructor(world, store) {
    this.world = world;
    this.store = store;
    this.sessions = new Map();
    this.nextSessionId = 1;
    this.lastSaveAt = Date.now();
  }

  // ------------------------------------------------------------ lifecycle --
  onConnection(conn) {
    const session = new Session(conn, this.nextSessionId++);
    this.sessions.set(session.id, session);

    conn.on('message', (raw) => {
      // Cheap flood guard: a well-behaved client sends ~25 messages a second.
      const now = Date.now();
      if (now - session.budgetAt > 1000) { session.budgetAt = now; session.msgCount = 0; }
      if (++session.msgCount > MSG_BUDGET) {
        session.send(S.ERROR, { msg: 'Too many messages.' });
        conn.close(1008, 'flood');
        return;
      }
      this.handleMessage(session, raw);
    });

    conn.on('close', () => this.onDisconnect(session));

    // Offer up any characters saved from previous evenings.
    session.send(S.ROSTER, {
      chars: this.store.roster(),
      online: [...this.sessions.values()].filter(s => s.player)
        .map(s => ({ name: s.player.name, cls: s.player.cls, lv: s.player.level })),
      classes: Object.fromEntries(Object.entries(CLASSES).map(([k, v]) => [k, {
        name: v.name, blurb: v.blurb, color: v.color, abilities: v.abilities,
      }])),
      version: PROTOCOL_VERSION,
    });
  }

  onDisconnect(session) {
    this.sessions.delete(session.id);
    const p = session.player;
    if (!p) return;
    this.store.put(p.name, p.cls, p.toSaveJSON());
    this.store.flush().catch(() => {});
    this.world.removePlayer(p.id);
    this.broadcastLog(`${p.name} has left the party.`, 'info');
  }

  // -------------------------------------------------------------- messages --
  handleMessage(session, raw) {
    const msg = decode(raw);
    if (!msg) return;
    const { m, d } = msg;

    if (m === C.PING) { session.send(S.PONG, { t: d?.t ?? 0 }); return; }
    if (m === C.HELLO) { this.handleHello(session, d); return; }

    const p = session.player;
    if (!p) return;                    // everything else needs a character

    switch (m) {
      case C.INPUT:
        this.world.setInput(p, Number(d.dx) || 0, Number(d.dy) || 0);
        break;

      case C.ACTION:
        if (d.kind === 'attack') this.world.primaryAttack(p);
        else if (d.kind === 'interact') this.world.interact(p);
        else if (d.kind === 'ability') {
          const slot = Number(d.slot);
          if (slot >= 0 && slot <= 2) this.world.useAbility(p, slot);
        }
        break;

      case C.INVENTORY: {
        const itemId = Number(d.id);
        if (d.op === 'use') this.world.useItem(p, itemId);
        else if (d.op === 'equip') this.world.equipItem(p, itemId);
        else if (d.op === 'drop') this.world.dropInventoryItem(p, itemId);
        else if (d.op === 'unequip' && ['weapon', 'armor', 'trinket'].includes(d.slot)) {
          this.world.unequipItem(p, d.slot);
        }
        break;
      }

      case C.SHOP: {
        const npcId = Number(d.npcId);
        if (d.op === 'buy') this.world.buy(p, npcId, d.id === 'heal' ? 'heal' : Number(d.id));
        else if (d.op === 'sell') this.world.sell(p, npcId, Number(d.id));
        else if (d.op === 'close') p.openShopId = null;
        break;
      }

      case C.CHAT: {
        const text = cleanChat(d.text);
        if (!text) break;
        for (const s of this.sessions.values()) {
          if (!s.player) continue;
          s.send(S.CHAT, { from: p.name, text, color: CHAT_COLORS[session.colorIdx] });
        }
        break;
      }
    }
  }

  handleHello(session, d) {
    if (session.player) return;
    if (Number(d?.version) !== PROTOCOL_VERSION) {
      session.send(S.ERROR, {
        msg: 'This page is from an older version of Stormhold. Reload the page to update.',
      });
      return;
    }

    const name = cleanName(d.name);
    const cls = CLASSES[d.cls] ? d.cls : 'warrior';

    // One character per name at a time, so nobody plays as someone else.
    for (const s of this.sessions.values()) {
      if (s !== session && s.player && s.player.name.toLowerCase() === name.toLowerCase()) {
        session.send(S.ERROR, { msg: `${name} is already playing. Pick another name.` });
        return;
      }
    }

    const save = d.resume ? this.store.get(name, cls) : null;
    const player = this.world.addPlayer(name, cls, save);
    player.name = name;
    session.player = player;

    session.send(S.WELCOME, {
      you: player.toSelfJSON(),
      seed: this.world.seed,
      motd: save
        ? `Welcome back, ${name}. The keep has not forgotten you.`
        : `Welcome to Aldershade, ${name}. The keep gate is north of the square.`,
      resumed: !!save,
    });
    this.sendLevel(session);
    this.sendInventory(session);

    this.broadcastLog(`${name} the ${CLASSES[cls].name} joins the party.`, 'good');
  }

  // --------------------------------------------------------------- sending --
  sendLevel(session) {
    const p = session.player;
    const level = this.world.levels.get(p.depth);
    if (!level) return;
    session.send(S.LEVEL, {
      depth: level.depth, w: level.w, h: level.h,
      name: level.name, town: !!level.isTown, theme: level.theme,
    });
    this.world.resendLevel(p);
    this.flushTiles(session);
  }

  flushTiles(session) {
    const p = session.player;
    while (p.pendingTiles.length) {
      const chunk = p.pendingTiles.splice(0, TILES_PER_PACKET * 3);
      session.send(S.TILES, { d: chunk });
    }
  }

  sendInventory(session) {
    const p = session.player;
    session.send(S.INV, {
      items: p.inventory.map(i => ({ ...i, desc: describeItem(i) })),
      equipped: Object.fromEntries(Object.entries(p.equipped).map(([k, v]) =>
        [k, v ? { ...v, desc: describeItem(v) } : null])),
      gold: p.gold,
    });
  }

  sendShop(session, npcId, shop, shopName) {
    session.send(S.SHOP_OPEN, {
      npcId, shop, name: shopName,
      stock: this.world.shopStockJSON(shop),
      sell: session.player.inventory.map(i => ({
        id: i.id, name: i.name, icon: i.icon, qty: i.qty,
        price: Math.max(1, Math.floor(i.value * 0.45)), desc: describeItem(i),
      })),
      healCost: 25 + session.player.level * 8,
    });
  }

  broadcastLog(msg, kind = 'info') {
    for (const s of this.sessions.values()) {
      if (s.player) s.send(S.LOG, { msg, kind });
    }
  }

  // ------------------------------------------------------------- main loop --
  tick() {
    const world = this.world;
    world.tick();

    const live = [...this.sessions.values()].filter(s => s.player && s.conn.open);

    // Route this tick's events to the players who should perceive them.
    for (const e of world.events) {
      if (e.t === 'log') {
        for (const s of live) {
          if (e.to && s.player.id !== e.to) continue;
          if (!e.to && e.d != null && s.player.depth !== e.d) continue;
          s.send(S.LOG, { msg: e.msg, kind: e.kind });
        }
        continue;
      }
      if (e.t === 'inv') {
        const s = live.find(x => x.player.id === e.to);
        if (s) this.sendInventory(s);
        continue;
      }
      if (e.t === 'shopopen') {
        const s = live.find(x => x.player.id === e.to);
        if (s) this.sendShop(s, e.npcId, e.shop, e.name);
        continue;
      }
      if (e.t === 'level') {
        const s = live.find(x => x.player.id === e.to);
        if (s) { this.sendLevel(s); this.sendInventory(s); }
        continue;
      }
      if (e.t === 'tile') continue;        // already queued into pendingTiles

      // Positional events: floating text, sounds, visual effects.
      for (const s of live) {
        const p = s.player;
        if (e.d != null && p.depth !== e.d) continue;
        const level = world.levels.get(p.depth);
        if (!level) continue;
        const visible = p.fov.has(e.y * level.w + e.x);
        if (e.t === 'sound') {
          // You hear what is close even through a wall; that is half the tension.
          if (!visible && chebyshev(p.x, p.y, e.x, e.y) > HEAR_RADIUS) continue;
          s.send(S.SOUND, { name: e.name, x: e.x, y: e.y });
        } else if (e.t === 'float') {
          if (!visible) continue;
          s.send(S.FLOAT, { x: e.x, y: e.y, text: e.text, kind: e.kind });
        } else if (e.t === 'fx') {
          if (!visible) continue;
          s.send(S.FX, { kind: e.kind, x: e.x, y: e.y, color: e.color });
        }
      }
    }
    world.events.length = 0;

    // Newly discovered terrain, then the snapshot.
    for (const s of live) {
      this.flushTiles(s);
      const snap = world.snapshotFor(s.player);
      if (snap) s.send(S.STATE, snap);
    }

    // Autosave every half minute so a crashed laptop costs almost nothing.
    const now = Date.now();
    if (now - this.lastSaveAt > 30_000) {
      this.lastSaveAt = now;
      for (const s of live) this.store.put(s.player.name, s.player.cls, s.player.toSaveJSON());
      this.store.flush().catch(() => {});
    }
  }

  async shutdown() {
    for (const s of this.sessions.values()) {
      if (s.player) this.store.put(s.player.name, s.player.cls, s.player.toSaveJSON());
      try { s.conn.close(1001, 'server shutting down'); } catch { /* already gone */ }
    }
    await this.store.flush();
  }
}

export { TICK_MS };
