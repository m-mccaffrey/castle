"""Press every key the original's help file lists, and see what happens.

The original documents its whole keyboard in CASTLE1.HLP: eight vi keys and
eight keypad keys for movement, shift to run, and a short alphabet of
commands - < > o c s d m i r R x v f g. Those letters are the game's
interface for anyone not using the mouse, and a remake that quietly binds
`s` to "walk south" has taken the Search command away from the player
without ever saying so.

This drives the real play screen: one key press per row, through
App.dispatch, recording the action the client sent, the window that opened
and anything the log said. It does not judge - it prints what happened
beside what the original's help says should happen, and the last column is
the one to read.

    python3 tools/key_audit.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame                                                    # noqa: E402

from tools.playtest import Session, free_port                                # noqa: E402
from tools import crawl as C                                      # noqa: E402

SHIFT = pygame.KMOD_LSHIFT

# (key, mod, label, what CASTLE1.HLP says it does)
COMMANDS = [
    (pygame.K_k, 0, "k", "move north"),
    (pygame.K_u, 0, "u", "move north-east"),
    (pygame.K_l, 0, "l", "move east"),
    (pygame.K_n, 0, "n", "move south-east"),
    (pygame.K_j, 0, "j", "move south"),
    (pygame.K_b, 0, "b", "move south-west"),
    (pygame.K_h, 0, "h", "move west"),
    (pygame.K_y, 0, "y", "move north-west"),
    (pygame.K_KP8, 0, "kp8", "move north"),
    (pygame.K_KP9, 0, "kp9", "move north-east"),
    (pygame.K_KP6, 0, "kp6", "move east"),
    (pygame.K_KP3, 0, "kp3", "move south-east"),
    (pygame.K_KP2, 0, "kp2", "move south"),
    (pygame.K_KP1, 0, "kp1", "move south-west"),
    (pygame.K_KP4, 0, "kp4", "move west"),
    (pygame.K_KP7, 0, "kp7", "move north-west"),
    (pygame.K_l, SHIFT, "shift+l", "run east until something stops you"),
    (pygame.K_COMMA, SHIFT, "<", "climb up stairs"),
    (pygame.K_PERIOD, SHIFT, ">", "climb down stairs"),
    (pygame.K_o, 0, "o", "open a door"),
    (pygame.K_c, 0, "c", "close a door"),
    (pygame.K_s, 0, "s", "search for traps and secret doors"),
    (pygame.K_d, 0, "d", "disarm a trap adjacent to you"),
    (pygame.K_m, 0, "m", "map mode, the whole level at once"),
    (pygame.K_i, 0, "i", "switch to inventory mode"),
    (pygame.K_r, 0, "r", "rest until fully healed"),
    (pygame.K_r, SHIFT, "R", "rest until mana is restored"),
    (pygame.K_x, 0, "x", "look at a site"),
    (pygame.K_v, 0, "v", "view the dungeon by scrolling the screen"),
    (pygame.K_f, 0, "f", "free hand: put one item into the free hand"),
    (pygame.K_g, 0, "g", "get what is underfoot"),
]


def main():
    s = Session(seed=11, port=free_port(), size=(1280, 800))
    C.make_character(s, spell="Spark", difficulty="Intermediate")
    play = s.app.play

    # Watch the wire, not App.act: movement goes straight out through
    # PlayScene.send_action, so a spy on act() sees every command except the
    # sixteen that matter most.
    sent = []
    real = s.app.client.send

    def spy(kind, data):
        if isinstance(data, dict) and "a" in data:
            sent.append(data)
        return real(kind, data)
    s.app.client.send = spy

    rows = []
    for key, mod, label, expected in COMMANDS:
        while s.scene_name() != "PlayScene":
            s.key(pygame.K_ESCAPE)
            s.settle(0.2)
        play.show_overview = False
        play.target_mode = play.cursor = play.pan = None
        before_scene = s.scene_name()
        before_log = len(play.messages)
        before_over = bool(getattr(play, "show_overview", False))
        sent.clear()
        s.key(key, mod=mod)
        s.settle(0.5)
        after = s.scene_name()
        saw = []
        if sent:
            saw.append("act " + ", ".join(sorted({a.get("a", "?") for a in sent})))
        if after != before_scene:
            saw.append(f"opened {after}")
        if bool(getattr(play, "show_overview", False)) != before_over:
            saw.append("map view")
        if play.target_mode:
            saw.append(f"targeting {play.target_mode[0]}")
        new = [m[0] if isinstance(m, tuple) else m
               for m in play.messages[before_log:]]
        if new:
            saw.append("said " + " / ".join(new[:2]))
        rows.append((label, expected, "; ".join(saw) or "NOTHING AT ALL"))

    # The crosshairs are the half of the command set a single key press
    # cannot show: what the original describes is moving them and pressing
    # Return, and the player must not walk while they are up.
    extra = []
    while s.scene_name() != "PlayScene":
        s.key(pygame.K_ESCAPE)
        s.settle(0.2)
    play.pan = play.cursor = play.target_mode = None
    me = dict(play.me() or {})
    sent.clear()
    s.key(pygame.K_x)
    s.key(pygame.K_l)
    s.key(pygame.K_l)
    s.key(pygame.K_j)
    s.settle(0.3)
    moved = [a for a in sent if a.get("a") == "move"]
    at = list(play.cursor or [])
    s.key(pygame.K_RETURN)
    s.settle(0.5)
    look = [a for a in sent if a.get("a") == "examine"]
    extra.append(("x then l l j", "crosshairs move without walking",
                  f"cursor {me.get('x')},{me.get('y')} -> {at}"
                  + ("  AND THE PLAYER WALKED" if moved else "")))
    extra.append(("Return", "looks at the square under the crosshairs",
                  f"sent {look[-1] if look else 'NOTHING'}"))
    extra.append(("", "crosshairs put away afterwards",
                  f"cursor is {play.cursor}"))
    rows += extra

    width = max(len(r[1]) for r in rows)
    print(f"\n{'key':<8} {'the original':<{width}}  what ours does")
    print("-" * (12 + width + 40))
    for label, expected, got in rows:
        flag = "  " if got != "NOTHING AT ALL" else "**"
        print(f"{flag}{label:<6} {expected:<{width}}  {got}")
    dead = [r for r in rows if r[2] == "NOTHING AT ALL"]
    print(f"\n{len(rows)} keys, {len(dead)} do nothing: "
          f"{', '.join(r[0] for r in dead) or 'none'}")
    s.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
