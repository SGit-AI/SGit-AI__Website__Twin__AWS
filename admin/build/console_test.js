#!/usr/bin/env node
/* The console, end to end in headless Chromium against the twin: every page loads Python and the
   twin's shared store; the overview seeds examples; Lambda lists, opens, shows code, invokes a
   Python and a Node.js function, shows logs and permissions; All resources lists through Cloud
   Control; Twin data opens a file; the call editor sends an operation; the request pane shows the
   calls with their requests, and a request opens with its replay link.

   MEASURE=1 also measures the calls page's two browser columns (boto3 under Pyodide, and the AWS
   SDK for JavaScript), with invented keys against real AWS, and RECORD=1 writes them into
   assets/console/call-matrix.json. Needs Playwright, and network to cdn.jsdelivr.net and PyPI
   (and AWS, to measure). Env: HTTPS_PROXY, SHOTS (a folder for screenshots). */
'use strict';
const fs = require('fs'), path = require('path');
const { chromium } = require('playwright');
const ROOT = path.join(__dirname, '../..'), ORIGIN = 'https://aws-twin.test';
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css', '.zip': 'application/zip', '.svg': 'image/svg+xml', '.json': 'application/json' };
const results = []; const check = (ok, what) => { results.push(!!ok); console.log((ok ? 'ok   ' : 'FAIL ') + what); };

