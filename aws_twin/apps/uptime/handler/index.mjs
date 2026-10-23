// aws.twin uptime check: is each website up, from this AWS region, and a report only a vault can read.
// Node.js 22 on AWS Lambda, one file, no imports: fetch and WebCrypto are built in, in Node and in the
// browser, so the AWS twin runs this same file in the page and in CI.
//
// Ways in:
//   a schedule (EventBridge)  checks UPTIME_TARGETS
//   a direct Invoke           AWS has checked the caller's IAM authority; the event may name its own targets
//   a function URL            only with a request signed by the controller key (UPTIME_CONTROLLER_KEY):
//                             headers x-uptime-ts (unix seconds) and x-uptime-sig, base64 of a raw
//                             ECDSA P-256 / SHA-256 signature over `${ts}\n${body}`, within five minutes
// Out: the report, encrypted to UPTIME_RECIPIENT_KEY as sgit's envelope v2 (RSA-OAEP SHA-256 wrapping
// an AES-256-GCM key, as `sgit pki encrypt` writes it), appended to the sgit lane at UPTIME_APPEND_URL
// with UPTIME_APPEND_TOKEN. The function holds no private key; the token can write to the lane, not read it.
// Content CC BY 4.0, code Apache-2.0. https://aws.twin.sgit.ai/uptime/plan.html

const VERSION     = 'aws.twin-uptime/1';
const MAX_TARGETS = 50;
const TIMEOUT_MS  = 10000;
const SKEW_S      = 300;
const enc = new TextEncoder();

const b64      = (bytes) => { let s = ''; for (const b of bytes) s += String.fromCharCode(b); return btoa(s); };
const unb64    = (text) => Uint8Array.from(atob(text), (c) => c.charCodeAt(0));
const pemToDer = (pem) => unb64(String(pem).replace(/-----[A-Z ]+-----/g, '').replace(/\s+/g, ''));
const envOf    = () => (globalThis.process && globalThis.process.env) || {};

// ── which targets ─────────────────────────────────────────────────────────
function targetList(requested, configured) {
  let list = requested;
  if (!Array.isArray(list)) {
    try { list = JSON.parse(configured || '[]'); } catch { list = String(configured || '').split(','); }
  }
  return list.map((t) => (typeof t === 'string' ? t : t && t.url)).map((t) => String(t || '').trim()).filter(Boolean).slice(0, MAX_TARGETS);
}

// a signed request may name any URL; never this machine or a private network
function refusal(url) {
  let u;
  try { u = new URL(url); } catch { return 'not a URL'; }
  if (u.protocol !== 'https:' && u.protocol !== 'http:') return 'only http and https';
  const h = u.hostname.replace(/^\[|\]$/g, '').toLowerCase();
  if (h === 'localhost' || h.endsWith('.localhost') || h.endsWith('.internal')) return 'a local host';
  if (/^(127\.|10\.|0\.|169\.254\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)/.test(h)) return 'a private address';
  if (h === '::1' || /^(fc|fd|fe80):/.test(h)) return 'a private address';
  return null;
}

// ── one check ─────────────────────────────────────────────────────────────
async function check(url) {
  const why = refusal(url);
  if (why) return { url, ok: false, status: null, ms: 0, error: `refused: ${why}` };
  const started = Date.now();
  try {
    const res = await fetch(url, { method: 'GET', redirect: 'follow', signal: AbortSignal.timeout(TIMEOUT_MS),
                                   headers: { 'user-agent': `${VERSION} (+https://aws.twin.sgit.ai/uptime/)` } });
    const ms = Date.now() - started;
    try { await res.body?.cancel(); } catch { /* the status is all we need */ }
    return { url, ok: res.status < 400, status: res.status, ms, final_url: res.url || url, redirected: !!res.redirected, error: null };
  } catch (e) {
    const cause = e?.cause?.code || e?.cause?.message || e?.name;
    return { url, ok: false, status: null, ms: Date.now() - started, error: e?.name === 'TimeoutError' ? `timeout after ${TIMEOUT_MS} ms` : `${e?.message || e}${cause ? ` (${cause})` : ''}` };
  }
}

// ── sgit's envelope, version 2 ────────────────────────────────────────────
function recipientPem(value) {
  const text = String(value || '').trim();
  if (text.startsWith('{')) return JSON.parse(text).encrypt;            // an sgit public-key bundle
  return text;
}

