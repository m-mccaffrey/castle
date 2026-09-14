"""Drive Castle of the Winds under Xvfb and read it back as text."""
import subprocess, time, os, re
D = os.path.dirname(os.path.abspath(__file__))
ENV = dict(os.environ, DISPLAY=":77")

def sh(*a, **k):
    return subprocess.run(a, env=ENV, capture_output=True, text=True, **k).stdout

def key(k, n=1, d=0.35):
    for _ in range(n):
        sh("xdotool", "key", k); time.sleep(d)

YOFF = 0           # window sits at 0,0; never move it off-screen (input breaks)

def click(x, y, n=1):
    sh("xdotool", "mousemove", str(x), str(y + YOFF), "click", "--repeat", str(n), "1")
    time.sleep(0.6)

def drag(x1, y1, x2, y2):
    y1 += YOFF; y2 += YOFF
    sh("xdotool", "mousemove", str(x1), str(y1), "mousedown", "1"); time.sleep(0.5)
    sh("xdotool", "mousemove", str((x1+x2)//2), str((y1+y2)//2)); time.sleep(0.4)
    sh("xdotool", "mousemove", str(x2), str(y2)); time.sleep(0.4)
    sh("xdotool", "mouseup", "1"); time.sleep(1.0)

def grab(name="cur"):
    p = f"{D}/shots/{name}.png"
    sh("import", "-window", "root", p)
    return p

def ocr(box, name="ocr", scale=300, psm=6):
    """box = (w,h,x,y)"""
    src = grab("_raw")
    w, h, x, y = box
    out = f"{D}/shots/{name}"
    sh("convert", src, "-crop", f"{w}x{h}+{x}+{y}", "+repage",
       "-colorspace", "Gray", "-scale", f"{scale}%", "-sharpen", "0x1",
       f"{out}.png")
    sh("tesseract", f"{out}.png", out, "--psm", str(psm))
    try:
        return open(f"{out}.txt").read().strip()
    except OSError:
        return ""

LOG_BOX    = (752, 68, 0, 688)
STATUS_BOX = (262, 92, 762, 664)

def log():   return ocr(LOG_BOX, "log", scale=400)
def status():return ocr(STATUS_BOX, "status")

def state():
    s, l = status(), log()
    return s + "\n--- log ---\n" + l

# --- chargen (window 1024x735, dialog as captured in shots/cg0.png) ---
ARROW = {"str": 207, "int": 303, "con": 399, "dex": 495}
SHEET_BOX = (270, 170, 355, 85)

def new_game():
    click(15, 11); click(45, 31); time.sleep(3)

def chargen(alloc, name="Probe", difficulty=None):
    """alloc: dict like {'con': 12}. Spends points, then enters the world."""
    if difficulty:
        click({"easy":107,"inter":187,"hard":306,"expert":399}[difficulty], 365)
    for stat, n in alloc.items():
        for _ in range(n):
            click(ARROW[stat], 83)
    click(130, 408); time.sleep(2)          # OK
    click(479, 381); time.sleep(3)          # Yes, if undistributed prompt
    click(244, 310); time.sleep(4)          # spell list OK
    time.sleep(2)

def sheet():
    click(62, 11); time.sleep(2.5)
    t = ocr(SHEET_BOX, "sheet", scale=300)
    return t

def sheet_close():
    click(205, 345); time.sleep(1.5)
