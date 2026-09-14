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
           (255,255,255), (0,0,0), (189,0,0), (132,0,0)}

def sprites(a, pxy):
    """Colour blobs on the map that are neither terrain nor the player."""
    mv = mapview(a)
    h, w, _ = mv.shape
    flat = mv.reshape(-1, 3)
    keys = (flat[:,0].astype(np.int32) << 16 |
            flat[:,1].astype(np.int32) << 8 | flat[:,2].astype(np.int32))
    bad = np.array(sorted({(r<<16)|(g<<8)|b for r,g,b in TERRAIN}), dtype=np.int32)
    isterrain = np.isin(keys, bad)
    mvi = flat.astype(int)
    sat = (mvi.max(-1) - mvi.min(-1)) > 50
    m = (~isterrain) & sat
    idx = np.nonzero(m)[0]
    if idx.size == 0:
        return []
    ys, xs = idx // w, idx % w
    px, py = pxy
    cells = collections.defaultdict(int)
    for x, y in zip(xs, ys):
        cells[(round((x - px) / TILE), round((y - py) / TILE))] += 1
    return [(c, n) for c, n in cells.items()
            if n >= 30 and max(abs(c[0]), abs(c[1])) > 0]

def note(tag, text):
    if text.strip():
        JOURNAL.write(f"[{tag}] {text.strip()}\n")

def read_log():
    t = drv.log()
    return [l.strip() for l in t.splitlines() if l.strip()]

def read_status():
    t = drv.status()
    hp = re.search(r"HP\s+(\d+)\s*\((\d+)\)", t)
    lvl = re.search(r"Level\s+(\d+)", t)
    tm  = re.search(r"(\d+d,\d\d:\d\d:\d\d)", t)
    mana= re.search(r"Mana\s+(\d+)\s*\((\d+)\)", t)
    return {"hp": int(hp.group(1)) if hp else None,
            "hpmax": int(hp.group(2)) if hp else None,
            "mana": int(mana.group(1)) if mana else None,
            "depth": int(lvl.group(1)) if lvl else None,
            "time": tm.group(1) if tm else None, "raw": t}

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
    play.last_time = None; play.idle = 0
    di = 0
    stuck = 0
    last_lines = []
    stats = {"attacks": 0, "moves": 0, "rests": 0, "descend": 0}
    for step in range(steps):
        a = frame()
        p = player_xy(a)
        if p is None:                       # a dialog is probably up
            note("odd", "player not visible; pressing Return")
            drv.key("Return"); continue
        adj = adjacent_monsters(a, p)
        if adj:
            c = adj[0]
            drv.key(DIRS[c]); stats["attacks"] += 1
        else:
            before = fhash(a)
            drv.key("shift+" + ORDER[di])
            a2 = frame()
            if fhash(a2) == before:
                di = (di + 1) % len(ORDER); stuck += 1
                if stuck % 8 == 7:
                    drv.key(">")            # maybe we are on stairs
                    stats["descend"] += 1
            else:
                stuck = 0; stats["moves"] += 1
        if step % journal_every == 0:
            st = read_status()
            lines = read_log()
            for l in lines:
                if l not in last_lines and len(l) > 3:
                    note("log", l)
            last_lines = lines
            note("stat", f"step={step} hp={st['hp']}/{st['hpmax']} "
                         f"depth={st['depth']} time={st['time']}")
            if st["hp"] and st["hpmax"] and st["hp"] / st["hpmax"] < hp_floor:
                drv.click(264, 59); stats["rests"] += 1   # Rest button
                note("act", "resting")
            # liveness: if the clock has not moved across polls we are wedged
            if st["time"] == play.last_time:
                play.idle += 1
                if play.idle >= 3:
                    note("odd", f"clock stuck at {st['time']}; nudging")
                    drv.key("Escape"); drv.sh("xdotool","mousemove","500","300")
                    di = random.randrange(len(ORDER)); play.idle = 0
            else:
                play.idle = 0
            play.last_time = st["time"]
    return stats