export async function sgitEncrypt(publicKey, plaintext) {
  const rsa  = await crypto.subtle.importKey('spki', pemToDer(recipientPem(publicKey)), { name: 'RSA-OAEP', hash: 'SHA-256' }, false, ['encrypt']);
  const raw  = crypto.getRandomValues(new Uint8Array(32));
  const iv   = crypto.getRandomValues(new Uint8Array(12));
  const aes  = await crypto.subtle.importKey('raw', raw, { name: 'AES-GCM' }, false, ['encrypt']);
  const c    = new Uint8Array(await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, aes, enc.encode(plaintext)));
  const w    = new Uint8Array(await crypto.subtle.encrypt({ name: 'RSA-OAEP' }, rsa, raw));
  return b64(enc.encode(JSON.stringify({ v: 2, w: b64(w), i: b64(iv), c: b64(c) })));   // the .enc text
}

async function submit(report, env) {
  if (!env.UPTIME_APPEND_URL || !env.UPTIME_APPEND_TOKEN || !env.UPTIME_RECIPIENT_KEY) {
    return { ok: false, skipped: 'UPTIME_APPEND_URL, UPTIME_APPEND_TOKEN and UPTIME_RECIPIENT_KEY are not all set' };
  }
  try {
    const encText = await sgitEncrypt(env.UPTIME_RECIPIENT_KEY, JSON.stringify(report));
    const payload = b64(enc.encode(encText));                            // base64 of the .enc file: encoded twice, as sgit's drainers expect
    const res = await fetch(env.UPTIME_APPEND_URL, { method: 'POST', headers: { 'content-type': 'application/json' },
                                                     body: JSON.stringify({ append_token: env.UPTIME_APPEND_TOKEN, payload }),
                                                     signal: AbortSignal.timeout(TIMEOUT_MS) });
    return { ok: res.ok, status: res.status, bytes: payload.length };
  } catch (e) {
    return { ok: false, status: null, error: String(e?.message || e) };
  }
}

// ── a function URL request, signed by the controller ──────────────────────
async function verified(event, env) {
  if (!env.UPTIME_CONTROLLER_KEY) return { error: 'this function takes no URL requests: UPTIME_CONTROLLER_KEY is not set' };
  const h    = Object.fromEntries(Object.entries(event.headers || {}).map(([k, v]) => [k.toLowerCase(), v]));
  const body = event.isBase64Encoded ? new TextDecoder().decode(unb64(event.body || '')) : (event.body || '');
  const ts   = Number(h['x-uptime-ts']);
  if (!Number.isFinite(ts) || Math.abs(Date.now() / 1000 - ts) > SKEW_S) return { error: 'x-uptime-ts is missing or more than five minutes out' };
  let ok = false;
  try {
    const key = await crypto.subtle.importKey('spki', pemToDer(env.UPTIME_CONTROLLER_KEY), { name: 'ECDSA', namedCurve: 'P-256' }, false, ['verify']);
    ok = await crypto.subtle.verify({ name: 'ECDSA', hash: 'SHA-256' }, key, unb64(h['x-uptime-sig'] || ''), enc.encode(`${ts}\n${body}`));
  } catch { ok = false; }
  if (!ok) return { error: 'x-uptime-sig does not verify against the controller key' };
  try { return { request: body ? JSON.parse(body) : {} }; } catch { return { error: 'the body is not JSON' }; }
}

// ── the handler ───────────────────────────────────────────────────────────
export const handler = async (event = {}, context = {}) => {
  const env     = envOf();
  const viaUrl  = !!event?.requestContext?.http;
  const trigger = viaUrl ? 'url' : (event?.source === 'aws.events' ? 'schedule' : 'invoke');
  let request = {};
  if (viaUrl) {
    const v = await verified(event, env);
    if (v.error) return { statusCode: 403, headers: { 'content-type': 'application/json' }, body: JSON.stringify({ ok: false, error: v.error }) };
    request = v.request;
  } else if (trigger === 'invoke') {
    request = event || {};
  }
  const targets = targetList(request.targets, env.UPTIME_TARGETS);
  const checked_at = new Date().toISOString();
  const results = await Promise.all(targets.map(check));
  const report = { v: 1, kind: VERSION, region: env.AWS_REGION || 'unknown', function: context.functionName || env.AWS_LAMBDA_FUNCTION_NAME || null,
                   request_id: context.awsRequestId || null, trigger, checked_at, results };
  const submitted = await submit(report, env);
  const up = results.filter((r) => r.ok).length;
  console.log(`${trigger}: ${up} of ${results.length} up in ${report.region}; report ${submitted.ok ? 'appended' : 'not appended'}`);
  const summary = { ok: true, region: report.region, trigger, checked_at, up, down: results.length - up, results, submitted };
  return viaUrl ? { statusCode: 200, headers: { 'content-type': 'application/json' }, body: JSON.stringify(summary) } : summary;
};
