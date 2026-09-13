"""Client end of the socket. A background thread reads; the game loop drains a
queue. Nothing in the UI ever blocks on the network."""

import queue
import socket
import threading
import time

from . import protocol as P


class GameClient:
    def __init__(self):
        self.sock = None
        self.thread = None
        self.inbox = queue.Queue()
        self.connected = False
        self.error = None
        self.latency = 0
        self._decoder = P.Decoder()
        self._send_lock = threading.Lock()
        self._stop = threading.Event()

    def connect(self, host, port, timeout=6.0):
        try:
            self.sock = socket.create_connection((host, int(port)), timeout=timeout)
            self.sock.settimeout(None)
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError as exc:
            self.error = f"Could not reach {host}:{port} - {exc.strerror or exc}"
            return False
        self.connected = True
        self._stop.clear()
        self.thread = threading.Thread(target=self._reader, daemon=True, name="net-read")
        self.thread.start()
        return True

    def _reader(self):
        try:
            while not self._stop.is_set():
                chunk = self.sock.recv(16384)
                if not chunk:
                    break
                for kind, data in self._decoder.feed(chunk):
                    if kind == P.S_PONG:
                        self.latency = int((time.time() - data.get("t", 0)) * 1000)
                        continue
                    self.inbox.put((kind, data))
        except (OSError, ValueError):
            pass
        finally:
            self.connected = False
            self.inbox.put(("__closed", {}))

    def send(self, kind, data=None):
        if not self.connected or self.sock is None:
            return False
        try:
            with self._send_lock:
                self.sock.sendall(P.encode(kind, data))
            return True
        except OSError:
            self.connected = False
            return False

    def ping(self):
        self.send(P.C_PING, {"t": time.time()})

    def drain(self, limit=400):
        """Everything that arrived since last frame."""
        out = []
        for _ in range(limit):
            try:
                out.append(self.inbox.get_nowait())
            except queue.Empty:
                break
        return out

    def close(self):
        self._stop.set()
        self.connected = False
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self.sock.close()
            except OSError:
                pass
