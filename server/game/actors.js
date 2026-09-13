import { CLASSES, clamp, xpForLevel, MAX_LEVEL } from '../../shared/constants.js';
import { MONSTERS, scaleMonster } from './monsters.js';

let nextActorId = 1;
export function newActorId() { return nextActorId++; }

const INV_SLOTS = 24;

export class Actor {
  constructor(kind, x, y) {
    this.id = newActorId();
    this.kind = kind;            // 'player' | 'monster' | 'npc'
    this.x = x; this.y = y;
    this.px = x; this.py = y;    // previous tile, for client-side tweening
    this.facing = 4;             // index into DIRS; 4 = south
    this.hp = 1; this.maxHp = 1;
    this.nextMoveAt = 0;
    this.nextAttackAt = 0;
    this.effects = [];           // { type, until, ...payload }
    this.dead = false;
  }

  hasEffect(type) { return this.effects.some(e => e.type === type); }
  getEffect(type) { return this.effects.find(e => e.type === type); }

  addEffect(type, ms, payload = {}, now = Date.now()) {
    const existing = this.getEffect(type);
    if (existing) {
      existing.until = Math.max(existing.until, now + ms);
      Object.assign(existing, payload);
      return existing;
    }
    const e = { type, until: now + ms, ...payload };
    this.effects.push(e);
    return e;
  }

  clearEffect(type) { this.effects = this.effects.filter(e => e.type !== type); }

  expireEffects(now) {
    if (!this.effects.length) return;
    this.effects = this.effects.filter(e => e.until > now);
  }

  /** Movement time in ms for one step, after haste/chill and terrain. */
  moveTime(terrainSlow = false) {
    let t = this.baseMoveTime;
    if (this.hasEffect('haste')) t *= 0.6;
    const chill = this.getEffect('chill');
    if (chill) t /= (1 - (chill.slow ?? 0.5));
    if (terrainSlow) t *= 1.6;
    return t;
  }
}

// --------------------------------------------------------------------------

export class Player extends Actor {
  constructor(name, cls, x, y) {
    super('player', x, y);
    const def = CLASSES[cls] || CLASSES.warrior;
    this.name = name;
    this.cls = CLASSES[cls] ? cls : 'warrior';
    this.def = def;
    this.color = def.color;
    this.level = 1;
    this.xp = 0;
    this.gold = 40;
    this.might = def.might;
    this.agility = def.agility;
    this.wits = def.wits;
    this.baseMoveTime = 165;
    this.inventory = [];
    this.equipped = { weapon: null, armor: null, trinket: null };
    this.abilityReady = {};      // ability key -> timestamp
    this.downed = false;
    this.bleedUntil = 0;
    this.reviveProgress = 0;
    this.depth = 0;
    this.memory = new Map();     // depth -> Uint8Array of remembered tiles
    this.fov = new Set();
    this.pendingTiles = [];      // [x, y, tile, ...] queued for the next packet
    this.kills = 0;
    this.deepest = 0;
    this.input = { dx: 0, dy: 0 };
    this.recalc();
    this.hp = this.maxHp;
    this.mana = this.maxMana;
  }

  /** Sum a bonus across all equipped gear. */
  gearBonus(field) {
    let n = 0;
    for (const slot of ['weapon', 'armor', 'trinket']) {
      const it = this.equipped[slot];
      if (it && it[field]) n += it[field];
    }
    return n;
  }

  recalc() {
    const d = this.def;
    const lv = this.level - 1;
    this.maxHp = d.hp + d.hpPerLevel * lv + this.might * 2 + this.gearBonus('hp');
    this.maxMana = d.mana + d.manaPerLevel * lv + this.wits * 2 + this.gearBonus('mana');
    this.accuracy = 2 + Math.floor(this.level / 2) + this.agility + this.gearBonus('atk');
    this.armor = this.gearBonus('def') + Math.floor(this.agility / 3);
    this.hp = Math.min(this.hp, this.maxHp);
    this.mana = Math.min(this.mana ?? this.maxMana, this.maxMana);
  }

  /** Total might/agility/wits including gear, used by combat maths. */
  stat(name) { return this[name] + this.gearBonus(name); }

  weapon() { return this.equipped.weapon; }

  /** Damage roll for a basic attack. */
  rollDamage(rng) {
    const w = this.weapon();
    const base = w?.dmg ? rng.dice(w.dmg[0], w.dmg[1]) : rng.dice(1, 3);
    const scale = w?.magic ? Math.floor(this.stat('wits') * 0.8)
                           : Math.floor(this.stat('might') * 0.8);
    let dmg = base + scale + Math.floor(this.level * 0.4);
    if (this.hasEffect('fury')) dmg = Math.round(dmg * 1.5);
    return Math.max(1, dmg);
  }

  attackTime() {
    const w = this.weapon();
    let t = 520 * (w?.speed ?? 1) - this.stat('agility') * 8;
    if (this.hasEffect('haste')) t *= 0.6;
    return Math.max(180, t);
  }

  addXp(amount) {
    this.xp += amount;
    const gained = [];
    while (this.level < MAX_LEVEL && this.xp >= xpForLevel(this.level)) {
      this.level++;
      // Classes grow into their strengths.
      if (this.cls === 'warrior') { this.might += 2; this.agility += 1; if (this.level % 3 === 0) this.wits += 1; }
      else if (this.cls === 'ranger') { this.agility += 2; this.might += 1; if (this.level % 3 === 0) this.wits += 1; }
      else { this.wits += 2; this.agility += 1; if (this.level % 3 === 0) this.might += 1; }
      const beforeHp = this.maxHp, beforeMana = this.maxMana;
      this.recalc();
      this.hp = Math.min(this.maxHp, this.hp + (this.maxHp - beforeHp) + 12);
      this.mana = Math.min(this.maxMana, this.mana + (this.maxMana - beforeMana) + 8);
      gained.push(this.level);
    }
    return gained;
  }

