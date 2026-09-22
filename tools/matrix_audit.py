"""An exhaustive drag matrix across every inventory location at once.

"The bots should be very exhaustive for everything... maybe because I'm
using all of the features and they don't." interaction_audit.py checks one
drag at a time, in isolation, with an empty pack. Every inventory bug found
by actual play this pass (duplication, refused drops, stuck items) came from
a *combination*: a full pack, a belt with something already in it, a cursed
item, two items fighting for one slot. This drives every pairwise
combination of {floor, pack, belt, free hand, each body slot} at once,
under both an empty and a completely full pack, and checks a single
invariant after every drag: nothing was created, and nothing was destroyed.

    python3 tools/matrix_audit.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame                                                    # noqa: E402

from stormhold.game.items import Item                             # noqa: E402
from tools.interaction_audit import Bench                         # noqa: E402


# Every location a thing can end up, and one item that fits it. "body:X"
# means the doll slot X; "belt" means a belt worn at the waist; "freehand"
# is the free hand slot itself (not a container).
LOCATIONS = [
    ("floor",        "potion_heal"),
    ("pack",         "potion_heal"),
    ("belt",         "potion_heal"),
    ("freehand",     "potion_heal"),
    ("body:head",    "cap"),
    ("body:torso",   "leather"),
    ("body:weapon",  "dagger"),
    ("body:ring_left", "ring_might"),
]


class MatrixBench(Bench):

    def fill_pack_to_bursting(self):
        """As full as the pack goes, so a drag that only works when there
        is room is exercised right alongside one that must work anyway."""
        srv, p = self.s.app.server, self.s.me()
        with srv.lock:
            p.inventory = []
            while True:
                it = Item("dagger")
                it.known = True
                if not p.add_item(it):
                    break
            srv.send_inventory(srv.session_for(p.id))
        self.s.settle(0.3)
        return len(self.s.me().inventory)

    def all_item_ids(self):
        """Every item id anywhere the party can see it - pack, worn,
        belt/quiver contents, free hand, and the floor underfoot. Used
        before and after a drag: the set must be exactly the same size,
        or something got duplicated or swallowed."""
        p = self.s.me()
        ids = []
        for it in p.inventory:
            ids.append(it.id)
            for sub in (it.contents or []):
                ids.append(sub.id)
        for slot, it in p.equipment.items():
            if it is None:
                continue
            ids.append(it.id)
            for sub in (it.contents or []):
                ids.append(sub.id)
        lvl = self.s.level()
        for stack in lvl.ground.get((p.x, p.y), []):
            ids.append(stack.id)
            for sub in (stack.contents or []):
                ids.append(sub.id)
        return ids

    def place_source(self, kind, key):
        """Get one of `key` into the given source location, direct through
        the server rather than by dragging it there through the pack -
        setting up a "pack full of daggers, plus a potion worn in the free
        hand" starting position is not itself the thing under test, and
        routing it through a pack that may deliberately have no room left
        only breaks the setup, not the drag being tested. Returns (item,
        the scene once the state is in place)."""
        srv, p = self.s.app.server, self.s.me()
        it = Item(key)
        it.known = True
        with srv.lock:
            if kind == "floor":
                lvl = self.s.level()
                lvl.add_ground_item(p.x, p.y, it)
            elif kind == "pack":
                p.add_item(it, force=True)
            elif kind == "belt":
                belt = Item("belt3")
                belt.known = True
                p.equipment["waist"] = belt
                belt.contents.append(it)
            elif kind == "freehand":
                p.equipment["free_hand"] = it
            elif kind.startswith("body:"):
                slot = kind.split(":", 1)[1]
                p.equipment[slot] = it
            session = srv.session_for(p.id)
            if session:
                srv.send_inventory(session)
        self.s.settle(0.3)
        sc = self.open_pack()
        sc.draw(self.s.app.screen)
        return it, sc

    def source_point(self, sc, kind, item_id):
        """Where the just-placed item is actually drawn right now."""
        sc.draw(self.s.app.screen)
        if kind == "floor":
            return next((r.center for r, fi in sc.floor_rects
                        if fi["id"] == item_id), None)
        if kind == "pack":
            return self.cell_for(sc, item_id)
        if kind == "belt":
            return sc.slot_rects["waist"].center
        if kind == "freehand":
            return sc.slot_rects["free_hand"].center
        if kind.startswith("body:"):
            return sc.slot_rects[kind.split(":", 1)[1]].center

    def dest_point(self, sc, kind):
        if kind == "floor":
            sc.draw(self.s.app.screen)
            return sc.floor_grid_rect.center
        if kind == "pack":
            sc.draw(self.s.app.screen)
            return sc.grid_rect.center
        if kind == "belt":
            sc.draw(self.s.app.screen)
            cells = list(sc.empty_stow_rects)
            return cells[0][0].center if cells else sc.slot_rects["waist"].center
        if kind == "freehand":
            return sc.slot_rects["free_hand"].center
        if kind.startswith("body:"):
            return sc.slot_rects[kind.split(":", 1)[1]].center

    def clear_floor(self):
        """Every check that ends "-> floor" leaves something lying there;
        without this a later check's freshly placed item can land on a
        second page of the floor window that source_point never looks at."""
        p = self.s.me()
        lvl = self.s.level()
        srv = self.s.app.server
        with srv.lock:
            lvl.ground[(p.x, p.y)] = []
            session = srv.session_for(p.id)
            if session:
                srv.send_inventory(session)
        self.s.settle(0.2)

    def one_drag(self, from_kind, from_key, to_kind, full_pack):
        self.empty_the_pack()
        self.clear_floor()
        if full_pack:
            self.fill_pack_to_bursting()
        it, sc = self.place_source(from_kind, from_key)
        src = self.source_point(sc, from_kind, it.id)
        if src is None:
            return self.note("matrix", f"{from_kind}->{to_kind} (full={full_pack}): "
                                       f"item reached its starting spot", False)
        before = sorted(self.all_item_ids())
        dst = self.dest_point(sc, to_kind)
        self.drag(src, dst)
        self.home()
        after = sorted(self.all_item_ids())
        self.note("matrix",
                  f"{from_kind:>10} -> {to_kind:<10} (full pack={full_pack})"
                  f" keeps every item exactly once",
                  before == after,
                  f"{len(before)} ids before, {len(after)} after"
                  if before != after else "")

    def run(self):
        for full_pack in (False, True):
            for from_kind, from_key in LOCATIONS:
                for to_kind, _ in LOCATIONS:
                    if from_kind == to_kind:
                        continue
                    # A thing that starts worn and a destination that is
                    # also a body slot is a swap, covered by check_equip's
                    # "wrong slot" case elsewhere; skip body-to-body here to
                    # keep this pass on the combinations that actually broke
                    # (something moving through the pack on its way past).
                    if from_kind.startswith("body:") and to_kind.startswith("body:"):
                        continue
                    self.one_drag(from_kind, from_key, to_kind, full_pack)


def main():
    b = MatrixBench()
    b.run()
    bad = [r for r in b.rows if r[2] != "ok"]
    print(f"\n{len(b.rows)} checks, {len(bad)} failed")
    b.s.close()
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
