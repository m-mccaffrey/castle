"""Monster behaviour and pathfinding.

Everything here returns the number of ticks the creature's action took, so the
scheduler knows when to give it another go.
"""

import heapq
import random

from ..common.constants import (
    DIRS, T, MOVE_COST, ATTACK_COST, chebyshev, is_solid,
)
from ..common.fov import has_los
from . import combat


def find_path(level, sx, sy, tx, ty, ignore_id=None, max_nodes=700):
    """A*, treating a closed door as passable at a cost: monsters open doors."""
    if (sx, sy) == (tx, ty):
        return []
    start = (sx, sy)
    goal = (tx, ty)
    open_heap = [(0, 0, start)]
    came = {}
    g_score = {start: 0}
    closed = set()
    nodes = 0

    while open_heap and nodes < max_nodes:
        _, g, cur = heapq.heappop(open_heap)
        if cur in closed:
            continue
        closed.add(cur)
        nodes += 1
        if cur == goal:
            path = []
            node = goal
            while node != start:
                path.append(node)
                node = came[node]
            path.reverse()
            return path
        cx, cy = cur
        for dx, dy in DIRS:
            nx, ny = cx + dx, cy + dy
            if not level.in_bounds(nx, ny):
                continue
            nxt = (nx, ny)
            if nxt in closed:
                continue
            tile = level.tiles[ny * level.w + nx]
            if tile in (T.WALL, T.VOID, T.TREE):
                continue
            cost = 1.414 if (dx and dy) else 1.0
            if tile == T.DOOR:
                cost += 1.5
            elif tile in (T.WATER, T.RUBBLE):
                cost += 0.8
            if dx and dy:
                a = level.tiles[cy * level.w + nx]
                b = level.tiles[ny * level.w + cx]
                if is_solid(a) and is_solid(b):
                    continue
            occ = level.occupancy.get(nxt)
            if occ is not None and occ != ignore_id and nxt != goal:
                cost += 4
            ng = g + cost
            if ng < g_score.get(nxt, 1e9):
                g_score[nxt] = ng
                came[nxt] = cur
                h = max(abs(nx - tx), abs(ny - ty))
                heapq.heappush(open_heap, (ng + h, ng, nxt))
    return None


def _acquire(world, level, m):
    best, best_d = None, 1e9
    for a in level.actors.values():
        if a.kind != "player" or a.dead:
            continue
        d = chebyshev(a.x, a.y, m.x, m.y)
        aggro = 12 if m.boss else 9
        if d > aggro:
            continue
        if d < best_d and has_los(level, m.x, m.y, a.x, a.y, aggro + 2):
            best, best_d = a, d
    return best


def _step_toward(world, level, m, tx, ty):
    stale = (m.path is None or not m.path or m.path_goal != (tx, ty))
    if stale:
        m.path = find_path(level, m.x, m.y, tx, ty, ignore_id=m.id)
        m.path_goal = (tx, ty)

    step = m.path[0] if m.path else None
    if step is None:
        dx = (tx > m.x) - (tx < m.x)
        dy = (ty > m.y) - (ty < m.y)
        for a, b in ((dx, dy), (dx, 0), (0, dy)):
            if (a or b) and level.walkable(m.x + a, m.y + b, m.id):
                step = (m.x + a, m.y + b)
                break
        if step is None:
            return m.action_cost(MOVE_COST)

    nx, ny = step
    tile = level.get(nx, ny)
    if tile == T.DOOR:
        world.set_tile(level, nx, ny, T.DOOR_OPEN)
        world.sound("door", nx, ny, level.depth)
        return m.action_cost(MOVE_COST)
    if not level.walkable(nx, ny, m.id):
        m.path = None
        return m.action_cost(MOVE_COST)

    m.facing = _dir_index(nx - m.x, ny - m.y)
    level.move_actor(m, nx, ny)
    if m.path:
        m.path.pop(0)
    extra = 1.5 if tile in (T.WATER, T.RUBBLE) else 1.0
    return int(m.action_cost(MOVE_COST) * extra)


