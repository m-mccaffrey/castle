"""A bot that plays Castle of the Winds and writes down everything it sees."""
import time, os, re, sys, collections
import numpy as np
from PIL import Image
import drv

D = os.path.dirname(os.path.abspath(__file__))
JOURNAL = open(f"{D}/journal.txt", "a", buffering=1)

MAP = (0, 44, 1005, 640)          # left, top, right, bottom of the map viewport
TILE = 32
PLAYER_MARKS = [(255,255,0), (0,0,255), (0,0,189)]  # male hair, female dress
# Directions as (dx, dy) -> vi key
DIRS = {(0,-1):"k", (0,1):"j", (-1,0):"h", (1,0):"l",
        (-1,-1):"y", (1,-1):"u", (-1,1):"b", (1,1):"n"}

def frame():
    p = drv.grab("_bot")
    return np.asarray(Image.open(p).convert("RGB"))

def mapview(a):
    l, t, r, b = MAP
    return a[t:b, l:r]

def find(a, rgb, tol=0):
    m = np.all(np.abs(a.astype(int) - np.array(rgb)) <= tol, axis=-1)
    ys, xs = np.nonzero(m)
    return xs, ys

def player_xy(a):
    """Densest 32px cluster of a player-sprite colour."""
    mv = mapview(a)
    best = None
    for rgb in PLAYER_MARKS:
        xs, ys = find(mv, rgb)
        if len(xs) < 20:
            continue
        cells = collections.Counter(zip(xs // TILE, ys // TILE))
        (cx, cy), n = cells.most_common(1)[0]
        if n < 20:
            continue
        sel = (xs // TILE == cx) & (ys // TILE == cy)
        cand = (float(xs[sel].mean()), float(ys[sel].mean()), n)
        if best is None or cand[2] > best[2]:
            best = cand
    return None if best is None else (best[0], best[1])

TERRAIN = {(0,130,0), (0,190,0), (0,134,0), (132,130,0), (132,134,0),
           (132,130,132), (132,134,132), (156,158,156), (173,174,173),
           (181,182,181), (198,199,198), (198,195,198), (247,247,247),
           (255,255,255), (0,0,0), (0,255,0), (0,190,0)}

def sprites(a, pxy):
    """Monsters and items: multi-coloured blobs that are not terrain.

    Terrain stripes are flat blocks of a single colour, so requiring two or
    more distinct non-terrain colours in a tile separates sprites from ground.
    """
    mv = mapview(a)
    h, w, _ = mv.shape
    flat = mv.reshape(-1, 3).astype(np.int32)
    keys = (flat[:, 0] << 16) | (flat[:, 1] << 8) | flat[:, 2]
    bad = np.array(sorted({(r << 16) | (g << 8) | b for r, g, b in TERRAIN}),
                   dtype=np.int32)
    sat = (flat.max(-1) - flat.min(-1)) > 50
    idx = np.nonzero((~np.isin(keys, bad)) & sat)[0]
    if idx.size == 0:
        return []
    ys, xs = idx // w, idx % w
    px, py = pxy
    cells = collections.defaultdict(list)
    for x, y, k in zip(xs, ys, keys[idx]):
        cells[(round((x - px) / TILE), round((y - py) / TILE))].append(int(k))
    out = []
    for c, ks in cells.items():
        if max(abs(c[0]), abs(c[1])) == 0:
            continue
        if len(ks) >= 40 and len(set(ks)) >= 2:
            out.append((c, len(ks)))
    return out

def note(tag, text):
    if text.strip():
        JOURNAL.write(f"[{tag}] {text.strip()}\n")

def read_log():
    t = drv.log()
    return [l.strip() for l in t.splitlines() if l.strip()]

def _num(x):
    x = x.translate(str.maketrans({"i":"1","I":"1","l":"1","O":"0"}))
    try:
        return int(x)
    except ValueError:
        return None

def read_status():
    t = drv.status()
    hp = re.search(r"HP\s+(\d+)\s*\((\d+)\)", t)
    lvl = re.search(r"Level\s+([0-9iIlO]+)", t)
    tm = None
    for line in t.splitlines():
        if "ime" in line:
            digits = "".join(c for c in line if c in "0123456789:")
            parts = [p for p in digits.split(":") if p]
            if len(parts) >= 3:
                tm = parts[-3:]
            break
    mana= re.search(r"Mana\s+(\d+)\s*\((\d+)\)", t)
    return {"hp": int(hp.group(1)) if hp else None,
            "hpmax": int(hp.group(2)) if hp else None,
            "mana": int(mana.group(1)) if mana else None,
            "depth": _num(lvl.group(1)) if lvl else None,
            "time": (int(tm[0]) * 3600 + int(tm[1]) * 60 + int(tm[2]))
                    if tm else None, "raw": t}

import hashlib, random

def fhash(a):
    return hashlib.md5(mapview(a).tobytes()).hexdigest()

ORDER = ["k","l","j","h","u","n","b","y"]

def adjacent_monsters(a, p):
    out = []
    for c, n in sprites(a, p):
        if max(abs(c[0]), abs(c[1])) == 1:
            out.append(c)
    return out

def play(steps=200, journal_every=10, hp_floor=0.45):
    """Single-step exploration: run commands proved unreliable here."""
    di = 0
    last_lines = []
    stats = {"attacks": 0, "moves": 0, "blocked": 0, "rests": 0}
    for step in range(steps):
        a = frame()
        p = player_xy(a)
        if p is None:
            drv.key("Escape"); drv.key("Return")
            note("odd", "player not visible")
            continue
        adj = adjacent_monsters(a, p)
        if adj:
            drv.key(DIRS[adj[0]], d=0.5)
            stats["attacks"] += 1
        else:
            before = fhash(a)
            drv.key(ORDER[di], d=0.45)
            if fhash(frame()) == before:
                stats["blocked"] += 1
                di = (di + 1) % len(ORDER)
                if stats["blocked"] % 11 == 10:
                    drv.key(">")
            else:
                stats["moves"] += 1
                if random.random() < 0.12:        # wander a little
                    di = (di + 1) % len(ORDER)
        if step % journal_every == 0:
            st = read_status()
            for l in read_log():
                if l not in last_lines and len(l) > 3:
                    note("log", l)
            last_lines = read_log()
            note("stat", f"step={step} hp={st['hp']}/{st['hpmax']} "
                         f"depth={st['depth']} t={st['time']} {stats}")
            if st["hp"] and st["hpmax"] and st["hp"] / st["hpmax"] < hp_floor:
                drv.click(264, 59); stats["rests"] += 1
                note("act", "resting")
    return stats
