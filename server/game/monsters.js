// Monster roster. `minD`/`maxD` gate which depths a creature shows up on,
// and `w` is its relative frequency once it is eligible.
//
// speed    = ms to cross one tile
// atkSpeed = ms per attack swing
// ai       = melee | brute | skittish | ranged | caster | summoner

export const MONSTERS = {
  rat:       { name: 'Sewer Rat',       sprite: 'rat',      color: '#8a6a4a', minD: 1, maxD: 4,  w: 10, hp: 9,   atk: 1,  def: 0,  dmg: [1, 3], speed: 320, atkSpeed: 700,  xp: 4,   ai: 'skittish', aggro: 6 },
  bat:       { name: 'Cave Bat',        sprite: 'bat',      color: '#6b5b8a', minD: 1, maxD: 6,  w: 9,  hp: 11,  atk: 3,  def: 1,  dmg: [1, 4], speed: 190, atkSpeed: 600,  xp: 6,   ai: 'erratic',  aggro: 8 },
  kobold:    { name: 'Kobold',          sprite: 'kobold',   color: '#a8632c', minD: 1, maxD: 6,  w: 10, hp: 16,  atk: 3,  def: 2,  dmg: [1, 5], speed: 280, atkSpeed: 750,  xp: 9,   ai: 'melee',    aggro: 8 },
  goblin:    { name: 'Goblin Cutter',   sprite: 'goblin',   color: '#5f8a3a', minD: 2, maxD: 8,  w: 11, hp: 22,  atk: 4,  def: 3,  dmg: [1, 6], speed: 270, atkSpeed: 700,  xp: 13,  ai: 'melee',    aggro: 9 },
  gobarch:   { name: 'Goblin Archer',   sprite: 'gobarch',  color: '#7aa84a', minD: 3, maxD: 10, w: 8,  hp: 18,  atk: 5,  def: 2,  dmg: [1, 6], speed: 290, atkSpeed: 1100, xp: 16,  ai: 'ranged',   aggro: 10, range: 7, projectile: 'arrow' },
  spider:    { name: 'Cellar Spider',   sprite: 'spider',   color: '#4a4a66', minD: 2, maxD: 9,  w: 9,  hp: 20,  atk: 5,  def: 2,  dmg: [1, 6], speed: 230, atkSpeed: 650,  xp: 15,  ai: 'melee',    aggro: 9,  onHit: { type: 'poison', dmg: 3, ms: 4000 } },
  skeleton:  { name: 'Rattling Bones',  sprite: 'skeleton', color: '#d8d2c0', minD: 3, maxD: 11, w: 11, hp: 30,  atk: 6,  def: 5,  dmg: [1, 8], speed: 300, atkSpeed: 800,  xp: 22,  ai: 'melee',    aggro: 9 },
  zombie:    { name: 'Shambler',        sprite: 'zombie',   color: '#6e8a5a', minD: 3, maxD: 12, w: 9,  hp: 46,  atk: 4,  def: 4,  dmg: [2, 4], speed: 480, atkSpeed: 1000, xp: 24,  ai: 'brute',    aggro: 8 },
  wolf:      { name: 'Dire Wolf',       sprite: 'wolf',     color: '#7a7a8a', minD: 4, maxD: 12, w: 10, hp: 34,  atk: 7,  def: 4,  dmg: [1, 9], speed: 180, atkSpeed: 620,  xp: 28,  ai: 'melee',    aggro: 11 },
  orc:       { name: 'Orc Raider',      sprite: 'orc',      color: '#4f7a4a', minD: 5, maxD: 14, w: 11, hp: 52,  atk: 8,  def: 6,  dmg: [2, 5], speed: 280, atkSpeed: 780,  xp: 38,  ai: 'melee',    aggro: 10 },
  cultist:   { name: 'Ash Cultist',     sprite: 'cultist',  color: '#8a3a5a', minD: 5, maxD: 15, w: 8,  hp: 40,  atk: 8,  def: 4,  dmg: [1, 8], speed: 300, atkSpeed: 1300, xp: 42,  ai: 'caster',   aggro: 11, range: 8, projectile: 'bolt' },
  ghoul:     { name: 'Crypt Ghoul',     sprite: 'ghoul',    color: '#9aa87a', minD: 6, maxD: 15, w: 9,  hp: 60,  atk: 9,  def: 6,  dmg: [2, 6], speed: 250, atkSpeed: 720,  xp: 52,  ai: 'melee',    aggro: 10, onHit: { type: 'poison', dmg: 5, ms: 4000 } },
  ogre:      { name: 'Ogre',            sprite: 'ogre',     color: '#a07a4a', minD: 7, maxD: 17, w: 8,  hp: 95,  atk: 9,  def: 8,  dmg: [3, 5], speed: 400, atkSpeed: 1200, xp: 78,  ai: 'brute',    aggro: 9,  knockback: 2 },
  wraith:    { name: 'Pale Wraith',     sprite: 'wraith',   color: '#9fd8e8', minD: 8, maxD: 18, w: 8,  hp: 70,  atk: 12, def: 7,  dmg: [2, 7], speed: 260, atkSpeed: 800,  xp: 86,  ai: 'erratic',  aggro: 12, onHit: { type: 'chill', slow: 0.5, ms: 2500 } },
  troll:     { name: 'Moss Troll',      sprite: 'troll',    color: '#4a7a5a', minD: 10, maxD: 20, w: 8, hp: 150, atk: 11, def: 10, dmg: [3, 6], speed: 340, atkSpeed: 1000, xp: 140, ai: 'brute',    aggro: 10, regen: 3 },
  golem:     { name: 'Stone Golem',     sprite: 'golem',    color: '#8a8a90', minD: 11, maxD: 20, w: 7, hp: 200, atk: 11, def: 16, dmg: [3, 7], speed: 480, atkSpeed: 1300, xp: 175, ai: 'brute',    aggro: 8,  knockback: 2 },
  sorcerer:  { name: 'Storm Sorcerer',  sprite: 'sorcerer', color: '#6a5ad8', minD: 12, maxD: 20, w: 7, hp: 110, atk: 14, def: 8,  dmg: [2, 9], speed: 290, atkSpeed: 1400, xp: 190, ai: 'caster',   aggro: 12, range: 9, projectile: 'bolt' },
  drake:     { name: 'Ember Drake',     sprite: 'drake',    color: '#c8562c', minD: 14, maxD: 20, w: 7, hp: 185, atk: 15, def: 12, dmg: [3, 8], speed: 230, atkSpeed: 900,  xp: 240, ai: 'ranged',   aggro: 13, range: 7, projectile: 'fire', onHit: { type: 'burn', dmg: 6, ms: 3000 } },
  revenant:  { name: 'Iron Revenant',   sprite: 'revenant', color: '#b0b8c8', minD: 16, maxD: 20, w: 7, hp: 260, atk: 17, def: 15, dmg: [4, 7], speed: 300, atkSpeed: 850,  xp: 320, ai: 'melee',    aggro: 12 },

  // ---- bosses -------------------------------------------------------------
  warden: {
    name: 'The Warden of Ash', sprite: 'warden', color: '#e0703c',
    minD: 10, maxD: 10, w: 0, boss: true,
    hp: 620, atk: 14, def: 12, dmg: [3, 8], speed: 280, atkSpeed: 850, xp: 900,
    ai: 'boss', aggro: 18, range: 8, projectile: 'fire', knockback: 2,
    onHit: { type: 'burn', dmg: 8, ms: 3000 },
    title: 'The Warden of Ash stirs in the dark.',
  },
  stormking: {
    name: 'Vaelrik, the Storm-Bound', sprite: 'stormking', color: '#7d6ae8',
    minD: 20, maxD: 20, w: 0, boss: true,
    hp: 1500, atk: 20, def: 18, dmg: [4, 9], speed: 240, atkSpeed: 800, xp: 4000,
    ai: 'boss', aggro: 20, range: 10, projectile: 'bolt', knockback: 3,
    summons: ['revenant', 'wraith'],
    title: 'Vaelrik, the Storm-Bound, rises from his broken throne.',
  },
};

/** Every non-boss monster that can appear at this depth, with weights. */
export function spawnTableFor(depth) {
  const out = [];
  for (const [key, m] of Object.entries(MONSTERS)) {
    if (m.boss || m.w <= 0) continue;
    if (depth < m.minD || depth > m.maxD) continue;
    // Favour creatures near the middle of their band.
    const mid = (m.minD + m.maxD) / 2;
    const falloff = 1 / (1 + Math.abs(depth - mid) * 0.18);
    out.push([key, m.w * falloff]);
  }
  if (!out.length) out.push(['rat', 1]);
  return out;
}

/**
 * Scale a template for depth. Monsters get meaningfully tougher as you
 * descend, but never so fast that a level feels like a wall.
 */
export function scaleMonster(template, depth) {
  const over = Math.max(0, depth - template.minD);
  const f = 1 + over * 0.11;
  return {
    hp: Math.round(template.hp * f),
    atk: template.atk + Math.floor(over * 0.45),
    def: template.def + Math.floor(over * 0.35),
    dmgBonus: Math.floor(over * 0.55),
    xp: Math.round(template.xp * (1 + over * 0.16)),
  };
}
