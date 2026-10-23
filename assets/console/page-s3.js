/* The console's S3 page: buckets, objects, upload, properties. Every action calls one Python method
   (aws_twin/web/Console.py, whose S3 part is aws_twin/web/S3__Browser.py), which calls OSBot-AWS or
   boto3; the twin in this page answers, or the account does in live mode. In live mode buckets are
   listed through the Cloud Control API, because S3's own ListBuckets never answers a browser; a
   bucket's objects need a CORS rule on the bucket for this site, or the local relay. */
import { boot, api, act, esc, enc, state, go, say, render, fmtSize, b64ToBytes, bytesToB64, saveBlob, tabStore } from './core.js';

const REGIONS = ['eu-west-2', 'eu-west-1', 'eu-central-1', 'us-east-1', 'us-west-2', 'ap-southeast-1'];
const NAMED_KEY = 'aws.twin/live-buckets';
const store = tabStore;
const sel = new Set();
const app = () => document.getElementById('cx-app');
const fmtDate = iso => { try { return new Date(iso).toLocaleString('en-GB', { dateStyle: 'long', timeStyle: 'medium', timeZone: 'UTC' }) + ' UTC'; } catch (e) { return iso; } };
const mode = () => state.mode;

const crumb = (...items) => `<div class="s3-crumb"><a href="#/buckets">S3</a><span class="sep">›</span>` + items.map((it, i) => i === items.length - 1 ? esc(it[0]) : `<a href="${it[1]}">${esc(it[0])}</a>`).join('<span class="sep">›</span>') + '</div>';

