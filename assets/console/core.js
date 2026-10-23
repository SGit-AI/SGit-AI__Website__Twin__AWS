/* aws.twin.sgit.ai — the console's core, shared by every page under /console/.

   Each page is one service (Overview, S3, Lambda, All resources, Twin data) and imports this file
   with its own views. This file loads Python (Pyodide, boto3, OSBot-AWS, the twin), restores the
   twin's store from IndexedDB (sg-vfs, written through after every call, so every console page
   sees the same twin), keeps the mode (the twin, or live with the session pasted on /sessions/)
   and the region across pages for this tab, routes the page's hash to its views, and keeps the
   request pane: every Python call, every request it made, twin or live, and what came back.

   Every action calls one method of aws_twin/web/Console.py, entered with callPromising, so a
   Node.js Lambda function can run in the twin through the browser's JSPI. */
import { IndexedDbProvider } from '../vendor/sg-vfs/v0.1.0/sg-vfs-provider-indexeddb.js';

/* ── helpers every page uses ───────────────────────────────────────────── */
export const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
export const fmtSize = n => n == null ? '-' : n < 1024 ? n + ' B' : n < 1048576 ? (n / 1024).toFixed(1) + ' KB' : (n / 1048576).toFixed(1) + ' MB';
export const fmtDate = iso => { if (!iso) return '-'; try { return new Date(iso).toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'medium', timeZone: 'UTC' }) + ' UTC'; } catch (e) { return iso; } };
export const b64ToBytes = b64 => Uint8Array.from(atob(b64), c => c.charCodeAt(0));
export const bytesToB64 = bytes => { let s = ''; const CH = 0x8000; for (let i = 0; i < bytes.length; i += CH) s += String.fromCharCode.apply(null, bytes.subarray(i, i + CH)); return btoa(s); };
export const enc = s => encodeURIComponent(s);
export const pretty = v => `<pre class="s3-preview cx-json">${esc(typeof v === 'string' ? v : JSON.stringify(v, null, 2))}</pre>`;
export function saveBlob(name, bytes, type) {
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([bytes], { type: type || 'application/octet-stream' })); a.download = name;
  document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 0);
}
const tabStore = { get(k, d) { try { const v = sessionStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } },
                   set(k, v) { try { sessionStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* this tab only, or nowhere */ } } };
const keepStore = { get(k, d) { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } },
                    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* a convenience only */ } } };
export const SESSION_KEY = 'aws.twin/session', MODE_KEY = 'aws.twin/console-mode', REGION_KEY = 'aws.twin/console-region', PANE_KEY = 'aws.twin/console-pane';
export function pastedSession() {
  const s = tabStore.get(SESSION_KEY, null);
  if (!s || !s.sessionToken) return null;
  s.expired = !!(s.expiresAt && Date.parse(s.expiresAt) < Date.now());
  return s;
}
export { tabStore };

/* ── state ─────────────────────────────────────────────────────────────── */
export const state = { mode: 'twin', live: null, region: 'eu-west-2', regions: [], resourceTypes: [], page: '' };
let py = null, consoleObj = null, callFn = null, idb = null, flash = null, config = null;
const app = () => document.getElementById('cx-app');

/* ── Python ────────────────────────────────────────────────────────────── */
export async function api(name, args = {}, opts = {}) {
  const out = JSON.parse(await callFn.callPromising(name, JSON.stringify(args)));
  if (state.mode === 'twin') await persist(out.changes);
  if (!opts.quiet) pane.add(out.call);
  if (out.call.error) { const e = new Error(out.call.error.message); e.code = out.call.error.code; e.python = out.call.python; throw e; }
  return out.result;
}
async function persist(changes) {
  for (const c of changes) {
    if (c.op === 'write') await idb.writeFile(c.path, c.b64);
    else { try { await idb.deleteFile(c.path); } catch (e) { if (e.code !== 'ENOENT') throw e; } }
  }
}
async function walkIdb(path, out) {
  for (const e of await idb.listFolder(path)) {
    if (e.type === 'folder') await walkIdb(e.path, out);
    else out.push({ path: e.path, b64: await idb.readFile(e.path) });
  }
  return out;
}

