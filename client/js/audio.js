// Every sound is synthesised in the browser with WebAudio: short square- and
// triangle-wave blips, plus filtered noise for impacts. No audio files.

const SPECS = {
  // name:      [waveform, startHz, endHz, seconds, gain, (optional) noise]
  step:         ['triangle', 110, 80, 0.05, 0.05],
  splash:       ['noise', 600, 200, 0.18, 0.10],
  swing:        ['noise', 1800, 500, 0.09, 0.08],
  hit:          ['square', 220, 90, 0.09, 0.16],
  crit:         ['square', 420, 110, 0.16, 0.22],
  hurt:         ['sawtooth', 180, 70, 0.14, 0.18],
  miss:         ['noise', 900, 1400, 0.06, 0.05],
  die:          ['sawtooth', 260, 45, 0.30, 0.18],
  bossdie:      ['sawtooth', 150, 30, 0.90, 0.28],
  notice:       ['square', 300, 520, 0.10, 0.10],
  shoot:        ['triangle', 900, 300, 0.10, 0.10],
  door:         ['noise', 320, 120, 0.22, 0.10],
  gold:         ['square', 1050, 1600, 0.10, 0.12],
  pickup:       ['triangle', 700, 1100, 0.09, 0.10],
  drop:         ['triangle', 400, 200, 0.08, 0.08],
  equip:        ['square', 520, 760, 0.09, 0.11],
  buy:          ['square', 880, 1320, 0.12, 0.12],
  deny:         ['square', 200, 140, 0.16, 0.12],
  drink:        ['triangle', 300, 700, 0.16, 0.12],
  heal:         ['triangle', 660, 1320, 0.26, 0.14],
  buff:         ['triangle', 440, 880, 0.20, 0.12],
  magic:        ['triangle', 520, 1560, 0.28, 0.13],
  blink:        ['triangle', 1400, 400, 0.16, 0.12],
  fireball:     ['noise', 900, 150, 0.30, 0.16],
  frost:        ['triangle', 1600, 500, 0.30, 0.13],
  cleave:       ['noise', 1400, 300, 0.18, 0.14],
  charge:       ['sawtooth', 140, 420, 0.22, 0.14],
  dash:         ['triangle', 800, 1600, 0.12, 0.10],
  snare:        ['square', 700, 180, 0.18, 0.12],
  stairs:       ['triangle', 400, 160, 0.30, 0.13],
  down:         ['sawtooth', 300, 60, 0.45, 0.24],
  revive:       ['triangle', 440, 1100, 0.40, 0.18],
  channel:      ['triangle', 300, 420, 0.20, 0.08],
  summon:       ['sawtooth', 200, 600, 0.35, 0.18],
  slam:         ['noise', 300, 60, 0.35, 0.24],
  firehit:      ['noise', 700, 120, 0.18, 0.12],
  magichit:     ['triangle', 900, 300, 0.14, 0.10],
};

// Little arpeggios for the moments that deserve one.
const JINGLES = {
  levelup: [[660, 0.09], [880, 0.09], [1100, 0.14], [1320, 0.20]],
  join:    [[520, 0.08], [660, 0.08], [880, 0.14]],
  victory: [[523, 0.14], [659, 0.14], [784, 0.14], [1047, 0.36]],
};

// Sounds that repeat constantly get a minimum gap so they never buzz.
const THROTTLE = { step: 90, splash: 140, swing: 60, hit: 40, miss: 70 };

export class Audio {
  constructor() {
    this.ctx = null;
    this.master = null;
    this.enabled = true;
    this.volume = 0.7;
    this.lastPlayed = new Map();
    this.noiseBuffer = null;
  }

  /** Browsers require a user gesture before audio can start. */
  unlock() {
    if (this.ctx) { if (this.ctx.state === 'suspended') this.ctx.resume(); return; }
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) { this.enabled = false; return; }
    this.ctx = new Ctx();
    this.master = this.ctx.createGain();
    this.master.gain.value = this.volume;
    this.master.connect(this.ctx.destination);

    // One second of white noise, reused for every impact sound.
    const len = this.ctx.sampleRate;
    const buf = this.ctx.createBuffer(1, len, this.ctx.sampleRate);
    const data = buf.getChannelData(0);
    for (let i = 0; i < len; i++) data[i] = Math.random() * 2 - 1;
    this.noiseBuffer = buf;
  }

  setVolume(v) {
    this.volume = Math.max(0, Math.min(1, v));
    if (this.master) this.master.gain.value = this.volume;
  }

  toggle() {
    this.enabled = !this.enabled;
    return this.enabled;
  }

  /**
   * Play a named sound. `pan` is -1..1 and `dist` 0..1 (1 = far away), both
   * derived from where the sound happened relative to your character.
   */
  play(name, { pan = 0, dist = 0 } = {}) {
    if (!this.enabled || !this.ctx) return;
    if (this.ctx.state === 'suspended') this.ctx.resume();

    const now = this.ctx.currentTime;
    const gap = THROTTLE[name];
    if (gap) {
      const last = this.lastPlayed.get(name) ?? 0;
      if (performance.now() - last < gap) return;
      this.lastPlayed.set(name, performance.now());
    }

    if (JINGLES[name]) { this.jingle(JINGLES[name], pan, dist); return; }
    const spec = SPECS[name];
    if (!spec) return;

    const [wave, f0, f1, dur, gain] = spec;
    const falloff = Math.max(0.12, 1 - dist);
    const out = this.panner(pan);

    const env = this.ctx.createGain();
    env.gain.setValueAtTime(0.0001, now);
    env.gain.exponentialRampToValueAtTime(Math.max(0.0002, gain * falloff), now + 0.008);
    env.gain.exponentialRampToValueAtTime(0.0001, now + dur);
    env.connect(out);

    if (wave === 'noise') {
      const src = this.ctx.createBufferSource();
      src.buffer = this.noiseBuffer;
      const filter = this.ctx.createBiquadFilter();
      filter.type = 'bandpass';
      filter.Q.value = 1.2;
      filter.frequency.setValueAtTime(f0, now);
      filter.frequency.exponentialRampToValueAtTime(Math.max(40, f1), now + dur);
      src.connect(filter).connect(env);
      src.start(now);
      src.stop(now + dur + 0.02);
    } else {
      const osc = this.ctx.createOscillator();
      osc.type = wave;
      osc.frequency.setValueAtTime(f0, now);
      osc.frequency.exponentialRampToValueAtTime(Math.max(20, f1), now + dur);
      osc.connect(env);
      osc.start(now);
      osc.stop(now + dur + 0.02);
    }
  }

  jingle(notes, pan = 0, dist = 0) {
    if (!this.ctx) return;
    let t = this.ctx.currentTime;
    const out = this.panner(pan);
    const falloff = Math.max(0.2, 1 - dist);
    for (const [freq, dur] of notes) {
      const osc = this.ctx.createOscillator();
      const env = this.ctx.createGain();
      osc.type = 'square';
      osc.frequency.setValueAtTime(freq, t);
      env.gain.setValueAtTime(0.0001, t);
      env.gain.exponentialRampToValueAtTime(0.14 * falloff, t + 0.01);
      env.gain.exponentialRampToValueAtTime(0.0001, t + dur);
      osc.connect(env).connect(out);
      osc.start(t);
      osc.stop(t + dur + 0.02);
      t += dur * 0.85;
    }
  }

  panner(pan) {
    if (!this.ctx.createStereoPanner) return this.master;
    const node = this.ctx.createStereoPanner();
    node.pan.value = Math.max(-1, Math.min(1, pan));
    node.connect(this.master);
    return node;
  }
}
