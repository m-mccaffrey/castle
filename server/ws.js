// A small RFC 6455 WebSocket server.
//
// The whole point of this file is that Stormhold installs nothing: you copy the
// folder onto a laptop, run `node server/index.js`, and the kids can connect.
// It handles exactly what the game needs - text frames, fragmentation, ping,
// pong and close - and rejects anything malformed.

import { createHash } from 'node:crypto';

const GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11';
const MAX_MESSAGE = 1 << 20;        // 1 MiB: far more than any game message
const PING_INTERVAL = 20_000;
const PONG_TIMEOUT = 60_000;

const OP = { CONT: 0x0, TEXT: 0x1, BIN: 0x2, CLOSE: 0x8, PING: 0x9, PONG: 0xa };

function frame(opcode, payload) {
  const len = payload.length;
  let header;
  if (len < 126) {
    header = Buffer.allocUnsafe(2);
    header[1] = len;
  } else if (len < 65536) {
    header = Buffer.allocUnsafe(4);
    header[1] = 126;
    header.writeUInt16BE(len, 2);
  } else {
    header = Buffer.allocUnsafe(10);
    header[1] = 127;
    header.writeBigUInt64BE(BigInt(len), 2);
  }
  header[0] = 0x80 | opcode;        // FIN + opcode; server frames are unmasked
  return Buffer.concat([header, payload]);
}

export class WebSocketConnection {
  constructor(socket, req) {
    this.socket = socket;
    this.req = req;
    this.remote = socket.remoteAddress;
    this.open = true;
    this.buf = Buffer.alloc(0);
    this.fragments = [];
    this.fragOpcode = 0;
    this.fragLength = 0;
    this.alive = true;
    this.lastPong = Date.now();
    this.handlers = { message: [], close: [], error: [] };

    socket.setNoDelay(true);
    socket.on('data', (chunk) => this.onData(chunk));
    socket.on('error', (err) => { this.emit('error', err); this.destroy(); });
    socket.on('close', () => this.cleanup());

    this.pinger = setInterval(() => {
      if (!this.open) return;
      if (Date.now() - this.lastPong > PONG_TIMEOUT) { this.destroy(); return; }
      try { this.socket.write(frame(OP.PING, Buffer.alloc(0))); } catch { this.destroy(); }
    }, PING_INTERVAL);
  }

  on(event, fn) { this.handlers[event]?.push(fn); return this; }
  emit(event, ...args) { for (const fn of this.handlers[event] ?? []) fn(...args); }

  send(text) {
    if (!this.open) return false;
    try {
      this.socket.write(frame(OP.TEXT, Buffer.from(text, 'utf8')));
      return true;
    } catch {
      this.destroy();
      return false;
    }
  }

  close(code = 1000, reason = '') {
    if (!this.open) return;
    const payload = Buffer.alloc(2 + Buffer.byteLength(reason));
    payload.writeUInt16BE(code, 0);
    payload.write(reason, 2);
    try { this.socket.write(frame(OP.CLOSE, payload)); } catch { /* already gone */ }
    this.open = false;
    this.socket.end();
    this.cleanup();
  }

  destroy() {
    this.open = false;
    try { this.socket.destroy(); } catch { /* already gone */ }
    this.cleanup();
  }

  cleanup() {
    if (this.pinger) { clearInterval(this.pinger); this.pinger = null; }
    if (!this.closedEmitted) {
      this.closedEmitted = true;
      this.open = false;
      this.emit('close');
    }
  }

