// Item definitions and the loot generator.
// Every item in the game is a BASE entry plus (optionally) a prefix and suffix.

let nextItemId = 1;
export function newItemId() { return nextItemId++; }

export const BASES = {
  // ---- weapons: dmg is [count, sides] -------------------------------------
  dagger:          { name: 'Dagger',          type: 'weapon', slot: 'weapon', dmg: [1, 4],  atk: 1, speed: 0.85, value: 12,   depth: 0, icon: 'dagger' },
  shortsword:      { name: 'Short Sword',     type: 'weapon', slot: 'weapon', dmg: [1, 6],  atk: 1, speed: 1.0,  value: 30,   depth: 0, icon: 'sword' },
  mace:            { name: 'Mace',            type: 'weapon', slot: 'weapon', dmg: [1, 7],  atk: 0, speed: 1.1,  value: 42,   depth: 1, icon: 'mace' },
  longsword:       { name: 'Long Sword',      type: 'weapon', slot: 'weapon', dmg: [2, 4],  atk: 2, speed: 1.05, value: 85,   depth: 3, icon: 'sword' },
  waraxe:          { name: 'War Axe',         type: 'weapon', slot: 'weapon', dmg: [1, 10], atk: 1, speed: 1.2,  value: 130,  depth: 5, icon: 'axe' },
  greatsword:      { name: 'Greatsword',      type: 'weapon', slot: 'weapon', dmg: [2, 6],  atk: 2, speed: 1.25, value: 210,  depth: 8, icon: 'sword' },
  runeblade:       { name: 'Rune Blade',      type: 'weapon', slot: 'weapon', dmg: [2, 8],  atk: 4, speed: 1.0,  value: 420,  depth: 12, icon: 'sword' },
  stormaxe:        { name: 'Storm Cleaver',   type: 'weapon', slot: 'weapon', dmg: [3, 7],  atk: 5, speed: 1.15, value: 800,  depth: 16, icon: 'axe' },

  shortbow:        { name: 'Short Bow',       type: 'weapon', slot: 'weapon', dmg: [1, 6],  atk: 2, speed: 1.0,  value: 40,   depth: 0, ranged: true, icon: 'bow' },
  longbow:         { name: 'Long Bow',        type: 'weapon', slot: 'weapon', dmg: [1, 9],  atk: 3, speed: 1.1,  value: 140,  depth: 4, ranged: true, icon: 'bow' },
  huntersbow:      { name: "Hunter's Bow",    type: 'weapon', slot: 'weapon', dmg: [2, 6],  atk: 4, speed: 1.0,  value: 330,  depth: 9, ranged: true, icon: 'bow' },
  tempestbow:      { name: 'Tempest Bow',     type: 'weapon', slot: 'weapon', dmg: [2, 9],  atk: 6, speed: 1.0,  value: 760,  depth: 15, ranged: true, icon: 'bow' },

  apprenticestaff: { name: 'Apprentice Staff', type: 'weapon', slot: 'weapon', dmg: [1, 5], atk: 1, speed: 1.0, value: 35,   depth: 0, ranged: true, magic: true, mana: 4, icon: 'staff' },
  oakstaff:        { name: 'Oak Staff',        type: 'weapon', slot: 'weapon', dmg: [1, 8], atk: 2, speed: 1.0, value: 120,  depth: 4, ranged: true, magic: true, mana: 5, icon: 'staff' },
  emberstaff:      { name: 'Ember Staff',      type: 'weapon', slot: 'weapon', dmg: [2, 6], atk: 4, speed: 1.0, value: 340,  depth: 9, ranged: true, magic: true, mana: 6, icon: 'staff' },
  stormstaff:      { name: 'Storm Staff',      type: 'weapon', slot: 'weapon', dmg: [2, 9], atk: 6, speed: 1.0, value: 780,  depth: 15, ranged: true, magic: true, mana: 7, icon: 'staff' },

  // ---- armor --------------------------------------------------------------
  robe:      { name: 'Cloth Robe',     type: 'armor', slot: 'armor', def: 1,  value: 15,  depth: 0, icon: 'robe' },
  leather:   { name: 'Leather Armor',  type: 'armor', slot: 'armor', def: 3,  value: 45,  depth: 0, icon: 'armor' },
  studded:   { name: 'Studded Leather',type: 'armor', slot: 'armor', def: 5,  value: 95,  depth: 2, icon: 'armor' },
  chain:     { name: 'Chain Mail',     type: 'armor', slot: 'armor', def: 8,  value: 190, depth: 5, icon: 'armor' },
  scale:     { name: 'Scale Mail',     type: 'armor', slot: 'armor', def: 11, value: 340, depth: 9, icon: 'armor' },
  plate:     { name: 'Plate Armor',    type: 'armor', slot: 'armor', def: 15, value: 620, depth: 13, icon: 'armor' },
  stormmail: { name: 'Storm Mail',     type: 'armor', slot: 'armor', def: 20, value: 1100, depth: 17, icon: 'armor' },

  // ---- trinkets -----------------------------------------------------------
  ringmight:  { name: 'Ring of Might',    type: 'trinket', slot: 'trinket', might: 2,  value: 180, depth: 2, icon: 'ring' },
  ringgrace:  { name: 'Ring of Grace',    type: 'trinket', slot: 'trinket', agility: 2, value: 180, depth: 2, icon: 'ring' },
  ringinsight:{ name: 'Ring of Insight',  type: 'trinket', slot: 'trinket', wits: 2,   value: 180, depth: 2, icon: 'ring' },
  amuletvigor:{ name: 'Amulet of Vigor',  type: 'trinket', slot: 'trinket', hp: 18,    value: 260, depth: 4, icon: 'amulet' },
  amuletfocus:{ name: 'Amulet of Focus',  type: 'trinket', slot: 'trinket', mana: 20,  value: 260, depth: 4, icon: 'amulet' },
  amuletward: { name: 'Amulet of Warding',type: 'trinket', slot: 'trinket', def: 4,    value: 380, depth: 7, icon: 'amulet' },
  ringstorm:  { name: 'Ring of the Storm', type: 'trinket', slot: 'trinket', might: 3, agility: 3, wits: 3, value: 900, depth: 14, icon: 'ring' },

  // ---- consumables --------------------------------------------------------
  potheal:   { name: 'Potion of Healing',   type: 'potion', use: 'heal',   power: 35,  value: 40,  depth: 0, stack: true, icon: 'potion_red' },
  potheal2:  { name: 'Draught of Healing',  type: 'potion', use: 'heal',   power: 90,  value: 110, depth: 6, stack: true, icon: 'potion_red' },
  potmana:   { name: 'Potion of Mana',      type: 'potion', use: 'mana',   power: 35,  value: 45,  depth: 0, stack: true, icon: 'potion_blue' },
  potmana2:  { name: 'Draught of Mana',     type: 'potion', use: 'mana',   power: 85,  value: 120, depth: 6, stack: true, icon: 'potion_blue' },
  potspeed:  { name: 'Potion of Swiftness', type: 'potion', use: 'haste',  power: 8000, value: 90, depth: 3, stack: true, icon: 'potion_green' },
  potmight:  { name: 'Potion of Fury',      type: 'potion', use: 'fury',   power: 8000, value: 95, depth: 3, stack: true, icon: 'potion_yellow' },

  scrmap:    { name: 'Scroll of Mapping',   type: 'scroll', use: 'map',      value: 60,  depth: 1, stack: true, icon: 'scroll' },
  scrtele:   { name: 'Scroll of Blink',     type: 'scroll', use: 'teleport', value: 70,  depth: 2, stack: true, icon: 'scroll' },
  scrfire:   { name: 'Scroll of Firestorm', type: 'scroll', use: 'firestorm', power: 30, value: 110, depth: 4, stack: true, icon: 'scroll' },
  scrrecall: { name: 'Scroll of Recall',    type: 'scroll', use: 'recall',   value: 130, depth: 3, stack: true, icon: 'scroll' },
  scrward:   { name: 'Scroll of Warding',   type: 'scroll', use: 'ward',     power: 12000, value: 120, depth: 6, stack: true, icon: 'scroll' },
};