(async () => {
  const launch = {}; if (process.env.HTTPS_PROXY) launch.proxy = { server: process.env.HTTPS_PROXY, bypass: 'aws-twin.test' };
  const browser = await chromium.launch(launch);
  const ctx = await browser.newContext({ ignoreHTTPSErrors: !!process.env.HTTPS_PROXY, viewport: { width: 1440, height: 1000 } });
  await ctx.route(ORIGIN + '/**', route => {
    let f = path.join(ROOT, decodeURIComponent(new URL(route.request().url()).pathname));
    if (fs.existsSync(f) && fs.statSync(f).isDirectory()) f = path.join(f, 'index.html');
    return fs.existsSync(f) ? route.fulfill({ status: 200, contentType: TYPES[path.extname(f)] || 'application/octet-stream', body: fs.readFileSync(f) }) : route.fulfill({ status: 404, body: 'not found' });
  });
  const p = await ctx.newPage(); const errors = []; p.on('pageerror', e => errors.push(String(e)));
  const text = () => p.textContent('#cx-app');
  const open = async (url) => { const t = Date.now(); await p.goto(ORIGIN + url); await p.waitForFunction(() => window.__consoleReady || window.__consoleError, null, { timeout: 400000 }); return Date.now() - t; };
  const waitText = (s, timeout = 60000) => p.waitForFunction(x => document.getElementById('cx-app').textContent.includes(x), s, { timeout });
  const shot = async name => { if (process.env.SHOTS) await p.screenshot({ path: path.join(process.env.SHOTS, `console-${name}.png`), fullPage: false }); };

  const cold = await open('/console/index.html');
  check(await p.evaluate(() => !!window.__consoleReady), `the overview loads Python and the twin (${cold} ms, first load)`);
  await p.click('[data-act=seed]'); await waitText('Created example functions');
  check((await text()).includes('Lambda functions'), 'examples created in the twin');
  await p.click('[data-cx=pane]');
  check(await p.isVisible('#cx-pane'), 'the request pane opens');
  check((await p.textContent('#cx-pane-list')).includes('lambda_seed'), 'the pane lists the seeding call');
  await shot('overview');

  const warm = await open('/console/lambda.html');
  check(warm < 60000, `the Lambda page loads (${warm} ms, from the browser's cache)`);
  await waitText('example-site-check');
  check((await text()).includes('example-hello-python') && (await text()).includes('nodejs22.x'), 'Lambda lists both functions, from the shared store');
  check(await p.isVisible('#cx-pane'), 'the pane stays open across pages');
  await shot('lambda-list');
  await p.goto(ORIGIN + '/console/lambda.html#/fn/eu-west-2/example-site-check'); await waitText('Function overview');
  const ov = await text();
  check(ov.includes('index.handler') && ov.includes('rate(15 minutes)') && ov.includes('AWS_IAM'), 'a function\'s configuration, trigger and URL');
  check(await p.evaluate(() => document.getElementById('cx-env').classList.contains('cx-masked')), 'environment values hidden until asked');
  await shot('lambda-function');
  await p.click('.s3-tabs a:has-text("Code")'); await waitText('index.mjs');
  check((await p.textContent('#cx-file')).includes('export const handler'), 'the function\'s code, from the twin');
  await p.click('.s3-tabs a:has-text("Test")'); await waitText('Test event');
  await p.click('button:has-text("Invoke")'); await waitText('Result:', 60000);
  check((await text()).includes('"status": 200'), 'a Node.js function invoked in the twin, through the browser');
  await shot('lambda-test');
  await p.goto(ORIGIN + '/console/lambda.html#/fn/eu-west-2/example-hello-python/test'); await waitText('Test event');
  await p.fill('textarea[name=payload]', '{"name": "Dinis"}'); await p.click('button:has-text("Invoke")'); await waitText('Result:');
  check((await text()).includes('"hello": "Dinis"'), 'a Python function invoked in the twin');
  await p.click('.s3-tabs a:has-text("Logs")'); await waitText('Invocations');
  check((await text()).includes('event {"name": "Dinis"}'), 'the invocation\'s log lines');
  await p.click('.s3-tabs a:has-text("Permissions")'); await waitText('Resource-based policy');
  check((await text()).includes('Execution role'), 'permissions');

  await open('/console/resources.html#/type/' + encodeURIComponent('AWS::IAM::Role')); await waitText('example-lambda-role');
  await p.click('a:has-text("example-lambda-role")'); await waitText('ManagedPolicyArns');
  check((await text()).includes('AWSLambdaBasicExecutionRole'), 'All resources: a role, through Cloud Control');

  await open('/console/twin.html'); await waitText('/lambda');
  await p.click('a:has-text("/lambda/eu-west-2/functions/example-hello-python/config.json")'); await waitText('python3.13');
  check(true, 'Twin data: a file opens');

  await open('/console/s3.html'); await waitText('example-twin-bucket');
  check(true, 'S3: the example bucket, from the shared store');
  p.on('dialog', d => d.type() === 'prompt' ? d.accept('renamed.md') : d.accept());
  await p.goto(ORIGIN + '/console/s3.html#/create-bucket'); await waitText('General configuration');
  await p.fill('input[name=name]', 'console-test-bucket'); await p.click('button:has-text("Create bucket")'); await waitText('Successfully created bucket');
  await p.goto(ORIGIN + '/console/s3.html#/upload/console-test-bucket'); await waitText('Upload');
  await p.fill('input[name=name]', 'notes.md'); await p.fill('textarea[name=body]', '# from the console test'); await p.click('form[data-submit=upload-text] button[type=submit]'); await waitText('Upload succeeded');
  check((await text()).includes('notes.md'), 'S3: create a bucket and upload an object');
  await p.goto(ORIGIN + '/console/s3.html#/obj/console-test-bucket/notes.md'); await waitText('Preview');
  check((await text()).includes('# from the console test'), 'S3: the object\'s preview');
  await p.goto(ORIGIN + '/console/s3.html#/b/console-test-bucket'); await waitText('notes.md');
  await p.check('input[type=checkbox][value="notes.md"]'); await p.click('[data-act=rename]'); await waitText('Renamed to renamed.md');
  check((await text()).includes('renamed.md') && !(await text()).includes('notes.md'), 'S3: rename');
  await open('/console/s3.html#/b/console-test-bucket'); await waitText('renamed.md');
  check(true, 'S3: the object is still there after a reload (IndexedDB)');
  await p.check('input[type=checkbox][value="renamed.md"]'); await p.click('[data-act=delete]'); await waitText('Deleted 1 object');
  check((await text()).includes('No objects'), 'S3: delete');

  await open('/console/calls.html'); await waitText('Which AWS calls work');
  check((await text()).includes('s3.ListBuckets') && (await text()).includes('cloudcontrol.ListResources'), 'the calls matrix shows');
  await shot('calls-matrix');
  await p.goto(ORIGIN + '/console/calls.html#/editor/lambda/ListFunctions'); await waitText('Call editor');
  await p.click('button:has-text("Send")'); await waitText('example-site-check');
  check(true, 'the call editor sends lambda.ListFunctions to the twin');
  await shot('calls-editor');
  const req = p.locator('#cx-pane-list details.cx-call').first();
  await req.locator('summary').first().click();
  await req.locator('details.cx-req summary').first().click();
  await p.waitForFunction(() => document.querySelector('#cx-pane-list .cx-req-body') && document.querySelector('#cx-pane-list .cx-req-body').textContent.includes('request headers'), null, { timeout: 30000 });
  const detail = await p.textContent('#cx-pane-list .cx-req-body');
  check(detail.includes('Replay in the call editor') && detail.includes('x-amz-date'), 'a request opens with its headers and a replay link');
  await shot('pane');

  if (process.env.MEASURE) {
    await p.goto(ORIGIN + '/console/calls.html#/matrix'); await waitText('Which AWS calls work');
    await p.click('[data-act=measure-py]'); await p.waitForFunction(() => window.__matrixPyodide, null, { timeout: 600000 });
    await p.click('[data-act=measure-js]'); await p.waitForFunction(() => window.__matrixJsSdk, null, { timeout: 900000 });
    const py = await p.evaluate(() => window.__matrixPyodide), js = await p.evaluate(() => window.__matrixJsSdk);
    const blockedPy = Object.keys(py).filter(k => py[k].status === 'blocked'), blockedJs = Object.keys(js).filter(k => js[k].status === 'blocked');
    console.log('blocked, boto3 under Pyodide:', blockedPy.join(', ')); console.log('blocked, AWS SDK for JavaScript:', blockedJs.join(', '));
    const other = Object.entries(Object.assign({}, py, js)).filter(([, v]) => !['reached', 'blocked', 'ok'].includes(v.status));
    if (other.length) console.log('neither reached nor blocked:', JSON.stringify(other));
    check(blockedPy.includes('s3.ListBuckets') && blockedJs.includes('s3.ListBuckets'), 's3.ListBuckets is blocked in the browser, for boto3 and for the JS SDK');
    await shot('calls-measured');
    if (process.env.RECORD) {
      const file = path.join(ROOT, 'assets/console/call-matrix.json'), doc = JSON.parse(fs.readFileSync(file, 'utf8'));
      for (const r of doc.rows) { if (py[r.id]) r.pyodide = py[r.id]; if (js[r.id]) r.jssdk = js[r.id]; }
      const ua = await p.evaluate(() => navigator.userAgent.match(/(HeadlessChrome|Chrome)\/[\d.]+/)[0]);
      doc.measured.browser = new Date().toISOString().slice(0, 10);
      Object.assign(doc.versions, { browser: ua, pyodide: '0.28.3', js_sdk: '3.1147.0' });
      fs.writeFileSync(file, JSON.stringify(doc, null, 1));
      console.log('recorded the browser columns in assets/console/call-matrix.json');
    }
  }
  check(errors.length === 0, 'no page errors ' + JSON.stringify(errors));
  console.log(results.filter(Boolean).length + ' of ' + results.length);
  await browser.close(); process.exit(results.every(Boolean) ? 0 : 1);
})().catch(e => { console.error(e); process.exit(1); });
