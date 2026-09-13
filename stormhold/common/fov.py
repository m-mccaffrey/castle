"""Recursive shadowcasting. Used by the server to decide what each character
can see, and by the client to decide what to light up."""

from .constants import is_opaque

_MULT = (
    (1, 0, 0, -1, -1, 0, 0, 1),
    (0, 1, -1, 0, 0, -1, 1, 0),
    (0, 1, 1, 0, 0, -1, -1, 0),
    (1, 0, 0, 1, -1, 0, 0, -1),
)


def compute_fov(level, cx, cy, radius, out=None):
    """Fill and return a set of tile indices visible from (cx, cy)."""
    if out is None:
        out = set()
    else:
        out.clear()
    out.add(cy * level.w + cx)
    for octant in range(8):
        _cast(level, out, cx, cy, 1, 1.0, 0.0, radius,
              _MULT[0][octant], _MULT[1][octant],
              _MULT[2][octant], _MULT[3][octant])
    return out


def _cast(level, out, cx, cy, row, start, end, radius, xx, xy, yx, yy):
    if start < end:
        return
    r2 = radius * radius
    new_start = start
    for j in range(row, radius + 1):
        blocked = False
        dy = -j
        for dx in range(-j, 1):
            x = cx + dx * xx + dy * xy
            y = cy + dx * yx + dy * yy
            l_slope = (dx - 0.5) / (dy + 0.5)
            r_slope = (dx + 0.5) / (dy - 0.5)
            if start < r_slope:
                continue
            if end > l_slope:
                break

            in_bounds = 0 <= x < level.w and 0 <= y < level.h
            if dx * dx + dy * dy <= r2 and in_bounds:
                out.add(y * level.w + x)

            solid = (not in_bounds) or is_opaque(level.tiles[y * level.w + x])
            if blocked:
                if solid:
                    new_start = r_slope
                    continue
                blocked = False
                start = new_start
            elif solid and j < radius:
                blocked = True
                _cast(level, out, cx, cy, j + 1, start, l_slope, radius, xx, xy, yx, yy)
                new_start = r_slope
        if blocked:
            break


def has_los(level, x0, y0, x1, y1, max_dist=999):
    """Bresenham line of sight, ignoring whether the endpoints themselves block."""
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    x, y = x0, y0
    steps = 0
    while not (x == x1 and y == y1):
        steps += 1
        if steps > max_dist:
            return False
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy
        if x == x1 and y == y1:
            break
        if is_opaque(level.tiles[y * level.w + x]):
            return False
    return True


def line_between(x0, y0, x1, y1):
    """Every tile from a to b, excluding the start. Used for bolts and arrows."""
    pts = []
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    x, y = x0, y0
    for _ in range(512):
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy
        pts.append((x, y))
    return pts