// Quality tiers. `w` is the relative chance of rolling that tier.
const PREFIXES = [
  { key: null,        name: '',           w: 60, mult: 1.0,  value: 1 },
  { key: 'worn',      name: 'Worn',       w: 14, mult: 0.75, value: 0.5, atk: -1, def: -1 },
  { key: 'fine',      name: 'Fine',       w: 14, mult: 1.15, value: 1.8, atk: 1, def: 1 },
  { key: 'masterful', name: 'Masterful',  w: 8,  mult: 1.35, value: 3.2, atk: 2, def: 2 },
  { key: 'runed',     name: 'Runed',      w: 4,  mult: 1.6,  value: 6.0, atk: 3, def: 4 },
];

const SUFFIXES = [
  { key: null,      name: '',              w: 68, value: 1 },
  { key: 'flame',   name: 'of Flame',      w: 8,  value: 2.4, onHit: { type: 'burn', dmg: 4, ms: 3000 }, weaponOnly: true },
  { key: 'frost',   name: 'of Frost',      w: 8,  value: 2.4, onHit: { type: 'chill', slow: 0.5, ms: 2500 }, weaponOnly: true },
  { key: 'leech',   name: 'of Leeching',   w: 5,  value: 3.0, lifesteal: 0.18, weaponOnly: true },
  { key: 'bear',    name: 'of the Bear',   w: 6,  value: 2.0, might: 2 },
  { key: 'fox',     name: 'of the Fox',    w: 6,  value: 2.0, agility: 2 },
  { key: 'owl',     name: 'of the Owl',    w: 6,  value: 2.0, wits: 2 },
  { key: 'ox',      name: 'of the Ox',     w: 6,  value: 2.2, hp: 15 },
];

