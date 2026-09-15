"""Wire format: a four-byte big-endian length, then UTF-8 JSON.

Stormhold is turn-based, so there is no tick loop and no streaming. The server
speaks when somebody does something. On a home network that means a handful of
small messages per action, which even a Pi handles without noticing.
"""

import json
import struct

HEADER = struct.Struct(">I")
MAX_MESSAGE = 4 << 20          # 4 MiB: generous for a whole-level tile dump


def encode(kind, data=None):
    payload = json.dumps({"m": kind, "d": data or {}}, separators=(",", ":")).encode("utf-8")
    if len(payload) > MAX_MESSAGE:
        raise ValueError("message too large")
    return HEADER.pack(len(payload)) + payload


class Decoder:
    """Feed it bytes, get back whole messages."""

    def __init__(self):
        self.buf = bytearray()

    def feed(self, chunk):
        self.buf.extend(chunk)
        out = []
        while len(self.buf) >= HEADER.size:
            (length,) = HEADER.unpack_from(self.buf, 0)
            if length > MAX_MESSAGE:
                raise ValueError("oversized message")
            if len(self.buf) < HEADER.size + length:
                break
            raw = bytes(self.buf[HEADER.size:HEADER.size + length])
            del self.buf[:HEADER.size + length]
            try:
                obj = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                continue
            if isinstance(obj, dict) and isinstance(obj.get("m"), str):
                out.append((obj["m"], obj.get("d") or {}))
        return out


# client -> server
C_HELLO = "hello"
C_ACTION = "act"
C_CHAT = "chat"
C_PING = "ping"
C_SAVE = "save"

# server -> client
S_WELCOME = "welcome"
S_ERROR = "err"
S_LEVEL = "level"
S_TILES = "tiles"
S_STATE = "state"
S_MSG = "msg"
S_FX = "fx"
S_SOUND = "snd"
S_INV = "inv"
S_SHOP = "shop"
S_DIED = "died"
S_CHAT = "chat"
S_ROSTER = "roster"
S_PONG = "pong"
