/* The console's Lambda page: functions per region, a scan of every region, and each function's
   configuration, code, test invoke, logs and permissions. Every button is one method of
   aws_twin/web/Console.py; the twin answers, or the account does in live mode. */
import { boot, api, act, esc, enc, crumb, state, go, say, pretty, fmtSize, fmtDate, b64ToBytes, saveBlob, render } from './core.js';

const fnHref = (region, name, tab) => `#/fn/${enc(region)}/${enc(name)}${tab ? '/' + tab : ''}`;
const home = (region) => crumb(['Lambda', '#/list'], ['Functions', '#/list'], [region || state.region]);
let scan = null;                                                         // the last scan of every region
let lastInvoke = null;

function tabs(region, name, here) {
  const t = [['overview', 'Configuration'], ['code', 'Code'], ['test', 'Test'], ['logs', 'Logs'], ['permissions', 'Permissions']];
  return `<div class="s3-tabs">${t.map(([k, label]) => `<a class="${k === here ? 'here' : ''}" href="${fnHref(region, name, k)}">${label}</a>`).join('')}</div>`;
}
const kv = (k, v) => `<div><div class="k">${esc(k)}</div><div class="v">${v}</div></div>`;
const roleLink = arn => { const n = (arn || '').split('/').pop(); return `<a href="resources.html#/res/${enc('AWS::IAM::Role')}/${enc(n)}">${esc(arn)}</a>`; };

