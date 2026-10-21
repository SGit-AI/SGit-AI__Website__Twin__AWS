/* aws.twin.sgit.ai — the S3 browser.

   Every action calls one Python method (aws_twin/web/S3__Browser.py) through Pyodide;
   the method calls OSBot-AWS or boto3; botocore signs the request; the Python twin in the
   same page answers it. The page renders what comes back and shows, under the console,
   the Python call and the AWS operations it caused.

   Persistence: the twin's memory VFS journals every change; after each call this page
   writes the changes through to sg-vfs's IndexedDbProvider (vendored from
   SGraph-AI__Tools), and on load it reads them back and seeds the twin. */
import { IndexedDbProvider } from '../vendor/sg-vfs/v0.1.0/sg-vfs-provider-indexeddb.js';

const REGIONS = ['eu-west-2', 'eu-west-1', 'eu-central-1', 'us-east-1', 'us-west-2', 'ap-southeast-1'];
const app = document.getElementById('s3-app');
const pyLog = document.getElementById('s3-py');
let browser = null, idb = null, flash = null, pyCalls = 0;
let mode = 'twin', liveInfo = null;                                     // twin: the Python twin answers; live: the real account
const SESSION_KEY = 'aws.twin/session', NAMED_KEY = 'aws.twin/live-buckets', RELAY_KEY = 'aws.twin/relay';
const store = { get(k, d) { try { const v = sessionStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } },
                set(k, v) { try { sessionStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* this tab only, or nowhere */ } } };
function pastedSession() {
  const s = store.get(SESSION_KEY, null);
  if (!s || !s.sessionToken) return null;
  s.expired = s.expiresAt && Date.parse(s.expiresAt) < Date.now();
  return s;
}
const sel = new Set();

const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmtSize = n => n < 1024 ? n + ' B' : n < 1048576 ? (n / 1024).toFixed(1) + ' KB' : (n / 1048576).toFixed(1) + ' MB';
const fmtDate = iso => { try { return new Date(iso).toLocaleString('en-GB', { dateStyle: 'long', timeStyle: 'medium', timeZone: 'UTC' }) + ' UTC'; } catch (e) { return iso; } };
const b64ToBytes = b64 => Uint8Array.from(atob(b64), c => c.charCodeAt(0));
const bytesToB64 = bytes => { let s = ''; const CH = 0x8000; for (let i = 0; i < bytes.length; i += CH) s += String.fromCharCode.apply(null, bytes.subarray(i, i + CH)); return btoa(s); };
const enc = s => encodeURIComponent(s);

/* ── Python ─────────────────────────────────────────────────────────────── */
async function api(name, args = {}) {
  const out = JSON.parse(browser.call(name, JSON.stringify(args)));
  await persist(out.changes);
  logCall(out.call);
  if (out.call.error) { const e = new Error(out.call.error.message); e.code = out.call.error.code; e.python = out.call.python; throw e; }
  return out.result;
}
async function persist(changes) {
  if (mode === 'live') return;                                          // live mode never writes the twin's store
  for (const c of changes) {
    if (c.op === 'write') await idb.writeFile(c.path, c.b64);
    else { try { await idb.deleteFile(c.path); } catch (e) { if (e.code !== 'ENOENT') throw e; } }
  }
}
function logCall(c) {
  pyCalls++;
  const ops = c.traffic.map(t => `<span class="op">${esc(t.service)}.${esc(t.operation)}</span> ${t.status < 400 ? `<span class="ok">${t.status}</span>` : `<span class="er">${t.status}</span>`}`).join(' · ');
  const where = c.mode === 'live' || (c.mode === undefined && mode === 'live') ? '<span class="er">live</span> ' : '<span class="ok">twin</span> ';
  const line = `<div><span class="d">${new Date().toISOString().slice(11, 19)}</span> ${where}<span class="py">${esc(c.python)}</span> <span class="d">${c.ms} ms →</span> ${ops || '<span class="d">no AWS call</span>'}${c.error ? ` <span class="er">${esc(c.error.code || c.error.type)}</span>` : ''}</div>`;
  pyLog.insertAdjacentHTML('beforeend', line);
  pyLog.querySelector('.h').textContent = `Python calls in this page · ${pyCalls} · each line is one method in aws_twin/web/S3__Browser.py, where it went (the twin, or live to the account), and the AWS operations it caused`;
  pyLog.scrollTop = pyLog.scrollHeight;
}
async function walkIdb(path, out) {
  for (const e of await idb.listFolder(path)) {
    if (e.type === 'folder') await walkIdb(e.path, out);
    else out.push({ path: e.path, b64: await idb.readFile(e.path) });
  }
  return out;
}

