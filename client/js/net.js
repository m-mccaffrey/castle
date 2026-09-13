// WebSocket client with automatic reconnection. On a home network the socket
// rarely drops, but a laptop lid closing should not end the evening.

import { C, S, encode, decode } from '../../shared/protocol.js';

export class Net {
  constructor(url) {
    this.url = url;
    this.ws = null;
    this.handlers = new Map();
    this.connected = false;
    this.retries = 0;
    this.latency = 0;
    this.closedByUs = false;
    this.pingTimer = null;
    this.queue = [];
  }

  on(type, fn) { this.handlers.set(type, fn); return this; }

  emit(type, data) {
    const fn = this.handlers.get(type);
    if (fn) fn(data);
  }

  connect() {
    this.closedByUs = false;
    try {
      this.ws = new WebSocket(this.url);
    } catch {
      this.scheduleReconnect();
      return;
    }

    this.ws.addEventListener('open', () => {
      this.connected = true;
      this.retries = 0;
      this.emit('__open');
      while (this.queue.length) this.ws.send(this.queue.shift());
      this.pingTimer = setInterval(() => {
        this.send(C.PING, { t: performance.now() });
      }, 3000);
    });

    this.ws.addEventListener('message', (ev) => {
      const msg = decode(ev.data);
      if (!msg) return;
      if (msg.m === S.PONG) {
        this.latency = Math.round(performance.now() - (msg.d.t ?? 0));
        return;
      }
      this.emit(msg.m, msg.d);
    });

    this.ws.addEventListener('close', () => {
      this.connected = false;
      if (this.pingTimer) { clearInterval(this.pingTimer); this.pingTimer = null; }
      this.emit('__close');
      if (!this.closedByUs) this.scheduleReconnect();
    });

    this.ws.addEventListener('error', () => { /* close follows */ });
  }

  scheduleReconnect() {
    this.retries++;
    const delay = Math.min(8000, 400 * 2 ** Math.min(this.retries, 5));
    this.emit('__retry', { attempt: this.retries, delay });
    setTimeout(() => this.connect(), delay);
  }

  send(type, data = {}) {
    const raw = encode(type, data);
    if (this.ws && this.ws.readyState === WebSocket.OPEN) this.ws.send(raw);
    else if (this.queue.length < 32) this.queue.push(raw);
  }

  close() {
    this.closedByUs = true;
    if (this.pingTimer) clearInterval(this.pingTimer);
    this.ws?.close();
  }
}
