/* The console's Calls page.

   #/matrix  the same AWS calls made five ways: the AWS CLI, boto3 in a normal Python, boto3 in this
             browser (Pyodide), the official AWS SDK for JavaScript in this browser, and the twin.
             The first two and the twin are recorded in assets/console/call-matrix.json by
             admin/build/call_matrix.py; the two browser columns are measured here, in whatever
             browser opens the page, with invented keys (an AWS error back means the call reached
             AWS; a blocked request means the browser stopped it: CORS).
   #/editor  any operation of any service, by hand: botocore's model gives the operations and a
             skeleton of the required parameters; the console's mode decides where it goes. A
             request in the request pane can be replayed here.

   The JavaScript SDK is loaded on demand from cdn.jsdelivr.net, one package per service, pinned. */
import { boot, api, esc, enc, crumb, state, go, say, render, pretty, tabStore } from './core.js';

const SDK_VERSION = '3.1147.0';
const INVENTED = { accessKeyId: 'INVENTED-KEY-FOR-PROBE', secretAccessKey: 'invented-for-the-call-matrix', sessionToken: 'invented-session-token' };
const HISTORY_KEY = 'aws.twin/editor-history';
let recorded = null, rows = null;
const mine = { pyodide: {}, jssdk: {} };                                 // measured in this browser, this visit
let measuring = '', onlyBad = false;

