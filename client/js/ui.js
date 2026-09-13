// All DOM work lives here: the lobby, the sidebar, the pack and the shop.
// The renderer owns the canvas; this owns everything around it.

import { ABILITIES, CLASSES, BLEEDOUT_MS } from '../../shared/constants.js';
import { SPRITES } from './sprites.js';

const $ = (id) => document.getElementById(id);

function iconCanvas(name, px = 28) {
  const src = SPRITES.items[name] || SPRITES.items.gold;
  const c = document.createElement('canvas');
  c.width = px; c.height = px;
  const g = c.getContext('2d');
  g.imageSmoothingEnabled = false;
  if (src) g.drawImage(src, 0, 0, px, px);
  return c;
}

export class UI {
  constructor(actions) {
    this.a = actions;              // callbacks into main.js
    this.cls = 'warrior';
    this.selectedItem = null;
    this.shopData = null;
    this.invData = { items: [], equipped: {}, gold: 0 };
    this.openModal = null;
    this.logLines = 0;
    this.bindStatic();
  }

  // ----------------------------------------------------------------- lobby --
  bindStatic() {
    $('enter-btn').addEventListener('click', () => this.submitLobby(false));
    $('name-input').addEventListener('keydown', (e) => {
      if (e.key === 'Enter') this.submitLobby(false);
    });

    $('chat-form').addEventListener('submit', (e) => {
      e.preventDefault();
      const input = $('chat-input');
      const text = input.value.trim();
      input.value = '';
      input.blur();
      if (text) this.a.chat(text);
    });

    $('btn-help').addEventListener('click', () => this.toggleModal('help'));
    $('btn-pack').addEventListener('click', () => this.toggleModal('pack'));
    $('btn-sound').addEventListener('click', (e) => {
      const on = this.a.toggleSound();
      e.currentTarget.style.opacity = on ? '1' : '0.45';
    });

    for (const btn of document.querySelectorAll('[data-close]')) {
      btn.addEventListener('click', () => this.closeModal());
    }
    $('modal-root').addEventListener('click', (e) => {
      if (e.target === $('modal-root')) this.closeModal();
    });
  }

  buildLobby(data) {
    const picker = $('class-picker');
    picker.innerHTML = '';
    const classes = data.classes ?? CLASSES;
    for (const [key, def] of Object.entries(classes)) {
      const card = document.createElement('button');
      card.type = 'button';
      card.className = 'class-card' + (key === this.cls ? ' selected' : '');
      card.innerHTML =
        `<b><span class="class-swatch" style="background:${def.color}"></span>${def.name}</b>` +
        `<span>${def.blurb}</span>`;
      card.addEventListener('click', () => {
        this.cls = key;
        for (const c of picker.children) c.classList.remove('selected');
        card.classList.add('selected');
      });
      picker.appendChild(card);
    }

    // Saved characters, newest-looking first.
    const chars = (data.chars ?? []).filter(c => c.name);
    const box = $('resume-box');
    const list = $('resume-list');
    list.innerHTML = '';
    if (chars.length) {
      box.hidden = false;
      for (const c of chars) {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'resume-btn';
        btn.textContent = `${c.name} — ${CLASSES[c.cls]?.name ?? c.cls}, level ${c.level}` +
          (c.deepest ? ` (reached ${c.deepest})` : '');
        btn.addEventListener('click', () => {
          $('name-input').value = c.name;
          this.cls = c.cls;
          for (const el of $('class-picker').children) el.classList.remove('selected');
          const idx = Object.keys(classes).indexOf(c.cls);
          if (idx >= 0) $('class-picker').children[idx]?.classList.add('selected');
          this.submitLobby(true);
        });
        list.appendChild(btn);
      }
    } else {
      box.hidden = true;
    }

    const online = data.online ?? [];
    $('online-list').textContent = online.length
      ? online.map(o => `${o.name} (${CLASSES[o.cls]?.name ?? o.cls} ${o.lv})`).join(', ')
      : 'Nobody yet — you would be first.';
  }

  submitLobby(resume) {
    const name = $('name-input').value.trim();
    if (!name) {
      this.lobbyStatus('Type a name first.');
      $('name-input').focus();
      return;
    }
    $('enter-btn').disabled = true;
    this.a.join(name, this.cls, resume);
  }

  lobbyStatus(msg) { $('lobby-status').textContent = msg; $('enter-btn').disabled = false; }

