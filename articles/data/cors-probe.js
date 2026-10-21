/* CORS probe: from a page on http://localhost, fetch each AWS service endpoint the twin's
   manifest names, twice: a simple GET (no custom headers, no preflight) and a request
   shaped like the SDK's (Authorization + x-amz-date + content-type, which forces an
   OPTIONS preflight). Record whether the browser could read the response at all. The
   requests are unsigned, so AWS answers 4xx when it answers; the question is only
   whether the browser is allowed to see that answer. */
const { chromium } = require('playwright');
const http = require('http'), fs = require('fs'), path = require('path');
const server = http.createServer((req, res) => { res.writeHead(200, { 'content-type': 'text/html' }); res.end('<!doctype html><title>cors probe</title>'); }).listen(8788);
const ENDPOINTS = [
  ['sts (global)', 'https://sts.amazonaws.com/?Action=GetCallerIdentity&Version=2011-06-15', 'GET'],
  ['sts (regional)', 'https://sts.eu-west-2.amazonaws.com/?Action=GetCallerIdentity&Version=2011-06-15', 'GET'],
  ['s3 (service root)', 'https://s3.eu-west-2.amazonaws.com/', 'GET'],
  ['s3 (a bucket, path style)', 'https://s3.eu-west-2.amazonaws.com/aws-twin-cors-probe-does-not-exist/', 'GET'],
  ['lambda', 'https://lambda.eu-west-2.amazonaws.com/2015-03-31/functions/', 'GET'],
  ['ec2', 'https://ec2.eu-west-2.amazonaws.com/?Action=DescribeInstances&Version=2016-11-15', 'GET'],
  ['iam', 'https://iam.amazonaws.com/?Action=ListRoles&Version=2010-05-08', 'GET'],
  ['logs', 'https://logs.eu-west-2.amazonaws.com/', 'POST'],
  ['ce (cost explorer)', 'https://ce.us-east-1.amazonaws.com/', 'POST'],
  ['cloudformation', 'https://cloudformation.eu-west-2.amazonaws.com/?Action=ListStacks&Version=2010-05-15', 'GET'],
  ['control: example.com (no CORS)', 'https://example.com/', 'GET'],
];
(async () => {
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium', proxy: { server: process.env.HTTPS_PROXY, bypass: 'localhost,127.0.0.1' } });
  const ctx = await browser.newContext({ ignoreHTTPSErrors: true });
  const page = await ctx.newPage();
  await page.goto('http://localhost:8788/');
  const out = [];
  for (const [name, url, method] of ENDPOINTS) {
    const r = await page.evaluate(async ({ url, method }) => {
      const one = async (opts) => {
        const t = performance.now();
        try {
          const res = await fetch(url, Object.assign({ method, mode: 'cors' }, opts));
          const text = await res.text();
          return { readable: true, status: res.status, acao: res.headers.get('access-control-allow-origin'), bodyStart: text.slice(0, 80).replace(/\s+/g, ' '), ms: Math.round(performance.now() - t) };
        } catch (e) { return { readable: false, error: String(e.message || e), ms: Math.round(performance.now() - t) }; }
      };
      const simple = await one({});
      const sdk = await one({ headers: { 'authorization': 'AWS4-HMAC-SHA256 Credential=PROBE/20261021/eu-west-2/svc/aws4_request, SignedHeaders=host;x-amz-date, Signature=0', 'x-amz-date': '20261021T120000Z', 'content-type': method === 'POST' ? 'application/x-amz-json-1.1' : 'application/x-www-form-urlencoded', 'x-amz-target': 'Probe.Probe' }, body: method === 'POST' ? '{}' : undefined });
      return { simple, sdk };
    }, { url, method });
    out.push(Object.assign({ name, url, method }, r));
    console.log(name.padEnd(28), 'simple:', r.simple.readable ? r.simple.status + ' acao=' + r.simple.acao : 'BLOCKED', '| sdk-shaped:', r.sdk.readable ? r.sdk.status + ' acao=' + r.sdk.acao : 'BLOCKED');
  }
  fs.writeFileSync(path.join(__dirname, 'cors-result.json'), JSON.stringify({ measuredAt: new Date().toISOString(), origin: 'http://localhost:8788', chromium: await browser.version(), results: out }, null, 2));
  await browser.close(); server.close();
})().catch(e => { console.error(e); process.exit(1); });