boot({
  page: 'lambda', home: 'list',
  views: {
    async list() {
      const r = await api('lambda_list', { region: state.region });
      const rows = r.functions.map(f => `<tr data-row="${esc(f.name)}"><td><a href="${fnHref(r.region, f.name)}">${esc(f.name)}</a>${f.description ? `<br><small class="cx-dim">${esc(f.description)}</small>` : ''}</td><td>${esc(f.runtime)}</td><td>${esc(f.arch)}</td><td>${f.memory} MB</td><td>${f.timeout} s</td><td>${fmtSize(f.code_size)}</td><td>${esc(fmtDate(f.modified))}</td></tr>`).join('');
      return home(r.region) + `<h1>Functions</h1>
        <div class="s3-panel"><div class="s3-panel-h"><h2>Functions in ${esc(r.region)} <span class="count">(${r.functions.length})</span></h2>
          <button class="s3-btn" data-act="refresh">↻</button><button class="s3-btn" data-act="nav" data-to="#/scan">Scan every region</button>${state.mode === 'twin' ? '<button class="s3-btn primary" data-act="seed">Create example functions</button>' : ''}</div>
          <div class="s3-panel-sub">${state.mode === 'live' ? `The account's functions in ${esc(r.region)}; change the region top right, or scan every region.` : 'The twin\'s functions in this region, kept in this browser. The twin runs them when invoked: Node.js through the browser, Python in the page.'}</div>
          <div class="s3-search"><input placeholder="Find functions by name" data-filter="fn"></div>
          ${r.functions.length ? `<table class="s3-table"><thead><tr><th>Function name</th><th>Runtime</th><th>Architecture</th><th>Memory</th><th>Timeout</th><th>Code size</th><th>Last modified</th></tr></thead><tbody>${rows}</tbody></table>`
            : `<div class="s3-empty"><b>No functions in ${esc(r.region)}</b>${state.mode === 'twin' ? 'Create the examples, or deploy one from <a href="../uptime/index.html">the uptime page</a>.' : 'Scan every region to see where this account has functions.'}</div>`}</div>`;
    },

    async scan() {
      const rows = (scan || []).map(s => `<tr><td><a href="#" data-act="pick-region" data-region="${esc(s.region)}">${esc(s.region)}</a></td><td>${s.error ? `<span class="cx-no">${esc(s.error)}</span>` : s.count == null ? '<span class="cx-dim">…</span>' : `<b>${s.count}</b>`}</td></tr>`).join('');
      return crumb(['Lambda', '#/list'], ['Scan every region']) + `<h1>Every region</h1>
        <div class="s3-panel"><div class="s3-panel-h"><h2>Functions per region</h2><button class="s3-btn primary" data-act="scan">${scan ? 'Scan again' : 'Scan'}</button></div>
          <div class="s3-panel-sub">One ListFunctions per region, one after the other; each shows in the request pane. A region the account has not enabled answers with an error, by name.</div>
          ${scan ? `<table class="s3-table"><thead><tr><th>Region</th><th>Functions</th></tr></thead><tbody>${rows}</tbody></table>` : ''}</div>`;
    },

    async fn(region, name, tab = 'overview') {
      const g = await api('lambda_get', { region, name });
      const c = g.configuration;
      const head = crumb(['Lambda', '#/list'], ['Functions', '#/list'], [region, '#/list'], [name]) + `<h1>${esc(name)}</h1>` + tabs(region, name, tab);
      if (tab === 'code') return head + await codeView(region, name, c);
      if (tab === 'test') return head + testView(region, name);
      if (tab === 'logs') return head + await logsView(region, name);
      if (tab === 'permissions') return head + permissionsView(g);
      const env = Object.entries((c.Environment || {}).Variables || {});
      const rules = Array.isArray(g.rules) ? g.rules : [];
      return head + `
        <div class="s3-panel"><div class="s3-panel-h"><h2>Function overview</h2><button class="s3-btn" data-act="nav" data-to="${fnHref(region, name, 'test')}">Test</button></div><div class="s3-grid">
          ${kv('Function ARN', esc(c.FunctionArn))}${kv('Runtime', esc(c.Runtime || c.PackageType))}${kv('Handler', `<code>${esc(c.Handler)}</code>`)}
          ${kv('Architecture', esc((c.Architectures || []).join(', ')))}${kv('Memory', esc(c.MemorySize) + ' MB')}${kv('Timeout', esc(c.Timeout) + ' s')}
          ${kv('Ephemeral storage', esc((c.EphemeralStorage || {}).Size || 512) + ' MB')}${kv('Code size', fmtSize(c.CodeSize))}${kv('Code SHA-256', `<code>${esc(c.CodeSha256)}</code>`)}
          ${kv('Last modified', esc(c.LastModified))}${kv('State', esc(c.State || '-') + ' / ' + esc(c.LastUpdateStatus || '-'))}${kv('Execution role', roleLink(c.Role))}
          ${kv('Log group', esc((c.LoggingConfig || {}).LogGroup || '/aws/lambda/' + name))}${kv('Description', esc(c.Description || '-'))}</div></div>
        <div class="s3-panel cx-env cx-masked" id="cx-env"><div class="s3-panel-h"><h2>Environment variables <span class="count">(${env.length})</span></h2>${env.length ? '<button class="s3-btn" data-act="reveal">Show values</button>' : ''}</div>
          ${env.length ? `<table class="s3-table"><thead><tr><th>Key</th><th>Value</th></tr></thead><tbody>${env.map(([k, v]) => `<tr><td><code>${esc(k)}</code></td><td class="v secret">${esc(v)}</td></tr>`).join('')}</tbody></table>
          <div class="s3-panel-sub">Values are blurred until you ask: they are often secrets, and they are in the GetFunction answer either way (see the request pane).</div>` : '<div class="s3-panel-sub">None.</div>'}</div>
        <div class="s3-panel"><div class="s3-panel-h"><h2>Triggers</h2></div>
          ${rules.length ? `<table class="s3-table"><thead><tr><th>EventBridge rule</th><th>Schedule</th><th>State</th></tr></thead><tbody>${rules.map(r => `<tr><td><a href="resources.html#/res/${enc('AWS::Events::Rule')}/${enc(r.Arn)}">${esc(r.Name)}</a></td><td><code>${esc(r.ScheduleExpression || '-')}</code></td><td>${esc(r.State)}</td></tr>`).join('')}</tbody></table>`
            : `<div class="s3-panel-sub">${Array.isArray(g.rules) ? 'No EventBridge rule targets this function in ' + esc(region) + '.' : 'Could not read the rules: ' + esc(g.rules.error)}</div>`}</div>
        <div class="s3-panel"><div class="s3-panel-h"><h2>Function URL</h2></div>
          ${g.url && !g.url.error ? `<div class="s3-grid">${kv('URL', `<code>${esc(g.url.FunctionUrl)}</code>`)}${kv('Auth type', esc(g.url.AuthType))}${kv('Invoke mode', esc(g.url.InvokeMode || 'BUFFERED'))}${kv('CORS', g.url.Cors ? `<code>${esc(JSON.stringify(g.url.Cors))}</code>` : '-')}</div>`
            : `<div class="s3-panel-sub">${g.url && g.url.error ? 'Could not read it: ' + esc(g.url.error) : 'None.'}</div>`}</div>
        <div class="s3-panel"><div class="s3-panel-h"><h2>Tags <span class="count">(${Object.keys(g.tags || {}).length})</span></h2></div>
          ${Object.keys(g.tags || {}).length ? `<table class="s3-table"><tbody>${Object.entries(g.tags).map(([k, v]) => `<tr><td>${esc(k)}</td><td>${esc(v)}</td></tr>`).join('')}</tbody></table>` : '<div class="s3-panel-sub">None.</div>'}</div>`;
    }
  },
  actions: {
    nav: el => go(el.dataset.to),
    refresh: () => render(),
    reveal: el => { document.getElementById('cx-env').classList.toggle('cx-masked'); el.textContent = el.textContent === 'Show values' ? 'Hide values' : 'Show values'; },
    seed: () => act(() => api('lambda_seed', { region: state.region }), r => r.created.length ? `Created ${r.created.join(' and ')} in ${r.region}, with a role, a function URL and a schedule` : 'The examples are already there'),
    'pick-region': el => { const s = document.getElementById('cx-region'); s.value = el.dataset.region; s.dispatchEvent(new Event('change')); go('#/list'); },
    scan: async () => {
      scan = state.regions.map(r => ({ region: r, count: null }));
      await render();
      for (const s of scan) { Object.assign(s, await api('lambda_count', { region: s.region })); await render(); }
    },
    'show-file': el => { document.querySelectorAll('.cx-code nav a').forEach(a => a.classList.toggle('here', a === el)); document.getElementById('cx-file').textContent = el.dataset.text; },
    'download-zip': el => saveBlob(el.dataset.name + '.zip', b64ToBytes(el.dataset.zip), 'application/zip'),
    'test-example': el => { document.querySelector('textarea[name=payload]').value = el.dataset.payload; }
  },
  submits: {
    invoke: (f, data) => act(async () => {
      lastInvoke = { region: f.dataset.region, name: f.dataset.name, payload: data.get('payload') };
      lastInvoke.result = await api('lambda_invoke', { region: f.dataset.region, name: f.dataset.name, payload: data.get('payload') });
      return lastInvoke.result;
    }, r => r.function_error ? `The function failed: ${r.function_error}` : `Invoked: ${r.status}`)
  }
});

async function codeView(region, name, c) {
  const code = await api('lambda_code', { region, name });
  if (!code.files) {
    return `<div class="s3-panel"><div class="s3-panel-h"><h2>Code</h2></div><div class="s3-panel-sub">${esc(code.why)}.</div>
      <div class="s3-grid">${kv('Package', `<a href="${esc(code.location)}" rel="noopener">Download the deployment package (.zip)</a>`)}${kv('Code SHA-256', `<code>${esc(c.CodeSha256)}</code>`)}${kv('Size', fmtSize(c.CodeSize))}</div></div>`;
  }
  const first = code.files.find(f => f.text != null) || code.files[0];
  return `<div class="s3-panel"><div class="s3-panel-h"><h2>Code <span class="count">(${code.files.length} file${code.files.length === 1 ? '' : 's'})</span></h2><button class="s3-btn" data-act="download-zip" data-name="${esc(name)}" data-zip="${code.zip_b64}">Download .zip</button></div>
    <div class="s3-panel-sub">The deployment package as the twin holds it, unpacked in this page. Handler: <code>${esc(c.Handler)}</code>.</div>
    <div class="cx-code"><nav>${code.files.map(f => `<a href="#" class="${f === first ? 'here' : ''}" data-act="show-file" data-text="${esc(f.text == null ? '(binary or large: ' + f.size + ' bytes)' : f.text)}">${esc(f.name)} <small class="cx-dim">${fmtSize(f.size)}</small></a>`).join('')}</nav>
    <pre class="s3-preview" id="cx-file">${esc(first && first.text != null ? first.text : '')}</pre></div></div>`;
}

function testView(region, name) {
  const mine = lastInvoke && lastInvoke.region === region && lastInvoke.name === name ? lastInvoke : null;
  const payload = mine ? mine.payload : '{}';
  const r = mine && mine.result;
  let parsed = r ? r.payload : '';
  try { parsed = JSON.stringify(JSON.parse(r.payload), null, 2); } catch (e) { /* as it came */ }
  const writesNote = state.mode === 'live' && !state.live.allow_writes ? `<div class="s3-flash err">Invoking runs the function in the account. Live mode is read-only: allow writes with <b>Live</b>, top left, to invoke.</div>` : '';
  return `<div class="s3-panel"><div class="s3-panel-h"><h2>Test event</h2>
      <button class="s3-btn" data-act="test-example" data-payload='{}'>Empty</button><button class="s3-btn" data-act="test-example" data-payload='${esc(JSON.stringify({ name: 'Dinis' }))}'>A name</button><button class="s3-btn" data-act="test-example" data-payload='${esc(JSON.stringify({ url: 'https://sgit.ai/' }))}'>A URL</button><button class="s3-btn" data-act="test-example" data-payload='${esc(JSON.stringify({ source: 'aws.events', 'detail-type': 'Scheduled Event', detail: {} }))}'>A scheduled event</button></div>
    ${writesNote}
    <form class="s3-form" data-submit="invoke" data-region="${esc(region)}" data-name="${esc(name)}" style="max-width:none"><label>Event JSON<textarea name="payload" rows="8" spellcheck="false">${esc(payload)}</textarea></label><div><button class="s3-btn primary" type="submit">Invoke</button></div></form></div>
    ${r ? `<div class="s3-panel"><div class="s3-panel-h"><h2>Result: ${r.function_error ? `<span class="cx-no">${esc(r.function_error)}</span>` : '<span class="cx-ok">succeeded</span>'} <span class="count">(${r.status})</span></h2></div>
      ${pretty(parsed)}<div class="s3-panel-h"><h2>Log output <span class="count">(the last 4 KB)</span></h2></div>${pretty(r.log || '(none)')}</div>` : ''}`;
}

async function logsView(region, name) {
  const l = await api('lambda_logs', { region, name });
  if (l.source === 'twin') {
    return `<div class="s3-panel"><div class="s3-panel-h"><h2>Invocations <span class="count">(${l.invocations.length}, the twin keeps the last 25)</span></h2><button class="s3-btn" data-act="refresh">↻</button></div>
      <div class="s3-panel-sub">The twin has no CloudWatch Logs; it keeps each invocation's event, result and log lines with the function.</div>
      ${l.invocations.length ? l.invocations.map(i => `<div class="s3-panel-sub"><b>${esc(i.at)}</b> · ${esc(i.request_id)} · ${i.ms} ms · ${i.error ? `<span class="cx-no">${esc(i.error.errorType)}</span>` : '<span class="cx-ok">ok</span>'}${(i.requests || []).length ? ' · ' + i.requests.length + ' outbound request(s)' : ''}</div>${pretty((i.logs || []).join('\n') || '(no log lines)')}`).join('')
        : '<div class="s3-empty"><b>Not invoked yet</b>Use the Test tab.</div>'}</div>`;
  }
  return `<div class="s3-panel"><div class="s3-panel-h"><h2>CloudWatch Logs <span class="count">${esc(l.group)}</span></h2><button class="s3-btn" data-act="refresh">↻</button></div>
    <div class="s3-panel-sub">The three most recent log streams, the last 60 events of each, read from this browser (CloudWatch Logs answers a page).</div>
    ${l.streams.length ? l.streams.map(s => `<div class="s3-panel-sub"><b>${esc(s.stream)}</b></div>${pretty(s.events.map(e => new Date(e.t).toISOString().slice(0, 19) + '  ' + e.m.trimEnd()).join('\n') || '(empty)')}`).join('')
      : '<div class="s3-empty"><b>No log streams</b>The function has not run, or its logs have expired.</div>'}</div>`;
}

function permissionsView(g) {
  const c = g.configuration, p = g.policy;
  const st = p && !p.error ? p.Statement || [] : [];
  return `<div class="s3-panel"><div class="s3-panel-h"><h2>Execution role</h2></div><div class="s3-grid">${kv('Role', roleLink(c.Role))}</div>
      <div class="s3-panel-sub">What the function may do when it runs: the role's policies, on <a href="resources.html#/res/${enc('AWS::IAM::Role')}/${enc((c.Role || '').split('/').pop())}">the role's page</a>.</div></div>
    <div class="s3-panel"><div class="s3-panel-h"><h2>Resource-based policy <span class="count">(${st.length})</span></h2></div>
      <div class="s3-panel-sub">Who may invoke the function: AWS services (EventBridge for a schedule), accounts, or anyone through a function URL.</div>
      ${p && p.error ? `<div class="s3-panel-sub cx-no">Could not read it: ${esc(p.error)}</div>` : st.length ? `<table class="s3-table"><thead><tr><th>Statement</th><th>Principal</th><th>Action</th><th>Conditions</th></tr></thead><tbody>${st.map(s => `<tr><td>${esc(s.Sid)}</td><td><code>${esc(JSON.stringify(s.Principal))}</code></td><td><code>${esc(s.Action)}</code></td><td><code>${esc(s.Condition ? JSON.stringify(s.Condition) : '-')}</code></td></tr>`).join('')}</tbody></table>` : '<div class="s3-panel-sub">None: only callers with IAM permission may invoke it.</div>'}</div>`;
}
