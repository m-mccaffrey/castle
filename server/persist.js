// Character save/load. Keeps one JSON file so a character survives between
// evenings: each kid keeps their level, gear and gold.

import { readFile, writeFile, rename, mkdir } from 'node:fs/promises';
import { dirname, join } from 'node:path';

export class Store {
  constructor(file) {
    this.file = file;
    this.data = { version: 1, players: {} };
    this.dirty = false;
    this.saving = false;
  }

  static key(name, cls) { return `${String(name).trim().toLowerCase()}:${cls}`; }

  async load() {
    try {
      const raw = await readFile(this.file, 'utf8');
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === 'object' && parsed.players) this.data = parsed;
    } catch (err) {
      if (err.code !== 'ENOENT') {
        console.warn(`[stormhold] could not read ${this.file}: ${err.message}`);
        console.warn('[stormhold] starting with fresh characters (your old file is untouched)');
      }
    }
    return this;
  }

  get(name, cls) { return this.data.players[Store.key(name, cls)] ?? null; }

  put(name, cls, save) {
    this.data.players[Store.key(name, cls)] = { ...save, savedAt: Date.now() };
    this.dirty = true;
  }

  /** Atomic write: a crash mid-save must not eat anyone's character. */
  async flush() {
    if (!this.dirty || this.saving) return;
    this.saving = true;
    this.dirty = false;
    try {
      await mkdir(dirname(this.file), { recursive: true });
      const tmp = `${this.file}.tmp`;
      await writeFile(tmp, JSON.stringify(this.data, null, 2), 'utf8');
      await rename(tmp, this.file);
    } catch (err) {
      console.warn(`[stormhold] save failed: ${err.message}`);
      this.dirty = true;
    } finally {
      this.saving = false;
    }
  }

  roster() {
    return Object.entries(this.data.players).map(([key, p]) => ({
      key, name: p.name, cls: p.cls, level: p.level, deepest: p.deepest ?? 0,
    }));
  }
}

export function defaultStorePath(root) { return join(root, 'data', 'players.json'); }