/** Build a concrete item instance from a base key plus optional affixes. */
export function makeItem(baseKey, prefix = null, suffix = null, qty = 1) {
  const base = BASES[baseKey];
  if (!base) throw new Error(`unknown item base: ${baseKey}`);
  const pre = PREFIXES.find(p => p.key === prefix) || PREFIXES[0];
  const suf = SUFFIXES.find(s => s.key === suffix) || SUFFIXES[0];

  const it = {
    id: newItemId(),
    key: baseKey,
    type: base.type,
    slot: base.slot || null,
    icon: base.icon,
    use: base.use || null,
    power: base.power || 0,
    stack: !!base.stack,
    qty: base.stack ? qty : 1,
    ranged: !!base.ranged,
    magic: !!base.magic,
    manaCost: base.mana || 0,
    speed: base.speed || 1,
    name: [pre.name, base.name, suf.name].filter(Boolean).join(' '),
    prefix: pre.key, suffix: suf.key,
  };

  if (base.dmg) {
    it.dmg = [base.dmg[0], Math.max(2, Math.round(base.dmg[1] * pre.mult))];
  }
  it.atk = (base.atk || 0) + (pre.atk || 0);
  it.def = Math.max(0, Math.round((base.def || 0) * pre.mult)) + (base.def ? (pre.def || 0) : 0);
  it.might = (base.might || 0) + (suf.might || 0);
  it.agility = (base.agility || 0) + (suf.agility || 0);
  it.wits = (base.wits || 0) + (suf.wits || 0);
  it.hp = (base.hp || 0) + (suf.hp || 0);
  it.mana = base.type === 'trinket' ? (base.mana || 0) : 0;
  if (suf.onHit) it.onHit = suf.onHit;
  if (suf.lifesteal) it.lifesteal = suf.lifesteal;
  it.value = Math.max(1, Math.round((base.value || 1) * pre.value * suf.value));
  it.tier = pre.key === 'runed' ? 4 : pre.key === 'masterful' ? 3 : suf.key ? 2 : pre.key === 'fine' ? 2 : 1;
  return it;
}

/** Human-readable one-liner for tooltips. */
export function describeItem(it) {
  const bits = [];
  if (it.dmg) bits.push(`${it.dmg[0]}d${it.dmg[1]} dmg`);
  if (it.atk) bits.push(`${it.atk > 0 ? '+' : ''}${it.atk} acc`);
  if (it.def) bits.push(`+${it.def} armour`);
  if (it.might) bits.push(`+${it.might} might`);
  if (it.agility) bits.push(`+${it.agility} agility`);
  if (it.wits) bits.push(`+${it.wits} wits`);
  if (it.hp) bits.push(`+${it.hp} max hp`);
  if (it.mana) bits.push(`+${it.mana} max mana`);
  if (it.lifesteal) bits.push(`${Math.round(it.lifesteal * 100)}% life steal`);
  if (it.onHit?.type === 'burn') bits.push('sets foes alight');
  if (it.onHit?.type === 'chill') bits.push('chills foes');
  if (it.ranged) bits.push('ranged');
  if (it.use === 'heal') bits.push(`restores ${it.power} hp`);
  if (it.use === 'mana') bits.push(`restores ${it.power} mana`);
  if (it.use === 'haste') bits.push('haste for 8s');
  if (it.use === 'fury') bits.push('+50% damage for 8s');
  if (it.use === 'map') bits.push('reveals the level');
  if (it.use === 'teleport') bits.push('blink somewhere safe');
  if (it.use === 'firestorm') bits.push('burns everything nearby');
  if (it.use === 'recall') bits.push('returns the party to town');
  if (it.use === 'ward') bits.push('halves damage for 12s');
  return bits.join(', ');
}