/* ── views ──────────────────────────────────────────────────────────────── */
const VIEWS = {
  async buckets() {
    let buckets = [], blocked = null;
    try { buckets = await api('buckets'); }
    catch (e) { if (mode() === 'live' && ['BrowserBlocked', 'AccessDenied'].includes(e.code)) blocked = e; else throw e; }
    if (mode() === 'live') {                                              // buckets opened by name, when listing is not possible
      const named = store.get(NAMED_KEY, []).filter(n => !buckets.some(b => b.name === n.name));
      buckets = buckets.concat(named.map(n => ({ name: n.name, region: n.region, created: '', named: true })));
    }
    const rows = buckets.map(b => `<tr data-row="${esc(b.name)}"><td class="cb"><input type="radio" name="bucket" value="${esc(b.name)}"></td><td><a href="#/b/${enc(b.name)}">${esc(b.name)}</a>${b.named ? ' <span class="s3-tag">opened by name</span>' : ''}</td><td>${esc(b.region)}</td><td>${b.created ? esc(fmtDate(b.created)) : '-'}</td></tr>`).join('');
    const sub = mode() === 'live'
      ? `These are the real account's buckets (${esc(state.live.account)}), every region's, ${state.live.relay ? `listed through the local relay at <code>${esc(state.live.relay)}</code>` : 'listed through the <b>Cloud Control API</b> (S3\'s own ListBuckets never answers a browser; Cloud Control does, from this page)'}. Regions and creation dates are not in that list. Opening a bucket needs a CORS rule on it for this site (<a href="../iam/index.html#cors">the rule</a>), or the local relay.`
      : 'Buckets are containers for data stored in S3. These are answered by the twin in this page, kept in this browser.';
    const blockedBox = blocked ? `<div class="s3-flash err"><b>${blocked.code === 'AccessDenied' ? 'This role may not list buckets.' : 'S3 does not let a page list buckets.'}</b> ${blocked.code === 'AccessDenied'
        ? 'The session\'s role may not list buckets: listing through Cloud Control needs <code>cloudformation:ListResources</code> and <code>s3:ListAllMyBuckets</code> (<a href="../iam/index.html">least privilege</a>). Open a bucket you may read by name below.'
        : 'S3 ListBuckets never answers a browser (CORS); the console lists buckets through Cloud Control, which needs <code>cloudformation:ListResources</code> on the role. Open a bucket by name below.'}</div>` : '';
    const openForm = mode() === 'live' ? `<form class="s3-form s3-inline" data-submit="open-bucket"><label>Open a bucket by name<input name="name" required placeholder="my-bucket" autocomplete="off"></label><div><button class="s3-btn" type="submit">Open</button></div></form>` : '';
    return crumb(['Buckets']) + `<h1>Buckets</h1>` + blockedBox + `
      <div class="s3-panel"><div class="s3-panel-h"><h2>General purpose buckets <span class="count">(${buckets.length})</span></h2>
        <button class="s3-btn" data-act="copy-arn" disabled>Copy ARN</button><button class="s3-btn" data-act="empty-bucket" disabled>Empty</button><button class="s3-btn" data-act="delete-bucket" disabled>Delete</button><button class="s3-btn primary" data-act="nav" data-to="#/create-bucket">Create bucket</button></div>
        <div class="s3-panel-sub">${sub}</div>
        ${openForm}
        <div class="s3-search"><input placeholder="Find buckets by name" data-filter="bucket"></div>
        ${buckets.length ? `<table class="s3-table"><thead><tr><th class="cb"></th><th>Name</th><th>AWS Region</th><th>Creation date</th></tr></thead><tbody>${rows}</tbody></table>`
          : mode() === 'live' ? `<div class="s3-empty"><b>No buckets to show</b>${blocked ? 'Open one by name above.' : 'This account has no buckets the session can see.'}</div>`
          : `<div class="s3-empty"><b>No buckets</b>You don't have any buckets.<br><br><button class="s3-btn" data-act="nav" data-to="#/create-bucket">Create bucket</button> <button class="s3-btn" data-act="seed">Create an example bucket</button></div>`}
      </div>`;
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
      <div class="s3-tabs"><a class="here" href="#/b/${enc(bucket)}">Objects</a><a href="#/props/${enc(bucket)}">Properties</a></div>
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
      <div class="s3-tabs"><a href="#/b/${enc(bucket)}">Objects</a><a class="here" href="#/props/${enc(bucket)}">Properties</a></div>
      <div class="s3-panel"><div class="s3-panel-h"><h2>Bucket overview</h2></div><div class="s3-grid">
        <div><div class="k">AWS Region</div><div class="v">${esc(p.region)}</div></div>
        <div><div class="k">Amazon Resource Name (ARN)</div><div class="v">${esc(p.arn)}</div></div>
        <div><div class="k">Answered by</div><div class="v">${mode() === 'live' ? 'the account' : 'the Python twin in this page'}</div></div></div></div>
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
  }
};

/* ── actions ────────────────────────────────────────────────────────────── */
function selected() { return Array.from(sel); }
function ctx() { const c = document.getElementById('ctx'); return c ? { bucket: c.dataset.bucket, prefix: c.dataset.prefix } : {}; }
function updateButtons() {
  const n = sel.size;
  app().querySelectorAll('[data-act="copy-arn"],[data-act="empty-bucket"],[data-act="delete-bucket"]').forEach(b => { b.disabled = n !== 1; });
  app().querySelectorAll('[data-act="delete"]').forEach(b => { b.disabled = n === 0; });
  app().querySelectorAll('[data-act="copy-uri"],[data-act="download"],[data-act="rename"]').forEach(b => { b.disabled = n !== 1 || [...sel][0].endsWith('/'); });
  app().querySelectorAll('tr[data-row]').forEach(tr => tr.classList.toggle('sel', sel.has(tr.dataset.row)));
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
const ACTIONS = {
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
  reset: () => { if (confirm('Delete every bucket and object the twin holds in this browser?')) act(async () => { for (const b of await api('buckets')) { await api('empty_bucket', { name: b.name }); await api('delete_bucket', { name: b.name }); } }, 'Reset: no buckets left'); }
};
const SUBMITS = {
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


function onChange(e) {
  const t = e.target;
  if (t.matches('input[type=radio][name=bucket]')) { sel.clear(); sel.add(t.value); updateButtons(); }
  else if (t.matches('[data-all]')) { app().querySelectorAll('tbody input[type=checkbox]').forEach(cb => { cb.checked = t.checked; t.checked ? sel.add(cb.value) : sel.delete(cb.value); }); updateButtons(); }
  else if (t.matches('tbody input[type=checkbox]')) { t.checked ? sel.add(t.value) : sel.delete(t.value); updateButtons(); }
  else if (t.matches('[data-upload]')) { const b = t.dataset.bucket, p = t.dataset.prefix, files = Array.from(t.files); act(async () => { const n = await uploadFiles(b, p, files); go(`#/b/${enc(b)}/${p.split('/').filter(Boolean).map(enc).join('/')}`); return n; }, n => `Upload succeeded: ${n} file(s)`); }
}
function bindDrop() {
  sel.clear();
  const drop = document.getElementById('drop');
  if (!drop) return;
  const input = drop.querySelector('input[data-upload]');
  drop.addEventListener('dragover', e => { e.preventDefault(); drop.classList.add('over'); });
  drop.addEventListener('dragleave', () => drop.classList.remove('over'));
  drop.addEventListener('drop', e => { e.preventDefault(); drop.classList.remove('over'); const b = input.dataset.bucket, p = input.dataset.prefix, files = Array.from(e.dataTransfer.files); act(async () => { const n = await uploadFiles(b, p, files); go(`#/b/${enc(b)}/${p.split('/').filter(Boolean).map(enc).join('/')}`); return n; }, n => `Upload succeeded: ${n} file(s)`); });
}

boot({ page: 's3', home: 'buckets', views: VIEWS, actions: ACTIONS, submits: SUBMITS, onChange, afterRender: bindDrop });
