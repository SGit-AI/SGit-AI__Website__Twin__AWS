#!/usr/bin/env node
/* The uptime page, end to end in headless Chromium, against the twin: load Python, make a results key,
   deploy to three regions, run it, let the schedule come round, read and decrypt the reports, tear down.
   Needs Playwright and network to cdn.jsdelivr.net and PyPI, like browser_tests.js. Env: HTTPS_PROXY, SHOT. */
const fs = require('fs'), path = require('path');
const { chromium } = require('playwright');
const ROOT = path.join(__dirname, '../..'), ORIGIN = 'https://aws-twin.test';
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css', '.zip': 'application/zip', '.svg': 'image/svg+xml' };
const results = []; const check = (ok, what) => { results.push(ok); console.log((ok ? 'ok   ' : 'FAIL ') + what); };
(async () => {
  const launch = {}; if (process.env.HTTPS_PROXY) launch.proxy = { server: process.env.HTTPS_PROXY, bypass: 'aws-twin.test' };
  const b = await chromium.launch(launch); const ctx = await b.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1280, height: 1000 } });
  await ctx.route(ORIGIN + '/**', (route) => { let f = path.join(ROOT, decodeURIComponent(new URL(route.request().url()).pathname)); if (fs.existsSync(f) && fs.statSync(f).isDirectory()) f = path.join(f, 'index.html');
    return fs.existsSync(f) ? route.fulfill({ status: 200, contentType: TYPES[path.extname(f)] || 'application/octet-stream', body: fs.readFileSync(f) }) : route.fulfill({ status: 404, body: 'nf' }); });
  const p = await ctx.newPage(); const errors = []; p.on('pageerror', (e) => errors.push(String(e)));
  await p.goto(ORIGIN + '/uptime/index.html');
  await p.waitForFunction(() => window.__uptimeReady || window.__uptimeError, null, { timeout: 400000 });
  check(await p.evaluate(() => !!window.__uptimeReady), 'page loads Python and the twin');
  check((await p.textContent('#up-source')).includes('export const handler'), 'the function source is shown');
  await p.click('#up-genkey'); await p.waitForFunction(() => document.getElementById('up-keyinfo').textContent.includes('sha256:'), null, { timeout: 120000 });
  check((await p.inputValue('#up-pubkey')).includes('BEGIN PUBLIC KEY'), 'a results key is made in the browser');
  const log = () => p.textContent('#up-log');
  await p.click('#up-deploy'); await p.waitForFunction(() => /deployed\.|✗/.test(document.getElementById('up-log').textContent), null, { timeout: 120000 });
  const l1 = await log(); check(l1.includes('deployed.') && (l1.match(/function created/g) || []).length === 3, 'deploy to three regions in the twin'); 
  check(l1.includes('lambda.CreateFunction → 201') && l1.includes('events.PutRule → 200') && l1.includes('iam.CreateRole → 200'), 'each boto3 call shown with the twin\'s answer');
  await p.click('#up-invoke'); await p.waitForFunction(() => /\(invoke\)|function error|✗ /.test(document.getElementById('up-log').textContent), null, { timeout: 60000 });
  const l2 = await log(); check(/eu-west-2 \(invoke\): 2 up, 1 down; report appended to the lane/.test(l2), 'run it now: 2 up, 1 down, report appended');
  await p.selectOption('#up-region', 'us-east-1'); await p.click('#up-fire'); await p.waitForFunction(() => /\(schedule\)/.test(document.getElementById('up-log').textContent), null, { timeout: 60000 });
  check(/us-east-1 \(schedule\): 2 up, 1 down/.test(await log()), 'the schedule comes round in us-east-1');
  await p.click('#up-read'); await p.waitForFunction(() => window.__uptimeReports, null, { timeout: 60000 });
  const reps = await p.evaluate(() => window.__uptimeReports);
  check(reps.length === 2 && reps.every((r) => r.report && r.report.kind === 'aws.twin-uptime/1'), 'two reports read from the lane and decrypted in the page');
  check((await p.textContent('#up-reports')).includes('https://down.example/'), 'the reports table shows the down site');
  if (process.env.SHOT) await p.screenshot({ path: process.env.SHOT, fullPage: true });
  await p.click('#up-teardown'); await p.waitForFunction(() => /role: deleted|✗ /.test(document.getElementById('up-log').textContent), null, { timeout: 60000 });
  check((await log()).includes('role: deleted') && (await p.textContent('#up-functions')).includes('not deployed'), 'tear down removes everything');
  check(errors.length === 0, 'no page errors ' + JSON.stringify(errors));
  console.log(results.filter(Boolean).length + ' of ' + results.length);
  await b.close(); process.exit(results.every(Boolean) ? 0 : 1);
})().catch((e) => { console.error(e); process.exit(1); });