  enterGame() {
    $('lobby').hidden = true;
    $('game').hidden = false;
    window.dispatchEvent(new Event('resize'));
  }

  // ------------------------------------------------------------------- hud --
  updateHud(you) {
    this.you = you;
    $('char-name').textContent = you.name;
    $('char-level').textContent = `${CLASSES[you.cls]?.name ?? ''} · Lv ${you.level}`;

    const hpPct = Math.max(0, (you.hp / you.maxHp) * 100);
    $('hp-fill').style.width = `${hpPct}%`;
    $('hp-text').textContent = `${you.hp} / ${you.maxHp}`;
    const mpPct = you.maxMana ? (you.mana / you.maxMana) * 100 : 0;
    $('mp-fill').style.width = `${mpPct}%`;
    $('mp-text').textContent = `${you.mana} / ${you.maxMana}`;

    // XP bar measures progress through the current level, not total.
    const prev = you.xpPrev ?? 0;
    const span = Math.max(1, you.xpNext - prev);
    const pct = Math.max(0, Math.min(100, ((you.xp - prev) / span) * 100));
    $('xp-fill').style.width = `${pct}%`;
    $('xp-text').textContent = you.level >= 30 ? 'max level' : `${you.xp} / ${you.xpNext} xp`;

    $('stat-might').textContent = you.might;
    $('stat-agility').textContent = you.agility;
    $('stat-wits').textContent = you.wits;
    $('stat-armor').textContent = you.armor;
    $('stat-gold').textContent = you.gold;
    $('depth-label').textContent = you.depth === 0 ? 'Aldershade' : `Keep level ${you.depth}`;

    const fx = $('effects');
    fx.innerHTML = '';
    const now = Date.now();
    for (const e of you.effects ?? []) {
      const span2 = document.createElement('span');
      span2.className = 'effect';
      const left = Math.max(0, Math.ceil((e.until - now) / 1000));
      span2.textContent = `${e.type} ${left}s`;
      fx.appendChild(span2);
    }

    // Downed overlay and bleed-out timer.
    const over = $('downed-overlay');
    if (you.downed) {
      over.hidden = false;
      const left = Math.max(0, you.bleedUntil - now);
      $('bleed-bar').firstElementChild.style.width = `${(left / BLEEDOUT_MS) * 100}%`;
    } else {
      over.hidden = true;
    }

    this.updateAbilities(you);
  }

  updateAbilities(you) {
    const host = $('abilities');
    if (!this.abilityEls || this.abilityCls !== you.cls) {
      host.innerHTML = '';
      this.abilityEls = [];
      this.abilityCls = you.cls;
      (you.abilities ?? []).forEach((key, i) => {
        const ab = ABILITIES[key];
        if (!ab) return;
        const el = document.createElement('div');
        el.className = 'ability';
        el.title = ab.desc;
        el.innerHTML = `<span class="cd"></span><span class="key">${i + 1}</span>` +
          `<span class="nm">${ab.name}</span><span class="cost">${ab.cost} mp</span>`;
        el.addEventListener('click', () => this.a.ability(i));
        host.appendChild(el);
        this.abilityEls.push({ el, key, ab });
      });
    }
    const now = Date.now();
    for (const { el, key, ab } of this.abilityEls) {
      const ready = you.cds?.[key] ?? 0;
      const left = ready - now;
      const cd = el.querySelector('.cd');
      if (left > 0) {
        cd.style.width = `${Math.min(100, (left / ab.cd) * 100)}%`;
        el.classList.add('cool');
      } else {
        cd.style.width = '0%';
        el.classList.toggle('cool', you.mana < ab.cost);
      }
    }
  }

  updateParty(party, youId) {
    const host = $('party');
    host.innerHTML = '';
    for (const p of party ?? []) {
      const row = document.createElement('div');
      row.className = 'mate' + (p.dn ? ' down' : '');
      const pct = Math.max(0, (p.hp / p.mhp) * 100);
      row.innerHTML =
        `<span class="dot" style="background:${CLASSES[p.cls]?.color ?? '#888'}"></span>` +
        `<span>${p.name}${p.id === youId ? ' (you)' : ''}</span>` +
        `<span class="mbar"><span style="width:${pct}%"></span></span>` +
        `<span class="muted">${p.dn ? 'down' : p.hp}</span>`;
      host.appendChild(row);
    }
    if (!party?.length) host.innerHTML = '<span class="muted">Alone down here.</span>';
  }

