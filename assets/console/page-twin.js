/* The console's Twin data page: what the twin holds in this browser, file by file. The twin's state
   is an sg-vfs file system: each service keeps its resources as JSON documents and bytes under its own
   folder, and every change is written through to IndexedDB (database aws-twin-s3), which is what
   every console page restores on load. A vault is the next place for the same files (see the plan). */
import { boot, api, act, esc, enc, crumb, state, go, pretty, fmtSize, render } from './core.js';

const WHAT = { s3: 'S3: a record per bucket, each object\'s bytes and metadata', lambda: 'Lambda: per region, each function\'s configuration, code (.zip), policy, URL and last invocations',
               iam: 'IAM: roles, their trust policies and attached policies', events: 'EventBridge: per region, rules and their targets',
               cloudfront: 'CloudFront: distributions, with their configuration as sent', sgit: 'sgit append lanes: what functions appended, as the server holds it',
               internet: 'the internet a twinned function reaches: an answer per URL' };

boot({
  page: 'twin', home: 'tree',
  views: {
    async tree() {
      const t = await api('twin_tree');
      const groups = Object.entries(t.groups).sort();
      return crumb(['Twin data']) + `<h1>What the twin holds</h1>
        ${state.mode === 'live' ? '<div class="s3-flash ok">You are in live mode: this page still shows the twin\'s own data in this browser, not the account\'s.</div>' : ''}
        <div class="cx-cards">${groups.map(([g, s]) => `<a class="cx-card" href="#" data-act="filter" data-prefix="/${esc(g)}/"><div class="n">${s.files}</div><div class="k">/${esc(g)}</div><div class="s">${esc(WHAT[g] || '')} · ${fmtSize(s.bytes)}</div></a>`).join('') || '<div class="s3-empty"><b>The twin is empty</b>Create something on <a href="s3.html">S3</a> or <a href="lambda.html">Lambda</a>, or the examples on <a href="index.html">the overview</a>.</div>'}</div>
        <div class="s3-panel"><div class="s3-panel-h"><h2>Files <span class="count">(${t.files.length})</span></h2></div>
          <div class="s3-panel-sub">The twin's virtual file system (sg-vfs), restored from this browser's IndexedDB on every console page and written back after every call. Open a file to read it.</div>
          <div class="s3-search"><input placeholder="Filter by path, for example /lambda/eu-west-2" data-filter="path" id="cx-path-filter"></div>
          <table class="s3-table"><thead><tr><th>Path</th><th>Size</th></tr></thead><tbody>${t.files.map(f => `<tr data-row="${esc(f.path)}"><td><a href="#/file/${f.path.split('/').filter(Boolean).map(enc).join('/')}"><code>${esc(f.path)}</code></a></td><td>${fmtSize(f.size)}</td></tr>`).join('')}</tbody></table></div>
        <div class="s3-panel"><div class="s3-panel-h"><h2>Reset</h2></div><div class="s3-panel-sub">Delete one service's data from the twin in this browser. The account is never touched from here.</div>
          <div class="s3-panel-sub">${groups.map(([g]) => `<button class="s3-btn danger" data-act="reset" data-prefix="/${esc(g)}">Delete /${esc(g)}</button>`).join(' ')}</div></div>`;
    },
    async file(...parts) {
      const path = '/' + parts.join('/');
      const f = await api('twin_file', { path });
      const body = f.json !== undefined ? pretty(f.json) : f.text !== undefined ? pretty(f.text)
        : f.zip ? `<table class="s3-table"><thead><tr><th>In the zip</th><th>Size</th></tr></thead><tbody>${f.zip.map(z => `<tr><td><code>${esc(z.name)}</code></td><td>${fmtSize(z.size)}</td></tr>`).join('')}</tbody></table>`
        : `<div class="s3-panel-sub">Binary, ${f.size} bytes.</div>`;
      const crumbs = parts.map((p, i) => [p, i < parts.length - 1 ? null : null]);
      return crumb(['Twin data', '#/tree'], ...crumbs) + `<h1><code>${esc(path)}</code></h1>
        <div class="s3-panel"><div class="s3-panel-h"><h2>${f.json !== undefined ? 'JSON' : f.zip ? 'Zip' : 'Contents'} <span class="count">(${fmtSize(f.size)})</span></h2></div>${body}</div>`;
    }
  },
  actions: {
    filter: el => { const i = document.getElementById('cx-path-filter'); i.value = el.dataset.prefix; i.dispatchEvent(new Event('input', { bubbles: true })); i.scrollIntoView({ block: 'center' }); },
    reset: el => { if (confirm(`Delete everything under ${el.dataset.prefix} from the twin in this browser?`)) act(() => api('twin_reset', { prefix: el.dataset.prefix }), r => `Deleted ${r.deleted} file(s) under ${r.prefix}`); }
  }
});
