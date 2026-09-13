#!/usr/bin/env node
// Stormhold server. Serves the game to any browser on the local network and
// runs the authoritative simulation. No dependencies, no build step.

import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { networkInterfaces } from 'node:os';
import { join, normalize, extname, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

import { attachWebSocket } from './ws.js';
import { NetServer } from './net.js';
import { World } from './game/world.js';
import { Store, defaultStorePath } from './persist.js';
import { TICK_MS } from '../shared/constants.js';

const ROOT = normalize(join(dirname(fileURLToPath(import.meta.url)), '..'));

// ------------------------------------------------------------------ args ---
function parseArgs(argv) {
  const opts = { port: 3000, host: '0.0.0.0', seed: null };
  for (const arg of argv.slice(2)) {
    const [k, v] = arg.replace(/^--/, '').split('=');
    if (k === 'port') opts.port = Number(v) || 3000;
    else if (k === 'host') opts.host = v || '0.0.0.0';
    else if (k === 'seed') opts.seed = Number(v);
    else if (k === 'help' || k === 'h') opts.help = true;
  }
  return opts;
}

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.ico': 'image/x-icon',
  '.webmanifest': 'application/manifest+json',
  '.txt': 'text/plain; charset=utf-8',
};

// Only these directories are ever served.
const SERVE_DIRS = ['client', 'shared'];

async function serveStatic(req, res) {
  let urlPath = decodeURIComponent((req.url || '/').split('?')[0]);
  if (urlPath === '/' || urlPath === '') urlPath = '/client/index.html';
  else if (!urlPath.startsWith('/client/') && !urlPath.startsWith('/shared/')) {
    urlPath = `/client${urlPath}`;
  }

  const full = normalize(join(ROOT, urlPath));
  // Refuse anything that escapes the two served directories.
  const allowed = SERVE_DIRS.some(d => full.startsWith(join(ROOT, d) + '/'));
  if (!allowed) {
    res.writeHead(403, { 'Content-Type': 'text/plain' });
    res.end('Forbidden');
    return;
  }

  try {
    const info = await stat(full);
    if (!info.isFile()) throw new Error('not a file');
    const body = await readFile(full);
    res.writeHead(200, {
      'Content-Type': MIME[extname(full).toLowerCase()] ?? 'application/octet-stream',
      'Content-Length': body.length,
      // The game is served off a laptop and edited between sessions: never cache.
      'Cache-Control': 'no-cache, no-store, must-revalidate',
    });
    res.end(body);
  } catch {
    res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
    res.end('Not found');
  }
}

function lanAddresses() {
  const out = [];
  for (const [name, addrs] of Object.entries(networkInterfaces())) {
    for (const a of addrs ?? []) {
      if (a.family === 'IPv4' && !a.internal) out.push({ name, address: a.address });
    }
  }
  return out;
}

function banner(port) {
  const lines = [];
  lines.push('');
  lines.push('   ====================================================');
  lines.push('     S T O R M H O L D   -   the keep is open');
  lines.push('   ====================================================');
  lines.push('');
  lines.push(`   On this computer:      http://localhost:${port}`);
  const lan = lanAddresses();
  if (lan.length) {
    lines.push('');
    lines.push('   From other machines on the same network:');
    for (const { name, address } of lan) {
      lines.push(`     ${String(name).padEnd(10)} http://${address}:${port}`);
    }
    lines.push('');
    lines.push('   Open that address in any browser. Nothing to install.');
  } else {
    lines.push('');
    lines.push('   No network interface found - only this computer can connect.');
  }
  lines.push('');
  lines.push('   Press Ctrl+C to stop the server. Characters save automatically.');
  lines.push('');
  return lines.join('\n');
}

// ------------------------------------------------------------------ main ---
async function main() {
  const opts = parseArgs(process.argv);
  if (opts.help) {
    console.log(`Stormhold server

Usage: node server/index.js [options]

  --port=3000     port to listen on
  --host=0.0.0.0  interface to bind (0.0.0.0 serves the whole LAN)
  --seed=12345    fixed world seed, so the dungeon is the same every run
  --help          this message
`);
    return;
  }

  const store = await new Store(defaultStorePath(ROOT)).load();
  const world = new World({ seed: opts.seed ?? undefined });
  const net = new NetServer(world, store);

  const server = createServer((req, res) => {
    serveStatic(req, res).catch(() => {
      res.writeHead(500, { 'Content-Type': 'text/plain' });
      res.end('Server error');
    });
  });

  attachWebSocket(server, '/ws', (conn) => net.onConnection(conn));

  server.on('error', (err) => {
    if (err.code === 'EADDRINUSE') {
      console.error(`\n  Port ${opts.port} is already in use.`);
      console.error(`  Try:  node server/index.js --port=${opts.port + 1}\n`);
      process.exit(1);
    }
    throw err;
  });

  await new Promise((resolve) => server.listen(opts.port, opts.host, resolve));
  console.log(banner(opts.port));
  console.log(`   world seed ${world.seed}   tick ${TICK_MS}ms   saves in data/players.json\n`);

  // The simulation heartbeat. Everything in the game happens here.
  let running = true;
  let slowTicks = 0;
  const loop = setInterval(() => {
    if (!running) return;
    const t0 = performance.now();
    try {
      net.tick();
    } catch (err) {
      console.error('[stormhold] tick error:', err);
    }
    const ms = performance.now() - t0;
    if (ms > TICK_MS) {
      if (++slowTicks % 40 === 0) {
        console.warn(`[stormhold] simulation running slow (${ms.toFixed(0)}ms this tick)`);
      }
    }
  }, TICK_MS);

  const shutdown = async (signal) => {
    if (!running) return;
    running = false;
    console.log(`\n[stormhold] ${signal}: saving characters...`);
    clearInterval(loop);
    await net.shutdown();
    server.close();
    console.log('[stormhold] saved. See you next time.');
    process.exit(0);
  };
  process.on('SIGINT', () => shutdown('SIGINT'));
  process.on('SIGTERM', () => shutdown('SIGTERM'));
}

main().catch((err) => {
  console.error('[stormhold] failed to start:', err);
  process.exit(1);
});