  // ------------------------------------------------------------------- log --
  log(msg, kind = 'info') {
    const box = $('log');
    const line = document.createElement('div');
    line.className = kind;
    line.textContent = msg;
    box.appendChild(line);
    if (++this.logLines > 160) { box.removeChild(box.firstChild); this.logLines--; }
    box.scrollTop = box.scrollHeight;
  }

  chat(from, text, color) {
    const box = $('log');
    const line = document.createElement('div');
    line.className = 'chat';
    const who = document.createElement('b');
    who.style.color = color || '#fff';
    who.textContent = `${from}: `;
    line.appendChild(who);
    line.appendChild(document.createTextNode(text));
    box.appendChild(line);
    box.scrollTop = box.scrollHeight;
  }

  focusChat() { $('chat-input').focus(); }
  blurChat() { $('chat-input').blur(); }

  banner(text, ms = 2600) {
    const el = $('banner');
    el.textContent = text;
    el.hidden = false;
    clearTimeout(this.bannerTimer);
    if (ms > 0) this.bannerTimer = setTimeout(() => { el.hidden = true; }, ms);
  }

  hideBanner() { $('banner').hidden = true; }

  netStatus(text, bad = false) {
    const el = $('netstat');
    el.textContent = text;
    el.classList.toggle('bad', bad);
  }

  // ------------------------------------------------------------- modals ----
  toggleModal(which) {
    if (this.openModal === which) this.closeModal();
    else this.showModal(which);
  }

  showModal(which) {
    this.openModal = which;
    $('modal-root').hidden = false;
    for (const id of ['pack', 'shop', 'help']) $(`${id}-window`).hidden = id !== which;
    if (which === 'pack') this.renderPack();
  }

  closeModal() {
    if (this.openModal === 'shop') this.a.closeShop();
    this.openModal = null;
    $('modal-root').hidden = true;
    for (const id of ['pack', 'shop', 'help']) $(`${id}-window`).hidden = true;
  }

  // --------------------------------------------------------------- pack ----
  setInventory(data) {
    this.invData = data;
    if (this.openModal === 'pack') this.renderPack();
    if (this.openModal === 'shop') this.a.refreshShop();
  }

  renderPack() {
    const slots = $('equip-slots');
    slots.innerHTML = '';
    for (const [slot, label] of [['weapon', 'Weapon'], ['armor', 'Armour'], ['trinket', 'Trinket']]) {
      const it = this.invData.equipped?.[slot];
      const row = document.createElement('button');
      row.type = 'button';
      row.className = 'equip-slot';
      row.innerHTML = `<span class="slotname">${label}</span>`;
      if (it) {
        row.appendChild(iconCanvas(it.icon, 22));
        const nm = document.createElement('span');
        nm.textContent = it.name;
        row.appendChild(nm);
        row.addEventListener('click', () => this.selectItem(it, { equipped: slot }));
      } else {
        const nm = document.createElement('span');
        nm.className = 'muted';
        nm.textContent = '(empty)';
        row.appendChild(nm);
      }
      slots.appendChild(row);
    }

    const grid = $('pack-grid');
    grid.innerHTML = '';
    $('pack-count').textContent = `${this.invData.items.length} / 24 · ${this.invData.gold} gold`;
    for (const it of this.invData.items) {
      const cell = document.createElement('button');
      cell.type = 'button';
      cell.className = `item-cell t${it.tier ?? 1}`;
      if (this.selectedItem?.id === it.id) cell.classList.add('sel');
      cell.title = `${it.name}\n${it.desc ?? ''}`;
      cell.appendChild(iconCanvas(it.icon));
      if (it.qty > 1) {
        const q = document.createElement('span');
        q.className = 'qty';
        q.textContent = it.qty;
        cell.appendChild(q);
      }
      cell.addEventListener('click', () => this.selectItem(it, {}));
      cell.addEventListener('dblclick', () => this.a.useItem(it.id));
      grid.appendChild(cell);
    }
    for (let i = this.invData.items.length; i < 24; i++) {
      const cell = document.createElement('div');
      cell.className = 'item-cell';
      cell.style.opacity = '0.4';
      grid.appendChild(cell);
    }
    if (!this.selectedItem) this.renderItemDetail(null);
  }

  selectItem(it, opts) {
    this.selectedItem = it;
    this.renderItemDetail(it, opts);
    this.renderPackSelection();
  }

