"""Minimal WinHelp (.HLP) reader: internal file directory + topic text."""
import struct, sys

def u16(b, o): return struct.unpack_from("<H", b, o)[0]
def i16(b, o): return struct.unpack_from("<h", b, o)[0]
def u32(b, o): return struct.unpack_from("<I", b, o)[0]
def i32(b, o): return struct.unpack_from("<i", b, o)[0]

class Hlp:
    def __init__(self, path):
        self.d = open(path, "rb").read()
        magic, self.dirstart, self.freeblk, self.size = struct.unpack_from("<iiii", self.d, 0)
        assert magic == 0x00035F3F, f"not a WinHelp file: {magic:#x}"
        self.files = self._dir()

    def _fileheader(self, off):
        reserved, used, flags = struct.unpack_from("<iiB", self.d, off)
        return off + 9, used

    def _dir(self):
        off, _used = self._fileheader(self.dirstart)
        (bmagic, bflags, pagesize) = struct.unpack_from("<HHH", self.d, off)
        assert bmagic == 0x293B, f"bad btree magic {bmagic:#x}"
        structure = self.d[off+6:off+22]
        (_mbz, _splits, rootpage, _neg1, totalpages, nlevels, nentries) = \
            struct.unpack_from("<hhhhhhi", self.d, off+22)
        pages_start = off + 38
        out = {}
        # walk down to the leftmost leaf, then follow NextPage
        # node header is: Unused, NEntries, PreviousPage[, NextPage]
        page = rootpage
        for _ in range(nlevels - 1):
            p = pages_start + page * pagesize
            page = i16(self.d, p + 4)          # first child
        while page != -1:
            p = pages_start + page * pagesize
            n = i16(self.d, p + 2)
            nxt = i16(self.d, p + 6)
            q = p + 8
            for _ in range(n):
                end = self.d.index(b"\0", q)
                name = self.d[q:end].decode("latin-1")
                q = end + 1
                out[name] = i32(self.d, q); q += 4
            page = nxt
        return out

    def raw(self, name):
        off = self.files[name]
        start, used = self._fileheader(off)
        return self.d[start:start+used]

if __name__ == "__main__":
    h = Hlp(sys.argv[1])
    print("internal files:")
    for k, v in sorted(h.files.items()):
        try:
            n = len(h.raw(k))
        except Exception as e:
            n = f"err {e}"
        print(f"  {k:<14} at {v:<8} size {n}")


def phrase_table(h):
    n = u16(h.raw("|Phrases"), 0)
    ph = h.raw("|Phrases")
    offs = struct.unpack_from("<%dH" % (n + 1), ph, 4)
    return [ph[offs[i] + 4:offs[i + 1] + 4] for i in range(n)]

def expand(data, phrases):
    """Undo WinHelp phrase compression: byte 1..15 + byte selects a phrase."""
    out = bytearray()
    i = 0
    while i < len(data):
        c = data[i]
        if 1 <= c <= 15 and i + 1 < len(data):
            k = (c - 1) * 256 + data[i + 1]
            i += 2
            idx = k // 2
            if idx < len(phrases):
                out += phrases[idx]
                if k & 1:
                    out += b" "
            continue
        out.append(c)
        i += 1
    return bytes(out)