/* ── routing ────────────────────────────────────────────────────────────── */
function route() {
  const h = location.hash.replace(/^#\/?/, '');
  const [view, ...rest] = h.split('/');
  return { view: view || 'buckets', parts: rest.map(decodeURIComponent) };
}
const go = hash => { location.hash = hash; };
const say = (text, kind = 'ok', code) => { flash = { text, kind, code }; };

async function render() {
  const r = route();
  sel.clear();
  document.querySelectorAll('.s3-nav a').forEach(a => a.classList.toggle('here', a.dataset.view === r.view || (a.dataset.view === 'buckets' && ['b', 'obj', 'upload', 'props', 'create-bucket'].includes(r.view))));
  let html;
  try { html = await (VIEWS[r.view] || VIEWS.buckets)(...r.parts); }
  catch (e) { html = `<div class="s3-flash err"><b>${esc(e.code || 'Error')}</b> ${esc(e.message)}${e.python ? `<br><code>${esc(e.python)}</code>` : ''}</div>`; }
  const banner = mode === 'live' ? `<div class="s3-live">LIVE · account ${esc(liveInfo.account)} · ${liveInfo.allow_writes ? 'writes allowed' : 'read-only'} · ${liveInfo.relay ? 'through the local relay' : 'straight from this browser'} · <a href="#/live">change</a></div>` : '';
  app.innerHTML = banner + (flash ? `<div class="s3-flash ${flash.kind}">${esc(flash.text)}${flash.code ? ` <code>${esc(flash.code)}</code>` : ''}</div>` : '') + html;
  flash = null;
  bindDrop();
}

const crumb = (...items) => `<div class="s3-crumb"><a href="#/buckets">S3</a><span class="sep">›</span>` + items.map((it, i) => i === items.length - 1 ? esc(it[0]) : `<a href="${it[1]}">${esc(it[0])}</a>`).join('<span class="sep">›</span>') + '</div>';

/* ── views ──────────────────────────────────────────────────────────────── */
const VIEWS = {
  async buckets() {
    let buckets = [], blocked = null;
    try { buckets = await api('buckets'); }
    catch (e) { if (mode === 'live' && ['BrowserBlocked', 'AccessDenied'].includes(e.code)) blocked = e; else throw e; }
    if (mode === 'live') {                                              // buckets opened by name, when listing is not possible
      const named = store.get(NAMED_KEY, []).filter(n => !buckets.some(b => b.name === n.name));
      buckets = buckets.concat(named.map(n => ({ name: n.name, region: n.region, created: '', named: true })));
    }
    const rows = buckets.map(b => `<tr data-row="${esc(b.name)}"><td class="cb"><input type="radio" name="bucket" value="${esc(b.name)}"></td><td><a href="#/b/${enc(b.name)}">${esc(b.name)}</a>${b.named ? ' <span class="s3-tag">opened by name</span>' : ''}</td><td>${esc(b.region)}</td><td>${b.created ? esc(fmtDate(b.created)) : '-'}</td></tr>`).join('');
    const sub = mode === 'live'
      ? `These are the real account's buckets (${esc(liveInfo.account)}), read with the session pasted on <a href="../sessions/index.html">the sessions page</a>${liveInfo.relay ? `, through the local relay at <code>${esc(liveInfo.relay)}</code>` : ', straight from this browser'}.`
      : 'Buckets are containers for data stored in S3. These are answered by the twin in this page, kept in this browser.';
    const blockedBox = blocked ? `<div class="s3-flash err"><b>${blocked.code === 'AccessDenied' ? 'This role may not list buckets.' : 'S3 does not let a page list buckets.'}</b> ${blocked.code === 'AccessDenied'
        ? 'The session\'s permission set has no <code>s3:ListAllMyBuckets</code>. Open a bucket you may read by name below.'
        : 'ListBuckets never answers a browser (CORS). <a href="#/live">Start the local relay</a> to list them, or open a bucket by name below; a bucket opens directly when it has a CORS rule for this site (<a href="../iam/index.html#cors">the rule</a>).'}</div>` : '';
    const openForm = mode === 'live' ? `<form class="s3-form s3-inline" data-submit="open-bucket"><label>Open a bucket by name<input name="name" required placeholder="my-bucket" autocomplete="off"></label><div><button class="s3-btn" type="submit">Open</button></div></form>` : '';
    return crumb(['Buckets']) + `<h1>Buckets</h1>` + blockedBox + `
      <div class="s3-panel"><div class="s3-panel-h"><h2>General purpose buckets <span class="count">(${buckets.length})</span></h2>
        <button class="s3-btn" data-act="copy-arn" disabled>Copy ARN</button><button class="s3-btn" data-act="empty-bucket" disabled>Empty</button><button class="s3-btn" data-act="delete-bucket" disabled>Delete</button><button class="s3-btn primary" data-act="nav" data-to="#/create-bucket">Create bucket</button></div>
        <div class="s3-panel-sub">${sub}</div>
        ${openForm}
        <div class="s3-search"><input placeholder="Find buckets by name" data-filter="bucket"></div>
        ${buckets.length ? `<table class="s3-table"><thead><tr><th class="cb"></th><th>Name</th><th>AWS Region</th><th>Creation date</th></tr></thead><tbody>${rows}</tbody></table>`
          : mode === 'live' ? `<div class="s3-empty"><b>No buckets to show</b>${blocked ? 'Open one by name above.' : 'This account has no buckets the session can see.'}</div>`
          : `<div class="s3-empty"><b>No buckets</b>You don't have any buckets.<br><br><button class="s3-btn" data-act="nav" data-to="#/create-bucket">Create bucket</button> <button class="s3-btn" data-act="seed">Create an example bucket</button></div>`}
      </div>`;
  },

  async live() {
    const s = pastedSession();
    const relay = store.get(RELAY_KEY, { url: 'http://127.0.0.1:4567', on: false });
    const sess = s ? `<div class="s3-grid">
        <div><div class="k">Account</div><div class="v">${esc(s.accountId)}</div></div>
        <div><div class="k">Role</div><div class="v">${esc(s.role || '-')}</div></div>
        <div><div class="k">Region</div><div class="v">${esc(s.region)}</div></div>
        <div><div class="k">Expires</div><div class="v">${esc((s.expiresAt || '').replace('T', ' ').slice(0, 16))} UTC${s.expired ? ' <b style="color:#d91515">expired</b>' : ''}</div></div></div>`
      : `<div class="s3-panel-sub">No session in this tab. Paste one on <a href="../sessions/index.html">the sessions page</a> (in this same tab: the session lives in the tab's sessionStorage), then come back here.</div>`;
    return crumb(['Live session']) + `<h1>Live session</h1>
      <div class="s3-panel"><div class="s3-panel-h"><h2>Now: ${mode === 'live' ? `<span class="s3-live-word">live</span>, account ${esc(liveInfo.account)}${liveInfo.allow_writes ? ', writes allowed' : ', read-only'}` : 'the twin in this page'}</h2>
        ${mode === 'live' ? '<button class="s3-btn" data-act="go-twin">Back to the twin</button>' : ''}</div>
        <div class="s3-panel-sub">Live mode sends the same Python calls (OSBot-AWS and boto3) to the real account instead of the twin. Each request is signed in this page with the pasted session and recorded in <a href="#/traffic">Traffic</a>. Nothing is stored: live mode keeps nothing in this browser except the bucket names you open.</div></div>
      <div class="s3-panel"><div class="s3-panel-h"><h2>The session</h2></div>${sess}</div>
      <form class="s3-panel s3-form" data-submit="go-live" style="padding-top:1rem">
        <label><span><input type="checkbox" name="relay_on"${relay.on ? ' checked' : ''}> Use the local relay</span><small>S3 never lets a page list buckets, and answers a page for a bucket only when the bucket has a CORS rule for this site. The relay, on your machine, forwards the page's signed requests and adds the CORS headers. It holds no credentials and forwards only to *.amazonaws.com. The first time, the browser asks whether this site may reach apps on your device: allow it. Start the relay with:<br><code>curl -sO https://aws.twin.sgit.ai/aws_twin/core/Twin__Relay.py &amp;&amp; python3 Twin__Relay.py</code> · <a href="../how-it-works/index.html#relay">how it works</a></small></label>
        <label>Relay address<input name="relay_url" value="${esc(relay.url)}"></label>
        <label><span><input type="checkbox" name="allow_writes"> Allow writes</span><small>Off by default. Upload, create folder, rename, delete and bucket changes are refused in live mode until this is ticked, whatever the session's role allows.</small></label>
        <div><button class="s3-btn primary" type="submit"${s && !s.expired ? '' : ' disabled'}>Go live</button></div>
      </form>`;
  },

  async 'create-bucket'() {
    return crumb(['Buckets', '#/buckets'], ['Create bucket']) + `<h1>Create bucket</h1>
      <div class="s3-panel"><div class="s3-panel-h"><h2>General configuration</h2></div>
      <form class="s3-form" data-submit="create-bucket">
        <label>AWS Region<select name="region">${REGIONS.map(r => `<option${r === 'eu-west-2' ? ' selected' : ''}>${r}</option>`).join('')}</select></label>
        <label>Bucket name <small>Must be 3 to 63 characters: lower-case letters, numbers, dots and hyphens, starting and ending with a letter or number.</small><input name="name" required placeholder="my-bucket-name" autocomplete="off"></label>
        <label><span><input type="checkbox" name="versioning"> Enable bucket versioning <small>(the twin records the setting; it does not keep old versions yet)</small></span></label>
        <div><button class="s3-btn" type="button" data-act="nav" data-to="#/buckets">Cancel</button> <button class="s3-btn primary" type="submit">Create bucket</button></div>
      </form></div>`;
  },

  async b(bucket, ...prefixParts) {
    const segs = prefixParts.filter(Boolean);
    const prefix = segs.length ? segs.join('/') + '/' : '';                 // a folder route always ends in '/', with or without it in the URL
    const listing = await api('list', { bucket, prefix });
    const items = listing.folders.map(f => ({ folder: true, key: f, name: f.slice(prefix.length) })).concat(listing.files.map(f => ({ ...f, name: f.key.slice(prefix.length) })));
    const rows = items.map(it => it.folder
      ? `<tr data-row="${esc(it.key)}"><td class="cb"><input type="checkbox" value="${esc(it.key)}"></td><td><span class="ico">📁</span><a href="#/b/${enc(bucket)}/${it.key.split('/').filter(Boolean).map(enc).join('/')}/">${esc(it.name)}</a></td><td>Folder</td><td>-</td><td>-</td><td>-</td></tr>`
      : `<tr data-row="${esc(it.key)}"><td class="cb"><input type="checkbox" value="${esc(it.key)}"></td><td><span class="ico">📄</span><a href="#/obj/${enc(bucket)}/${enc(it.key)}">${esc(it.name)}</a></td><td>${esc((it.name.split('.').pop() || '').slice(0, 8))}</td><td>${esc(fmtDate(it.modified))}</td><td>${fmtSize(it.size)}</td><td>Standard</td></tr>`).join('');
    const pathCrumbs = prefix.split('/').filter(Boolean).map((p, i, arr) => [p + '/', `#/b/${enc(bucket)}/${arr.slice(0, i + 1).map(enc).join('/')}/`]);
    return crumb(['Buckets', '#/buckets'], [bucket, `#/b/${enc(bucket)}`], ...pathCrumbs) + `<h1>${esc(prefix ? prefix.split('/').filter(Boolean).pop() + '/' : bucket)}</h1>
      <div class="s3-tabs"><a class="here" href="#/b/${enc(bucket)}">Objects</a><a href="#/props/${enc(bucket)}">Properties</a><a href="#/traffic">Traffic</a></div>
      <div class="s3-panel"><div class="s3-panel-h"><h2>Objects <span class="count">(${items.length})</span></h2>
        <button class="s3-btn" data-act="refresh">↻</button><button class="s3-btn" data-act="copy-uri" disabled>Copy S3 URI</button><button class="s3-btn" data-act="download" disabled>Download</button><button class="s3-btn" data-act="rename" disabled>Rename</button><button class="s3-btn danger" data-act="delete" disabled>Delete</button><button class="s3-btn" data-act="create-folder">Create folder</button><button class="s3-btn primary" data-act="nav" data-to="#/upload/${enc(bucket)}/${prefix.split('/').filter(Boolean).map(enc).join('/')}">Upload</button></div>
        <div class="s3-panel-sub">Objects are the fundamental entities stored in S3. Folders are key prefixes, as in the console.</div>
        <div class="s3-search"><input placeholder="Find objects by prefix" data-filter="object"></div>
        ${items.length ? `<table class="s3-table" data-bucket="${esc(bucket)}" data-prefix="${esc(prefix)}"><thead><tr><th class="cb"><input type="checkbox" data-all></th><th>Name</th><th>Type</th><th>Last modified</th><th>Size</th><th>Storage class</th></tr></thead><tbody>${rows}</tbody></table>`
          : `<div class="s3-empty"><b>No objects</b>You don't have any objects in this ${prefix ? 'folder' : 'bucket'}.<br><br><button class="s3-btn primary" data-act="nav" data-to="#/upload/${enc(bucket)}/${prefix.split('/').filter(Boolean).map(enc).join('/')}">Upload</button></div>`}
      </div><div hidden id="ctx" data-bucket="${esc(bucket)}" data-prefix="${esc(prefix)}"></div>`;
  },

  async props(bucket) {
    const p = await api('bucket_properties', { name: bucket });
    return crumb(['Buckets', '#/buckets'], [bucket, `#/b/${enc(bucket)}`], ['Properties']) + `<h1>${esc(bucket)}</h1>
      <div class="s3-tabs"><a href="#/b/${enc(bucket)}">Objects</a><a class="here" href="#/props/${enc(bucket)}">Properties</a><a href="#/traffic">Traffic</a></div>
      <div class="s3-panel"><div class="s3-panel-h"><h2>Bucket overview</h2></div><div class="s3-grid">
        <div><div class="k">AWS Region</div><div class="v">${esc(p.region)}</div></div>
        <div><div class="k">Amazon Resource Name (ARN)</div><div class="v">${esc(p.arn)}</div></div>
        <div><div class="k">Answered by</div><div class="v">the Python twin in this page</div></div></div></div>
      <div class="s3-panel"><div class="s3-panel-h"><h2>Bucket Versioning</h2><button class="s3-btn" data-act="toggle-versioning" data-bucket="${esc(bucket)}" data-on="${p.versioning === 'Enabled' ? '0' : '1'}">${p.versioning === 'Enabled' ? 'Suspend' : 'Enable'}</button></div>
        <div class="s3-grid"><div><div class="k">Bucket Versioning</div><div class="v">${esc(p.versioning === 'Not Enabled' ? 'Disabled' : p.versioning)}</div></div></div>
        <div class="s3-panel-sub">The twin stores this setting and lists one version per object. It does not keep old versions yet.</div></div>
      <div class="s3-panel"><div class="s3-panel-h"><h2>Bucket policy</h2></div><div class="s3-preview">${p.policy ? esc(p.policy) : 'No policy to display.'}</div></div>`;
  },

  async obj(bucket, key) {
    const d = await api('details', { bucket, key });
    const prefix = key.includes('/') ? key.slice(0, key.lastIndexOf('/') + 1) : '';
    const pathCrumbs = prefix.split('/').filter(Boolean).map((p, i, arr) => [p + '/', `#/b/${enc(bucket)}/${arr.slice(0, i + 1).map(enc).join('/')}/`]);
    let preview = '';
    if (d.size <= 512 * 1024 && /^(text\/|application\/(json|xml|javascript))|svg/.test(d.content_type || '')) {
      const dl = await api('download', { bucket, key });
      preview = `<div class="s3-panel"><div class="s3-panel-h"><h2>Preview</h2></div><div class="s3-preview">${esc(new TextDecoder().decode(b64ToBytes(dl.b64)))}</div></div>`;
    } else if (d.size <= 5 * 1048576 && /^image\//.test(d.content_type || '')) {
      const dl = await api('download', { bucket, key });
      preview = `<div class="s3-panel"><div class="s3-panel-h"><h2>Preview</h2></div><div class="s3-preview"><img alt="${esc(key)}" src="data:${esc(d.content_type)};base64,${dl.b64}"></div></div>`;
    }
    const meta = Object.entries(d.metadata || {});
    return crumb(['Buckets', '#/buckets'], [bucket, `#/b/${enc(bucket)}`], ...pathCrumbs, [key.slice(prefix.length)]) + `<h1>${esc(key.slice(prefix.length))}</h1>
      <div class="s3-panel"><div class="s3-panel-h"><h2>Object overview</h2><button class="s3-btn" data-act="copy-text" data-text="s3://${esc(bucket)}/${esc(key)}">Copy S3 URI</button><button class="s3-btn" data-act="download-one" data-bucket="${esc(bucket)}" data-key="${esc(key)}">Download</button></div><div class="s3-grid">
        <div><div class="k">AWS Region</div><div class="v">${esc((await api('bucket_properties', { name: bucket })).region)}</div></div>
        <div><div class="k">Last modified</div><div class="v">${esc(fmtDate(d.modified))}</div></div>
        <div><div class="k">Size</div><div class="v">${fmtSize(d.size)} (${d.size} bytes)</div></div>
        <div><div class="k">Type</div><div class="v">${esc(d.content_type)}</div></div>
        <div><div class="k">Key</div><div class="v">${esc(key)}</div></div>
        <div><div class="k">S3 URI</div><div class="v">s3://${esc(bucket)}/${esc(key)}</div></div>
        <div><div class="k">Amazon Resource Name (ARN)</div><div class="v">arn:aws:s3:::${esc(bucket)}/${esc(key)}</div></div>
        <div><div class="k">Entity tag (Etag)</div><div class="v">${esc(d.etag.replace(/"/g, ''))}</div></div></div></div>
      <div class="s3-panel"><div class="s3-panel-h"><h2>Metadata <span class="count">(${meta.length})</span></h2></div>
        ${meta.length ? `<table class="s3-table"><thead><tr><th>Key</th><th>Value</th></tr></thead><tbody>${meta.map(([k, v]) => `<tr><td>x-amz-meta-${esc(k)}</td><td>${esc(v)}</td></tr>`).join('')}</tbody></table>` : '<div class="s3-panel-sub">No user-defined metadata.</div>'}
        <form class="s3-form" data-submit="metadata" data-bucket="${esc(bucket)}" data-key="${esc(key)}"><label>Replace user metadata <small>key=value, one per line; written with a copy onto itself, as S3 requires</small><textarea name="meta" rows="3">${esc(meta.map(([k, v]) => k + '=' + v).join('\n'))}</textarea></label><div><button class="s3-btn" type="submit">Save metadata</button></div></form></div>
      ${preview}`;
  },

  async upload(bucket, ...prefixParts) {
    prefixParts = prefixParts.filter(Boolean);
    const prefix = prefixParts.length ? prefixParts.join('/') + '/' : '';
    return crumb(['Buckets', '#/buckets'], [bucket, `#/b/${enc(bucket)}`], ['Upload']) + `<h1>Upload</h1>
      <div class="s3-panel"><div class="s3-panel-sub" style="padding-top:.9rem">Add the files you want to upload to <b>s3://${esc(bucket)}/${esc(prefix)}</b>. Each file is read in this browser and passed to <code>S3().file_create_from_bytes</code>.</div>
        <div class="s3-drop" id="drop">Drag and drop files here, or <label style="color:#0972d3;cursor:pointer;font-weight:700">choose files<input type="file" multiple hidden data-upload data-bucket="${esc(bucket)}" data-prefix="${esc(prefix)}"></label></div>
        <form class="s3-form" data-submit="upload-text" data-bucket="${esc(bucket)}" data-prefix="${esc(prefix)}"><label>Or write a text object <small>name and contents</small><input name="name" placeholder="notes.md" required></label><textarea name="body" rows="5" placeholder="# hello from the twin"></textarea><div><button class="s3-btn" type="button" data-act="nav" data-to="#/b/${enc(bucket)}/${prefixParts.map(enc).join('/')}">Cancel</button> <button class="s3-btn primary" type="submit">Upload</button></div></form>
      </div>`;
  },

  async traffic() {
    const recs = await api('traffic');
    return crumb(['Traffic']) + `<h1>Traffic</h1>
      <div class="s3-panel"><div class="s3-panel-h"><h2>Requests the twin answered <span class="count">(${recs.length})</span></h2><button class="s3-btn" data-act="export-traffic">Export JSON</button></div>
        <div class="s3-panel-sub">Every request botocore signed and sent, as AWS would have received it, and the twin's answer. This is the recording a replay plays back.</div>
        <table class="s3-table"><thead><tr><th>#</th><th>Operation</th><th>Request</th><th>Signed</th><th>Status</th><th>ms</th></tr></thead><tbody>${recs.slice().reverse().map(t => `<tr><td>${t.seq}</td><td>${esc(t.service)}.${esc(t.operation)}</td><td><code>${esc(t.method)} ${esc(t.url.replace(/^https:\/\//, '').slice(0, 90))}</code></td><td>${t.signed ? 'SigV4' : '-'}</td><td>${t.status}</td><td>${t.ms}</td></tr>`).join('')}</tbody></table></div>`;
  },

  async storage() {
    const files = await api('storage');
    return crumb(['Storage']) + `<h1>Storage</h1>
      <div class="s3-panel"><div class="s3-panel-h"><h2>The twin's virtual file system <span class="count">(${files.length} files)</span></h2><button class="s3-btn danger" data-act="reset">Reset everything</button></div>
        <div class="s3-panel-sub">What the S3 twin wrote, as sg-vfs paths: a bucket record, each object's bytes and its metadata. The same files are in this browser's IndexedDB (database <code>aws-twin-s3</code>), written through after every call.</div>
        <table class="s3-table"><thead><tr><th>Path</th><th>Size</th></tr></thead><tbody>${files.map(f => `<tr><td><code>${esc(f.path)}</code></td><td>${f.size}</td></tr>`).join('')}</tbody></table></div>`;
  }
};

/* ── actions ────────────────────────────────────────────────────────────── */
function selected() { return Array.from(sel); }
function ctx() { const c = document.getElementById('ctx'); return c ? { bucket: c.dataset.bucket, prefix: c.dataset.prefix } : {}; }
function updateButtons() {
  const n = sel.size;
  app.querySelectorAll('[data-act="copy-arn"],[data-act="empty-bucket"],[data-act="delete-bucket"]').forEach(b => { b.disabled = n !== 1; });
  app.querySelectorAll('[data-act="delete"]').forEach(b => { b.disabled = n === 0; });
  app.querySelectorAll('[data-act="copy-uri"],[data-act="download"],[data-act="rename"]').forEach(b => { b.disabled = n !== 1 || [...sel][0].endsWith('/'); });
  app.querySelectorAll('tr[data-row]').forEach(tr => tr.classList.toggle('sel', sel.has(tr.dataset.row)));
}
async function act(fn, ok) {
  try { const r = await fn(); if (ok) say(typeof ok === 'function' ? ok(r) : ok); }
  catch (e) {
    let m = String(e.message || e);
    if (m.includes('Traceback') || /^\w+(\.\w+)*Error: /.test(m)) m = m.trim().split('\n').pop().replace(/^[\w.]+: /, '');   // a Python error: its last line
    const code = e.code || (/An error occurred \((\w+)\)/.exec(m) || [])[1] || 'Error';
    say(`${code}: ${m.replace(/^An error occurred \(\w+\) when calling the (\w+) operation: /, '$1: ')}`, 'err', e.python);
  }
  await render();
}
function saveBlob(name, bytes, type) {
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([bytes], { type: type || 'application/octet-stream' })); a.download = name;
  document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 0);
}
async function uploadFiles(bucket, prefix, files) {
  let n = 0;
  for (const f of files) {
    const b64 = bytesToB64(new Uint8Array(await f.arrayBuffer()));
    await api('upload', { bucket, key: prefix + (f.webkitRelativePath || f.name), b64, content_type: f.type || null });
    n++;
  }
  return n;
}
function setModePill() {
  const pill = document.getElementById('s3-mode');
  pill.textContent = mode === 'live' ? `live: account ${liveInfo.account}${liveInfo.allow_writes ? '' : ', read-only'}` : 'answered by the Python twin in this page, not by AWS';
  pill.classList.toggle('live', mode === 'live');
}
const ACTIONS = {
  'go-twin': () => act(async () => { browser.use_twin(); mode = 'twin'; liveInfo = null; setModePill(); go('#/buckets'); }, 'Back to the twin'),
  nav: el => go(el.dataset.to),
  refresh: () => render(),
  seed: () => act(async () => {
    await api('create_bucket', { name: 'example-twin-bucket', region: 'eu-west-2' });
    const put = (key, text, type) => api('upload', { bucket: 'example-twin-bucket', key, b64: bytesToB64(new TextEncoder().encode(text)), content_type: type });
    await put('README.md', '# example-twin-bucket\n\nCreated by the S3 browser on aws.twin.sgit.ai, answered by the Python twin in this page.\n', 'text/markdown');
    await put('docs/how-it-works.txt', 'button → aws_twin/web/S3__Browser.py → OSBot-AWS S3() → boto3 → botocore (SigV4) → the twin → sg-vfs → IndexedDB\n', 'text/plain');
    await put('data/sample.json', JSON.stringify({ twin: true, services: ['s3', 'sts'], answered_by: 'python' }, null, 2), 'application/json');
    await put('images/twin.svg', '<svg xmlns="http://www.w3.org/2000/svg" width="240" height="80"><rect width="240" height="80" rx="12" fill="#0f766e"/><text x="120" y="48" font-family="sans-serif" font-size="20" fill="#fff" text-anchor="middle">the AWS twin</text></svg>', 'image/svg+xml');
  }, 'Created example-twin-bucket with four objects'),
  'copy-arn': () => { navigator.clipboard && navigator.clipboard.writeText('arn:aws:s3:::' + selected()[0]); say('Copied the ARN'); render(); },
  'copy-uri': () => { const c = ctx(); navigator.clipboard && navigator.clipboard.writeText(`s3://${c.bucket}/${selected()[0]}`); say('Copied the S3 URI'); render(); },
  'copy-text': el => { navigator.clipboard && navigator.clipboard.writeText(el.dataset.text); say('Copied ' + el.dataset.text); render(); },
  'empty-bucket': () => { const b = selected()[0]; if (confirm(`Empty ${b}? Every object in it is deleted.`)) act(() => api('empty_bucket', { name: b }), r => `Emptied ${b}: ${r.deleted} objects deleted`); },
  'delete-bucket': () => { const b = selected()[0]; if (confirm(`Delete ${b}?`)) act(() => api('delete_bucket', { name: b }), `Deleted bucket ${b}`); },
  delete: () => { const c = ctx(), keys = selected(); if (confirm(`Delete ${keys.length} item(s)? Folders are deleted with everything under them.`)) act(() => api('delete', { bucket: c.bucket, keys }), r => `Deleted ${r.deleted} object(s)`); },
  download: () => { const c = ctx(); ACTIONS['download-one']({ dataset: { bucket: c.bucket, key: selected()[0] } }); },
  'download-one': el => act(async () => { const d = await api('download', { bucket: el.dataset.bucket, key: el.dataset.key }); saveBlob(el.dataset.key.split('/').pop(), b64ToBytes(d.b64), d.content_type); }, 'Downloaded'),
  rename: () => { const c = ctx(), key = selected()[0]; const nk = prompt('New key', key); if (nk && nk !== key) act(() => api('rename', { bucket: c.bucket, key, new_key: nk }), `Renamed to ${nk}`); },
  'create-folder': () => { const c = ctx(); const name = prompt('Folder name'); if (name) act(() => api('create_folder', { bucket: c.bucket, prefix: c.prefix + name.replace(/\/+$/, '') + '/' }), `Created folder ${name}/`); },
  'toggle-versioning': el => act(() => api('set_versioning', { name: el.dataset.bucket, enabled: el.dataset.on === '1' }), 'Versioning updated'),
  'export-traffic': async () => { const t = await api('traffic'); saveBlob('aws-twin-traffic.json', new TextEncoder().encode(JSON.stringify(t, null, 2)), 'application/json'); },
  reset: () => { if (confirm('Delete every bucket and object the twin holds in this browser?')) act(async () => { for (const b of await api('buckets')) { await api('empty_bucket', { name: b.name }); await api('delete_bucket', { name: b.name }); } }, 'Reset: no buckets left'); }
};
const SUBMITS = {
  'go-live': (f, data) => act(async () => {
    const s = pastedSession();
    if (!s || s.expired) throw Object.assign(new Error('no unexpired session in this tab: paste one on the sessions page'), { code: 'NoSession' });
    const relayOn = !!data.get('relay_on'), url = (data.get('relay_url') || '').trim();
    store.set(RELAY_KEY, { url, on: relayOn });
    if (relayOn) {                                                      // an ordinary request first: it checks the relay is running,
      try {                                                             // and raises the browser's one-time local-network prompt
        const h = await fetch(url.replace(/\/+$/, '') + '/health', { signal: AbortSignal.timeout(60000) });
        if (!h.ok) throw new Error('HTTP ' + h.status);
      } catch (e) {
        throw Object.assign(new Error(`the local relay at ${url} did not answer (${e.message}). Start it with: python3 Twin__Relay.py, and allow this site to reach your device if the browser asks`), { code: 'RelayNotRunning' });
      }
    }
    const t = performance.now();
    const out = browser.use_live(JSON.stringify(s), relayOn ? url : '', !!data.get('allow_writes')).toJs({ dict_converter: Object.fromEntries });
    mode = 'live'; liveInfo = out; setModePill();
    logCall({ python: `S3__Browser().use_live(<session>, relay=${relayOn ? JSON.stringify(url) : 'None'}); sts.get_caller_identity()`, ms: Math.round(performance.now() - t), traffic: [{ service: 'sts', operation: 'GetCallerIdentity', status: 200 }] });
    go('#/buckets');
    return out;
  }, r => `Live: ${r.arn}`),
  'open-bucket': (f, data) => act(async () => {
    const name = data.get('name').trim();
    const r = await api('open_bucket', { name });
    const named = store.get(NAMED_KEY, []).filter(n => n.name !== name); named.push(r); store.set(NAMED_KEY, named);
    return r;
  }, r => `Opened ${r.name}${r.region ? ' (' + r.region + ')' : ''}`),
  'create-bucket': (f, data) => act(async () => { await api('create_bucket', { name: data.get('name').trim(), region: data.get('region') }); if (data.get('versioning')) await api('set_versioning', { name: data.get('name').trim(), enabled: true }); go('#/buckets'); }, `Successfully created bucket "${data.get('name').trim()}"`),
  'upload-text': (f, data) => act(async () => { await api('upload', { bucket: f.dataset.bucket, key: f.dataset.prefix + data.get('name').trim(), b64: bytesToB64(new TextEncoder().encode(data.get('body') || '')), content_type: /\.md$/.test(data.get('name')) ? 'text/markdown' : /\.json$/.test(data.get('name')) ? 'application/json' : 'text/plain' }); go(`#/b/${enc(f.dataset.bucket)}/${f.dataset.prefix.split('/').filter(Boolean).map(enc).join('/')}`); }, 'Upload succeeded'),
  metadata: (f, data) => act(() => api('metadata', { bucket: f.dataset.bucket, key: f.dataset.key, metadata: Object.fromEntries((data.get('meta') || '').split('\n').map(l => l.trim()).filter(Boolean).map(l => [l.split('=')[0].trim(), l.split('=').slice(1).join('=').trim()])) }), 'Metadata saved')
};

app.addEventListener('click', e => {
  const el = e.target.closest('[data-act]');
  if (el && !el.disabled) { e.preventDefault(); ACTIONS[el.dataset.act] && ACTIONS[el.dataset.act](el); }
});
app.addEventListener('change', e => {
  const t = e.target;
  if (t.matches('input[type=radio][name=bucket]')) { sel.clear(); sel.add(t.value); updateButtons(); }
  else if (t.matches('[data-all]')) { app.querySelectorAll('tbody input[type=checkbox]').forEach(cb => { cb.checked = t.checked; t.checked ? sel.add(cb.value) : sel.delete(cb.value); }); updateButtons(); }
  else if (t.matches('tbody input[type=checkbox]')) { t.checked ? sel.add(t.value) : sel.delete(t.value); updateButtons(); }
  else if (t.matches('[data-upload]')) { const b = t.dataset.bucket, p = t.dataset.prefix, files = Array.from(t.files); act(async () => { const n = await uploadFiles(b, p, files); go(`#/b/${enc(b)}/${p.split('/').filter(Boolean).map(enc).join('/')}`); return n; }, n => `Upload succeeded: ${n} file(s)`); }
});
app.addEventListener('input', e => {
  const t = e.target;
  if (t.matches('[data-filter]')) { const q = t.value.toLowerCase(); app.querySelectorAll('tbody tr[data-row]').forEach(tr => { tr.style.display = tr.dataset.row.toLowerCase().includes(q) ? '' : 'none'; }); }
});
app.addEventListener('submit', e => {
  const f = e.target.closest('form[data-submit]');
  if (f) { e.preventDefault(); SUBMITS[f.dataset.submit](f, new FormData(f)); }
});
function bindDrop() {
  const drop = document.getElementById('drop');
  if (!drop) return;
  const input = drop.querySelector('input[data-upload]');
  drop.addEventListener('dragover', e => { e.preventDefault(); drop.classList.add('over'); });
  drop.addEventListener('dragleave', () => drop.classList.remove('over'));
  drop.addEventListener('drop', e => { e.preventDefault(); drop.classList.remove('over'); const b = input.dataset.bucket, p = input.dataset.prefix, files = Array.from(e.dataTransfer.files); act(async () => { const n = await uploadFiles(b, p, files); go(`#/b/${enc(b)}/${p.split('/').filter(Boolean).map(enc).join('/')}`); return n; }, n => `Upload succeeded: ${n} file(s)`); });
}

/* ── start ──────────────────────────────────────────────────────────────── */
(async function start() {
  const steps = document.getElementById('s3-steps');
  const step = t => { steps.textContent += t + '\n'; };
  try {
    idb = new IndexedDbProvider({ dbName: 'aws-twin-s3' });
    await idb.init();
    const files = await walkIdb('/', []);
    step(`sg-vfs IndexedDB: ${files.length} file(s) to restore`);
    const py = await window.loadTwinPython({ onStep: (n, ms) => step(`loaded ${n} in ${ms} ms`) });
    py.runPython('from aws_twin.web.S3__Browser import S3__Browser\nbrowser = S3__Browser()');
    browser = py.globals.get('browser');
    const started = browser.start(JSON.stringify(files)).toJs({ dict_converter: Object.fromEntries });
    step(`twin started, ${started.files_restored} file(s) restored`);
    document.getElementById('s3-state').textContent = `Python ${py.runPython('import sys; sys.version.split()[0]')} · boto3 ${py.runPython('import boto3; boto3.__version__')} · OSBot-AWS ${py.runPython('from importlib.metadata import version; version("osbot-aws")')} · loaded in ${(py.twinTimings.total / 1000).toFixed(1)} s`;
    document.getElementById('s3-state').classList.add('ok');
    setModePill();
    window.__s3Ready = true;
    window.addEventListener('hashchange', render);
    await render();
  } catch (e) {
    app.innerHTML = `<div class="s3-flash err"><b>Could not start the twin.</b> ${esc(e.message)}</div><pre class="s3-preview">${esc(steps.textContent)}</pre>`;
    window.__s3Error = String(e && e.stack || e);
  }
}());
