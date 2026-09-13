// Boot and glue. Builds the artwork, opens the socket, and runs the frame loop.

import { C, S } from '../../shared/protocol.js';
import { xpForLevel, chebyshev } from '../../shared/constants.js';
import { buildSprites } from './sprites.js';
import { Net } from './net.js';
import { Renderer } from './render.js';
import { Input } from './input.js';
import { Audio } from './audio.js';
import { UI } from './ui.js';

buildSprites();

const canvas = document.getElementById('screen');
const renderer = new Renderer(canvas);
const audio = new Audio();
const wsUrl = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`;
const net = new Net(wsUrl);

let joined = false;
let lastShopNpc = null;
let hudAt = 0;
let partyAt = 0;

// --------------------------------------------------------------------- ui ---
const ui = new UI({
  join(name, cls, resume) {
    audio.unlock();
    net.send(C.HELLO, { name, cls, resume, version: 3 });
  },
  chat(text) { net.send(C.CHAT, { text }); },
  ability(slot) { net.send(C.ACTION, { kind: 'ability', slot }); },
  useItem(id) { net.send(C.INVENTORY, { op: 'use', id }); },
  equip(id) { net.send(C.INVENTORY, { op: 'equip', id }); },
  unequip(slot) { net.send(C.INVENTORY, { op: 'unequip', slot }); },
  drop(id) { net.send(C.INVENTORY, { op: 'drop', id }); ui.selectedItem = null; },
  buy(npcId, id) { net.send(C.SHOP, { op: 'buy', npcId, id }); },
  sell(npcId, id) { net.send(C.SHOP, { op: 'sell', npcId, id }); },
  closeShop() { net.send(C.SHOP, { op: 'close' }); },
  refreshShop() {
    // Re-open to pick up the new stock and gold after a transaction.
    if (lastShopNpc != null) net.send(C.ACTION, { kind: 'interact' });
  },
  toggleSound() {
    audio.unlock();
    return audio.toggle();
  },
});

// ------------------------------------------------------------------ input ---
let lastAttackSent = 0;

const input = new Input(canvas, {
  move(dx, dy) { net.send(C.INPUT, { dx, dy }); },
  attack() { sendAttack(); },
  interact() { net.send(C.ACTION, { kind: 'interact' }); },
  ability(slot) { net.send(C.ACTION, { kind: 'ability', slot }); },
  ui(action) {
    switch (action) {
      case 'inventory': ui.toggleModal('pack'); break;
      case 'help': ui.toggleModal('help'); break;
      case 'map': renderer.showMinimap = !renderer.showMinimap; break;
      case 'chat': ui.focusChat(); break;
      case 'closeChat': ui.blurChat(); break;
      case 'close': ui.closeModal(); break;
      case 'quickheal': quickHeal(); break;
      case 'fullscreen': toggleFullscreen(); break;
    }
  },
});

function sendAttack() {
  const now = performance.now();
  if (now - lastAttackSent < 110) return;      // the server gates the real rate
  lastAttackSent = now;
  // Aim at the mouse when it is over the viewport.
  if (input.aim && renderer.you) {
    const dx = input.aim.x - canvas.width / 2;
    const dy = input.aim.y - canvas.height / 2;
    if (Math.hypot(dx, dy) > 18) {
      net.send(C.INPUT, { dx: Math.sign(Math.abs(dx) > Math.abs(dy) * 0.45 ? dx : 0),
                          dy: Math.sign(Math.abs(dy) > Math.abs(dx) * 0.45 ? dy : 0), aimOnly: 1 });
    }
  }
  net.send(C.ACTION, { kind: 'attack' });
}

/** Q: drink the smallest healing potion that will do the job. */
function quickHeal() {
  const pots = ui.invData.items.filter(i => i.use === 'heal');
  if (!pots.length) { ui.log('No healing potions left.', 'warn'); return; }
  const missing = (ui.you?.maxHp ?? 0) - (ui.you?.hp ?? 0);
  pots.sort((a, b) => a.power - b.power);
  const pick = pots.find(p => p.power >= missing) ?? pots[pots.length - 1];
  net.send(C.INVENTORY, { op: 'use', id: pick.id });
}

function toggleFullscreen() {
  if (document.fullscreenElement) document.exitFullscreen?.();
  else document.documentElement.requestFullscreen?.().catch(() => {});
}

// ---------------------------------------------------------------- messages --
net.on('__open', () => ui.netStatus('connected'));
net.on('__close', () => ui.netStatus('disconnected — reconnecting…', true));
net.on('__retry', ({ attempt }) => ui.netStatus(`reconnecting (try ${attempt})…`, true));

net.on(S.ROSTER, (d) => {
  ui.buildLobby(d);
  ui.netStatus('ready');
});

net.on(S.ERROR, (d) => {
  if (joined) ui.log(d.msg, 'warn');
  else ui.lobbyStatus(d.msg);
});

net.on(S.WELCOME, (d) => {
  joined = true;
  ui.enterGame();
  ui.updateHud(withXpFloor(d.you));
  ui.log(d.motd, 'good');
  ui.banner(d.motd, 4000);
  audio.play('join');
});

net.on(S.LEVEL, (d) => {
  renderer.setLevel(d);
  ui.banner(d.town ? 'Aldershade' : d.name, 2600);
  ui.log(d.town ? 'You are back in Aldershade.' : `You enter ${d.name}.`, 'good');
});

net.on(S.TILES, (d) => renderer.applyTiles(d.d));

net.on(S.STATE, (d) => {
  renderer.applyState(d);
  const now = performance.now();
  if (now - hudAt > 90) {
    hudAt = now;
    ui.updateHud(withXpFloor(d.you));
  }
  if (now - partyAt > 260) {
    partyAt = now;
    ui.updateParty(d.party, d.you.id);
  }
  // Countdown banner while the party is travelling.
  if (d.descend) {
    const left = Math.max(0, Math.ceil((d.descend.at - d.t) / 1000));
    ui.banner(d.descend.to === 0
      ? `Climbing back to Aldershade in ${left}…`
      : `Party descends to level ${d.descend.to} in ${left}…`, 0);
  } else if (!renderer.lastDescend) {
    /* nothing to clear */
  } else {
    ui.hideBanner();
  }
  renderer.lastDescend = d.descend;
});

net.on(S.LOG, (d) => ui.log(d.msg, d.kind));
net.on(S.CHAT, (d) => ui.chat(d.from, d.text, d.color));
net.on(S.FLOAT, (d) => renderer.addFloat(d));
net.on(S.FX, (d) => renderer.addEffect(d));

net.on(S.SOUND, (d) => {
  const me = renderer.you && renderer.actors.get(renderer.you.id);
  let pan = 0, dist = 0;
  if (me) {
    pan = Math.max(-1, Math.min(1, (d.x - me.x) / 12));
    dist = Math.min(1, chebyshev(d.x, d.y, me.x, me.y) / 16);
  }
  audio.play(d.name, { pan, dist });
});

net.on(S.INV, (d) => ui.setInventory(d));

net.on(S.SHOP_OPEN, (d) => {
  lastShopNpc = d.npcId;
  ui.showShop(d);
});

net.on(S.DEAD, (d) => ui.log(d.reason ?? 'You have fallen.', 'bad'));

/** The server sends the next threshold; work out the previous one for the bar. */
function withXpFloor(you) {
  return { ...you, xpPrev: you.level > 1 ? xpForLevel(you.level - 1) : 0 };
}

// --------------------------------------------------------------- main loop --
function resize() { renderer.resize(); }
window.addEventListener('resize', resize);
resize();

let last = performance.now();
function frame(now) {
  const dt = Math.min(0.1, (now - last) / 1000);
  last = now;

  // Held attack button keeps swinging.
  if (input.attacking) sendAttack();

  renderer.draw(dt);
  if (net.connected && joined) {
    ui.netStatus(`connected · ${net.latency}ms`);
  }
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);

net.connect();

// Start audio on the first real interaction, as browsers require.
for (const ev of ['click', 'keydown', 'touchstart']) {
  window.addEventListener(ev, () => audio.unlock(), { once: true });
}

// Expose a little state for debugging from the console.
window.stormhold = { net, renderer, ui, audio, input };
