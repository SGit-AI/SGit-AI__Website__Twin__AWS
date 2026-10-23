// The Lambda twin's runtime for Node.js handlers. One file, two hosts:
//   node (CPython, CI):  node node_harness.mjs < invocation.json > result.json
//   a browser (Pyodide): imported by the page; the twin waits for runInvocation() through JSPI.
// It imports the deployed module, gives it the function's environment, swaps fetch for the twin's
// internet (configured answers per URL, and the sgit append lanes the twin holds), captures what
// it logs, and returns the handler's result with every request the function made.
// No imports: what it uses (fetch's Response, WebCrypto, TextEncoder) is global in both hosts.

const enc = new TextEncoder();
const b64 = (s) => { let bin = ''; for (const c of enc.encode(s)) bin += String.fromCharCode(c); return btoa(bin); };
const sleep = (ms, signal) => new Promise((resolve, reject) => {
  if (signal?.aborted) return reject(signal.reason);
  const t = setTimeout(resolve, ms);
  signal?.addEventListener('abort', () => { clearTimeout(t); reject(signal.reason); }, { once: true });
});
const hex = (buf) => Array.from(new Uint8Array(buf), (b) => b.toString(16).padStart(2, '0')).join('');
const show = (v) => { if (typeof v === 'string') return v; try { return JSON.stringify(v); } catch { return String(v); } };

function headersOf(init, resource) {
  const out = {};
  const h = new Headers(init?.headers || resource?.headers || {});
  h.forEach((v, k) => { out[k] = v; });
  return out;
}

// sgit's append write, as the server answers it (sgit.ai/api/append-lanes.md, checked 26 September 2026):
// 400 JSON for a malformed token or a missing field, 413 over 5 MB, 404 with an HTML page for an unknown
// vault or a token whose sha256 is not one of the lane's anchors, else exactly {"ok": true}.
async function appendLane(lane, body) {
  let doc;
  try { doc = JSON.parse(body || ''); } catch { return [400, { detail: 'the body is not JSON' }]; }
  const token = doc.append_token || '';
  if (!/^[0-9a-f]{16,128}$/.test(token)) return [400, { detail: 'append_token must be 16 to 128 hex characters' }];
  if (typeof doc.payload !== 'string' || !doc.payload) return [400, { detail: 'payload is required' }];
  if (doc.payload.length > 5 * 1024 * 1024) return [413, { detail: 'payload too large' }];
  const anchor = hex(await crypto.subtle.digest('SHA-256', enc.encode(token)));
  if (!lane.anchors.includes(anchor)) return [404, null];
  return [200, { ok: true }];
}

function twinFetch(internet, requests) {
  return async function fetch(resource, init = {}) {
    const url = typeof resource === 'string' ? resource : (resource?.url ?? String(resource));
    const method = (init.method || resource?.method || 'GET').toUpperCase();
    const body = typeof init.body === 'string' ? init.body : (init.body == null ? null : String(init.body));
    const record = { method, url, headers: headersOf(init, resource), body, status: null, error: null };
    requests.push(record);
    const lane = internet.lanes?.[url.split('?')[0]];
    if (lane) {
      const [status, answer] = await appendLane(lane, body);
      record.status = status;
      if (answer === null) return new Response('<!doctype html><title>404 Not Found</title><h1>Not Found</h1>', { status, headers: { 'content-type': 'text/html' } });
      return new Response(JSON.stringify(answer), { status, headers: { 'content-type': 'application/json' } });
    }
    let host = '';
    try { host = new URL(url).host; } catch { /* the function's own check refuses bad URLs */ }
    const a = internet.answers?.[url] ?? internet.answers?.[url.replace(/\/$/, '')] ?? internet.answers?.[host] ?? internet.answers?.['*'];
    if (!a) {
      record.error = 'ENOTFOUND';
      throw new TypeError('fetch failed', { cause: { code: 'ENOTFOUND', message: `the twin's internet has no answer for ${url}` } });
    }
    if (a.ms) await sleep(Math.min(a.ms, 15000), init.signal);
    if (a.error) {
      record.error = a.error;
      throw new TypeError('fetch failed', { cause: { code: a.error, message: `${a.error} (the twin's internet, as configured)` } });
    }
    record.status = a.status ?? 200;
    const empty = [101, 204, 205, 304].includes(record.status);
    return new Response(empty ? null : (a.body ?? ''), { status: record.status, headers: a.headers || { 'content-type': 'text/html' } });
  };
}

