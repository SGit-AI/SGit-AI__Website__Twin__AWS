/* serve the research dir over http, open boto3-twin.html in headless Chromium through the
   container's egress proxy, wait for the experiment, write the result as JSON */
const { chromium } = require('playwright');
const http = require('http'), fs = require('fs'), path = require('path');
const DIR = __dirname;
const server = http.createServer((req, res) => {
  const f = path.join(DIR, decodeURIComponent(req.url.split('?')[0]).replace(/^\//, '') || 'index.html');
  if (!fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); res.end(); return; }
  res.writeHead(200, { 'content-type': f.endsWith('.js') ? 'text/javascript' : 'text/html' });
  fs.createReadStream(f).pipe(res);
}).listen(8787);
(async () => {
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium', proxy: { server: process.env.HTTPS_PROXY, bypass: 'localhost,127.0.0.1,pypi.org,files.pythonhosted.org,*.pythonhosted.org' } });
  const ctx = await browser.newContext({ ignoreHTTPSErrors: true });
  const page = await ctx.newPage();
  const bytes = {}; const errors = [];
  page.on('response', async r => { if (!/localhost/.test(r.url())) console.error('[resp] ' + r.status() + ' ' + r.url().slice(0, 110)); try { const u = new URL(r.url()); const h = r.headers(); const n = parseInt(h['content-length'] || '0', 10); bytes[u.host] = (bytes[u.host] || 0) + (isNaN(n) ? 0 : n); } catch (e) {} });
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', m => { console.error('[console:' + m.type() + '] ' + m.text().slice(0, 300)); if (m.type() === 'error') errors.push(m.text()); });
  page.on('requestfailed', r => console.error('[failed] ' + r.url().slice(0, 120) + ' ' + (r.failure() || {}).errorText));
  const t0 = Date.now();
  await page.goto('file://' + path.join(DIR, 'boto3-twin.html')); /* run from articles/data/ in the repository */
  await page.waitForFunction(() => window.__result, null, { timeout: 420000 });
  const result = await page.evaluate(() => window.__result);
  result.wallMs = Date.now() - t0; result.bytesByHost = bytes; result.consoleErrors = errors;
  fs.writeFileSync(path.join(DIR, 'boto3-result.json'), JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result, null, 2));
  await browser.close(); server.close();
})().catch(e => { console.error(e); process.exit(1); });