const LOOT_POOLS = {
  weapon: ['dagger', 'shortsword', 'mace', 'longsword', 'waraxe', 'greatsword', 'runeblade', 'stormaxe',
           'shortbow', 'longbow', 'huntersbow', 'tempestbow',
           'apprenticestaff', 'oakstaff', 'emberstaff', 'stormstaff'],
  armor: ['robe', 'leather', 'studded', 'chain', 'scale', 'plate', 'stormmail'],
  trinket: ['ringmight', 'ringgrace', 'ringinsight', 'amuletvigor', 'amuletfocus', 'amuletward', 'ringstorm'],
  potion: ['potheal', 'potheal2', 'potmana', 'potmana2', 'potspeed', 'potmight'],
  scroll: ['scrmap', 'scrtele', 'scrfire', 'scrrecall', 'scrward'],
};

/** Pick a base appropriate to the depth: mostly on-level, sometimes a treat. */
function pickBase(pool, depth, rng) {
  const eligible = LOOT_POOLS[pool].filter(k => BASES[k].depth <= depth + 2);
  if (!eligible.length) return LOOT_POOLS[pool][0];
  const weighted = eligible.map(k => {
    const gap = depth - BASES[k].depth;
    // Items far below your depth become junk; items just ahead stay exciting.
    const w = gap < 0 ? 0.5 : 1 / (1 + gap * 0.55);
    return [k, w];
  });
  return rng.weighted(weighted);
}

function rollAffix(list, depth, rng, weaponOnly) {
  const entries = list
    .filter(a => !a.weaponOnly || weaponOnly)
    .map(a => {
      let w = a.w;
      // Deeper levels shed the junk tiers and favour the good ones.
      if (a.key === 'worn') w *= Math.max(0.15, 1 - depth * 0.09);
      if (a.key === 'masterful') w *= 1 + depth * 0.07;
      if (a.key === 'runed') w *= 1 + depth * 0.12;
      if (a.key && a.value > 1.5) w *= 1 + depth * 0.05;
      return [a.key, w];
    });
  return rng.weighted(entries);
}

/**
 * Roll a random item for a given depth.
 * `rich` (vaults, bosses) shifts the odds toward gear over consumables.
 */
export function generateItem(depth, rng, rich = false) {
  const pool = rng.weighted(rich
    ? [['weapon', 30], ['armor', 24], ['trinket', 20], ['potion', 18], ['scroll', 12]]
    : [['weapon', 18], ['armor', 15], ['trinket', 7], ['potion', 38], ['scroll', 22]]);

  const baseKey = pickBase(pool, depth, rng);
  const base = BASES[baseKey];

  if (base.stack) {
    const qty = rng.chance(0.25) ? 2 : 1;
    return makeItem(baseKey, null, null, qty);
  }
  const weaponOnly = base.type === 'weapon';
  const prefix = rollAffix(PREFIXES, rich ? depth + 4 : depth, rng, weaponOnly);
  const suffix = rollAffix(SUFFIXES, rich ? depth + 4 : depth, rng, weaponOnly);
  return makeItem(baseKey, prefix, suffix);
}

/** Gold piles scale gently so town prices stay meaningful all the way down. */
export function generateGold(depth, rng) {
  return rng.int(6 + depth * 4, 20 + depth * 14);
}

/** What each shop keeps on the shelves. Restocked when the party returns. */
export function shopStock(shop, rng, partyDepth = 1) {
  const d = Math.max(1, partyDepth);
  const out = [];
  if (shop === 'smith') {
    const seen = new Set();
    for (let i = 0; i < 7; i++) {
      const pool = i < 4 ? 'weapon' : 'armor';
      let key = null;
      // Re-roll a few times so the shelves are not three copies of one item.
      for (let tries = 0; tries < 8; tries++) {
        key = pickBase(pool, d, rng);
        if (!seen.has(key)) break;
      }
      seen.add(key);
      const prefix = rng.chance(0.45) ? rollAffix(PREFIXES, d, rng, pool === 'weapon') : null;
      out.push(makeItem(key, prefix === 'worn' ? null : prefix, null));
    }
  } else if (shop === 'apoth') {
    const staples = ['potheal', 'potmana', 'scrmap', 'scrtele'];
    for (const k of staples) out.push(makeItem(k, null, null, 1));
    const seen = new Set(staples);
    for (let i = 0; i < 3; i++) {
      const pool = rng.chance(0.5) ? 'potion' : 'scroll';
      let key = null;
      for (let tries = 0; tries < 8; tries++) {
        key = pickBase(pool, d, rng);
        if (!seen.has(key)) break;
      }
      seen.add(key);
      out.push(makeItem(key, null, null, 1));
    }
  } else if (shop === 'temple') {
    out.push(makeItem('scrrecall'), makeItem('scrward'));
    if (d >= 4) out.push(makeItem(rng.chance(0.5) ? 'amuletvigor' : 'amuletfocus'));
  }
  return out;
}