export const b64url = s => btoa(unescape(encodeURIComponent(s))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
const unb64url = s => decodeURIComponent(escape(atob(s.replace(/-/g, '+').replace(/_/g, '/'))));

async function load() {
  if (!recorded) recorded = await (await fetch('../assets/console/call-matrix.json')).json();
  if (!rows) rows = await api('matrix', {}, { quiet: true });
}
const recordedRow = id => (recorded.rows || []).find(r => r.id === id) || {};

function cell(r, yours) {
  const show = (x, label) => {
    if (!x) return '';
    const t = x.status === 'reached' ? `<span class="cx-ok" title="${esc(x.code || '')}">✓ reaches AWS</span>`
      : x.status === 'ok' ? '<span class="cx-ok">✓ ok</span>'
      : x.status === 'blocked' ? '<span class="cx-no" title="the browser refused the answer: no CORS headers for this origin">✗ blocked (CORS)</span>'
      : x.status === 'twinned' ? `<span class="cx-ok">✓ twinned</span>${x.code ? ` <small>${esc(x.code)}</small>` : ''}`
      : x.status === 'not twinned' ? '<span class="cx-dim">not twinned</span>'
      : `<span class="cx-maybe" title="${esc(x.message || '')}">! ${esc(x.code || 'error')}</span>`;
    return `<div>${t}${label ? ` <small>${label}</small>` : ''}</div>`;
  };
  return show(r) + (yours ? show(yours, 'this browser') : '');
}
const blocked = (id) => [recordedRow(id).pyodide, recordedRow(id).jssdk, mine.pyodide[id], mine.jssdk[id]].some(x => x && x.status === 'blocked');

async function jsProbe(row) {
  const t = performance.now();
  try {
    const m = await import(`https://cdn.jsdelivr.net/npm/@aws-sdk/${row.js_package}@${SDK_VERSION}/+esm`);
    const C = m[Object.keys(m).find(k => /Client$/.test(k) && k !== 'Client' && !k.startsWith('_'))];
    const Cmd = m[row.operation + 'Command'];
    if (!C || !Cmd) return { status: 'error', code: 'NotInPackage', message: `${row.js_package} has no ${row.operation}Command` };
    const input = { ...row.params };
    if (typeof input.Payload === 'string') input.Payload = new TextEncoder().encode(input.Payload);
    await new C({ region: row.region, credentials: INVENTED, maxAttempts: 1 }).send(new Cmd(input));
    return { status: 'ok', ms: Math.round(performance.now() - t) };
  } catch (e) {
    const ms = Math.round(performance.now() - t);
    if (e && e.$metadata && e.$metadata.httpStatusCode) return { status: 'reached', code: e.name, ms };
    if (e && (e.name === 'TypeError' || /fetch|network/i.test(String(e.message)))) return { status: 'blocked', code: `${e.name}: ${e.message}`, ms };
    return { status: 'error', code: (e && e.name) || 'Error', message: String(e && e.message || e).slice(0, 200), ms };
  }
}

function history() { return tabStore.get(HISTORY_KEY, []); }
function remember(entry) { tabStore.set(HISTORY_KEY, [entry].concat(history().filter(h => JSON.stringify(h) !== JSON.stringify(entry))).slice(0, 30)); }
let lastSend = null;

boot({
  page: 'calls', home: 'matrix',
  views: {
    async matrix() {
      await load();
      const list = rows.filter(r => !onlyBad || blocked(r.id));
      const counted = col => rows.filter(r => (mine[col][r.id] || recordedRow(r.id)[col] || {}).status === 'blocked').map(r => r.id);
      const badPy = counted('pyodide'), badJs = counted('jssdk');
      const v = recorded.versions || {}, m = recorded.measured || {};
      return crumb(['Calls', '#/matrix'], ['What works where']) + `<h1>Which AWS calls work, and from where</h1>
        <div class="s3-panel"><div class="s3-panel-h"><h2>In short</h2><a class="s3-btn" href="#/editor">Open the call editor</a></div>
          <div class="s3-panel-sub">Outside a browser, every call below reaches AWS: nothing stands between the AWS CLI or boto3 and AWS but AWS itself. In a browser, the browser lets a page read an answer only if AWS sends CORS headers for the page's origin, so a call can be blocked however good the credentials are. ${badPy.length || badJs.length
            ? `Blocked in a browser: <b>${esc([...new Set(badPy.concat(badJs))].join(', '))}</b>. S3's ListBuckets has no CORS at all; a bucket answers a page only with a CORS rule for it (<a href="../iam/index.html#cors">the rule</a>). The console lists buckets through Cloud Control instead.`
            : 'No browser measurement recorded yet.'}</div>
          <div class="s3-panel-sub">Every probe uses <b>invented keys</b>: AWS answering with an error such as <code>InvalidClientTokenId</code> proves the request reached AWS and the answer could be read. Recorded: CLI and boto3 ${esc(m.code || '-')} (boto3 ${esc(v.boto3 || '-')}, ${esc(v.aws_cli || 'aws-cli')}); browser ${esc(m.browser || 'not yet')} (${esc(v.browser || '')}, Pyodide ${esc(v.pyodide || '-')}, JS SDK ${esc(v.js_sdk || SDK_VERSION)}).</div>
          <div class="s3-panel-sub"><button class="s3-btn primary" data-act="measure-py"${measuring ? ' disabled' : ''}>${measuring === 'py' ? 'Measuring…' : 'Measure boto3 in this browser'}</button> <button class="s3-btn primary" data-act="measure-js"${measuring ? ' disabled' : ''}>${measuring === 'js' ? 'Measuring…' : 'Measure the JS SDK in this browser'}</button>
            <label style="margin-left:1rem"><input type="checkbox" name="only_bad"${onlyBad ? ' checked' : ''}> only calls blocked in a browser</label></div></div>
        <div class="s3-panel cx-scroll"><table class="s3-table cx-matrix"><thead><tr><th>Call</th><th>AWS CLI</th><th>boto3, outside a browser</th><th>boto3 in the browser (Pyodide)</th><th>AWS SDK for JavaScript in the browser</th><th>The twin</th><th></th></tr></thead><tbody>
          ${list.map(r => { const rec = recordedRow(r.id); return `<tr class="${blocked(r.id) ? 'bad' : ''}"><td class="op"><b>${esc(r.id)}</b><br><small>${esc(r.note || r.group)}</small></td>
            <td>${cell(rec.cli)}</td><td>${cell(rec.code)}</td><td>${cell(rec.pyodide, mine.pyodide[r.id])}</td><td>${cell(rec.jssdk, mine.jssdk[r.id])}</td><td>${cell(rec.twin)}</td>
            <td><a class="s3-btn cx-small" href="#/editor/${enc(r.service)}/${enc(r.operation)}/${b64url(JSON.stringify(r.params))}">Try it</a></td></tr>`; }).join('')}
        </tbody></table></div>`;
    },

    async editor(service, operation, paramsB64) {
      const services = await api('services', {}, { quiet: true });
      service = service || 'lambda';
      const ops = await api('operations', { service }, { quiet: true });
      operation = operation && ops.operations.includes(operation) ? operation : ops.operations.find(o => /^List/.test(o)) || ops.operations[0];
      const sk = await api('skeleton', { service, operation }, { quiet: true });
      let params = JSON.stringify(sk.params, null, 2);
      if (paramsB64) { try { params = JSON.stringify(JSON.parse(unb64url(paramsB64)), null, 2); } catch (e) { /* the skeleton */ } }
      const r = lastSend && lastSend.service === service && lastSend.operation === operation ? lastSend : null;
      const live = state.mode === 'live';
      return crumb(['Calls', '#/matrix'], ['Call editor']) + `<h1>Call editor</h1>
        <div class="s3-panel"><div class="s3-panel-sub" style="padding-top:.9rem">Any operation of any of boto3's ${services.length} services, sent with boto3 in this page ${live ? `to <b>the account</b> (${esc(state.live.account)}, ${state.live.allow_writes ? 'writes allowed' : 'read-only: only List, Get, Describe and the like are sent'})` : 'to <b>the twin</b>'}. The request, as sent and as answered, is in the request pane. A call that needs something to exist (a function, a bucket) needs it in ${live ? 'the account' : 'the twin: create it first, or seed the examples on the overview'}.</div>
          <form class="cx-editor" data-submit="send">
            <div>
              <label>Service <select name="service" data-act-change="service">${services.map(s => `<option${s === service ? ' selected' : ''}>${esc(s)}</option>`).join('')}</select></label>
              <label>Operation <small class="cx-dim">${esc(ops.protocol)} protocol, signed as ${esc(ops.signing_name)}, API ${esc(ops.api_version)}</small><select name="operation" data-act-change="operation">${ops.operations.map(o => `<option${o === operation ? ' selected' : ''}>${esc(o)}</option>`).join('')}</select></label>
              <div class="s3-panel-sub" style="padding:0 0 .6rem">${esc(sk.doc)}${sk.write ? ' <b class="cx-maybe">May change state.</b>' : ''}</div>
              <label>Region <input name="region" value="${esc(state.region)}"></label>
              <label>Parameters <small class="cx-dim">JSON; required: ${esc(sk.required.join(', ') || 'none')}; all: ${esc(sk.members.join(', ') || 'none')}</small><textarea name="params" spellcheck="false">${esc(params)}</textarea></label>
              <div><button class="s3-btn primary" type="submit">Send</button> <button class="s3-btn" type="button" data-act="skeleton">Reset to the skeleton</button></div>
            </div>
            <div>${r ? (r.error ? `<div class="s3-flash err"><b>${esc(r.error.code || 'Error')}</b> ${esc(r.error.message)}</div>` : `<div class="cx-kv"><b class="cx-ok">${esc(r.out.status)}</b> · request id <code>${esc(r.out.request_id || '-')}</code></div>${pretty(r.out.result)}`) : '<div class="s3-empty"><b>Nothing sent yet</b>The answer, parsed by botocore, shows here.</div>'}</div>
          </form></div>
        <div class="s3-panel"><div class="s3-panel-h"><h2>Sent from this tab <span class="count">(${history().length})</span></h2></div>
          ${history().length ? `<table class="s3-table"><tbody>${history().map(h => `<tr><td><a href="#/editor/${enc(h.service)}/${enc(h.operation)}/${b64url(h.params)}">${esc(h.service)}.${esc(h.operation)}</a></td><td><code class="cx-dim">${esc(h.params.slice(0, 120))}</code></td><td>${esc(h.mode)}</td><td>${h.ok ? '<span class="cx-ok">ok</span>' : `<span class="cx-no">${esc(h.code || 'error')}</span>`}</td></tr>`).join('')}</tbody></table>` : '<div class="s3-panel-sub">None yet.</div>'}</div>`;
    }
  },
  actions: {
    'measure-py': async () => {
      await load(); measuring = 'py'; await render();
      for (const r of rows) { try { mine.pyodide[r.id] = await api('probe', { id: r.id }); } catch (e) { mine.pyodide[r.id] = { status: 'error', code: e.code, message: e.message }; } if (rows.indexOf(r) % 4 === 3) await render(); }
      measuring = ''; window.__matrixPyodide = mine.pyodide; say('Measured boto3 in this browser: every probe is in the request pane'); await render();
    },
    'measure-js': async () => {
      await load(); measuring = 'js'; await render();
      for (const r of rows) { mine.jssdk[r.id] = await jsProbe(r); if (rows.indexOf(r) % 4 === 3) await render(); }
      measuring = ''; window.__matrixJsSdk = mine.jssdk; say(`Measured the AWS SDK for JavaScript ${SDK_VERSION} in this browser (its requests are the SDK's own, not in the request pane)`); await render();
    },
    skeleton: () => { const f = document.querySelector('form[data-submit=send]'); go(`#/editor/${enc(f.service.value)}/${enc(f.operation.value)}`); render(); }
  },
  submits: {
    send: async (f, data) => {
      const service = data.get('service'), operation = data.get('operation'), text = data.get('params') || '{}';
      let params;
      try { params = JSON.parse(text); } catch (e) { say('The parameters are not JSON: ' + e.message, 'err'); return render(); }
      lastSend = { service, operation };
      try { lastSend.out = await api('send', { service, operation, params, region: data.get('region') || state.region }); remember({ service, operation, params: JSON.stringify(params), mode: state.mode, ok: true }); }
      catch (e) { lastSend.error = { code: e.code, message: e.message.split('\n').pop() }; remember({ service, operation, params: JSON.stringify(params), mode: state.mode, ok: false, code: e.code }); }
      go(`#/editor/${enc(service)}/${enc(operation)}/${b64url(JSON.stringify(params))}`);
      await render();
    }
  },
  onChange: e => {
    const t = e.target;
    if (t.name === 'only_bad') { onlyBad = t.checked; render(); }
    else if (t.name === 'service') go(`#/editor/${enc(t.value)}`);
    else if (t.name === 'operation') go(`#/editor/${enc(t.form.service.value)}/${enc(t.value)}`);
  }
});
