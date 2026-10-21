#!/usr/bin/env node
/* Run the Python twin's tests in a real browser: serve the site (through Playwright's request
   routing, so no local port and no proxy is involved), open python/tests.html#run
   in headless Chromium, wait for the report, print it, exit non-zero on a failure.
   Needs Playwright and network to cdn.jsdelivr.net and PyPI. CI runs it as its own job.

   Env: CHROMIUM_PATH (default: Playwright's own), HTTPS_PROXY (used if set),
        REPORT (path to write the JSON report). */
'use strict';
const fs = require('fs'), path = require('path');
const { chromium } = require('playwright');
const ROOT = path.join(__dirname, '../..');
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.zip': 'application/zip', '.json': 'application/json', '.svg': 'image/svg+xml' };
const ORIGIN = 'http://aws-twin.test';
function serve(route) {
  const url = new URL(route.request().url());
  let f = path.join(ROOT, decodeURIComponent(url.pathname));
  if (fs.existsSync(f) && fs.statSync(f).isDirectory()) f = path.join(f, 'index.html');
  if (!f.startsWith(ROOT) || !fs.existsSync(f)) return route.fulfill({ status: 404, body: 'not found' });
  return route.fulfill({ status: 200, contentType: TYPES[path.extname(f)] || 'application/octet-stream', body: fs.readFileSync(f) });
}
(async () => {
  const launch = { };
  if (process.env.CHROMIUM_PATH) launch.executablePath = process.env.CHROMIUM_PATH;
  if (process.env.HTTPS_PROXY) launch.proxy = { server: process.env.HTTPS_PROXY, bypass: 'localhost,127.0.0.1,pypi.org,files.pythonhosted.org' };
  const browser = await chromium.launch(launch);
  const context = await browser.newContext({ ignoreHTTPSErrors: !!process.env.HTTPS_PROXY });
  await context.route(ORIGIN + '/**', serve);
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  const t0 = Date.now();
  await page.goto(ORIGIN + '/python/tests.html#run');
  await page.waitForFunction(() => window.__twinTestReport, null, { timeout: 600000 });
  const report = await page.evaluate(() => window.__twinTestReport);
  report.wallMs = Date.now() - t0; report.pageErrors = errors;
  await browser.close();
  if (process.env.REPORT) fs.writeFileSync(process.env.REPORT, JSON.stringify(report, null, 2));
  if (report.error) { console.error('browser tests could not start: ' + report.error); process.exit(1); }
  for (const r of report.results) console.log((r.skipped ? 'skip ' : r.ok ? 'ok   ' : 'FAIL ') + r.test + ' (' + r.ms + ' ms)' + (r.skipped ? ': ' + r.skipped : r.ok ? '' : '\n     ' + r.error));
  console.log(`browser tests: ${report.passed} passed, ${report.skipped} skipped, ${report.failed} failed; python ${report.versions.python}, boto3 ${report.versions.boto3}, osbot-aws ${report.versions.osbot_aws}, osbot-utils ${report.versions.osbot_utils}; load ${report.timings.total} ms, tests ${report.ms} ms`);
  process.exit(report.failed ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1); });
