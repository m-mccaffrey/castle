import test from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { attachWebSocket } from '../server/ws.js';

/** Start an echo server on an ephemeral port. */
async function echoServer(onConn) {
  const server = createServer((req, res) => { res.writeHead(404); res.end(); });
  const conns = [];
  attachWebSocket(server, '/ws', (conn) => {
    conns.push(conn);
    conn.on('message', (text) => conn.send(text));
    onConn?.(conn);
  });
  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  return { server, port: server.address().port, conns };
}

function connect(port, path = '/ws') {
  const ws = new WebSocket(`ws://127.0.0.1:${port}${path}`);
  return new Promise((resolve, reject) => {
    ws.addEventListener('open', () => resolve(ws));
    ws.addEventListener('error', () => reject(new Error('connection failed')));
    setTimeout(() => reject(new Error('connect timed out')), 4000);
  });
}

function once(ws) {
  return new Promise((resolve, reject) => {
    ws.addEventListener('message', (e) => resolve(e.data), { once: true });
    setTimeout(() => reject(new Error('no message')), 4000);
  });
}

test('completes the handshake and echoes a text frame', async () => {
  const { server, port } = await echoServer();
  const ws = await connect(port);
  ws.send('hello stormhold');
  assert.equal(await once(ws), 'hello stormhold');
  ws.close();
  server.close();
});

test('handles payloads across all three length encodings', async () => {
  const { server, port } = await echoServer();
  const ws = await connect(port);
  for (const size of [10, 125, 126, 200, 65535, 65536, 200_000]) {
    const msg = 'x'.repeat(size);
    ws.send(msg);
    const back = await once(ws);
    assert.equal(back.length, size, `length ${size} round-tripped as ${back.length}`);
  }
  ws.close();
  server.close();
});

test('preserves multi-byte utf8 and json payloads', async () => {
  const { server, port } = await echoServer();
  const ws = await connect(port);
  const payload = JSON.stringify({ m: 'chat', d: { text: 'Sam found a Rune Blade — 3 gold left 😀' } });
  ws.send(payload);
  assert.equal(await once(ws), payload);
  ws.close();
  server.close();
});

test('delivers many small messages in order', async () => {
  const { server, port } = await echoServer();
  const ws = await connect(port);
  const got = [];
  ws.addEventListener('message', (e) => got.push(e.data));
  for (let i = 0; i < 300; i++) ws.send(String(i));
  await new Promise((r) => setTimeout(r, 600));
  assert.equal(got.length, 300, `expected 300 messages, got ${got.length}`);
  assert.deepEqual(got.map(Number), [...Array(300).keys()], 'messages arrived out of order');
  ws.close();
  server.close();
});

test('reports a clean close to the server side', async () => {
  const { server, port, conns } = await echoServer();
  const ws = await connect(port);
  let closed = false;
  conns[0].on('close', () => { closed = true; });
  ws.close();
  await new Promise((r) => setTimeout(r, 300));
  assert.equal(closed, true, 'server never saw the close');
  server.close();
});

test('rejects an upgrade on the wrong path', async () => {
  const { server, port } = await echoServer();
  await assert.rejects(() => connect(port, '/nope'));
  server.close();
});

test('rejects a non-websocket request to the upgrade path', async () => {
  const { server, port } = await echoServer();
  const res = await fetch(`http://127.0.0.1:${port}/ws`).catch((e) => e);
  // The plain GET is handled by the http server (404), not the upgrade path.
  assert.ok(res.status === 404 || res instanceof Error);
  server.close();
});

test('survives several simultaneous clients', async () => {
  const { server, port } = await echoServer();
  const clients = await Promise.all([...Array(6)].map(() => connect(port)));
  const replies = await Promise.all(clients.map((ws, i) => {
    const p = once(ws);
    ws.send(`client-${i}`);
    return p;
  }));
  replies.forEach((r, i) => assert.equal(r, `client-${i}`));
  for (const ws of clients) ws.close();
  server.close();
});
