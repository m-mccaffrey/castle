// Keyboard, mouse and touch. Movement is sent only when the direction changes,
// so holding a key costs one message, not twenty a second.

const MOVE_KEYS = {
  ArrowUp: [0, -1], ArrowDown: [0, 1], ArrowLeft: [-1, 0], ArrowRight: [1, 0],
  KeyW: [0, -1], KeyS: [0, 1], KeyA: [-1, 0], KeyD: [1, 0],
};

export class Input {
  constructor(canvas, handlers) {
    this.canvas = canvas;
    this.h = handlers;             // { move, attack, interact, ability, ui }
    this.held = new Set();
    this.dir = [0, 0];
    this.attacking = false;
    this.aim = null;               // last mouse position in tile space
    this.touchActive = false;

    this.onKeyDown = this.onKeyDown.bind(this);
    this.onKeyUp = this.onKeyUp.bind(this);
    window.addEventListener('keydown', this.onKeyDown);
    window.addEventListener('keyup', this.onKeyUp);
    window.addEventListener('blur', () => this.releaseAll());

    canvas.addEventListener('mousedown', (e) => this.onMouseDown(e));
    canvas.addEventListener('mouseup', () => { this.attacking = false; });
    canvas.addEventListener('mousemove', (e) => this.onMouseMove(e));
    canvas.addEventListener('contextmenu', (e) => e.preventDefault());

    this.setupTouch();
  }

  /** True when a text field has focus, so typing in chat never moves you. */
  get typing() {
    const el = document.activeElement;
    return !!el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA');
  }

  onKeyDown(e) {
    if (this.typing) {
      if (e.code === 'Escape') this.h.ui?.('closeChat');
      return;
    }

    // UI and action keys.
    switch (e.code) {
      case 'Space':    e.preventDefault(); this.attacking = true; this.h.attack?.(); return;
      case 'KeyE':     e.preventDefault(); this.h.interact?.(); return;
      case 'Digit1':   this.h.ability?.(0); return;
      case 'Digit2':   this.h.ability?.(1); return;
      case 'Digit3':   this.h.ability?.(2); return;
      case 'KeyI':     e.preventDefault(); this.h.ui?.('inventory'); return;
      case 'KeyM':     this.h.ui?.('map'); return;
      case 'KeyH':     this.h.ui?.('help'); return;
      case 'KeyQ':     this.h.ui?.('quickheal'); return;
      case 'KeyF':     this.h.ui?.('fullscreen'); return;
      case 'Enter':    e.preventDefault(); this.h.ui?.('chat'); return;
      case 'Escape':   this.h.ui?.('close'); return;
      case 'Slash':    if (e.shiftKey) { this.h.ui?.('help'); return; } break;
    }

    if (MOVE_KEYS[e.code]) {
      e.preventDefault();
      this.held.add(e.code);
      this.updateDir();
    }
  }

  onKeyUp(e) {
    if (e.code === 'Space') this.attacking = false;
    if (MOVE_KEYS[e.code]) { this.held.delete(e.code); this.updateDir(); }
  }

  releaseAll() {
    this.held.clear();
    this.attacking = false;
    this.updateDir();
  }

  updateDir() {
    let dx = 0, dy = 0;
    for (const code of this.held) {
      const [ax, ay] = MOVE_KEYS[code];
      dx += ax; dy += ay;
    }
    dx = Math.sign(dx); dy = Math.sign(dy);
    if (dx !== this.dir[0] || dy !== this.dir[1]) {
      this.dir = [dx, dy];
      this.h.move?.(dx, dy);
    }
  }

  /** Mouse position as an offset in tiles from the centre of the screen. */
  onMouseMove(e) {
    const r = this.canvas.getBoundingClientRect();
    this.aim = {
      x: (e.clientX - r.left) / r.width * this.canvas.width,
      y: (e.clientY - r.top) / r.height * this.canvas.height,
    };
  }

  onMouseDown(e) {
    e.preventDefault();
    this.onMouseMove(e);
    if (e.button === 2) this.h.interact?.();
    else { this.attacking = true; this.h.attack?.(); }
  }

  // ----------------------------------------------------------------- touch --
  // A thumb-stick on the left, action buttons on the right: enough for a kid
  // on a tablet to play properly.
  setupTouch() {
    const stick = document.getElementById('touch-stick');
    const pad = document.getElementById('touch-pad');
    if (!stick || !pad) return;

    let origin = null;
    const knob = stick.querySelector('.knob');

    const setFromTouch = (t) => {
      const r = stick.getBoundingClientRect();
      const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
      const dx = t.clientX - cx, dy = t.clientY - cy;
      const len = Math.hypot(dx, dy);
      const dead = r.width * 0.18;
      if (len < dead) { this.setTouchDir(0, 0); if (knob) knob.style.transform = 'translate(0,0)'; return; }
      const nx = dx / len, ny = dy / len;
      // Snap to one of eight directions.
      const ang = Math.atan2(ny, nx);
      const oct = Math.round(ang / (Math.PI / 4));
      const dirs = [[1, 0], [1, 1], [0, 1], [-1, 1], [-1, 0], [-1, -1], [0, -1], [1, -1]];
      const [sx, sy] = dirs[((oct % 8) + 8) % 8];
      this.setTouchDir(sx, sy);
      if (knob) {
        const max = r.width * 0.28;
        knob.style.transform = `translate(${(dx / len) * Math.min(len, max)}px, ${(dy / len) * Math.min(len, max)}px)`;
      }
    };

    stick.addEventListener('touchstart', (e) => {
      e.preventDefault();
      this.touchActive = true;
      origin = e.touches[0];
      setFromTouch(e.touches[0]);
    }, { passive: false });
    stick.addEventListener('touchmove', (e) => {
      e.preventDefault();
      setFromTouch(e.touches[0]);
    }, { passive: false });
    const end = (e) => {
      e.preventDefault();
      this.setTouchDir(0, 0);
      if (knob) knob.style.transform = 'translate(0,0)';
    };
    stick.addEventListener('touchend', end, { passive: false });
    stick.addEventListener('touchcancel', end, { passive: false });

    for (const btn of pad.querySelectorAll('[data-act]')) {
      btn.addEventListener('touchstart', (e) => {
        e.preventDefault();
        this.touchActive = true;
        const act = btn.dataset.act;
        if (act === 'attack') { this.attacking = true; this.h.attack?.(); }
        else if (act === 'interact') this.h.interact?.();
        else if (act.startsWith('ability')) this.h.ability?.(Number(act.slice(-1)));
        else if (act === 'inventory') this.h.ui?.('inventory');
      }, { passive: false });
      btn.addEventListener('touchend', (e) => {
        e.preventDefault();
        if (btn.dataset.act === 'attack') this.attacking = false;
      }, { passive: false });
    }

    // Reveal the touch controls the moment a finger touches the screen.
    window.addEventListener('touchstart', () => {
      document.body.classList.add('has-touch');
    }, { once: true, passive: true });
  }

  setTouchDir(dx, dy) {
    if (dx !== this.dir[0] || dy !== this.dir[1]) {
      this.dir = [dx, dy];
      this.h.move?.(dx, dy);
    }
  }

  destroy() {
    window.removeEventListener('keydown', this.onKeyDown);
    window.removeEventListener('keyup', this.onKeyUp);
  }
}
