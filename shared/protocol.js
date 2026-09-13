// Message type tags. Kept as short strings: they are readable in a network log
// but still cheap enough to send 20 times a second.

// client -> server
export const C = {
  HELLO: 'hello',       // { name, cls, version }
  INPUT: 'in',          // { dx, dy, seq }        continuous movement intent
  ACTION: 'act',        // { kind, ... }          attack / ability / interact
  INVENTORY: 'inv',     // { op, idx }            equip | use | drop
  SHOP: 'shop',         // { op, id, idx }        buy | sell | close
  CHAT: 'chat',         // { text }
  PING: 'ping',         // { t }
  RESPAWN: 'respawn',   // {}
};

// server -> client
export const S = {
  WELCOME: 'welcome',   // { you, motd, roster }
  ERROR: 'err',         // { msg }
  LEVEL: 'level',       // { depth, w, h, name } new level, wipes client map
  TILES: 'tiles',       // { d: [x,y,tile, ...] } newly discovered terrain
  STATE: 'state',       // { t, actors, items, fx, you, party }  per-tick snapshot
  LOG: 'log',           // { msg, kind }
  FX: 'fx',             // { kind, x, y, color }   transient visual effect
  FLOAT: 'float',       // { x, y, text, kind } floating combat text
  SOUND: 'sound',       // { name, x, y }
  SHOP_OPEN: 'shopopen',// { id, name, stock }
  INV: 'invfull',       // { items, equipped, gold }
  CHAT: 'chat',         // { from, text, color }
  PONG: 'pong',         // { t }
  DEAD: 'dead',         // { reason }
  ROSTER: 'roster',     // { players: [...] }
};

export function encode(type, data) {
  return JSON.stringify({ m: type, d: data });
}

export function decode(raw) {
  try {
    const obj = JSON.parse(raw);
    if (!obj || typeof obj.m !== 'string') return null;
    return { m: obj.m, d: obj.d ?? {} };
  } catch {
    return null;
  }
}
