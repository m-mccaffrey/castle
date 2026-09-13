import { isOpaque } from './constants.js';

// Recursive shadowcasting, one pass per octant.
const MULT = [
  [1, 0, 0, -1, -1, 0, 0, 1],
  [0, 1, -1, 0, 0, -1, 1, 0],
  [0, 1, 1, 0, 0, -1, -1, 0],
  [1, 0, 0, 1, -1, 0, 0, -1],
];

/**
 * Fill `out` (a Set of tile indices) with everything visible from (cx,cy).
 * The origin tile is always visible.
 */
export function computeFOV(level, cx, cy, radius, out) {
  out.clear();
  out.add(cy * level.w + cx);
  for (let oct = 0; oct < 8; oct++) {
    castLight(level, out, cx, cy, 1, 1.0, 0.0, radius,
      MULT[0][oct], MULT[1][oct], MULT[2][oct], MULT[3][oct]);
  }
  return out;
}

function castLight(level, out, cx, cy, row, start, end, radius, xx, xy, yx, yy) {
  if (start < end) return;
  const r2 = radius * radius;
  let newStart = start;

  for (let j = row; j <= radius; j++) {
    let blocked = false;
    const dy = -j;
    for (let dx = -j; dx <= 0; dx++) {
      const X = cx + dx * xx + dy * xy;
      const Y = cy + dx * yx + dy * yy;
      const lSlope = (dx - 0.5) / (dy + 0.5);
      const rSlope = (dx + 0.5) / (dy - 0.5);

      if (start < rSlope) continue;
      if (end > lSlope) break;

      const inBounds = X >= 0 && Y >= 0 && X < level.w && Y < level.h;
      if (dx * dx + dy * dy <= r2 && inBounds) out.add(Y * level.w + X);

      const solid = !inBounds || isOpaque(level.tiles[Y * level.w + X]);
      if (blocked) {
        if (solid) { newStart = rSlope; continue; }
        blocked = false;
        start = newStart;
      } else if (solid && j < radius) {
        blocked = true;
        castLight(level, out, cx, cy, j + 1, start, lSlope, radius, xx, xy, yx, yy);
        newStart = rSlope;
      }
    }
    if (blocked) break;
  }
}

/** Bresenham line-of-sight test used by monster AI. Endpoints may be solid. */
export function hasLOS(level, x0, y0, x1, y1, maxDist = 999) {
  let dx = Math.abs(x1 - x0), dy = Math.abs(y1 - y0);
  const sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1;
  let err = dx - dy, x = x0, y = y0, steps = 0;

  while (!(x === x1 && y === y1)) {
    if (++steps > maxDist) return false;
    const e2 = 2 * err;
    if (e2 > -dy) { err -= dy; x += sx; }
    if (e2 < dx) { err += dx; y += sy; }
    if (x === x1 && y === y1) break;
    if (isOpaque(level.tiles[y * level.w + x])) return false;
  }
  return true;
}

/** All tiles on the line from a to b, excluding the start. Used for projectiles. */
export function lineTo(x0, y0, x1, y1) {
  const pts = [];
  let dx = Math.abs(x1 - x0), dy = Math.abs(y1 - y0);
  const sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1;
  let err = dx - dy, x = x0, y = y0;
  for (let guard = 0; guard < 512; guard++) {
    if (x === x1 && y === y1) break;
    const e2 = 2 * err;
    if (e2 > -dy) { err -= dy; x += sx; }
    if (e2 < dx) { err += dx; y += sy; }
    pts.push([x, y]);
  }
  return pts;
}