  onData(chunk) {
    this.buf = this.buf.length ? Buffer.concat([this.buf, chunk]) : chunk;
    // Guard against a peer that opens a frame and never finishes it.
    if (this.buf.length > MAX_MESSAGE * 2) { this.close(1009, 'message too big'); return; }

    for (;;) {
      if (this.buf.length < 2) return;
      const b0 = this.buf[0], b1 = this.buf[1];
      const fin = (b0 & 0x80) !== 0;
      const rsv = b0 & 0x70;
      const opcode = b0 & 0x0f;
      const masked = (b1 & 0x80) !== 0;
      let len = b1 & 0x7f;
      let offset = 2;

      if (rsv !== 0) { this.close(1002, 'reserved bits set'); return; }

      if (len === 126) {
        if (this.buf.length < 4) return;
        len = this.buf.readUInt16BE(2);
        offset = 4;
      } else if (len === 127) {
        if (this.buf.length < 10) return;
        const big = this.buf.readBigUInt64BE(2);
        if (big > BigInt(MAX_MESSAGE)) { this.close(1009, 'message too big'); return; }
        len = Number(big);
        offset = 10;
      }

      // Clients must mask every frame they send.
      if (!masked) { this.close(1002, 'unmasked frame'); return; }
      if (this.buf.length < offset + 4) return;
      const mask = this.buf.subarray(offset, offset + 4);
      offset += 4;

      if (this.buf.length < offset + len) return;
      const payload = Buffer.allocUnsafe(len);
      const raw = this.buf.subarray(offset, offset + len);
      for (let i = 0; i < len; i++) payload[i] = raw[i] ^ mask[i & 3];
      this.buf = this.buf.subarray(offset + len);

      const isControl = (opcode & 0x8) !== 0;
      if (isControl) {
        if (!fin || len > 125) { this.close(1002, 'bad control frame'); return; }
        if (opcode === OP.CLOSE) { this.open = false; this.socket.end(); this.cleanup(); return; }
        if (opcode === OP.PING) {
          try { this.socket.write(frame(OP.PONG, payload)); } catch { this.destroy(); return; }
          continue;
        }
        if (opcode === OP.PONG) { this.lastPong = Date.now(); continue; }
        this.close(1002, 'unknown control frame');
        return;
      }

      // Data frames, possibly fragmented.
      if (opcode === OP.CONT) {
        if (!this.fragOpcode) { this.close(1002, 'continuation without start'); return; }
        this.fragments.push(payload);
        this.fragLength += payload.length;
      } else {
        if (this.fragOpcode) { this.close(1002, 'interleaved fragments'); return; }
        if (fin) {
          if (opcode === OP.TEXT) this.deliver(payload);
          continue;                                  // binary frames are ignored
        }
        this.fragOpcode = opcode;
        this.fragments = [payload];
        this.fragLength = payload.length;
      }

      if (this.fragLength > MAX_MESSAGE) { this.close(1009, 'message too big'); return; }
      if (fin) {
        const full = Buffer.concat(this.fragments, this.fragLength);
        const op = this.fragOpcode;
        this.fragments = [];
        this.fragOpcode = 0;
        this.fragLength = 0;
        if (op === OP.TEXT) this.deliver(full);
      }
    }
  }

  deliver(payload) {
    let text;
    try {
      text = payload.toString('utf8');
    } catch {
      this.close(1007, 'bad utf8');
      return;
    }
    this.emit('message', text);
  }
}

/**
 * Attach a WebSocket endpoint to an existing http.Server.
 * `onConnection(conn, req)` is called once the handshake completes.
 */
export function attachWebSocket(server, path, onConnection) {
  server.on('upgrade', (req, socket, head) => {
    const url = (req.url || '').split('?')[0];
    if (url !== path) { socket.destroy(); return; }

    const key = req.headers['sec-websocket-key'];
    const version = req.headers['sec-websocket-version'];
    const upgrade = String(req.headers.upgrade || '').toLowerCase();

    if (upgrade !== 'websocket' || !key || version !== '13') {
      socket.write('HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n');
      socket.destroy();
      return;
    }

    const accept = createHash('sha1').update(key + GUID).digest('base64');
    socket.write(
      'HTTP/1.1 101 Switching Protocols\r\n' +
      'Upgrade: websocket\r\n' +
      'Connection: Upgrade\r\n' +
      `Sec-WebSocket-Accept: ${accept}\r\n\r\n`
    );

    const conn = new WebSocketConnection(socket, req);
    if (head && head.length) conn.onData(head);
    onConnection(conn, req);
  });
}