/* ── routing, rendering ────────────────────────────────────────────────── */
export const go = hash => { location.hash = hash; };
export const say = (text, kind = 'ok', code) => { flash = { text, kind, code }; };
export function route() {
  const [view, ...rest] = location.hash.replace(/^#\/?/, '').split('/');
  return { view: view || config.home, parts: rest.map(decodeURIComponent) };
}
export function crumb(...items) {
  return `<div class="s3-crumb">` + items.map((it, i) => i === items.length - 1 || !it[1] ? esc(it[0]) : `<a href="${it[1]}">${esc(it[0])}</a>`).join('<span class="sep">›</span>') + '</div>';
}
export function errorBox(e) {
  let m = String(e.message || e);
  if (m.includes('Traceback') || /^\w+(\.\w+)*Error: /.test(m)) m = m.trim().split('\n').pop().replace(/^[\w.]+: /, '');
  const code = e.code || (/An error occurred \((\w+)\)/.exec(m) || [])[1] || 'Error';
  return `<div class="s3-flash err"><b>${esc(code)}</b> ${esc(m.replace(/^An error occurred \(\w+\) when calling the (\w+) operation: /, '$1: '))}${e.python ? `<br><code>${esc(e.python)}</code>` : ''}</div>`;
}
let renders = 0;
export async function render() {
  const r = route(), mine = ++renders;                                    // only the newest render may touch the page
  if (r.view === 'live') { openLiveForm(); history.replaceState(null, '', location.pathname + '#/' + config.home); return render(); }
  let html;
  try { html = await (config.views[r.view] || config.views[config.home])(...r.parts); }
  catch (e) { html = errorBox(e); }
  if (mine !== renders) return;                                           // a newer one started while this one waited: it shows the flash
  const banner = state.mode === 'live' ? `<div class="s3-live">LIVE · account ${esc(state.live.account)} · ${state.live.allow_writes ? 'writes allowed' : 'read-only'} · ${esc(state.region)} · <a href="#" data-cx="open-live">change</a></div>` : '';
  if (flash && flash.hash !== undefined && flash.hash !== location.hash) flash = null;   // a message belongs to the page it was shown on
  if (flash && flash.hash === undefined) flash.hash = location.hash;                     // and survives a redraw of that page
  app().innerHTML = banner + (flash ? `<div class="s3-flash ${flash.kind}">${esc(flash.text)}${flash.code ? ` <code>${esc(flash.code)}</code>` : ''}</div>` : '') + html;
  if (config.afterRender) config.afterRender();
}
export async function act(fn, ok) {
  try { const r = await fn(); if (ok) say(typeof ok === 'function' ? ok(r) : ok); }
  catch (e) { say(errorText(e), 'err', e.python); }
  await render();
}
function errorText(e) {
  let m = String(e.message || e);
  if (m.includes('Traceback') || /^\w+(\.\w+)*Error: /.test(m)) m = m.trim().split('\n').pop().replace(/^[\w.]+: /, '');
  const code = e.code || (/An error occurred \((\w+)\)/.exec(m) || [])[1] || 'Error';
  return `${code}: ${m.replace(/^An error occurred \(\w+\) when calling the (\w+) operation: /, '$1: ')}`;
}

/* ── the mode: the twin, or live ───────────────────────────────────────── */
function setTop() {
  const live = state.mode === 'live';
  document.querySelectorAll('#cx-mode button').forEach(b => b.classList.toggle('on', b.dataset.mode === state.mode));
  const who = document.getElementById('cx-who');
  who.textContent = live ? `live · ${state.live.account}${state.live.allow_writes ? '' : ' · read-only'}` : 'twin · 111111111111 · answered in this page';
  who.classList.toggle('live', live);
  document.querySelector('.cx-shell').classList.toggle('is-live', live);
}
function openLiveForm() {
  const box = document.getElementById('cx-live-form'), s = pastedSession(), saved = tabStore.get(MODE_KEY, {});
  box.innerHTML = s ? `<form class="cx-liveform" data-cx-form="go-live">
      <div><b>Live: the same calls, sent to the account</b> with the session pasted on <a href="../sessions/index.html">the sessions page</a>: account <code>${esc(s.accountId)}</code>${s.role ? `, role <code>${esc(s.role)}</code>` : ''}, ${s.expired ? '<b class="cx-bad">expired</b>' : 'expires ' + esc((s.expiresAt || '').slice(11, 16)) + ' UTC'}. Signed in this page, sent from this browser; every request shows in the request pane.</div>
      <label><input type="checkbox" name="allow_writes"${saved.allow_writes ? ' checked' : ''}> Allow writes <small>off: anything that changes the account (uploads, deletes, invoking a function) is refused before it is sent</small></label>
      <label><input type="checkbox" name="relay_on"${saved.relay ? ' checked' : ''}> Use the local relay for S3 <small>only for buckets without a CORS rule; buckets are listed through Cloud Control without it</small> <input name="relay_url" value="${esc(saved.relay || 'http://127.0.0.1:4567')}"></label>
      <div><button class="s3-btn primary" type="submit"${s.expired ? ' disabled' : ''}>Go live</button> <button class="s3-btn" type="button" data-cx="close-live">Cancel</button></div></form>`
    : `<div class="cx-liveform"><b>No session in this tab.</b> Paste one on <a href="../sessions/index.html">the sessions page</a>, in this same tab (the session lives in the tab's sessionStorage), then come back. <button class="s3-btn" type="button" data-cx="close-live">Close</button></div>`;
  box.hidden = false;
}
async function goLive(opts) {
  const s = pastedSession();
  if (!s || s.expired) throw Object.assign(new Error('no unexpired session in this tab: paste one on the sessions page'), { code: 'NoSession' });
  if (opts.relay) {
    try { const h = await fetch(opts.relay.replace(/\/+$/, '') + '/health', { signal: AbortSignal.timeout(60000) }); if (!h.ok) throw new Error('HTTP ' + h.status); }
    catch (e) { throw Object.assign(new Error(`the local relay at ${opts.relay} did not answer (${e.message})`), { code: 'RelayNotRunning' }); }
  }
  const t = performance.now();
  const info = consoleObj.use_live(JSON.stringify(s), opts.relay || '', !!opts.allow_writes).toJs({ dict_converter: Object.fromEntries });
  state.mode = 'live'; state.live = info;
  tabStore.set(MODE_KEY, { mode: 'live', allow_writes: !!opts.allow_writes, relay: opts.relay || '' });
  pane.add({ name: 'use_live', python: `Console().use_live(<session>, relay=${opts.relay ? JSON.stringify(opts.relay) : 'None'}, allow_writes=${!!opts.allow_writes}); sts.get_caller_identity()`, ms: Math.round(performance.now() - t), traffic: [{ service: 'sts', operation: 'GetCallerIdentity', status: 200, method: 'POST', url: 'https://sts.amazonaws.com/' }], error: null, mode: 'live' });
  if (s.region && !keepStore.get(REGION_KEY, null)) await setRegion(s.region);
  setTop();
  return info;
}
function goTwin() {
  consoleObj.use_twin();
  state.mode = 'twin'; state.live = null;
  tabStore.set(MODE_KEY, { mode: 'twin' });
  setTop();
}
async function setRegion(region) {
  await api('set_region', { region }, { quiet: true });
  state.region = region; keepStore.set(REGION_KEY, region);
  document.getElementById('cx-region').value = region;
}

/* ── the request pane ──────────────────────────────────────────────────── */
export const pane = {
  calls: [], filter: '',
  add(c) {
    c.at = c.at || new Date().toISOString(); c.mode = c.mode || state.mode; c.account = state.mode === 'live' ? state.live.account : '111111111111'; c.region = state.region;
    this.calls.push(c); if (this.calls.length > 300) this.calls.shift();
    document.getElementById('cx-count').textContent = this.calls.length;
    if (!document.getElementById('cx-pane').hidden) this.draw();
  },
  line(c) {
    const ops = (c.traffic || []).map(t => `${t.service}.${t.operation}`).join(' ');
    return `${c.mode} ${c.account}/${c.region} ${c.python} ${ops} ${c.error ? c.error.code : 'ok'}`.toLowerCase();
  },
  draw() {
    const list = this.calls.slice().reverse().filter(c => !this.filter || this.line(c).includes(this.filter.toLowerCase()));
    document.getElementById('cx-pane-list').innerHTML = list.length ? list.map(c => {
      const n = (c.traffic || []).length;
      const where = (c.traffic || []).some(t => t.target === 'live') ? 'live' : c.mode;   // a probe from the twin still goes to AWS
      const status = c.error ? `<span class="r">${esc(c.error.code || c.error.type)}</span>` : `<span class="g">ok</span>`;
      return `<details class="cx-call"><summary><span class="d">${esc(c.at.slice(11, 19))}</span> <span class="${where === 'live' ? 'lv' : 'tw'}">${where}</span> <span class="d">${esc(c.account)}/${esc(c.region)}</span> <b>${esc(c.name)}</b> <span class="d">${c.ms} ms · ${n} request${n === 1 ? '' : 's'} →</span> ${status}</summary>
        <div class="cx-py">${esc(c.python)}</div>${c.error ? `<div class="cx-err">${esc(c.error.message)}</div>` : ''}
        ${(c.traffic || []).map(t => `<details class="cx-req" data-seq="${t.seq ?? ''}"><summary><span class="${(t.target || c.mode) === 'live' ? 'lv' : 'tw'}">${(t.target || c.mode) === 'live' ? 'AWS' : 'twin'}</span> <b>${esc(t.service)}.${esc(t.operation)}</b> <span class="d">${esc(t.method || '')} ${esc((t.url || '').replace(/^https:\/\//, '').slice(0, 80))}</span> → <span class="${t.status < 400 ? 'g' : 'r'}">${t.status}</span> <span class="d">${t.ms ?? ''}${t.ms != null ? ' ms' : ''}</span></summary><div class="cx-req-body">click to load</div></details>`).join('')}</details>`;
    }).join('') : `<div class="cx-empty">${this.calls.length ? 'Nothing matches the filter.' : 'No calls yet. Every Python call this page makes shows here, with each request it sent, to the twin or to AWS, and what came back.'}</div>`;
  },
  async load(el) {
    const seq = Number(el.dataset.seq), box = el.querySelector('.cx-req-body');
    if (!seq || box.dataset.loaded) return;
    box.dataset.loaded = '1';
    try {
      const r = await api('request', { seq }, { quiet: true });
      const body = b => !b ? '<span class="d">(no body)</span>' : b.binary ? `<span class="d">${b.bytes} bytes, binary</span>` : `<pre>${esc(b.text)}${b.truncated ? `\n… ${b.bytes} bytes in all` : ''}</pre>`;
      const heads = h => `<pre>${esc(Object.entries(h || {}).map(([k, v]) => `${k}: ${v}`).join('\n'))}</pre>`;
      const b64url = x => btoa(unescape(encodeURIComponent(x))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
      const replay = r.api ? `<a class="s3-btn cx-small" href="calls.html#/editor/${enc(r.api.service)}/${enc(r.api.operation)}/${b64url(JSON.stringify(r.api.params))}">Replay in the call editor</a> <span class="d">${esc(r.api.service)}.${esc(r.api.operation)}(${esc(JSON.stringify(r.api.params).slice(0, 160))})</span>` : '';
      const twinBtn = r.target === 'live' && /^(List|Get|Describe|Head)/.test(r.operation) ? `<button class="s3-btn cx-small" data-cx="twin-answer" data-seq="${seq}">What would the twin answer?</button><div class="cx-twin-answer"></div>` : '';
      box.innerHTML = `<div class="cx-kv"><b>${esc(r.method)}</b> ${esc(r.url)} <span class="d">· ${r.signed ? 'SigV4-signed in this page' : 'unsigned'} · ${esc(r.at)}</span></div>${replay ? `<div>${replay}</div>` : ''}
        <div class="cx-sub">request headers <span class="d">(the session token is masked; Authorization is never kept)</span></div>${heads(r.request.headers)}<div class="cx-sub">request body</div>${body(r.request.body)}
        <div class="cx-sub">response ${r.status}</div>${heads(r.response.headers)}${body(r.response.body)}${twinBtn}`;
    } catch (e) { box.innerHTML = `<span class="r">${esc(e.message)}</span>`; }
  },
  open(on) {
    const p = document.getElementById('cx-pane');
    p.hidden = !on; document.querySelector('.cx-shell').classList.toggle('pane-open', on);
    keepStore.set(PANE_KEY, on);
    if (on) this.draw();
  }
};

/* ── boot ──────────────────────────────────────────────────────────────── */
export async function boot(cfg) {
  config = cfg;
  state.page = cfg.page;
  const steps = document.getElementById('cx-steps'), step = t => { if (steps) steps.textContent += t + '\n'; };
  document.addEventListener('click', e => {
    const el = e.target.closest('[data-cx]');
    if (!el) return;
    const a = el.dataset.cx;
    if (a === 'open-live') { e.preventDefault(); openLiveForm(); }
    else if (a === 'close-live') document.getElementById('cx-live-form').hidden = true;
    else if (a === 'pane') pane.open(document.getElementById('cx-pane').hidden);
    else if (a === 'pane-clear') { pane.calls = []; document.getElementById('cx-count').textContent = 0; pane.draw(); }
    else if (a === 'pane-export') saveBlob('aws-twin-console-calls.json', new TextEncoder().encode(JSON.stringify(pane.calls, null, 2)), 'application/json');
    else if (a === 'twin-answer') {
      api('request_twin', { seq: Number(el.dataset.seq) }, { quiet: true }).then(r => {
        el.nextElementSibling.innerHTML = `<div class="cx-sub">the twin answers ${r.status}${r.same_status ? ' (the same status)' : ' (AWS answered ' + r.live_status + ')'}</div><pre>${esc(r.body || '')}</pre>`;
      }).catch(err => { el.nextElementSibling.innerHTML = `<span class="r">${esc(err.message)}</span>`; });
    }
  });
  const appEl = app();
  appEl.addEventListener('click', e => {
    const el = e.target.closest('[data-act]');
    if (el && !el.disabled && cfg.actions && cfg.actions[el.dataset.act]) { e.preventDefault(); cfg.actions[el.dataset.act](el); }
  });
  appEl.addEventListener('submit', e => {
    const f = e.target.closest('form[data-submit]');
    if (f && cfg.submits && cfg.submits[f.dataset.submit]) { e.preventDefault(); cfg.submits[f.dataset.submit](f, new FormData(f)); }
  });
  appEl.addEventListener('change', e => { if (cfg.onChange) cfg.onChange(e); });
  appEl.addEventListener('input', e => {
    const t = e.target;
    if (t.matches('[data-filter]')) { const q = t.value.toLowerCase(); appEl.querySelectorAll('tbody tr[data-row]').forEach(tr => { tr.style.display = tr.dataset.row.toLowerCase().includes(q) ? '' : 'none'; }); }
    if (cfg.onInput) cfg.onInput(e);
  });
  document.addEventListener('toggle', e => { const d = e.target; if (d.matches && d.matches('details.cx-req') && d.open) pane.load(d); }, true);
  document.getElementById('cx-pane-filter').addEventListener('input', e => { pane.filter = e.target.value; pane.draw(); });
  document.querySelectorAll('#cx-mode button').forEach(b => b.addEventListener('click', () => {
    if (!consoleObj) return;
    if (b.dataset.mode === 'live') openLiveForm();
    else if (state.mode === 'live') { goTwin(); document.getElementById('cx-live-form').hidden = true; render(); }
  }));
  document.getElementById('cx-live-form').addEventListener('submit', e => {
    const f = e.target.closest('form[data-cx-form="go-live"]');
    if (!f) return;
    e.preventDefault();
    const d = new FormData(f);
    act(async () => { const info = await goLive({ allow_writes: !!d.get('allow_writes'), relay: d.get('relay_on') ? (d.get('relay_url') || '').trim() : '' }); document.getElementById('cx-live-form').hidden = true; return info; }, r => `Live: ${r.arn}`);
  });
  document.getElementById('cx-region').addEventListener('change', e => act(() => setRegion(e.target.value), `Region: ${e.target.value}`));
  if (keepStore.get(PANE_KEY, false)) pane.open(true);
  try {
    idb = new IndexedDbProvider({ dbName: 'aws-twin-s3' });              // the name from before the console: the same twin store
    await idb.init();
    const files = await walkIdb('/', []);
    step(`the twin's store (IndexedDB, sg-vfs): ${files.length} file(s)`);
    py = await window.loadTwinPython({ onStep: (n, ms) => step(`loaded ${n} in ${ms} ms`) });
    py.runPython('import aws_twin.web.Console as M\nM.console = M.Console()');
    const mod = py.pyimport('aws_twin.web.Console');
    consoleObj = mod.console; callFn = mod.console_call;
    const region = keepStore.get(REGION_KEY, null) || (pastedSession() || {}).region || 'eu-west-2';
    consoleObj.start(JSON.stringify(files), region);
    const st = await api('status', {}, { quiet: true });
    state.regions = st.regions; state.resourceTypes = st.resource_types; state.region = st.region;
    document.getElementById('cx-region').innerHTML = st.regions.map(r => `<option${r === region ? ' selected' : ''}>${r}</option>`).join('');
    const saved = tabStore.get(MODE_KEY, {});
    if (saved.mode === 'live') {
      try { await goLive(saved); }
      catch (e) { say(`Not live: ${errorText(e)}`, 'err'); tabStore.set(MODE_KEY, { mode: 'twin' }); }
    }
    setTop();
    document.getElementById('cx-state').textContent = `Python ${py.runPython('import sys; sys.version.split()[0]')} · boto3 ${py.runPython('import boto3; boto3.__version__')} · ${(py.twinTimings.total / 1000).toFixed(1)} s`;
    window.addEventListener('hashchange', render);
    await render();
    window.__consoleReady = true;
  } catch (e) {
    app().innerHTML = `<div class="s3-flash err"><b>Could not start the console.</b> ${esc(e.message)}</div><pre class="s3-preview">${esc(steps ? steps.textContent : '')}</pre>`;
    window.__consoleError = String(e && e.stack || e);
  }
}
