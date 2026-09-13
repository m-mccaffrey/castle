// Shared between server and browser client. Keep this file dependency-free.

export const PROTOCOL_VERSION = 3;
export const TICK_MS = 50;              // server simulation tick (20 Hz)
export const TILE = 24;                 // render size of one tile, in px

// ---------------------------------------------------------------- terrain --
export const T = {
  VOID: 0,
  FLOOR: 1,
  WALL: 2,
  DOOR: 3,
  DOOR_OPEN: 4,
  STAIRS_DOWN: 5,
  STAIRS_UP: 6,
  WATER: 7,
  RUBBLE: 8,
  GRASS: 9,
  ROAD: 10,
  TREE: 11,
  SHOP_FLOOR: 12,
  ALTAR: 13,
  BRIDGE: 14,
};

// Tiles you cannot walk through.
export const SOLID = new Set([T.VOID, T.WALL, T.DOOR, T.TREE]);
// Tiles you cannot see through.
export const OPAQUE = new Set([T.VOID, T.WALL, T.DOOR, T.TREE]);
// Tiles that cost extra time to cross.
export const SLOW = new Set([T.WATER, T.RUBBLE]);

export function isSolid(t) { return SOLID.has(t); }
export function isOpaque(t) { return OPAQUE.has(t); }

// ---------------------------------------------------------------- classes --
export const CLASSES = {
  warrior: {
    name: 'Warrior',
    blurb: 'Tough and fearless. Wades in swinging and soaks up the hits.',
    hp: 46, mana: 14,
    might: 8, agility: 4, wits: 3,
    hpPerLevel: 9, manaPerLevel: 2,
    startWeapon: 'shortsword', startArmor: 'leather',
    color: '#c8503c',
    abilities: ['cleave', 'bulwark', 'charge'],
  },
  ranger: {
    name: 'Ranger',
    blurb: 'Quick on their feet. Fights at range and never runs dry of arrows.',
    hp: 36, mana: 22,
    might: 5, agility: 8, wits: 5,
    hpPerLevel: 7, manaPerLevel: 4,
    startWeapon: 'shortbow', startArmor: 'leather',
    color: '#4a9c52',
    abilities: ['volley', 'snare', 'dash'],
  },
  mage: {
    name: 'Mage',
    blurb: 'Fragile, but throws fire and stitches the party back together.',
    hp: 28, mana: 40,
    might: 3, agility: 4, wits: 9,
    hpPerLevel: 5, manaPerLevel: 8,
    startWeapon: 'apprenticestaff', startArmor: 'robe',
    color: '#5b7fd4',
    abilities: ['firebolt', 'frostnova', 'mend'],
  },
};

// ------------------------------------------------------------- abilities ---
// cost   : mana
// cd     : cooldown in ms
// range  : tiles (0 = self / melee ring)
export const ABILITIES = {
  cleave:    { name: 'Cleave',      key: '1', cost: 4,  cd: 3500,  range: 1,  desc: 'Strike every enemy around you for 150% damage.' },
  bulwark:   { name: 'Bulwark',     key: '2', cost: 6,  cd: 12000, range: 0,  desc: 'Halve incoming damage for 6 seconds.' },
  charge:    { name: 'Charge',      key: '3', cost: 8,  cd: 9000,  range: 5,  desc: 'Hurtle forward, knocking back and damaging the first enemy hit.' },
  volley:    { name: 'Volley',      key: '1', cost: 5,  cd: 4000,  range: 9,  desc: 'Loose three arrows in a spread.' },
  snare:     { name: 'Snare',       key: '2', cost: 6,  cd: 8000,  range: 7,  desc: 'Pin an enemy in place for 3 seconds.' },
  dash:      { name: 'Dash',        key: '3', cost: 5,  cd: 7000,  range: 4,  desc: 'Leap backwards out of trouble.' },
  firebolt:  { name: 'Firebolt',    key: '1', cost: 7,  cd: 1800,  range: 10, desc: 'Hurl a bolt of fire that bursts on impact.' },
  frostnova: { name: 'Frost Nova',  key: '2', cost: 12, cd: 9000,  range: 3,  desc: 'Freeze and damage everything around you.' },
  mend:      { name: 'Mend',        key: '3', cost: 14, cd: 6000,  range: 4,  desc: 'Heal yourself and every nearby friend.' },
};

// ------------------------------------------------------------------ misc ---
export const DIRS = [
  [0, -1], [1, -1], [1, 0], [1, 1],
  [0, 1], [-1, 1], [-1, 0], [-1, -1],
];

// How far you can see. The client uses these for lighting and the server for
// what it will tell you about, so they must agree.
export const SIGHT_DUNGEON = 8;
export const SIGHT_TOWN = 18;

export const MAX_DEPTH = 20;
export const TOWN_DEPTH = 0;

export const REVIVE_MS = 3000;      // how long you hold the key to raise a friend
export const BLEEDOUT_MS = 75000;   // how long a downed player has before it is fatal
export const DESCEND_MS = 5000;     // countdown once someone calls the party down

export const MAX_LEVEL = 30;

// Cumulative XP needed to *reach* the next level. Tuned so a full descent of
// all twenty floors lands a character somewhere in the low-to-mid twenties,
// leaving room to grow across several evenings of play.
export const XP_TABLE = (() => {
  const t = [0];
  for (let lvl = 1; lvl <= MAX_LEVEL + 1; lvl++) t.push(Math.floor(14 * lvl ** 2.45));
  return t;
})();

export function xpForLevel(level) {
  return XP_TABLE[Math.min(level, XP_TABLE.length - 1)];
}

export function clamp(v, lo, hi) { return v < lo ? lo : v > hi ? hi : v; }
export function dist2(ax, ay, bx, by) { const dx = ax - bx, dy = ay - by; return dx * dx + dy * dy; }
export function chebyshev(ax, ay, bx, by) { return Math.max(Math.abs(ax - bx), Math.abs(ay - by)); }