async function importHandler(files, module, revision) {
  let code = files[module];
  if (code == null) {
    const e = new Error(`Cannot find module '${module.replace(/\.m?js$/, '')}'`); e.name = 'Runtime.ImportModuleError'; throw e;
  }
  if (module.endsWith('.js') && !/^\s*export\s/m.test(code)) {          // CommonJS, as Lambda reads a .js file by default
    code = `const module = { exports: {} }; const exports = module.exports;\n${code}\nexport default module.exports;`;
  }
  return import('data:text/javascript;base64,' + b64(`${code}\n//# aws.twin revision ${revision}`));
}

export async function runInvocation(input) {
  const logs = [], requests = [];
  const started = Date.now();
  const log = (level) => (...a) => logs.push(`${new Date().toISOString()}\t${input.context.awsRequestId}\t${level}\t${a.map(show).join(' ')}`);
  const isNode = !!globalThis.process?.versions?.node;
  const saved = { fetch: globalThis.fetch, console: globalThis.console, process: globalThis.process, env: isNode ? { ...process.env } : null };
  try {
    if (isNode) { for (const k of Object.keys(process.env)) if (!(k in input.env) && /^(AWS_|LAMBDA_)/.test(k)) delete process.env[k]; Object.assign(process.env, input.env); }
    else globalThis.process = { env: { ...input.env }, versions: {} };
    globalThis.fetch = twinFetch(input.internet || {}, requests);
    globalThis.console = Object.assign(Object.create(saved.console), { log: log('INFO'), info: log('INFO'), warn: log('WARN'), error: log('ERROR'), debug: log('DEBUG') });
    const mod = await importHandler(input.files, input.module, input.revision);
    const fn = mod[input.fn] ?? mod.default?.[input.fn];
    if (typeof fn !== 'function') {
      const e = new Error(`${input.module.replace(/\.m?js$/, '')}.${input.fn} is undefined or not exported`); e.name = 'Runtime.HandlerNotFound'; throw e;
    }
    const deadline = started + input.timeout_ms;
    const context = { functionName: input.context.functionName, functionVersion: '$LATEST', invokedFunctionArn: input.context.invokedFunctionArn,
                      memoryLimitInMB: String(input.context.memoryLimitInMB), awsRequestId: input.context.awsRequestId,
                      logGroupName: input.context.logGroupName, logStreamName: input.context.logStreamName,
                      callbackWaitsForEmptyEventLoop: true, getRemainingTimeInMillis: () => Math.max(0, deadline - Date.now()) };
    let timer;
    const timeout = new Promise((_, reject) => { timer = setTimeout(() => { const e = new Error(`Task timed out after ${(input.timeout_ms / 1000).toFixed(2)} seconds`); e.name = 'Sandbox.Timedout'; reject(e); }, input.timeout_ms); });
    try {
      const result = await Promise.race([Promise.resolve(fn(input.event, context)), timeout]);
      return { result: result === undefined ? null : result, error: null, logs, requests, ms: Date.now() - started };
    } finally { clearTimeout(timer); }
  } catch (e) {
    logs.push(`${new Date().toISOString()}\t${input.context.awsRequestId}\tERROR\t${e?.name || 'Error'}: ${e?.message || e}`);
    return { result: null, error: { errorType: e?.name || 'Error', errorMessage: String(e?.message ?? e), trace: String(e?.stack || '').split('\n').slice(0, 10) },
             logs, requests, ms: Date.now() - started };
  } finally {
    globalThis.fetch = saved.fetch; globalThis.console = saved.console;
    if (isNode) { for (const k of Object.keys(process.env)) if (!(k in saved.env)) delete process.env[k]; Object.assign(process.env, saved.env); }
    else if (saved.process === undefined) delete globalThis.process; else globalThis.process = saved.process;
  }
}

// node node_harness.mjs < input.json
if (globalThis.process?.versions?.node && process.argv[1]?.endsWith('node_harness.mjs')) {
  let text = '';
  process.stdin.setEncoding('utf8');
  for await (const chunk of process.stdin) text += chunk;
  process.stdout.write(JSON.stringify(await runInvocation(JSON.parse(text))));
}
