/* aws.twin.sgit.ai: the uptime page. Every AWS call is Python (aws_twin/web/Uptime__Page.py, which
   is Uptime__Deploy's boto3), entered with callPromising so the Lambda twin can run the Node.js
   function through JSPI. What stays in JavaScript, on purpose: the results key (WebCrypto, kept in
   IndexedDB, never exportable), decrypting reports, and reading a real sgit lane (dev.send.sgraph.ai
   answers a browser). Content CC BY 4.0, code Apache-2.0. */
(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  var esc = function (s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); };
  var sleep = function (ms) { return new Promise(function (r) { setTimeout(r, ms); }); };
  var REGIONS = ['eu-west-2', 'us-east-1', 'us-west-2', 'eu-central-1', 'ap-southeast-2', 'ap-northeast-1', 'sa-east-1', 'ap-south-1'];
  var ANSWERS = [['200', 'up: 200'], ['301', 'up: 301 redirect'], ['404', 'down: 404'], ['500', 'down: 500'], ['503', 'down: 503'],
                 ['ECONNREFUSED', 'refused'], ['ENOTFOUND', 'no such host'], ['ETIMEDOUT', 'timed out']];
  var state = { py: null, fn: null, mode: 'twin', key: null, lane: null, deployed: false, account: null };

  /* ── Python ─────────────────────────────────────────────────────────── */
  function call(name, args) {
    return state.fn.callPromising(name, JSON.stringify(args || {})).then(function (text) {
      var out = JSON.parse(text);
      out.traffic.forEach(function (t) { log((t.target === 'live' ? '  AWS  ' : '  twin ') + t.service + '.' + t.operation + ' → ' + t.status, 'd'); });
      return out;
    });
  }
  function step(name, args) {
    return call(name, args).then(function (out) {
      if (out.error) throw Object.assign(new Error(out.error.message), { code: out.error.code });
      return out.result;
    });
  }

  /* ── the log ────────────────────────────────────────────────────────── */
  function log(text, cls) {
    var el = $('up-log'), line = document.createElement('span');
    if (cls) line.className = cls;
    line.textContent = text + '\n';
    el.appendChild(line); el.scrollTop = el.scrollHeight;
  }
  function fail(e) { log('✗ ' + (e.code ? e.code + ': ' : '') + e.message, 'r'); }

  /* ── the session (pasted on /sessions/, this tab) ───────────────────── */
  function session() {
    try { var s = JSON.parse(sessionStorage.getItem('aws.twin/session') || 'null'); } catch (e) { return null; }
    if (!s || !s.sessionToken) return null;
    s.expired = s.expiresAt && Date.parse(s.expiresAt) < Date.now();
    return s;
  }

  /* ── the results key: WebCrypto, kept in IndexedDB ──────────────────── */
  function db() {
    return new Promise(function (resolve, reject) {
      var r = indexedDB.open('aws-twin-uptime', 1);
      r.onupgradeneeded = function () { r.result.createObjectStore('keys'); };
      r.onsuccess = function () { resolve(r.result); }; r.onerror = function () { reject(r.error); };
    });
  }
  function idb(mode, fn) {
    return db().then(function (d) { return new Promise(function (resolve, reject) {
      var tx = d.transaction('keys', mode), req = fn(tx.objectStore('keys'));
      tx.oncomplete = function () { resolve(req && req.result); }; tx.onerror = function () { reject(tx.error); };
    }); });
  }
  var b64 = function (buf) { var s = '', a = new Uint8Array(buf); for (var i = 0; i < a.length; i++) s += String.fromCharCode(a[i]); return btoa(s); };
  var unb64 = function (t) { return Uint8Array.from(atob(t), function (c) { return c.charCodeAt(0); }); };
  function fingerprint(der) {
    return crypto.subtle.digest('SHA-256', der).then(function (d) { return 'sha256:' + Array.from(new Uint8Array(d), function (b) { return b.toString(16).padStart(2, '0'); }).join('').slice(0, 16); });
  }
  function makeKey() {
    var alg = { name: 'RSA-OAEP', modulusLength: 4096, publicExponent: new Uint8Array([1, 0, 1]), hash: 'SHA-256' };
    $('up-keyinfo').textContent = 'making an RSA-4096 key…';
    return crypto.subtle.generateKey(alg, false, ['encrypt', 'decrypt']).then(function (pair) {
      return crypto.subtle.exportKey('spki', pair.publicKey).then(function (der) {
        var pem = '-----BEGIN PUBLIC KEY-----\n' + b64(der).match(/.{1,64}/g).join('\n') + '\n-----END PUBLIC KEY-----\n';
        return fingerprint(der).then(function (fp) {
          var key = { publicPem: pem, privateKey: pair.privateKey, fingerprint: fp, created: new Date().toISOString() };
          return idb('readwrite', function (s) { return s.put(key, 'results'); }).then(function () { return key; });
        });
      });
    });
  }
  function showKey() {
    if (!state.key) return;
    $('up-keyinfo').innerHTML = 'Results key <code>' + esc(state.key.fingerprint) + '</code>, made ' + esc(state.key.created.slice(0, 16).replace('T', ' ')) +
      ' UTC, private half in this browser only. Its public half is filled in below.';
    $('up-pubkey').value = state.key.publicPem;
  }

  /* sgit's envelope v2, opened as sgit's hybrid_decrypt does; content is base64 of the .enc text */
  function decrypt(content) {
    var env = JSON.parse(atob(atob(content)));
    return crypto.subtle.decrypt({ name: 'RSA-OAEP' }, state.key.privateKey, unb64(env.w)).then(function (raw) {
      return crypto.subtle.importKey('raw', raw, { name: 'AES-GCM' }, false, ['decrypt']);
    }).then(function (aes) {
      return crypto.subtle.decrypt({ name: 'AES-GCM', iv: unb64(env.i) }, aes, unb64(env.c));
    }).then(function (plain) { return JSON.parse(new TextDecoder().decode(plain)); });
  }

  /* ── the form ───────────────────────────────────────────────────────── */
  function targets() { return $('up-targets').value.split('\n').map(function (s) { return s.trim(); }).filter(Boolean); }
  function regions() { return Array.prototype.filter.call(document.querySelectorAll('#up-regions input'), function (i) { return i.checked; }).map(function (i) { return i.value; }); }
  function renderRegions() {
    $('up-regions').innerHTML = REGIONS.map(function (r, i) { return '<label class="up-check"><span><input type="checkbox" value="' + r + '"' + (i < 3 ? ' checked' : '') + '> ' + r + '</span></label>'; }).join('');
    $('up-regions').addEventListener('change', renderRegionSelect);
    renderRegionSelect();
  }
  function renderRegionSelect() { $('up-region').innerHTML = regions().map(function (r) { return '<option>' + r + '</option>'; }).join(''); }
  function renderInternet() {
    var rows = targets().map(function (t, i) {
      var guess = /down\.example|example\.invalid/.test(t) ? '503' : '200';
      return '<tr><td><code>' + esc(t) + '</code></td><td><select data-target="' + esc(t) + '">' + ANSWERS.map(function (a) {
        return '<option value="' + a[0] + '"' + (a[0] === guess ? ' selected' : '') + '>' + a[1] + '</option>'; }).join('') +
        '</select></td><td><input type="number" min="0" max="12000" step="10" value="' + (40 + i * 30) + '" data-ms="' + esc(t) + '"> ms</td></tr>';
    });
    $('up-internet').querySelector('tbody').innerHTML = rows.join('');
  }
  function internetAnswers() {
    return Array.prototype.map.call(document.querySelectorAll('#up-internet select'), function (s) {
      var v = s.value, ms = Number(document.querySelector('[data-ms="' + CSS.escape(s.dataset.target) + '"]').value) || 0;
      return /^\d+$/.test(v) ? { target: s.dataset.target, status: Number(v), ms: ms } : { target: s.dataset.target, error: v, ms: ms };
    });
  }

  /* ── modes ──────────────────────────────────────────────────────────── */
  function setMode(info) {
    state.mode = info.mode; state.account = info.account;
    var live = info.mode === 'live';
    $('up-mode').className = 'up-pill' + (live ? ' live' : '');
    $('up-mode').textContent = live ? 'LIVE · account ' + info.account : 'the twin in this page answers, not AWS';
    $('up-mode-note').innerHTML = live ? 'Calls go to AWS, signed in this page with the session from <a href="../sessions/index.html">the sessions page</a>: ' + esc(info.arn) + '. Deploy and tear down ask first.'
                                       : 'Calls go to the Python twin in this page: IAM, Lambda, EventBridge and CloudFront twins, an internet you set below, and a twinned sgit lane.';
    $('up-internet-box').hidden = live; $('up-lane-twin').hidden = live; $('up-lane-live').hidden = !live; $('up-fire').hidden = live;
    $('up-twin').disabled = !live; $('up-live').disabled = live;
    state.deployed = false; state.lane = null; renderFunctions([]);
  }

  /* ── deploy ─────────────────────────────────────────────────────────── */
  function laneConfig() {
    if (state.mode === 'twin') return step('twin_lane').then(function (lane) { state.lane = lane; return lane; });
    var host = $('up-host').value.trim(), vault = $('up-vault').value.trim(), token = $('up-token').value.trim();
    if (!vault || !token) return Promise.reject(new Error('live mode needs the lane: a vault id and an append token registered on it'));
    state.lane = { host: host, vault_id: vault, append_token: token, enum_key: $('up-enum').value.trim(), write_url: 'https://' + host + '/api/vault/append/write/' + vault };
    return Promise.resolve(state.lane);
  }
  function configure(lane) {
    var cf = $('up-cf').checked;
    return step('configure', { regions: regions(), targets: targets(), recipient_key: $('up-pubkey').value.trim(), append_url: lane.write_url,
                               append_token: lane.append_token, controller_key: $('up-controller').value.trim(), schedule: $('up-schedule').value,
                               function_url: $('up-url').checked || cf, cloudfront: cf });
  }
  function waitReady(region) {
    var tries = 0;
    var poll = function () {
      return step('state', { region: region }).then(function (s) {
        if (s.ready) return s;
        if (++tries > 45) throw new Error('the function in ' + region + ' did not become ready');
        log('  … ' + region + ': ' + s.state + ' / ' + s.update + ', waiting', 'd');
        return sleep(2000).then(poll);
      });
    };
    return poll();
  }
  function putFunction(region, roleArn, attempt) {
    return call('function', { region: region, role_arn: roleArn }).then(function (out) {
      if (!out.error) return out.result;
      if (out.error.code === 'InvalidParameterValueException' && /assumed/.test(out.error.message) && (attempt || 0) < 12) {
        log('  … the new role is not usable by Lambda yet; trying again in 5 s', 'y');
        return sleep(5000).then(function () { return putFunction(region, roleArn, (attempt || 0) + 1); });
      }
      throw Object.assign(new Error(out.error.message), { code: out.error.code });
    });
  }
  function deploy() {
    var rs = regions(), ts = targets();
    if (!rs.length || !ts.length) return Promise.reject(new Error('pick at least one region and one website'));
    if (!$('up-pubkey').value.trim()) return Promise.reject(new Error('make a results key, or paste the public key to encrypt to'));
    if (state.mode === 'live' && !confirm('Deploy the uptime function to account ' + state.account + ' in ' + rs.join(', ') + '?\n\nIt creates an IAM role, a Lambda function and an EventBridge rule in each region' +
                                          ($('up-cf').checked ? ', and a CloudFront distribution' : '') + '.')) return Promise.resolve();
    var urls = {}, role;
    log('— deploy, ' + state.mode + ', ' + rs.length + ' region' + (rs.length > 1 ? 's' : ''));
    return laneConfig().then(function (lane) {
      if (state.mode === 'twin') return step('internet', { answers: internetAnswers() }).then(function () { return lane; });
      return lane;
    }).then(configure).then(function (c) {
      log('package: index.mjs, ' + c.package_bytes + ' bytes zipped; environment ' + c.environment_bytes + ' of 4096 bytes');
      return step('role');
    }).then(function (r) {
      role = r; log('✓ role ' + r.arn + (r.created ? ' (created)' : ' (exists)'), 'g');
      return rs.reduce(function (p, region) {
        return p.then(function () { return putFunction(region, role.arn); }).then(function (f) {
          log('✓ ' + region + ': function ' + f.action, 'g');
          return waitReady(region).then(function () {
            return f.needs_config ? step('config', { region: region, role_arn: role.arn }).then(function () { log('✓ ' + region + ': configuration updated', 'g'); return waitReady(region); }) : null;
          }).then(function () { return step('schedule', { region: region, function_arn: f.arn }); });
        }).then(function (s) {
          log('✓ ' + region + ': ' + s.expression + ' → the function', 'g');
          if (!$('up-url').checked && !$('up-cf').checked) return null;
          return step('url', { region: region }).then(function (u) { urls[region] = u.url; log('✓ ' + region + ': ' + u.url, 'g'); });
        });
      }, Promise.resolve());
    }).then(function () {
      if (!$('up-cf').checked) return null;
      return step('cloudfront', { urls: urls }).then(function (d) { log('✓ CloudFront ' + d.action + ': https://' + d.domain + '/<region>/ (' + d.status + ')', 'g'); });
    }).then(function () { state.deployed = true; log('deployed.', 'g'); return refresh(); });
  }

  /* ── run, read, tear down ───────────────────────────────────────────── */
  function renderFunctions(rows) {
    $('up-functions').querySelector('tbody').innerHTML = rows.map(function (r) {
      return '<tr><td>' + esc(r.region) + '</td><td>' + esc(r.state) + (r.update ? ' / ' + esc(r.update) : '') + '</td><td>' + (r.invocations == null ? '—' : r.invocations) + '</td></tr>';
    }).join('');
    ['up-invoke', 'up-fire', 'up-read', 'up-teardown'].forEach(function (id) { $(id).disabled = !state.deployed; });
  }
  function refresh() { return step('functions').then(renderFunctions); }
  function showSummary(p) {
    if (!p || !p.results) { log(JSON.stringify(p), 'r'); return; }
    log(p.region + ' (' + p.trigger + '): ' + p.up + ' up, ' + p.down + ' down; report ' + (p.submitted.ok ? 'appended to the lane' : 'NOT appended: ' + (p.submitted.status || p.submitted.error || p.submitted.skipped)), p.down ? 'y' : 'g');
    p.results.forEach(function (r) { log('   ' + (r.ok ? 'up  ' : 'DOWN') + '  ' + (r.status || '—') + '  ' + String(r.ms).padStart(5) + ' ms  ' + r.url + (r.error ? '  (' + r.error + ')' : ''), r.ok ? 'd' : 'y'); });
  }
  function invoke() {
    var region = $('up-region').value;
    log('— run it now in ' + region);
    return step('invoke', { region: region }).then(function (out) {
      if (out.function_error) log('function error: ' + JSON.stringify(out.payload), 'r'); else showSummary(out.payload);
      return refresh();
    });
  }
  function fire() {
    var region = $('up-region').value;
    log('— the schedule comes round in ' + region + ' (the twin fires the EventBridge rule)');
    return step('fire', { region: region }).then(function (f) {
      f.invocations.forEach(function (i) { if (!i.ok && !i.result) log('not invoked: ' + i.reason, 'r'); else if (i.result && i.result.error) log('function error: ' + JSON.stringify(i.result.error), 'r'); else showSummary(i.result.result); });
      return refresh();
    });
  }
  function laneEntries() {
    if (state.mode === 'twin') return step('lane', { vault_id: state.lane.vault_id, enum_key: state.lane.enum_key });
    var l = state.lane;
    if (!l || !l.enum_key) return Promise.reject(new Error('reading a live lane needs its enum key'));
    return fetch('https://' + l.host + '/api/vault/append/list/' + encodeURIComponent(l.vault_id), {
      method: 'POST', headers: { 'content-type': 'application/json', 'x-sgraph-vault-enum-key': l.enum_key }, body: JSON.stringify({ include_content: true })
    }).then(function (r) {
      if (!r.ok) throw new Error('the lane answered ' + r.status + (r.status === 404 ? ': the vault id or the enum key is wrong' : ''));
      return r.json();
    }).then(function (d) { return (d.entries || d.files || d.items || []).filter(function (e) { return e.content; }); });
  }
  function read() {
    if (!state.key) return Promise.reject(new Error('the reports are encrypted to the key you gave; only a key made in this browser can be read here (else: sgit pki decrypt)'));
    log('— read the lane' + (state.mode === 'twin' ? ' (the twin\'s)' : ' at ' + state.lane.host));
    return laneEntries().then(function (entries) {
      log(entries.length + ' report' + (entries.length === 1 ? '' : 's') + ' in the lane');
      return Promise.all(entries.map(function (e) {
        return decrypt(e.content).then(function (rep) { return { id: e.file_id, report: rep }; }, function (err) { return { id: e.file_id, error: 'not decryptable with this key: ' + err.name }; });
      }));
    }).then(function (rows) {
      rows.sort(function (a, b) { return a.id < b.id ? 1 : -1; });
      $('up-reports').innerHTML = rows.length ? '<table class="up-table"><thead><tr><th>Checked</th><th>Region</th><th>Trigger</th><th>Results</th></tr></thead><tbody>' + rows.map(function (r) {
        if (r.error) return '<tr><td colspan="3"><code>' + esc(r.id) + '</code></td><td>' + esc(r.error) + '</td></tr>';
        var p = r.report;
        return '<tr><td>' + esc(p.checked_at.replace('T', ' ').slice(0, 19)) + '</td><td>' + esc(p.region) + '</td><td>' + esc(p.trigger) + '</td><td>' + p.results.map(function (x) {
          return '<div class="' + (x.ok ? 'up-ok' : 'up-down') + '">' + (x.ok ? '▲ ' : '▼ ') + esc(x.status || x.error) + ' · ' + x.ms + ' ms · <code>' + esc(x.url) + '</code></div>'; }).join('') + '</td></tr>';
      }).join('') + '</tbody></table><p class="up-note">Decrypted in this browser with the results key; the lane, the twin and AWS saw only ciphertext.</p>' : 'The lane is empty.';
      window.__uptimeReports = rows;
    });
  }
  function teardown() {
    var rs = regions();
    if (state.mode === 'live' && !confirm('Remove the uptime function, its schedule' + ($('up-cf').checked ? ', the CloudFront distribution' : '') + ' and its role from account ' + state.account + '?')) return Promise.resolve();
    log('— tear down');
    return rs.reduce(function (p, region) {
      return p.then(function () { return step('teardown_region', { region: region }); }).then(function (t) { log('✓ ' + region + ': removed ' + (t.removed.join(', ') || 'nothing'), 'g'); });
    }, Promise.resolve()).then(function () {
      if (!$('up-cf').checked) return null;
      return step('teardown_cloudfront').then(function (t) {
        log('CloudFront: ' + t.state, 'g');
        if (t.state === 'disabling') return state.mode === 'twin' ? step('teardown_cloudfront').then(function (t2) { log('CloudFront: ' + t2.state, 'g'); })
                                                                  : log('AWS takes minutes to deploy the disable: press tear down again later to delete it', 'y');
      });
    }).then(function () { return step('teardown_role'); }).then(function (t) { log('role: ' + t.state, 'g'); state.deployed = false; return refresh(); });
  }

  /* ── wiring ─────────────────────────────────────────────────────────── */
  function guard(fn, btn) {
    return function () {
      btn.disabled = true;
      Promise.resolve().then(fn).catch(fail).then(function () { btn.disabled = btn.id !== 'up-deploy' && !state.deployed; });
    };
  }
  function start() {
    renderRegions(); renderInternet();
    $('up-targets').addEventListener('input', renderInternet);
    $('up-genkey').addEventListener('click', function () { makeKey().then(function (k) { state.key = k; showKey(); }).catch(fail); });
    idb('readonly', function (s) { return s.get('results'); }).then(function (k) { if (k) { state.key = k; showKey(); } }).catch(function () {});
    loadTwinPython({ onStep: function (n, ms) { $('up-mode-note').textContent = 'loaded ' + n + ' in ' + ms + ' ms…'; } }).then(function (py) {
      state.py = py;
      py.runPython('from aws_twin.web.Uptime__Page import uptime_call');
      state.fn = py.globals.get('uptime_call');
      return step('handler_source').then(function (src) { $('up-source').textContent = src; return step('use_twin'); });
    }).then(function (info) {
      setMode(info);
      $('up-deploy').disabled = false;
      $('up-deploy').addEventListener('click', guard(deploy, $('up-deploy')));
      $('up-invoke').addEventListener('click', guard(invoke, $('up-invoke')));
      $('up-fire').addEventListener('click', guard(fire, $('up-fire')));
      $('up-read').addEventListener('click', guard(read, $('up-read')));
      $('up-teardown').addEventListener('click', guard(teardown, $('up-teardown')));
      $('up-twin').addEventListener('click', function () { step('use_twin').then(setMode).catch(fail); });
      $('up-live').addEventListener('click', function () {
        var s = session();
        if (!s || s.expired) return fail(new Error('no unexpired session in this tab: paste one on the sessions page, in this same tab'));
        step('use_live', { session_json: JSON.stringify({ accessKeyId: s.accessKeyId, secretAccessKey: s.secretAccessKey, sessionToken: s.sessionToken, region: s.region }) })
          .then(setMode).catch(fail);
      });
      window.__uptimeReady = true;
    }).catch(function (e) { $('up-mode').textContent = 'failed to load'; fail(e); window.__uptimeError = String(e); });
  }
  start();
}());