  /** Add to inventory, stacking consumables. Returns false when full. */
  addItem(item) {
    if (item.stack) {
      const slot = this.inventory.find(i => i.key === item.key && i.stack);
      if (slot) { slot.qty += item.qty; return true; }
    }
    if (this.inventory.length >= INV_SLOTS) return false;
    this.inventory.push(item);
    return true;
  }

  removeItem(itemId, qty = 1) {
    const i = this.inventory.findIndex(it => it.id === itemId);
    if (i < 0) return null;
    const it = this.inventory[i];
    if (it.stack && it.qty > qty) { it.qty -= qty; return { ...it, qty }; }
    this.inventory.splice(i, 1);
    return it;
  }

  equip(itemId) {
    const it = this.inventory.find(i => i.id === itemId);
    if (!it || !it.slot) return null;
    const prev = this.equipped[it.slot];
    this.inventory.splice(this.inventory.indexOf(it), 1);
    this.equipped[it.slot] = it;
    if (prev) this.inventory.push(prev);
    this.recalc();
    return { equipped: it, unequipped: prev };
  }

  unequip(slot) {
    const it = this.equipped[slot];
    if (!it) return null;
    if (this.inventory.length >= INV_SLOTS) return null;
    this.equipped[slot] = null;
    this.inventory.push(it);
    this.recalc();
    return it;
  }

  /** Everything the owning client needs about itself. */
  toSelfJSON() {
    return {
      id: this.id, name: this.name, cls: this.cls, level: this.level,
      hp: Math.ceil(this.hp), maxHp: this.maxHp,
      mana: Math.floor(this.mana), maxMana: this.maxMana,
      xp: this.xp, xpNext: xpForLevel(this.level),
      gold: this.gold, depth: this.depth,
      might: this.stat('might'), agility: this.stat('agility'), wits: this.stat('wits'),
      accuracy: this.accuracy, armor: this.armor,
      downed: this.downed, bleedUntil: this.bleedUntil,
      effects: this.effects.map(e => ({ type: e.type, until: e.until })),
      cds: this.abilityReady,
      abilities: this.def.abilities,
      kills: this.kills, deepest: this.deepest,
    };
  }

  /** The shape persisted to disk between sessions. */
  toSaveJSON() {
    return {
      name: this.name, cls: this.cls, level: this.level, xp: this.xp, gold: this.gold,
      might: this.might, agility: this.agility, wits: this.wits,
      hp: Math.ceil(this.hp), mana: Math.floor(this.mana),
      inventory: this.inventory, equipped: this.equipped,
      kills: this.kills, deepest: this.deepest,
    };
  }

  loadSave(save) {
    if (!save || save.cls !== this.cls) return false;
    this.level = save.level ?? 1;
    this.xp = save.xp ?? 0;
    this.gold = save.gold ?? 40;
    this.might = save.might ?? this.might;
    this.agility = save.agility ?? this.agility;
    this.wits = save.wits ?? this.wits;
    this.inventory = Array.isArray(save.inventory) ? save.inventory : [];
    this.equipped = save.equipped || { weapon: null, armor: null, trinket: null };
    for (const s of ['weapon', 'armor', 'trinket']) {
      if (!this.equipped[s]) this.equipped[s] = null;
    }
    this.kills = save.kills ?? 0;
    this.deepest = save.deepest ?? 0;
    this.recalc();
    this.hp = clamp(save.hp ?? this.maxHp, 1, this.maxHp);
    this.mana = clamp(save.mana ?? this.maxMana, 0, this.maxMana);
    return true;
  }
}

// --------------------------------------------------------------------------

export class Monster extends Actor {
  constructor(key, x, y, depth, elite = false) {
    super('monster', x, y);
    const t = MONSTERS[key];
    if (!t) throw new Error(`unknown monster: ${key}`);
    const s = scaleMonster(t, depth);
    this.key = key;
    this.tpl = t;
    this.name = t.name;
    this.sprite = t.sprite;
    this.color = t.color;
    this.boss = !!t.boss;
    this.elite = elite && !t.boss;

    const eliteMul = this.elite ? 1.5 : 1;
    this.maxHp = Math.round(s.hp * eliteMul);
    this.hp = this.maxHp;
    this.accuracy = s.atk + (this.elite ? 2 : 0);
    this.armor = s.def + (this.elite ? 2 : 0);
    this.dmgBonus = s.dmgBonus + (this.elite ? 2 : 0);
    this.xpValue = Math.round(s.xp * eliteMul);
    this.baseMoveTime = t.speed;
    this.atkSpeed = t.atkSpeed;
    this.ai = t.ai;
    this.aggro = t.aggro;
    this.range = t.range || 1;
    this.depth = depth;
    if (this.elite) this.name = `Elite ${t.name}`;

    this.target = null;       // player id being hunted
    this.lastSeen = null;     // { x, y } last known position of the target
    this.path = null;
    this.pathAt = 0;
    this.wanderDir = null;
    this.nextThinkAt = 0;
    this.nextSpecialAt = 0;
  }

  rollDamage(rng) {
    const d = this.tpl.dmg;
    return Math.max(1, rng.dice(d[0], d[1]) + this.dmgBonus);
  }
}

export function makeMonster(key, x, y, depth, elite = false) {
  return new Monster(key, x, y, depth, elite);
}

export class NPC extends Actor {
  constructor(spec, x, y) {
    super('npc', x, y);
    this.name = spec.name;
    this.sprite = spec.kind;
    this.shop = spec.shop;
    this.color = '#e0c070';
    this.maxHp = this.hp = 1;
    this.baseMoveTime = 9999;
  }
}