def _step_away(world, level, m, tx, ty):
    dx = (m.x > tx) - (m.x < tx)
    dy = (m.y > ty) - (m.y < ty)
    options = [(dx, dy), (dx, 0), (0, dy), (dy, dx), (-dy, -dx)]
    world.rng.shuffle(options)
    for a, b in options:
        if (a or b) and level.walkable(m.x + a, m.y + b, m.id):
            m.facing = _dir_index(a, b)
            level.move_actor(m, m.x + a, m.y + b)
            return m.action_cost(MOVE_COST)
    return m.action_cost(MOVE_COST)


def _wander(world, level, m):
    dx, dy = world.rng.choice(DIRS)
    if level.walkable(m.x + dx, m.y + dy, m.id):
        m.facing = _dir_index(dx, dy)
        level.move_actor(m, m.x + dx, m.y + dy)
    return int(m.action_cost(MOVE_COST) * 1.5)


def _dir_index(dx, dy):
    best, best_dot = 4, -9.0
    length = (dx * dx + dy * dy) ** 0.5 or 1.0
    ux, uy = dx / length, dy / length
    for i, (ex, ey) in enumerate(DIRS):
        el = (ex * ex + ey * ey) ** 0.5
        dot = (ex / el) * ux + (ey / el) * uy
        if dot > best_dot:
            best, best_dot = i, dot
    return best


def take_turn(world, level, m):
    """One creature's action. Returns the ticks it consumed."""
    if m.dead:
        return 100

    if m.has("held"):
        return m.action_cost(MOVE_COST)
    if m.has("afraid"):
        target = level.actors.get(m.target_id) if m.target_id else None
        if target:
            return _step_away(world, level, m, target.x, target.y)

    if m.tpl.get("regen") and m.hp < m.max_hp:
        m.hp = min(m.max_hp, m.hp + m.tpl["regen"])

    target = level.actors.get(m.target_id) if m.target_id else None
    if target is not None and (target.dead or target.kind != "player"):
        target = None
    if target is None:
        target = _acquire(world, level, m)
        if target is not None:
            m.target_id = target.id
            if not getattr(m, "noticed", False):
                m.noticed = True
                world.sound("notice", m.x, m.y, level.depth)

    if target is None:
        if m.last_seen:
            if chebyshev(m.x, m.y, m.last_seen[0], m.last_seen[1]) <= 1:
                m.last_seen = None
            else:
                return _step_toward(world, level, m, *m.last_seen)
        m.target_id = None
        return _wander(world, level, m)

    dist = chebyshev(m.x, m.y, target.x, target.y)
    los = has_los(level, m.x, m.y, target.x, target.y, 20)
    if los:
        m.last_seen = (target.x, target.y)

    # A cornered rat runs.
    if m.ai == "skittish" and m.hp < m.max_hp * 0.35 and dist <= 4:
        return _step_away(world, level, m, target.x, target.y)

    if dist <= 1:
        m.facing = _dir_index(target.x - m.x, target.y - m.y)
        combat.melee(world, m, target)
        return m.action_cost(ATTACK_COST)

    rng_attack = m.tpl.get("rng", 0)
    if rng_attack and los and dist <= rng_attack and m.ai in ("archer", "caster", "boss"):
        m.facing = _dir_index(target.x - m.x, target.y - m.y)
        world.monster_ranged(level, m, target)
        if dist < 3 and m.ai != "boss":
            _step_away(world, level, m, target.x, target.y)
        return m.action_cost(ATTACK_COST)

    if m.ai == "boss" and world.rng.random() < 0.18 and dist <= 7:
        world.boss_special(level, m, target)
        return m.action_cost(ATTACK_COST)

    if m.ai == "erratic" and world.rng.random() < 0.3:
        return _wander(world, level, m)

    goal = (target.x, target.y) if los else m.last_seen
    if goal:
        return _step_toward(world, level, m, *goal)
    return _wander(world, level, m)
