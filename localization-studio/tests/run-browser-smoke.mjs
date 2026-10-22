import { createServer } from 'node:http';
import { readFile, rm } from 'node:fs/promises';
import { extname, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';

const projectRoot = resolve(fileURLToPath(new URL('..', import.meta.url)));
const browser = process.env.BROWSER_BIN || 'chromium';
const profilePath = resolve(projectRoot, '.test-browser-profile');
if (typeof WebSocket !== 'function') {
  throw new Error('The browser smoke test requires Node.js 22 or later for its built-in WebSocket client. The format tests require Node.js 20 or later.');
}
const mimeTypes = new Map([
  ['.html', 'text/html; charset=utf-8'],
  ['.css', 'text/css; charset=utf-8'],
  ['.mjs', 'text/javascript; charset=utf-8'],
  ['.json', 'application/json; charset=utf-8'],
]);

const server = createServer(async (request, response) => {
  if (request.method !== 'GET' && request.method !== 'HEAD') {
    response.writeHead(405).end();
    return;
  }
  try {
    const requestPath = decodeURIComponent(new URL(request.url, 'http://localhost').pathname).replace(/^\/+/, '');
    const filePath = resolve(projectRoot, requestPath);
    if (filePath !== projectRoot && !filePath.startsWith(projectRoot + sep)) {
      response.writeHead(403).end();
      return;
    }
    const content = await readFile(filePath);
    response.writeHead(200, {
      'Content-Type': mimeTypes.get(extname(filePath)) || 'application/octet-stream',
      'Cache-Control': 'no-store',
      'X-Content-Type-Options': 'nosniff',
    });
    if (request.method === 'HEAD') response.end();
    else response.end(content);
  } catch {
    response.writeHead(404).end('Not found');
  }
});

await new Promise((resolveListen, rejectListen) => {
  server.once('error', rejectListen);
  server.listen(0, '127.0.0.1', resolveListen);
});

const address = server.address();
const url = `http://127.0.0.1:${address.port}/tests/browser-smoke.html`;
const args = [
  '--headless', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage',
  '--disable-background-networking', '--disable-extensions', '--no-first-run',
  '--no-default-browser-check', '--remote-debugging-port=0', '--remote-allow-origins=*',
  `--user-data-dir=${profilePath}`, 'about:blank',
];

let chrome;
let socket;
let stderr = '';
let requestId = 0;
const pending = new Map();
const sleep = (ms) => new Promise((resolveSleep) => setTimeout(resolveSleep, ms));

function cdpSend(method, params = {}) {
  const id = ++requestId;
  socket.send(JSON.stringify({ id, method, params }));
  return new Promise((resolveMessage, rejectMessage) => pending.set(id, { resolve: resolveMessage, reject: rejectMessage }));
}

async function waitForDebuggerPort(timeoutMs = 15_000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const port = stderr.match(/DevTools listening on ws:\/\/127\.0\.0\.1:(\d+)\//)?.[1];
    if (port) return Number(port);
    if (chrome.exitCode !== null) throw new Error(`${browser} exited before DevTools started.\n${stderr.slice(-1800)}`);
    await sleep(50);
  }
  throw new Error(`Timed out waiting for Chromium DevTools.\n${stderr.slice(-1800)}`);
}

async function waitForMessage(ws) {
  return new Promise((resolveMessage, rejectMessage) => {
    ws.addEventListener('open', resolveMessage, { once: true });
    ws.addEventListener('error', () => rejectMessage(new Error('Could not connect to Chromium DevTools.')), { once: true });
  });
}

async function stopChrome() {
  socket?.close();
  if (!chrome || chrome.exitCode !== null) return;
  try {
    if (process.platform === 'win32') chrome.kill('SIGTERM');
    else process.kill(-chrome.pid, 'SIGTERM');
  } catch {}
  await Promise.race([
    new Promise((resolveClose) => chrome.once('close', resolveClose)),
    sleep(2_000).then(() => {
      try {
        if (process.platform === 'win32') chrome.kill('SIGKILL');
        else process.kill(-chrome.pid, 'SIGKILL');
      } catch {}
    }),
  ]);
}

let result = '';
try {
  chrome = spawn(browser, args, { detached: process.platform !== 'win32', stdio: ['ignore', 'ignore', 'pipe'] });
  chrome.stderr.setEncoding('utf8').on('data', (chunk) => { stderr += chunk; });
  const port = await waitForDebuggerPort();
  const targetResponse = await fetch(`http://127.0.0.1:${port}/json/new?${encodeURIComponent(url)}`, { method: 'PUT' });
  if (!targetResponse.ok) throw new Error(`Chromium could not open the smoke test page (HTTP ${targetResponse.status}).`);
  const target = await targetResponse.json();

  socket = new WebSocket(target.webSocketDebuggerUrl);
  await waitForMessage(socket);
  socket.addEventListener('message', (event) => {
    const message = JSON.parse(event.data);
    if (!message.id) return;
    const task = pending.get(message.id);
    if (!task) return;
    pending.delete(message.id);
    if (message.error) task.reject(new Error(message.error.message));
    else task.resolve(message.result);
  });

  await cdpSend('Runtime.enable');
  const deadline = Date.now() + 12_000;
  while (Date.now() < deadline) {
    const response = await cdpSend('Runtime.evaluate', {
      expression: 'document.body?.dataset.testResult || "loading"',
      returnByValue: true,
    });
    result = response.result?.value || 'loading';
    if (result !== 'running' && result !== 'loading') break;
    await sleep(100);
  }

  const resultTextResponse = await cdpSend('Runtime.evaluate', {
    expression: 'document.getElementById("result")?.textContent || "The page did not report a result."',
    returnByValue: true,
  });
  const resultText = resultTextResponse.result?.value;
  if (result !== 'pass') throw new Error(`${resultText}\n${stderr.slice(-1800)}`);
  console.log(resultText);
} finally {
  await stopChrome();
  await new Promise((resolveClose) => server.close(resolveClose));
  await sleep(200);
  await rm(profilePath, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
}
