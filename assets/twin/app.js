/* aws.twin.sgit.ai — the twin's UI.

   Everything on screen is the result of a call through the interface, and every
   call is shown in the log at the bottom exactly as it would go to AWS: service,
   operation, SDK command, params, result or error. The UI never reads a backend's
   state directly; it is a consumer like any other, which is the point of a twin.

   Plain DOM, no framework, no third-party script. Views are functions that return
   HTML strings; actions are data-action attributes handled by one delegate. */
(function () {
  'use strict';

  var AT = window.AwsTwin, V = window.AwsTwinVault, T = window.AwsTwinTemplates;
  var REGIONS = ['eu-west-2', 'eu-west-1', 'eu-central-1', 'us-east-1', 'us-west-2', 'ap-southeast-1'];
  var UI_KEY = 'aws.twin/ui';

  /* --- stores and backends --- */
  var storage = safeStorage(window.localStorage), session = safeStorage(window.sessionStorage);
  var vault = new V.VaultBackend(storage);
  var memory = new AT.MemoryBackend();
  var sessionStore = new V.SessionStore(session);
  var live = new AT.LiveBackend(sessionStore);
  T.register(vault); T.register(memory);
  var backends = { vault: vault, memory: memory, live: live };

  var ui = loadUi();
  var calls = [];
  var view = {};          /* per-view transient state: selected bucket, diff refs... */
  var notice = null;

  function safeStorage(s) {
    try { s.setItem('aws.twin/probe', '1'); s.removeItem('aws.twin/probe'); return s; }
    catch (e) { var m = {}; return { getItem: function (k) { return k in m ? m[k] : null; }, setItem: function (k, v) { m[k] = String(v); }, removeItem: function (k) { delete m[k]; } }; }
  }
  function loadUi() {
    var d = { backend: 'vault', accountId: null, region: 'eu-west-2' };
    try { var raw = storage.getItem(UI_KEY); if (raw) { var x = JSON.parse(raw); Object.keys(x).forEach(function (k) { d[k] = x[k]; }); } } catch (e) { /* defaults */ }
    return d;
  }
  function saveUi() { try { storage.setItem(UI_KEY, JSON.stringify(ui)); } catch (e) { /* in-memory only */ } }

  function backend() { return backends[ui.backend] || vault; }
  function accounts() { return backend().accounts(); }
  function currentAccount() {
    var list = accounts();
    if (!list.length) return null;
    if (!list.some(function (a) { return a.accountId === ui.accountId; })) ui.accountId = list[0].accountId;
    return list.filter(function (a) { return a.accountId === ui.accountId; })[0];
  }
  function client() {
    var a = currentAccount();
    if (!a) throw AT.TwinError('NoAccount', 'no account in this backend yet: seed the demo estate or add an account');
    return AT.client(backend(), { accountId: a.accountId, region: ui.region }, logCall);
  }
  function logCall(rec) {
    calls.push(rec);
    if (calls.length > 500) calls.shift();
    renderCalls();
  }

  /* --- rendering --- */
  var esc = function (s) { return String(s === undefined || s === null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); };
  var json = function (x) { return esc(JSON.stringify(x, null, 2)); };
  var fmtTime = function (iso) { return iso ? iso.replace('T', ' ').slice(0, 19) + 'Z' : ''; };
  var short = function (s, n) { s = String(s); return s.length > n ? s.slice(0, n - 1) + '…' : s; };

  var VIEWS = ['overview', 's3', 'lambda', 'ec2', 'iam', 'billing', 'logs', 'deploy', 'graph', 'snapshots', 'session', 'calls'];
  var LABELS = { overview: 'Overview', s3: 'S3', lambda: 'Lambda', ec2: 'EC2', iam: 'IAM', billing: 'Billing', logs: 'Logs', deploy: 'Deploy', graph: 'Graph', snapshots: 'Snapshots', session: 'Session', calls: 'Calls' };

  function route() {
    var h = (location.hash || '#/overview').replace(/^#\/?/, '').split('/');
    return { view: VIEWS.indexOf(h[0]) >= 0 ? h[0] : 'overview', arg: h.slice(1).map(decodeURIComponent) };
  }
  function go(v, arg) { location.hash = '#/' + v + (arg ? '/' + encodeURIComponent(arg) : ''); }

  function render() {
    var r = route();
    renderBar();
    renderSide(r.view);
    var main = document.getElementById('tw-main');
    var p;
    try { p = Promise.resolve(RENDER[r.view](r.arg)); }
    catch (e) { p = Promise.reject(e); }
    p.then(function (html) {
      main.innerHTML = (notice ? noticeHtml() : '') + html;
      notice = null;
      if (r.view === 'graph') drawGraph();
    }, function (e) {
      main.innerHTML = '<div class="tw-err"><b>' + esc(e.code || e.name) + '</b> ' + esc(e.message) + (e.meta && e.meta.command ? '<br><code>' + esc(e.meta.command) + '</code>' : '') + '</div>' + (e.code === 'NoAccount' ? RENDER.accounts() : '');
    });
    renderCalls();
  }
  function noticeHtml() { return '<div class="tw-notice ' + (notice.kind || 'ok') + '">' + esc(notice.text) + (notice.code ? ' <code>' + esc(notice.code) + '</code>' : '') + '</div>'; }
  function say(text, kind, code) { notice = { text: text, kind: kind || 'ok', code: code }; }

  function renderBar() {
    var list = accounts(), a = currentAccount();
    var st = sessionStore.status();
    var opts = list.map(function (x) { return '<option value="' + esc(x.accountId) + '"' + (a && a.accountId === x.accountId ? ' selected' : '') + '>' + esc(x.name) + ' · ' + esc(x.accountId) + '</option>'; }).join('');
    var regions = REGIONS.slice();
    if (regions.indexOf(ui.region) < 0) regions.push(ui.region);
    var ropts = regions.map(function (r) { return '<option' + (r === ui.region ? ' selected' : '') + '>' + esc(r) + '</option>'; }).join('');
    var vaultState = ui.backend === 'vault' ? (vault.log().length + ' commit' + (vault.log().length === 1 ? '' : 's') + (vault.isDirty() ? ' · <b class="dirty">uncommitted changes</b>' : ' · clean')) : (ui.backend === 'memory' ? 'this page load only' : (st.present ? (st.expired ? '<b class="dirty">session expired</b>' : 'session · ' + Math.floor(st.secondsLeft / 60) + ' min left') : 'no session in the vault'));
    document.getElementById('tw-bar').innerHTML =
      '<label>Backend <select data-change="backend">' +
        '<option value="vault"' + (ui.backend === 'vault' ? ' selected' : '') + '>vault (localStorage)</option>' +
        '<option value="memory"' + (ui.backend === 'memory' ? ' selected' : '') + '>memory</option>' +
        '<option value="live"' + (ui.backend === 'live' ? ' selected' : '') + '>live (not wired)</option></select></label>' +
      '<label>Account <select data-change="account"' + (list.length ? '' : ' disabled') + '>' + (opts || '<option>none yet</option>') + '</select></label>' +
      '<label>Region <select data-change="region">' + ropts + '</select></label>' +
      '<span class="tw-state">' + vaultState + '</span>' +
      '<span class="tw-actions">' +
        (ui.backend !== 'live' ? '<button data-action="seed" title="Seed two illustrative accounts through the interface">Seed demo estate</button>' : '') +
        (ui.backend === 'vault' ? '<button data-action="commit-quick" title="Commit the working state as a snapshot">Commit</button>' : '') +
      '</span>';
  }
  function renderSide(current) {
    document.getElementById('tw-side').innerHTML = VIEWS.map(function (v) {
      return '<a href="#/' + v + '" class="' + (v === current ? 'here' : '') + '">' + LABELS[v] + (v === 'calls' && calls.length ? ' <span class="n">' + calls.length + '</span>' : '') + '</a>';
    }).join('');
  }
  function renderCalls() {
    var el = document.getElementById('tw-calls');
    if (!el) return;
    var last = calls.slice(-6).reverse();
    el.innerHTML = '<div class="tw-calls-h">calls through the interface · ' + calls.length + ' this page · <a href="#/calls">all →</a></div>' +
      (last.length ? last.map(callLine).join('') : '<div class="d">none yet: every call made by this page appears here, as it would go to AWS</div>');
  }
  function callLine(r) {
    return '<div class="tw-call ' + (r.error ? 'err' : 'ok') + '"><span class="d">' + esc(r.at.slice(11, 19)) + '</span> <span class="cy">' + esc(r.backend) + '</span> <span class="y">' + esc(r.scope.accountId) + '/' + esc(r.scope.region) + '</span> <b>' + esc(r.service + '.' + r.op) + '</b> <span class="d">' + esc(r.command) + '</span> ' + esc(short(JSON.stringify(r.params), 90)) + ' → ' + (r.error ? '<span class="r">' + esc(r.error.code) + '</span> ' + esc(short(r.error.message, 120)) : '<span class="g">ok</span> ' + esc(short(JSON.stringify(r.result), 80))) + '</div>';
  }

  /* --- shared fragments --- */
  function h2(t, sub) { return '<h2>' + esc(t) + '</h2>' + (sub ? '<p class="tw-sub">' + sub + '</p>' : ''); }
  function table(head, rows, empty) {
    if (!rows.length) return '<p class="tw-empty">' + esc(empty || 'nothing here yet') + '</p>';
    return '<div class="tablewrap"><table><thead><tr>' + head.map(function (x) { return '<th>' + x + '</th>'; }).join('') + '</tr></thead><tbody>' + rows.map(function (r) { return '<tr>' + r.map(function (c) { return '<td>' + c + '</td>'; }).join('') + '</tr>'; }).join('') + '</tbody></table></div>';
  }
  function form(action, fields, button, extra) {
    return '<form class="tw-form" data-submit="' + action + '">' + fields.map(function (f) {
      if (f.type === 'select') return '<label>' + esc(f.label) + '<select name="' + f.name + '">' + f.options.map(function (o) { return '<option value="' + esc(o.value) + '">' + esc(o.label) + '</option>'; }).join('') + '</select></label>';
      if (f.type === 'textarea') return '<label class="wide">' + esc(f.label) + '<textarea name="' + f.name + '" rows="' + (f.rows || 3) + '" placeholder="' + esc(f.placeholder || '') + '">' + esc(f.value || '') + '</textarea></label>';
      if (f.type === 'checks') return '<fieldset><legend>' + esc(f.label) + '</legend>' + f.options.map(function (o) { return '<label class="chk"><input type="checkbox" name="' + f.name + '" value="' + esc(o.value) + '"' + (o.checked ? ' checked' : '') + '> ' + esc(o.label) + '</label>'; }).join('') + '</fieldset>';
      return '<label>' + esc(f.label) + '<input name="' + f.name + '" type="' + (f.type || 'text') + '" value="' + esc(f.value || '') + '" placeholder="' + esc(f.placeholder || '') + '"' + (f.required ? ' required' : '') + '></label>';
    }).join('') + (extra || '') + '<button type="submit">' + esc(button) + '</button></form>';
  }
  function btn(action, label, arg, cls) { return '<button class="tw-btn ' + (cls || '') + '" data-action="' + action + '"' + (arg !== undefined ? ' data-arg="' + esc(arg) + '"' : '') + '>' + esc(label) + '</button>'; }
  function st(kind, label) { return '<span class="st st-' + kind + '">' + esc(label) + '</span>'; }

  /* --- the views --- */
  var RENDER = {};

  RENDER.accounts = function () {
    var list = accounts();
    return '<section class="tw-card"><h3>Accounts in this backend</h3>' +
      (ui.backend === 'live' ? '<p>The live backend has one account: the one the session belongs to. <a href="#/session">Paste a session →</a></p>' :
      table(['Account', 'Name', ''], list.map(function (a) { return [esc(a.accountId), esc(a.name), btn('use-account', 'use', a.accountId)]; }), 'no accounts yet') +
      form('add-account', [{ name: 'accountId', label: '12-digit account id', placeholder: '123456789012', required: true }, { name: 'name', label: 'Name', placeholder: 'e.g. sg-send-dev' }], 'Add account') +
      '<p class="tw-hint">Or ' + btn('seed', 'seed the demo estate') + ': two illustrative accounts, built through the same interface, every call logged.</p>') +
      '</section>';
  };

  RENDER.overview = function () {
    var a = currentAccount();
    if (!a) {
      return h2('The AWS twin', 'An AWS-shaped interface with a vault behind it. Nothing here calls AWS: the data lives in this browser\'s localStorage, versioned as commits, until a live session is put in front of the same interface.') + RENDER.accounts();
    }
    var c = client();
    var ask = function (p) { return p.then(function (r) { return r; }, function (e) { return { error: e }; }); };
    return Promise.all([
      ask(c.sts.getCallerIdentity({})), ask(c.s3.listBuckets({})), ask(c.lambda.listFunctions({})), ask(c.ec2.describeInstances({})),
      ask(c.iam.listRoles({})), ask(c.logs.describeLogGroups({})), ask(c.cloudformation.listStacks({})), ask(c.ce.getCostAndUsage({ Granularity: 'MONTHLY' }))
    ]).then(function (r) {
      if (r[0].error) {
        return h2('The AWS twin', 'The ' + esc(ui.backend) + ' backend answered the first call with an error, shown as the SDK would raise it.') +
          '<div class="tw-err"><b>' + esc(r[0].error.code) + '</b> ' + esc(r[0].error.message) + '</div>' +
          (ui.backend === 'live' ? '<p>This is the designed behaviour of the PoC\'s live backend: the slot for a session exists, the wire to AWS does not. <a href="#/session">The session page →</a></p>' : '');
      }
      var cost = 0; (r[7].ResultsByTime || []).forEach(function (t) { t.Groups.forEach(function (g) { cost += parseFloat(g.Metrics.UnblendedCost.Amount); }); });
      var inst = r[3].Reservations[0].Instances.filter(function (i) { return i.State.Name !== 'terminated'; });
      var tiles = [
        ['S3 buckets', r[1].Buckets.length, 's3', 'global'], ['Lambda functions', r[2].Functions.length, 'lambda', ui.region], ['EC2 instances', inst.length, 'ec2', ui.region],
        ['IAM roles', r[4].Roles.length, 'iam', 'global'], ['Log groups', r[5].logGroups.length, 'logs', ui.region], ['Stacks', r[6].StackSummaries.length, 'deploy', ui.region],
        ['Cost, all months', '$' + cost.toFixed(2), 'billing', 'global']
      ];
      return h2(a.name, 'Identity: <code>' + esc(r[0].Arn) + '</code>. Eight calls made this view; see them below.') +
        '<div class="tw-tiles">' + tiles.map(function (t) { return '<a class="tw-tile" href="#/' + t[2] + '"><span class="k">' + esc(t[0]) + '</span><span class="v">' + esc(t[1]) + '</span><span class="r">' + esc(t[3]) + '</span></a>'; }).join('') + '</div>' +
        '<div class="tw-cols"><section class="tw-card"><h3>What to try</h3><ol>' +
        '<li><a href="#/deploy">Rehearse a deployment</a>: the SG/Send API template into several accounts and regions, one session each, then commit the result.</li>' +
        '<li><a href="#/snapshots">Commit a snapshot</a>, change something, commit again, and diff Monday against Friday.</li>' +
        '<li><a href="#/graph">Read the account graph</a>: role → policy, function → bucket, instance → security group.</li>' +
        '<li>Switch the backend to <b>live</b> and make the same calls: each one reports the SDK command it would have sent.</li></ol></section>' +
        RENDER.accounts() + '</div>';
    });
  };

  RENDER.s3 = function (arg) {
    var c = client();
    var sel = arg[0] || view.bucket;
    return c.s3.listBuckets({}).then(function (r) {
      var rows = r.Buckets.map(function (b) { return ['<a href="#/s3/' + encodeURIComponent(b.Name) + '">' + esc(b.Name) + '</a>', esc(b.BucketRegion), fmtTime(b.CreationDate), btn('s3-delete-bucket', 'delete', b.Name, 'danger')]; });
      var html = h2('S3', 'Buckets are global to the account; each carries the region it was created in.') +
        table(['Bucket', 'Region', 'Created', ''], rows, 'no buckets in this account') +
        '<details class="tw-details"><summary>Create bucket</summary>' + form('s3-create-bucket', [{ name: 'Bucket', label: 'Bucket name', required: true, placeholder: 'lower-case, 3 to 63 chars' }, { name: 'Region', label: 'Region', value: ui.region }], 'CreateBucket') + '</details>';
      if (!sel) return html;
      view.bucket = sel;
      return c.s3.listObjectsV2({ Bucket: sel }).then(function (o) {
        return html + '<section class="tw-card"><h3>' + esc(sel) + ' · ' + o.KeyCount + ' object' + (o.KeyCount === 1 ? '' : 's') + '</h3>' +
          table(['Key', 'Size', 'Last modified', ''], o.Contents.map(function (x) { return [esc(x.Key), x.Size, fmtTime(x.LastModified), btn('s3-get', 'get', x.Key) + ' ' + btn('s3-delete', 'delete', x.Key, 'danger')]; }), 'empty bucket') +
          (view.object ? '<pre class="shell"><span class="d">GetObject ' + esc(view.object.Key) + ' · ' + esc(view.object.ContentType) + ' · ' + view.object.ContentLength + ' bytes</span>\n' + esc(view.object.Body) + '</pre>' : '') +
          '<details class="tw-details"><summary>Put object</summary>' + form('s3-put', [{ name: 'Key', label: 'Key', required: true }, { name: 'ContentType', label: 'Content type', value: 'text/plain' }, { name: 'Body', label: 'Body', type: 'textarea' }], 'PutObject') + '</details></section>';
      }, function (e) { view.bucket = null; return html + '<div class="tw-err">' + esc(e.code) + ': ' + esc(e.message) + '</div>'; });
    });
  };

  RENDER.lambda = function (arg) {
    var c = client();
    return Promise.all([c.lambda.listFunctions({}), c.iam.listRoles({}), c.s3.listBuckets({})]).then(function (r) {
      var fns = r[0].Functions, roles = r[1].Roles, buckets = r[2].Buckets;
      var rows = fns.map(function (f) {
        var vars = (f.Environment && f.Environment.Variables) || {};
        return [esc(f.FunctionName), esc(f.PackageType === 'Image' ? 'image · ' + short(f.ImageUri || '', 40) : f.Runtime), f.MemorySize + ' MB · ' + f.Timeout + ' s', esc(f.Role.split('/').pop()), esc(Object.keys(vars).map(function (k) { return k + '=' + vars[k]; }).join(', ')) || '<span class="d">none</span>', fmtTime(f.LastModified),
          btn('lambda-invoke', 'invoke', f.FunctionName) + ' <a class="tw-btn" href="#/logs/' + encodeURIComponent('/aws/lambda/' + f.FunctionName) + '">logs</a> ' + btn('lambda-delete', 'delete', f.FunctionName, 'danger')];
      });
      var sel = arg[0];
      var invoked = view.invoked && view.invoked.FunctionName === sel ? '<pre class="shell"><span class="d">Invoke ' + esc(sel) + ' → StatusCode ' + view.invoked.StatusCode + '</span>\n' + json(view.invoked.Payload) + '</pre>' : '';
      return h2('Lambda', 'Functions in <b>' + esc(ui.region) + '</b>. Creating one needs a role that exists in IAM, as it does in AWS; invoking one writes four lines to its log group.') +
        table(['Function', 'Package', 'Memory · timeout', 'Role', 'Environment', 'Modified', ''], rows, 'no functions in ' + ui.region) + invoked +
        '<details class="tw-details"' + (fns.length ? '' : ' open') + '><summary>Create function</summary>' + (roles.length ? form('lambda-create', [
          { name: 'FunctionName', label: 'Function name', required: true },
          { name: 'Role', label: 'Role', type: 'select', options: roles.map(function (x) { return { value: x.Arn, label: x.RoleName }; }) },
          { name: 'Runtime', label: 'Runtime', type: 'select', options: ['python3.12', 'nodejs22.x', 'provided.al2023'].map(function (x) { return { value: x, label: x }; }) },
          { name: 'MemorySize', label: 'Memory (MB)', type: 'number', value: '256' }, { name: 'Timeout', label: 'Timeout (s)', type: 'number', value: '10' },
          { name: 'Bucket', label: 'Bucket it uses (env var BUCKET)', type: 'select', options: [{ value: '', label: 'none' }].concat(buckets.map(function (b) { return { value: b.Name, label: b.Name }; })) }
        ], 'CreateFunction') : '<p class="tw-hint">Create a role in <a href="#/iam">IAM</a> first: Lambda refuses a function whose role does not exist.</p>') + '</details>' +
        '<details class="tw-details"><summary>Invoke with a payload</summary>' + form('lambda-invoke-payload', [{ name: 'FunctionName', label: 'Function', type: 'select', options: fns.map(function (f) { return { value: f.FunctionName, label: f.FunctionName }; }) }, { name: 'Payload', label: 'Payload (JSON)', type: 'textarea', value: '{"path": "/health"}' }], 'Invoke') + '</details>';
    });
  };

  RENDER.ec2 = function () {
    var c = client();
    return Promise.all([c.ec2.describeInstances({}), c.ec2.describeSecurityGroups({}), c.iam.listRoles({})]).then(function (r) {
      var inst = r[0].Reservations[0].Instances, sgs = r[1].SecurityGroups, roles = r[2].Roles;
      var name = function (i) { var t = (i.Tags || []).filter(function (x) { return x.Key === 'Name'; })[0]; return t ? t.Value : ''; };
      var rows = inst.map(function (i) {
        var s = i.State.Name;
        return [esc(i.InstanceId), esc(name(i)), esc(i.InstanceType), '<span class="tw-ist ' + esc(s) + '">' + esc(s) + '</span>', esc(i.SecurityGroups.map(function (g) { return g.GroupName; }).join(', ')), esc(i.IamInstanceProfile ? i.IamInstanceProfile.Name : ''), fmtTime(i.LaunchTime),
          (s === 'stopped' ? btn('ec2-start', 'start', i.InstanceId) : '') + (s === 'running' ? btn('ec2-stop', 'stop', i.InstanceId) : '') + (s !== 'terminated' ? ' ' + btn('ec2-terminate', 'terminate', i.InstanceId, 'danger') : '')];
      });
      return h2('EC2', 'Instances and security groups in <b>' + esc(ui.region) + '</b>. Terminated instances stay listed, as AWS keeps them for a while; they leave the graph.') +
        table(['Instance', 'Name', 'Type', 'State', 'Security groups', 'Profile', 'Launched', ''], rows, 'no instances in ' + ui.region) +
        '<details class="tw-details"><summary>Run instance</summary>' + form('ec2-run', [
          { name: 'Name', label: 'Name tag', required: true }, { name: 'ImageId', label: 'AMI', value: 'ami-0sgcompute0browser' },
          { name: 'InstanceType', label: 'Type', type: 'select', options: ['t3.micro', 't3.medium', 't3.large', 'm6i.xlarge'].map(function (x) { return { value: x, label: x }; }) },
          { name: 'SecurityGroupIds', label: 'Security groups', type: 'checks', options: sgs.map(function (g) { return { value: g.GroupId, label: g.GroupName }; }) },
          { name: 'IamInstanceProfile', label: 'Instance profile (role)', type: 'select', options: [{ value: '', label: 'none' }].concat(roles.map(function (x) { return { value: x.RoleName, label: x.RoleName }; })) }
        ], 'RunInstances') + '</details>' +
        '<section class="tw-card"><h3>Security groups</h3>' + table(['Group', 'Name', 'Description', 'Ingress rules', ''], sgs.map(function (g) {
          return [esc(g.GroupId), esc(g.GroupName), esc(g.Description), esc(g.IpPermissions.map(function (p) { return p.IpProtocol + ' ' + p.FromPort + (p.ToPort !== p.FromPort ? '-' + p.ToPort : '') + ' from ' + p.IpRanges.map(function (x) { return x.CidrIp; }).join(','); }).join('; ')) || '<span class="d">none</span>', btn('sg-ingress', 'allow 443', g.GroupId)];
        }), 'no security groups in ' + ui.region) +
        '<details class="tw-details"><summary>Create security group</summary>' + form('sg-create', [{ name: 'GroupName', label: 'Name', required: true }, { name: 'Description', label: 'Description' }], 'CreateSecurityGroup') + '</details></section>';
    });
  };

  RENDER.iam = function () {
    var c = client();
    return Promise.all([c.iam.listRoles({}), c.iam.listPolicies({})]).then(function (r) {
      var roles = r[0].Roles, policies = r[1].Policies;
      return Promise.all(roles.map(function (x) { return c.iam.listAttachedRolePolicies({ RoleName: x.RoleName }); })).then(function (att) {
        var rows = roles.map(function (x, i) {
          return [esc(x.RoleName), esc(x.Description), att[i].AttachedPolicies.map(function (p) { return '<code>' + esc(p.PolicyName) + '</code> ' + btn('iam-detach', '×', x.RoleName + '|' + p.PolicyArn, 'tiny'); }).join(' ') || '<span class="d">none</span>', fmtTime(x.CreateDate), btn('iam-delete-role', 'delete', x.RoleName, 'danger')];
        });
        return h2('IAM', 'Global to the account. A role cannot be deleted while a policy is attached or a function uses it, as in AWS.') +
          table(['Role', 'Description', 'Attached policies', 'Created', ''], rows, 'no roles in this account') +
          '<div class="tw-cols">' +
          '<details class="tw-details" open><summary>Create role</summary>' + form('iam-create-role', [{ name: 'RoleName', label: 'Role name', required: true }, { name: 'Description', label: 'Description' }, { name: 'Service', label: 'Trusted service', type: 'select', options: ['lambda', 'ec2', 'ecs-tasks'].map(function (s) { return { value: s, label: s + '.amazonaws.com' }; }) }], 'CreateRole') + '</details>' +
          '<details class="tw-details" open><summary>Attach policy</summary>' + (roles.length && policies.length ? form('iam-attach', [{ name: 'RoleName', label: 'Role', type: 'select', options: roles.map(function (x) { return { value: x.RoleName, label: x.RoleName }; }) }, { name: 'PolicyArn', label: 'Policy', type: 'select', options: policies.map(function (p) { return { value: p.Arn, label: p.PolicyName }; }).concat([{ value: 'arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess', label: 'AWS managed: AmazonS3ReadOnlyAccess' }, { value: 'arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore', label: 'AWS managed: AmazonSSMManagedInstanceCore' }]) }], 'AttachRolePolicy') : '<p class="tw-hint">Needs a role and a policy.</p>') + '</details></div>' +
          '<section class="tw-card"><h3>Policies</h3>' + table(['Policy', 'Description', 'Attachments', 'Statements'], policies.map(function (p) { return [esc(p.PolicyName), esc(p.Description), p.AttachmentCount, '<details><summary>' + (p.PolicyDocument.Statement || []).length + '</summary><pre class="tw-pre">' + json(p.PolicyDocument) + '</pre></details>']; }), 'no customer managed policies') +
          '<details class="tw-details"><summary>Create policy</summary>' + form('iam-create-policy', [{ name: 'PolicyName', label: 'Policy name', required: true }, { name: 'Description', label: 'Description' }, { name: 'PolicyDocument', label: 'Policy document (JSON)', type: 'textarea', rows: 6, value: JSON.stringify({ Version: '2012-10-17', Statement: [{ Effect: 'Allow', Action: ['s3:GetObject'], Resource: 'arn:aws:s3:::example/*' }] }, null, 2) }], 'CreatePolicy') + '</details></section>';
      });
    });
  };

  RENDER.billing = function (arg) {
    var c = client();
    var by = arg[0] === 'region' ? 'REGION' : 'SERVICE';
    return c.ce.getCostAndUsage({ Granularity: 'MONTHLY', GroupBy: [{ Type: 'DIMENSION', Key: by }] }).then(function (r) {
      var keys = {}, max = 0, total = 0;
      r.ResultsByTime.forEach(function (t) { t.Groups.forEach(function (g) { keys[g.Keys[0]] = true; var v = parseFloat(g.Metrics.UnblendedCost.Amount); total += v; }); });
      var klist = Object.keys(keys).sort();
      var rows = r.ResultsByTime.map(function (t) {
        var m = {}; var sum = 0;
        t.Groups.forEach(function (g) { m[g.Keys[0]] = parseFloat(g.Metrics.UnblendedCost.Amount); sum += m[g.Keys[0]]; });
        if (sum > max) max = sum;
        return { period: t.TimePeriod.Start.slice(0, 7), m: m, sum: sum };
      });
      var bars = rows.map(function (row) {
        return '<div class="tw-barrow"><span class="lbl">' + esc(row.period) + '</span><span class="bar">' + klist.map(function (k, i) { var v = row.m[k] || 0; return v ? '<i class="seg s' + (i % 6) + '" style="width:' + (100 * v / max).toFixed(1) + '%" title="' + esc(k) + ': $' + v.toFixed(2) + '"></i>' : ''; }).join('') + '</span><span class="val">$' + row.sum.toFixed(2) + '</span></div>';
      }).join('');
      return h2('Billing', 'Cost Explorer\'s <code>GetCostAndUsage</code>, monthly, grouped by ' + (by === 'REGION' ? 'region' : 'service') + '. <a href="#/billing/' + (by === 'REGION' ? 'service' : 'region') + '">Group by ' + (by === 'REGION' ? 'service' : 'region') + ' →</a>') +
        (rows.length ? '<div class="tw-bars">' + bars + '<div class="tw-legend">' + klist.map(function (k, i) { return '<span><i class="seg s' + (i % 6) + '"></i>' + esc(k) + '</span>'; }).join('') + '</div></div>' : '') +
        table(['Month'].concat(klist.map(esc)).concat(['Total']), rows.map(function (row) { return [esc(row.period)].concat(klist.map(function (k) { return row.m[k] ? '$' + row.m[k].toFixed(2) : '<span class="d">–</span>'; })).concat(['<b>$' + row.sum.toFixed(2) + '</b>']); }), 'no cost records in this account') +
        '<p class="tw-sub">Total across months: <b>$' + total.toFixed(2) + '</b>. Illustrative numbers from the seed, or whatever you record below.</p>' +
        '<details class="tw-details"><summary>Record a cost <span class="st st-poc">twin-only</span></summary><p class="tw-hint">AWS has no call that writes a cost; reality does that. In the twin it is an input, under <code>twin.recordCost</code>, never under an AWS service name.</p>' + form('cost-record', [{ name: 'Service', label: 'Service', value: 'AWS Lambda' }, { name: 'Amount', label: 'Amount (USD)', type: 'number', value: '1.00' }, { name: 'Date', label: 'Date', type: 'date', value: new Date().toISOString().slice(0, 10) }, { name: 'Region', label: 'Region', value: ui.region }], 'twin.recordCost') + '</details>';
    });
  };

  RENDER.logs = function (arg) {
    var c = client();
    var sel = arg[0] || view.group;
    return c.logs.describeLogGroups({}).then(function (r) {
      var groups = r.logGroups;
      var html = h2('Logs', 'CloudWatch log groups in <b>' + esc(ui.region) + '</b>. Lambda invocations write here; so can you.') +
        table(['Log group', 'Stored bytes', 'Created', ''], groups.map(function (g) { return ['<a href="#/logs/' + encodeURIComponent(g.logGroupName) + '">' + esc(g.logGroupName) + '</a>', g.storedBytes, fmtTime(new Date(g.creationTime).toISOString()), btn('logs-delete', 'delete', g.logGroupName, 'danger')]; }), 'no log groups in ' + ui.region) +
        '<details class="tw-details"><summary>Create log group</summary>' + form('logs-create', [{ name: 'logGroupName', label: 'Name', required: true, placeholder: '/app/service' }], 'CreateLogGroup') + '</details>';
      if (!sel) return html;
      view.group = sel;
      var pattern = view.pattern || '';
      return c.logs.filterLogEvents({ logGroupName: sel, filterPattern: pattern, limit: 200 }).then(function (ev) {
        return html + '<section class="tw-card"><h3>' + esc(sel) + ' · ' + ev.events.length + ' event' + (ev.events.length === 1 ? '' : 's') + '</h3>' +
          form('logs-filter', [{ name: 'filterPattern', label: 'Filter (substring)', value: pattern }], 'FilterLogEvents') +
          '<pre class="shell">' + (ev.events.map(function (e) { return '<span class="d">' + esc(new Date(e.timestamp).toISOString().replace('T', ' ').slice(0, 19)) + '</span> ' + esc(e.message); }).join('\n') || '<span class="d">no events</span>') + '</pre>' +
          '<details class="tw-details"><summary>Put log event</summary>' + form('logs-put', [{ name: 'message', label: 'Message', required: true }], 'PutLogEvents') + '</details></section>';
      }, function (e) { view.group = null; return html + '<div class="tw-err">' + esc(e.code) + ': ' + esc(e.message) + '</div>'; });
    });
  };

  RENDER.deploy = function () {
    var c = client();
    var list = accounts();
    return c.cloudformation.describeStacks({}).then(function (r) {
      var rows = r.Stacks.map(function (s) {
        return [esc(s.StackName), esc(s.TemplateName), st(s.StackStatus === 'CREATE_COMPLETE' ? 'built' : 'no', s.StackStatus), esc(s.Parameters.map(function (p) { return p.ParameterKey + '=' + p.ParameterValue; }).join(', ')), '<details><summary>' + s.Outputs.length + ' outputs · ' + s.Resources.length + ' resources</summary>' + table(['Key', 'Value'], s.Outputs.map(function (o) { return [esc(o.OutputKey), '<code>' + esc(o.OutputValue) + '</code>']; })) + '<p class="tw-hint">' + s.Resources.map(function (x) { return '<code>' + esc(x) + '</code>'; }).join(' ') + '</p></details>', fmtTime(s.CreationTime), btn('stack-delete', 'delete', s.StackName, 'danger')];
      });
      var tplOpts = Object.keys(T.TEMPLATES).map(function (k) { return { value: k, label: k + ' — ' + T.TEMPLATES[k].description }; });
      var result = view.deployResult ? '<section class="tw-card"><h3>Rehearsal result · ' + esc(view.deployResult.stack) + ' · ' + esc(view.deployResult.template) + '</h3>' +
        table(['Account', 'Region', 'Result', 'Outputs'], view.deployResult.rows.map(function (x) { return [esc(x.accountId), esc(x.region), x.error ? '<span class="r">' + esc(x.error.code) + '</span> ' + esc(x.error.message) : st('built', 'CREATE_COMPLETE'), x.outputs ? x.outputs.map(function (o) { return '<code>' + esc(o.OutputKey) + '=' + esc(short(o.OutputValue, 48)) + '</code>'; }).join(' ') : '']; })) +
        (ui.backend === 'vault' ? '<p>' + btn('commit-deploy', 'Commit this deployment as a snapshot') + ' <span class="tw-hint">so the vault is the record of what is deployed where</span></p>' : '') + '</section>' : '';
      return h2('Deploy', 'The first job from the article: one template, one session per account, several regions, every deployment written down. A template is a sequence of ordinary calls through the interface, so a rehearsal against the vault is the same calls as the live run.') +
        result +
        '<section class="tw-card"><h3>Rehearse a deployment</h3>' + form('deploy-run', [
          { name: 'TemplateName', label: 'Template', type: 'select', options: tplOpts },
          { name: 'StackName', label: 'Stack name', value: 'sg-send-api', required: true },
          { name: 'ImageTag', label: 'Container image tag', value: 'v0.9.2' },
          { name: 'accounts', label: 'Accounts (one session each)', type: 'checks', options: list.map(function (a) { return { value: a.accountId, label: a.name + ' · ' + a.accountId, checked: a.accountId === ui.accountId }; }) },
          { name: 'regions', label: 'Regions', type: 'checks', options: REGIONS.map(function (x) { return { value: x, label: x, checked: x === ui.region || x === 'eu-central-1' }; }) }
        ], 'CreateStack × accounts × regions') + '</section>' +
        '<section class="tw-card"><h3>Stacks in ' + esc(ui.accountId) + ' · ' + esc(ui.region) + '</h3>' + table(['Stack', 'Template', 'Status', 'Parameters', 'Outputs', 'Created', ''], rows, 'no stacks in ' + ui.region) + '</section>';
    });
  };

  RENDER.graph = function () {
    var c = client();
    return c.twin.state({}).then(function (acct) {
      var g = AT.graphOf(acct);
      view.graph = g;
      var kinds = {}; g.nodes.forEach(function (n) { kinds[n.kind] = (kinds[n.kind] || 0) + 1; });
      return h2('The account graph', 'Resources as nodes, relationships as edges, across every region of <b>' + esc(currentAccount().name) + '</b>. ' + g.nodes.length + ' nodes, ' + g.edges.length + ' edges. Built from the state the interface returns (<code>twin.state</code>, twin-only), the same way it will be built from a live snapshot.') +
        '<p class="tw-legend">' + Object.keys(kinds).map(function (k) { return '<span><i class="gk gk-' + k + '"></i>' + esc(k) + ' · ' + kinds[k] + '</span>'; }).join('') + '</p>' +
        '<div class="tw-graph" id="tw-graph"></div>' +
        '<details class="tw-details"><summary>As Mermaid, to paste elsewhere</summary><pre class="tw-pre">' + esc(AT.graphToMermaid(g)) + '</pre></details>' +
        '<details class="tw-details"><summary>Edges, as a table</summary>' + table(['From', 'Relation', 'To'], g.edges.map(function (e) { return [esc(labelOf(g, e.from)), '<code>' + esc(e.rel) + '</code>', esc(labelOf(g, e.to))]; })) + '</details>';
    });
  };
  function labelOf(g, id) { var n = g.nodes.filter(function (x) { return x.id === id; })[0]; return n ? n.kind + ': ' + n.label : id; }
  var KIND_ORDER = ['stack', 'instance', 'security-group', 'function', 'role', 'policy', 'bucket', 'log-group'];
  function drawGraph() {
    var el = document.getElementById('tw-graph'), g = view.graph;
    if (!el || !g) return;
    if (!g.nodes.length) { el.innerHTML = '<p class="tw-empty">no resources yet</p>'; return; }
    var cols = {}; KIND_ORDER.forEach(function (k, i) { cols[k] = i; });
    var colW = 190, rowH = 40, pos = {}, rows = {};
    g.nodes.forEach(function (n) { var ci = cols[n.kind] === undefined ? KIND_ORDER.length : cols[n.kind]; rows[ci] = (rows[ci] || 0); pos[n.id] = { x: 20 + ci * colW, y: 30 + rows[ci] * rowH, n: n }; rows[ci]++; });
    var maxRows = Math.max.apply(null, Object.keys(rows).map(function (k) { return rows[k]; }));
    var W = 20 + (KIND_ORDER.length + 1) * colW, H = 50 + maxRows * rowH;
    var svg = '<svg viewBox="0 0 ' + W + ' ' + H + '" style="min-width:' + Math.round(W * 0.7) + 'px" role="img" aria-label="account graph">';
    KIND_ORDER.forEach(function (k, i) { if (rows[i]) svg += '<text x="' + (20 + i * colW) + '" y="16" class="gh">' + esc(k) + '</text>'; });
    g.edges.forEach(function (e) {
      var a = pos[e.from], b = pos[e.to]; if (!a || !b) return;
      var x1 = a.x + 150, y1 = a.y + 12, x2 = b.x, y2 = b.y + 12;
      if (b.x < a.x) { x1 = a.x; x2 = b.x + 150; }
      var mx = (x1 + x2) / 2;
      svg += '<path class="ge ge-' + esc(e.rel) + '" d="M' + x1 + ',' + y1 + ' C' + mx + ',' + y1 + ' ' + mx + ',' + y2 + ' ' + x2 + ',' + y2 + '"><title>' + esc(e.rel) + '</title></path>';
    });
    g.nodes.forEach(function (n) {
      var p = pos[n.id];
      svg += '<g class="gn gk-' + esc(n.kind) + '"><rect x="' + p.x + '" y="' + p.y + '" width="150" height="24" rx="5"></rect><text x="' + (p.x + 6) + '" y="' + (p.y + 16) + '">' + esc(short(n.label, n.region ? 12 : 22)) + '</text>' + (n.region ? '<text class="gr" x="' + (p.x + 145) + '" y="' + (p.y + 16) + '" text-anchor="end">' + esc(n.region) + '</text>' : '') + '<title>' + esc(n.kind + ': ' + n.label + (n.region ? ' (' + n.region + ')' : '') + '\n' + n.id) + '</title></g>';
    });
    el.innerHTML = svg + '</svg>';
  }

  RENDER.snapshots = function (arg) {
    if (ui.backend !== 'vault') return h2('Snapshots', 'Snapshots are commits in the vault. Switch the backend to <b>vault</b>: the memory backend keeps nothing and the live backend\'s snapshots land in the vault once wired.');
    var log = vault.log();
    var a = arg[0] || view.diffA || (log[1] ? log[1].id : ''), b = arg[1] || view.diffB || 'working';
    view.diffA = a; view.diffB = b;
    var refOpts = function (sel) { return [{ value: 'working', label: 'working state (uncommitted)' }].concat(log.map(function (x) { return { value: x.id, label: x.id.slice(0, 8) + ' · ' + x.message + ' · ' + fmtTime(x.at) }; })).map(function (o) { return '<option value="' + esc(o.value) + '"' + (o.value === sel ? ' selected' : '') + '>' + esc(o.label) + '</option>'; }).join(''); };
    var diffHtml = '';
    if (a && b) {
      try {
        var d = vault.diff(a, b);
        diffHtml = Object.keys(d).map(function (acctId) {
          var x = d[acctId];
          var rows = x.added.map(function (r) { return ['<span class="g">added</span>', esc(r.key), '', '<pre class="tw-pre">' + json(r.after) + '</pre>']; })
            .concat(x.removed.map(function (r) { return ['<span class="r">removed</span>', esc(r.key), '<pre class="tw-pre">' + json(r.before) + '</pre>', '']; }))
            .concat(x.changed.map(function (r) { return ['<span class="y">changed</span>', esc(r.key), '<pre class="tw-pre">' + json(r.before) + '</pre>', '<pre class="tw-pre">' + json(r.after) + '</pre>']; }));
          return '<h4>' + esc(acctId) + ' · ' + x.added.length + ' added, ' + x.removed.length + ' removed, ' + x.changed.length + ' changed, ' + x.unchanged + ' unchanged</h4>' + (rows.length ? table(['', 'Resource', 'Before', 'After'], rows) : '');
        }).join('');
      } catch (e) { diffHtml = '<div class="tw-err">' + esc(e.message) + '</div>'; }
    }
    return h2('Snapshots', 'Every snapshot is a commit of the whole state document. Diff any two, or a commit against the working state, and read what changed between Monday and Friday. Head: <code>' + esc(vault.head() ? vault.head().slice(0, 8) : 'none') + '</code>' + (vault.isDirty() ? ' · <b class="dirty">uncommitted changes</b>' : ' · clean') + ' · ' + Math.round(vault.sizeBytes() / 1024) + ' KB in localStorage.') +
      '<div class="tw-cols"><section class="tw-card"><h3>Commit</h3>' + form('commit', [{ name: 'message', label: 'Message', value: 'snapshot ' + new Date().toISOString().slice(0, 16).replace('T', ' '), required: true }], 'Commit snapshot') + '</section>' +
      '<section class="tw-card"><h3>Vault document</h3><p class="tw-hint">The shape an sgit vault holds: working state, commits, head. Export it to carry it to a real vault; import one to continue from it.</p><p>' + btn('export', 'Export JSON') + ' <label class="tw-file">Import JSON <input type="file" accept="application/json" data-file="import"></label> ' + btn('reset', 'Reset vault', undefined, 'danger') + '</p></section></div>' +
      '<section class="tw-card"><h3>Log · ' + log.length + ' commit' + (log.length === 1 ? '' : 's') + '</h3>' + table(['Commit', 'When', 'Message', 'Summary', ''], log.map(function (x) {
        var s = x.summary;
        return ['<code>' + esc(x.id.slice(0, 8)) + '</code>', fmtTime(x.at), esc(x.message), esc(s.accounts + ' acct · ' + s.buckets + ' bkt · ' + s.objects + ' obj · ' + s.functions + ' fn · ' + s.instances + ' ec2 · ' + s.roles + ' role · ' + s.stacks + ' stack · $' + s.cost), btn('checkout', 'checkout', x.id) + ' ' + btn('diff-to-working', 'diff → working', x.id)];
      }), 'no commits yet: commit the working state above') + '</section>' +
      '<section class="tw-card"><h3>Diff</h3><form class="tw-form" data-submit="diff"><label>From <select name="a">' + refOpts(a) + '</select></label><label>To <select name="b">' + refOpts(b) + '</select></label><button type="submit">Diff</button></form>' + diffHtml + '</section>';
  };

  RENDER.session = function () {
    var s = sessionStore.status();
    var status = s.present ? '<div class="tw-card"><h3>Session in the vault</h3><table><tr><th>Account</th><td>' + esc(s.accountId) + (s.accountName ? ' · ' + esc(s.accountName) : '') + '</td></tr><tr><th>Role</th><td>' + esc(s.role || '—') + '</td></tr><tr><th>Region</th><td>' + esc(s.region) + '</td></tr><tr><th>Access key id</th><td><code>' + esc(s.keyId.slice(0, 4) + '…' + s.keyId.slice(-4)) + '</code> <span class="d">the secret and the token are never shown back</span></td></tr><tr><th>Expires</th><td>' + esc(fmtTime(s.expiresAt)) + ' · ' + (s.expired ? '<b class="dirty">expired</b>' : Math.floor(s.secondsLeft / 60) + ' min left') + '</td></tr></table><p>' + btn('session-clear', 'Clear session', undefined, 'danger') + ' ' + btn('session-try', 'Try sts.getCallerIdentity against the live backend') + '</p></div>' : '';
    return h2('Session', 'The live backend reads its credentials from here. Sign in to the AWS access portal (IAM Identity Center), pick the account and the permission set, choose <b>Access keys</b>, and paste what it shows: the export lines, the set lines, the PowerShell lines or the credentials-file block all parse. The session lives in <code>sessionStorage</code>, for this tab, with the expiry you give it (one to twelve hours, one by default).') +
      '<div class="tw-notice warn">In this PoC the live backend is <b>not wired</b>: it accepts the session and refuses every call with the SDK command it would have sent. Nothing pasted here leaves the browser, and nothing here calls AWS. The same interface, the same calls; the wire is the next step.</div>' +
      status +
      '<section class="tw-card"><h3>Paste a session</h3>' + form('session-set', [
        { name: 'paste', label: 'From the access portal\'s "Access keys" dialog', type: 'textarea', rows: 5, placeholder: 'export AWS_ACCESS_KEY_ID="ASIA..."\nexport AWS_SECRET_ACCESS_KEY="..."\nexport AWS_SESSION_TOKEN="..."' },
        { name: 'accountId', label: 'Account id (12 digits; parsed from a [account_role] profile header when present)' },
        { name: 'accountName', label: 'Account name (for the account picker)' },
        { name: 'role', label: 'Permission set / role' },
        { name: 'region', label: 'Region', value: ui.region },
        { name: 'hours', label: 'Session length in hours (1–12)', type: 'number', value: '1' }
      ], 'Put the session in the vault') + '</section>' +
      '<section class="tw-card"><h3>What the wire needs, when it is built</h3><ul><li>The AWS SDK for JavaScript v3 clients for the eight services in the manifest, constructed per call from the session, released as a fixed, independent copy per site version.</li><li>A CORS measurement per service: S3 needs a bucket CORS rule; which other endpoints answer a browser is to measure, and where one does not, a helper on the user\'s machine or an SG/Compute node makes the call.</li><li>Nothing else: the UI, the templates, the snapshots and the graph are already written against the interface.</li></ul></section>';
  };

  RENDER.calls = function () {
    var filter = view.callFilter || '';
    var list = calls.slice().reverse().filter(function (r) { return !filter || (r.service + '.' + r.op + ' ' + r.backend + ' ' + (r.error ? r.error.code : 'ok')).indexOf(filter) >= 0; });
    return h2('Calls', calls.length + ' calls through the interface since this page loaded, newest first. Each is what the SDK would send: a command and one params object; and what came back: a result or an error with an AWS-shaped code.') +
      form('calls-filter', [{ name: 'filter', label: 'Filter (service.op, backend, error code)', value: filter }], 'Filter') +
      '<p>' + btn('calls-clear', 'Clear') + ' ' + btn('calls-export', 'Export as JSON') + '</p>' +
      '<div class="tw-calllist">' + (list.map(function (r) {
        return '<details class="tw-call ' + (r.error ? 'err' : 'ok') + '"><summary>' + callLine(r).replace(/^<div[^>]*>|<\/div>$/g, '') + '</summary><pre class="tw-pre">' + json({ command: r.command, backend: r.backend, scope: r.scope, params: r.params, result: r.result, error: r.error, ms: r.ms }) + '</pre></details>';
      }).join('') || '<p class="tw-empty">nothing matches</p>') + '</div>';
  };

  /* --- actions --- */
  function run(label, fn) {
    var p;
    try { p = Promise.resolve(fn()); } catch (e) { p = Promise.reject(e); }
    return p.then(function (r) { if (label) say(label, 'ok'); render(); return r; }, function (e) { say((e.code || e.name) + ': ' + e.message, 'err', e.meta && e.meta.command); render(); });
  }
  var formObj = function (f) {
    var o = {};
    Array.prototype.forEach.call(f.elements, function (el) {
      if (!el.name) return;
      if (el.type === 'checkbox') { o[el.name] = o[el.name] || []; if (el.checked) o[el.name].push(el.value); }
      else o[el.name] = el.value;
    });
    return o;
  };
  var num = function (v, d) { var n = parseFloat(v); return isNaN(n) ? d : n; };
  var download = function (name, text) {
    var blob = new Blob([text], { type: 'application/json' });
    var a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; document.body.appendChild(a); a.click(); setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 0);
  };

  var ACTIONS = {
    'seed': function () { return run(null, function () { var r = T.seedDemo(backend(), logCall); ui.accountId = r.accounts[0]; saveUi(); say('Seeded ' + r.accounts.length + ' illustrative accounts with ' + r.calls + ' calls through the interface' + (ui.backend === 'vault' ? '. Commit a snapshot to keep a baseline.' : '.')); }); },
    'use-account': function (id) { ui.accountId = id; saveUi(); render(); },
    'commit-quick': function () { return run(null, function () { var c = vault.commit('snapshot ' + new Date().toISOString().slice(0, 16).replace('T', ' ')); say('Committed ' + c.id.slice(0, 8) + ': ' + c.message); }); },
    'commit-deploy': function () { return run(null, function () { var d = view.deployResult; var c = vault.commit('deploy ' + d.stack + ' (' + d.template + ') to ' + d.rows.filter(function (x) { return !x.error; }).length + ' of ' + d.rows.length + ' targets'); say('Committed ' + c.id.slice(0, 8) + ': ' + c.message); }); },
    's3-delete-bucket': function (b) { return run('Deleted bucket ' + b, function () { if (view.bucket === b) view.bucket = null; return client().s3.deleteBucket({ Bucket: b }); }); },
    's3-get': function (k) { return run(null, function () { return client().s3.getObject({ Bucket: view.bucket, Key: k }).then(function (o) { o.Key = k; view.object = o; }); }); },
    's3-delete': function (k) { return run('Deleted ' + k, function () { view.object = null; return client().s3.deleteObject({ Bucket: view.bucket, Key: k }); }); },
    'lambda-invoke': function (n) { return run(null, function () { return client().lambda.invoke({ FunctionName: n, Payload: { path: '/health', method: 'GET' } }).then(function (r) { r.FunctionName = n; view.invoked = r; go('lambda', n); }); }); },
    'lambda-delete': function (n) { return run('Deleted function ' + n, function () { return client().lambda.deleteFunction({ FunctionName: n }); }); },
    'ec2-start': function (id) { return run('Started ' + id, function () { return client().ec2.startInstances({ InstanceIds: [id] }); }); },
    'ec2-stop': function (id) { return run('Stopped ' + id, function () { return client().ec2.stopInstances({ InstanceIds: [id] }); }); },
    'ec2-terminate': function (id) { return run('Terminated ' + id, function () { return client().ec2.terminateInstances({ InstanceIds: [id] }); }); },
    'sg-ingress': function (id) { return run('Allowed 443 into ' + id, function () { return client().ec2.authorizeSecurityGroupIngress({ GroupId: id, IpProtocol: 'tcp', FromPort: 443, ToPort: 443, CidrIp: '0.0.0.0/0' }); }); },
    'iam-detach': function (arg) { var p = arg.split('|'); return run('Detached ' + p[1].split('/').pop() + ' from ' + p[0], function () { return client().iam.detachRolePolicy({ RoleName: p[0], PolicyArn: p[1] }); }); },
    'iam-delete-role': function (n) { return run('Deleted role ' + n, function () { return client().iam.deleteRole({ RoleName: n }); }); },
    'logs-delete': function (n) { return run('Deleted log group ' + n, function () { if (view.group === n) view.group = null; return client().logs.deleteLogGroup({ logGroupName: n }); }); },
    'stack-delete': function (n) { return run('Deleted stack ' + n, function () { return client().cloudformation.deleteStack({ StackName: n }); }); },
    'checkout': function (id) { return run('Checked out ' + id.slice(0, 8) + ' into the working state', function () { vault.checkout(id); }); },
    'diff-to-working': function (id) { go('snapshots', id + '/working'); },
    'export': function () { download('aws-twin-vault-' + new Date().toISOString().slice(0, 10) + '.json', JSON.stringify(vault.exportDoc(), null, 2)); },
    'reset': function () { if (confirm('Reset the vault? Every commit and the working state in this browser are deleted.')) return run('Vault reset', function () { vault.reset(); ui.accountId = null; saveUi(); }); },
    'session-clear': function () { sessionStore.clear(); say('Session cleared'); render(); },
    'session-try': function () { return run(null, function () { var s = sessionStore.status(); return AT.client(live, { accountId: s.accountId, region: s.region }, logCall).sts.getCallerIdentity({}); }); },
    'calls-clear': function () { calls = []; render(); },
    'calls-export': function () { download('aws-twin-calls.json', JSON.stringify(calls, null, 2)); }
  };

  var SUBMITS = {
    'add-account': function (o) { return run('Added account ' + o.accountId, function () { if (!/^\d{12}$/.test(o.accountId)) throw AT.TwinError('ValidationError', 'an account id is 12 digits'); backend().ensureAccount(o.accountId, o.name || o.accountId); ui.accountId = o.accountId; saveUi(); }); },
    's3-create-bucket': function (o) { return run('Created bucket ' + o.Bucket, function () { return client().s3.createBucket({ Bucket: o.Bucket, Region: o.Region || ui.region }); }); },
    's3-put': function (o) { return run('Put ' + o.Key, function () { return client().s3.putObject({ Bucket: view.bucket, Key: o.Key, Body: o.Body, ContentType: o.ContentType }); }); },
    'lambda-create': function (o) { return run('Created function ' + o.FunctionName, function () { var env = { Variables: {} }; if (o.Bucket) env.Variables.BUCKET = o.Bucket; return client().lambda.createFunction({ FunctionName: o.FunctionName, Role: o.Role, Runtime: o.Runtime, Handler: 'handler.run', MemorySize: num(o.MemorySize, 128), Timeout: num(o.Timeout, 3), Environment: env }); }); },
    'lambda-invoke-payload': function (o) { return run(null, function () { var payload; try { payload = JSON.parse(o.Payload || '{}'); } catch (e) { throw AT.TwinError('InvalidRequestContentException', 'payload is not JSON: ' + e.message); } return client().lambda.invoke({ FunctionName: o.FunctionName, Payload: payload }).then(function (r) { r.FunctionName = o.FunctionName; view.invoked = r; go('lambda', o.FunctionName); }); }); },
    'ec2-run': function (o) { return run('Launched ' + o.Name, function () { return client().ec2.runInstances({ ImageId: o.ImageId, InstanceType: o.InstanceType, SecurityGroupIds: o.SecurityGroupIds || [], IamInstanceProfile: o.IamInstanceProfile || undefined, Name: o.Name }); }); },
    'sg-create': function (o) { return run('Created security group ' + o.GroupName, function () { return client().ec2.createSecurityGroup({ GroupName: o.GroupName, Description: o.Description }); }); },
    'iam-create-role': function (o) { return run('Created role ' + o.RoleName, function () { return client().iam.createRole({ RoleName: o.RoleName, Description: o.Description, AssumeRolePolicyDocument: { Version: '2012-10-17', Statement: [{ Effect: 'Allow', Principal: { Service: o.Service + '.amazonaws.com' }, Action: 'sts:AssumeRole' }] } }); }); },
    'iam-create-policy': function (o) { return run('Created policy ' + o.PolicyName, function () { var doc; try { doc = JSON.parse(o.PolicyDocument); } catch (e) { throw AT.TwinError('MalformedPolicyDocument', 'policy document is not JSON: ' + e.message); } return client().iam.createPolicy({ PolicyName: o.PolicyName, Description: o.Description, PolicyDocument: doc }); }); },
    'iam-attach': function (o) { return run('Attached ' + o.PolicyArn.split('/').pop() + ' to ' + o.RoleName, function () { return client().iam.attachRolePolicy({ RoleName: o.RoleName, PolicyArn: o.PolicyArn }); }); },
    'cost-record': function (o) { return run('Recorded $' + num(o.Amount, 0).toFixed(2) + ' for ' + o.Service, function () { return client().twin.recordCost({ Service: o.Service, Amount: num(o.Amount, 0), Date: o.Date, Region: o.Region }); }); },
    'logs-create': function (o) { return run('Created log group ' + o.logGroupName, function () { return client().logs.createLogGroup({ logGroupName: o.logGroupName }); }); },
    'logs-filter': function (o) { view.pattern = o.filterPattern; render(); },
    'logs-put': function (o) { return run('Put event', function () { return client().logs.putLogEvents({ logGroupName: view.group, logEvents: [{ timestamp: Date.now(), message: o.message }] }); }); },
    'deploy-run': function (o) {
      var targets = [];
      (o.accounts || []).forEach(function (a) { (o.regions || []).forEach(function (r) { targets.push({ accountId: a, region: r }); }); });
      if (!targets.length) { say('Pick at least one account and one region', 'err'); render(); return; }
      var rows = [];
      var next = function (i) {
        if (i >= targets.length) { view.deployResult = { stack: o.StackName, template: o.TemplateName, rows: rows }; say('Rehearsed ' + o.StackName + ' into ' + rows.filter(function (x) { return !x.error; }).length + ' of ' + rows.length + ' targets'); render(); return; }
        var t = targets[i];
        var c = AT.client(backend(), { accountId: t.accountId, region: t.region, role: 'deploy' }, logCall);
        return c.cloudformation.createStack({ StackName: o.StackName, TemplateName: o.TemplateName, Parameters: [{ ParameterKey: 'ImageTag', ParameterValue: o.ImageTag }] })
          .then(function () { return c.cloudformation.describeStacks({ StackName: o.StackName }); })
          .then(function (d) { rows.push({ accountId: t.accountId, region: t.region, outputs: d.Stacks[0].Outputs }); }, function (e) { rows.push({ accountId: t.accountId, region: t.region, error: { code: e.code, message: e.message } }); })
          .then(function () { return next(i + 1); });
      };
      return next(0);
    },
    'commit': function (o) { return run(null, function () { var c = vault.commit(o.message); say('Committed ' + c.id.slice(0, 8) + ': ' + c.message); }); },
    'diff': function (o) { go('snapshots', o.a + '/' + o.b); },
    'session-set': function (o) {
      return run(null, function () {
        var parsed = V.SessionStore.parsePaste(o.paste);
        var s = sessionStore.set({ accessKeyId: parsed.accessKeyId, secretAccessKey: parsed.secretAccessKey, sessionToken: parsed.sessionToken, accountId: o.accountId || parsed.accountId, accountName: o.accountName, role: o.role || parsed.role, region: o.region || ui.region, expiresAt: new Date(Date.now() + Math.min(12, Math.max(1, num(o.hours, 1))) * 3600000).toISOString() });
        ui.backend = 'live'; ui.accountId = s.accountId; ui.region = s.region; saveUi();
        say('Session for ' + s.accountId + ' in the vault until ' + fmtTime(s.expiresAt) + '. Backend switched to live.');
      });
    },
    'calls-filter': function (o) { view.callFilter = o.filter; render(); }
  };

  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-action]');
    if (!b) return;
    e.preventDefault();
    var fn = ACTIONS[b.getAttribute('data-action')];
    if (fn) fn(b.getAttribute('data-arg'));
  });
  document.addEventListener('submit', function (e) {
    var f = e.target.closest('form[data-submit]');
    if (!f) return;
    e.preventDefault();
    var fn = SUBMITS[f.getAttribute('data-submit')];
    if (fn) fn(formObj(f));
  });
  document.addEventListener('change', function (e) {
    var el = e.target;
    if (el.getAttribute('data-change') === 'backend') { ui.backend = el.value; ui.accountId = null; saveUi(); render(); }
    else if (el.getAttribute('data-change') === 'account') { ui.accountId = el.value; saveUi(); render(); }
    else if (el.getAttribute('data-change') === 'region') { ui.region = el.value; saveUi(); render(); }
    else if (el.getAttribute('data-file') === 'import' && el.files && el.files[0]) {
      var reader = new FileReader();
      reader.onload = function () { run('Imported vault document', function () { vault.importDoc(JSON.parse(reader.result)); ui.accountId = null; saveUi(); }); };
      reader.readAsText(el.files[0]);
    }
  });
  window.addEventListener('hashchange', render);
  render();
}());
