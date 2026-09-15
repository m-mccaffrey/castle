"""The wire, and what happens when something sends rubbish down it.

The server is reachable from anywhere on the house network, and the thing on
the other end is not always the game: a port scanner, a browser, a second
copy at the wrong version, or a child pressing keys into netcat. None of that
should take the keep down for everyone else.
"""

import json
import os
import socket
import struct
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stormhold.net import protocol as P                        # noqa: E402
from stormhold.net.server import GameServer                    # noqa: E402

_port = [8100]


def next_port():
    _port[0] += 1
    return _port[0]


class TestDecoder(unittest.TestCase):
    def test_a_whole_message_comes_back(self):
        d = P.Decoder()
        self.assertEqual(d.feed(P.encode("hello", {"a": 1})),
                         [("hello", {"a": 1})])

    def test_a_message_split_across_reads_is_reassembled(self):
        blob = P.encode("hello", {"a": 1})
        d = P.Decoder()
        for i in range(len(blob) - 1):
            self.assertEqual(d.feed(blob[i:i + 1]), [])
        self.assertEqual(d.feed(blob[-1:]), [("hello", {"a": 1})])

    def test_several_messages_in_one_read(self):
        d = P.Decoder()
        blob = P.encode("a") + P.encode("b") + P.encode("c")
        self.assertEqual([k for k, _ in d.feed(blob)], ["a", "b", "c"])

    def test_rubbish_inside_a_frame_is_dropped_not_fatal(self):
        d = P.Decoder()
        bad = b"not json at all"
        frame = struct.pack(">I", len(bad)) + bad
        self.assertEqual(d.feed(frame), [])
        self.assertEqual(d.feed(P.encode("after", {})), [("after", {})])

    def test_json_that_is_not_a_message_is_dropped(self):
        d = P.Decoder()
        for payload in (b"[]", b'"hello"', b"5", b"null", b'{"d":{}}',
                        b'{"m":5}'):
            frame = struct.pack(">I", len(payload)) + payload
            self.assertEqual(d.feed(frame), [], payload)

    def test_invalid_utf8_is_dropped(self):
        d = P.Decoder()
        payload = b"\xff\xfe\xfd"
        frame = struct.pack(">I", len(payload)) + payload
        self.assertEqual(d.feed(frame), [])

    def test_an_absurd_length_is_refused_rather_than_allocated(self):
        d = P.Decoder()
        with self.assertRaises(ValueError):
            d.feed(struct.pack(">I", P.MAX_MESSAGE + 1))

    def test_a_missing_payload_is_just_treated_as_empty(self):
        d = P.Decoder()
        self.assertEqual(d.feed(P.encode("bare")), [("bare", {})])


class TestTheServerSurvivesRubbish(unittest.TestCase):
    def setUp(self):
        self.port = next_port()
        self.server = GameServer("127.0.0.1", self.port, seed=5,
                                 save_path=None).start()

    def tearDown(self):
        self.server.stop()

    def connect(self):
        s = socket.create_connection(("127.0.0.1", self.port), timeout=3)
        s.settimeout(3)
        return s

    def still_alive(self):
        """A fresh, well-behaved client must still be able to join."""
        s = self.connect()
        try:
            s.sendall(P.encode(P.C_HELLO, {
                "name": "Latecomer", "stats": {}, "colour": 0,
                "version": P.PROTOCOL_VERSION if hasattr(P, "PROTOCOL_VERSION")
                else __import__("stormhold.common.constants",
                                fromlist=["x"]).PROTOCOL_VERSION}))
            deadline = time.time() + 3
            decoder = P.Decoder()
            seen = []
            while time.time() < deadline:
                try:
                    chunk = s.recv(8192)
                except socket.timeout:
                    break
                if not chunk:
                    break
                seen += [k for k, _ in decoder.feed(chunk)]
                if "welcome" in seen or P.S_WELCOME in seen:
                    return True
            return P.S_WELCOME in seen
        finally:
            s.close()

    def test_a_connection_that_says_nothing_and_goes_away(self):
        self.connect().close()
        self.assertTrue(self.still_alive())

    def test_a_connection_that_sends_garbage_bytes(self):
        s = self.connect()
        s.sendall(b"GET / HTTP/1.1\r\nHost: x\r\n\r\n")
        time.sleep(0.2)
        s.close()
        self.assertTrue(self.still_alive())

    def test_a_frame_that_claims_to_be_enormous(self):
        s = self.connect()
        s.sendall(struct.pack(">I", 0xFFFFFFFF) + b"x" * 16)
        time.sleep(0.2)
        s.close()
        self.assertTrue(self.still_alive())

    def test_actions_before_saying_hello(self):
        s = self.connect()
        for action in ({"a": "move", "dx": 1}, {"a": "stairs"}, {"a": "use"}):
            s.sendall(P.encode(P.C_ACTION, action))
        time.sleep(0.3)
        s.close()
        self.assertTrue(self.still_alive())

    def test_a_hello_with_nothing_in_it(self):
        s = self.connect()
        s.sendall(P.encode(P.C_HELLO, {}))
        time.sleep(0.3)
        s.close()
        self.assertTrue(self.still_alive())

    def test_a_hello_from_the_wrong_version(self):
        s = self.connect()
        s.sendall(P.encode(P.C_HELLO, {"name": "Old", "version": -1}))
        time.sleep(0.3)
        s.close()
        self.assertTrue(self.still_alive())

    def test_nonsense_actions_from_a_real_player(self):
        from stormhold.common.constants import PROTOCOL_VERSION
        s = self.connect()
        s.sendall(P.encode(P.C_HELLO, {"name": "Chaos", "stats": {},
                                       "colour": 0,
                                       "version": PROTOCOL_VERSION}))
        time.sleep(0.4)
        rubbish = {"id": "not a number", "slot": ["a", "list"], "x": None,
                   "dx": "east", "spell": {"nested": True}, "amount": 1e30}
        for verb in ("move", "use", "cast", "buy", "sell", "service", "stow",
                     "equip", "drop", "callme", "shoot", "throne", "dance"):
            s.sendall(P.encode(P.C_ACTION, dict(rubbish, a=verb)))
        time.sleep(0.6)
        s.close()
        self.assertTrue(self.still_alive())

    def test_two_players_cannot_take_the_same_name(self):
        from stormhold.common.constants import PROTOCOL_VERSION
        first = self.connect()
        first.sendall(P.encode(P.C_HELLO, {"name": "Twin", "stats": {},
                                           "colour": 0,
                                           "version": PROTOCOL_VERSION}))
        time.sleep(0.4)
        second = self.connect()
        second.sendall(P.encode(P.C_HELLO, {"name": "twin", "stats": {},
                                            "colour": 0,
                                            "version": PROTOCOL_VERSION}))
        decoder = P.Decoder()
        seen = []
        deadline = time.time() + 2
        while time.time() < deadline:
            try:
                chunk = second.recv(8192)
            except socket.timeout:
                break
            if not chunk:
                break
            seen += [k for k, _ in decoder.feed(chunk)]
            if P.S_ERROR in seen:
                break
        first.close()
        second.close()
        self.assertIn(P.S_ERROR, seen, "the name was handed out twice")