  renderPackSelection() {
    for (const cell of $('pack-grid').children) cell.classList?.remove('sel');
    const idx = this.invData.items.findIndex(i => i.id === this.selectedItem?.id);
    if (idx >= 0) $('pack-grid').children[idx]?.classList.add('sel');
  }

  renderItemDetail(it, opts = {}) {
    const box = $('item-detail');
    box.innerHTML = '';
    if (!it) {
      box.innerHTML = '<p class="muted">Click an item to see what it does.</p>';
      return;
    }
    const h = document.createElement('h3');
    h.textContent = it.name;
    box.appendChild(h);

    const icon = iconCanvas(it.icon, 40);
    icon.style.imageRendering = 'pixelated';
    box.appendChild(icon);

    const props = document.createElement('p');
    props.className = 'props';
    props.textContent = it.desc || '—';
    box.appendChild(props);

    const val = document.createElement('p');
    val.className = 'muted';
    val.textContent = `Worth about ${Math.max(1, Math.floor(it.value * 0.45))} gold in town.`;
    box.appendChild(val);

    const actions = document.createElement('div');
    actions.className = 'actions';
    if (opts.equipped) {
      actions.appendChild(this.actionBtn('Take off', () => this.a.unequip(opts.equipped)));
    } else if (it.slot) {
      actions.appendChild(this.actionBtn('Equip', () => this.a.equip(it.id)));
      actions.appendChild(this.actionBtn('Drop', () => this.a.drop(it.id)));
    } else {
      actions.appendChild(this.actionBtn(it.type === 'potion' ? 'Drink' : 'Read', () => this.a.useItem(it.id)));
      actions.appendChild(this.actionBtn('Drop', () => this.a.drop(it.id)));
    }
    box.appendChild(actions);
  }

  actionBtn(label, fn) {
    const b = document.createElement('button');
    b.className = 'btn';
    b.textContent = label;
    b.addEventListener('click', fn);
    return b;
  }

  // --------------------------------------------------------------- shop ----
  showShop(data) {
    this.shopData = data;
    $('shop-title').textContent = data.name;
    this.showModal('shop');

    const stock = $('shop-stock');
    stock.innerHTML = '';
    for (const it of data.stock) {
      const row = document.createElement('button');
      row.type = 'button';
      row.className = 'shop-row';
      row.appendChild(iconCanvas(it.icon, 22));
      const nm = document.createElement('span');
      nm.className = 'nm';
      nm.innerHTML = `${it.name}<small>${it.desc || ''}</small>`;
      row.appendChild(nm);
      const pr = document.createElement('span');
      pr.className = 'pr';
      pr.textContent = `${it.value}g`;
      row.appendChild(pr);
      const affordable = (this.you?.gold ?? 0) >= it.value;
      row.disabled = !affordable;
      row.addEventListener('click', () => this.a.buy(data.npcId, it.id));
      stock.appendChild(row);
    }
    if (!data.stock.length) {
      stock.innerHTML = '<span class="muted">Sold out. Come back after the next trip down.</span>';
    }

    const extra = $('shop-extra');
    extra.innerHTML = '';
    if (data.shop === 'temple') {
      const btn = document.createElement('button');
      btn.className = 'btn';
      btn.style.marginTop = '8px';
      btn.textContent = `Full heal and cure (${data.healCost} gold)`;
      btn.addEventListener('click', () => this.a.buy(data.npcId, 'heal'));
      extra.appendChild(btn);
    }

    const sell = $('shop-sell');
    sell.innerHTML = '';
    for (const it of data.sell) {
      const row = document.createElement('button');
      row.type = 'button';
      row.className = 'shop-row';
      row.appendChild(iconCanvas(it.icon, 22));
      const nm = document.createElement('span');
      nm.className = 'nm';
      nm.innerHTML = `${it.name}${it.qty > 1 ? ` ×${it.qty}` : ''}<small>${it.desc || ''}</small>`;
      row.appendChild(nm);
      const pr = document.createElement('span');
      pr.className = 'pr';
      pr.textContent = `+${it.price}g`;
      row.appendChild(pr);
      row.addEventListener('click', () => this.a.sell(data.npcId, it.id));
      sell.appendChild(row);
    }
    if (!data.sell.length) sell.innerHTML = '<span class="muted">Your pack is empty.</span>';
    $('shop-gold').textContent = this.you?.gold ?? 0;
  }
}
