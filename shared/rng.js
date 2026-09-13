// Small, fast, seedable PRNG (mulberry32). Deterministic across server/client.
export class RNG {
  constructor(seed = Date.now()) {
    this.seed = seed >>> 0;
    this.state = this.seed;
  }
  next() {
    this.state = (this.state + 0x6d2b79f5) >>> 0;
    let t = this.state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  }
  /** Integer in [lo, hi] inclusive. */
  int(lo, hi) { return lo + Math.floor(this.next() * (hi - lo + 1)); }
  float(lo, hi) { return lo + this.next() * (hi - lo); }
  chance(p) { return this.next() < p; }
  pick(arr) { return arr[Math.floor(this.next() * arr.length)]; }
  /** Weighted pick: entries are [value, weight]. */
  weighted(entries) {
    let total = 0;
    for (const [, w] of entries) total += w;
    let r = this.next() * total;
    for (const [v, w] of entries) { r -= w; if (r <= 0) return v; }
    return entries[entries.length - 1][0];
  }
  shuffle(arr) {
    for (let i = arr.length - 1; i > 0; i--) {
      const j = Math.floor(this.next() * (i + 1));
      [arr[i], arr[j]] = [arr[j], arr[i]];
    }
    return arr;
  }
  /** Roll NdS, e.g. dice(2, 6). */
  dice(n, sides) {
    let sum = 0;
    for (let i = 0; i < n; i++) sum += this.int(1, sides);
    return sum;
  }
}
