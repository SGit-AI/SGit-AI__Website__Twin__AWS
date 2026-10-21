#!/usr/bin/env node
/* Render admin/content/diagrams/<name>.mmd to assets/diagrams/<name>.svg, once, at build time, so the
   pages show plain SVG and load no diagram script. Mermaid runs in headless Chromium (Playwright), from
   cdn.jsdelivr.net at a pinned version; labels are SVG text, not HTML, so the files render as <img>.
   Run after editing a diagram: node admin/build/diagrams.js [name ...]. validate.js checks that every
   source has its SVG, and the source's hash is stamped into the SVG, so a stale one fails the gate.

   Env: CHROMIUM_PATH (default: Playwright's own), HTTPS_PROXY (used if set). */
'use strict';
const fs = require('fs'), path = require('path'), crypto = require('crypto');
const { chromium } = require('playwright');
const ROOT = path.join(__dirname, '../..');
const SRC = path.join(ROOT, 'admin/content/diagrams'), OUT = path.join(ROOT, 'assets/diagrams');
const MERMAID = 'https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js';
const CONFIG = {
  startOnLoad: false, theme: 'base', securityLevel: 'strict', htmlLabels: false,
  flowchart: { htmlLabels: false, curve: 'basis', padding: 12 },
  sequence: { mirrorActors: false, useMaxWidth: true, wrap: false },
  themeVariables: {
    fontFamily: 'system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif', fontSize: '15px',
    primaryColor: '#ffffff', primaryBorderColor: '#0f766e', primaryTextColor: '#1c1d21',
    lineColor: '#5c5f66', secondaryColor: '#f2f0e9', tertiaryColor: '#faf9f5',
    clusterBkg: '#f2f0e9', clusterBorder: '#d5d0c2', edgeLabelBackground: '#faf9f5',
    actorBkg: '#ffffff', actorBorder: '#0f766e', signalColor: '#1c1d21', signalTextColor: '#1c1d21',
    noteBkgColor: '#fef3c7', noteBorderColor: '#b45309', labelBoxBkgColor: '#f2f0e9', altSectionBkgColor: '#f2f0e9'
  }
};
const hash = (s) => crypto.createHash('sha256').update(s).digest('hex').slice(0, 16);

(async () => {
  const only = process.argv.slice(2);
  const names = fs.readdirSync(SRC).filter((f) => f.endsWith('.mmd')).map((f) => f.slice(0, -4)).filter((n) => !only.length || only.includes(n));
  const launch = {};
  if (process.env.CHROMIUM_PATH) launch.executablePath = process.env.CHROMIUM_PATH;
  if (process.env.HTTPS_PROXY) launch.proxy = { server: process.env.HTTPS_PROXY };
  const browser = await chromium.launch(launch);
  const page = await (await browser.newContext({ ignoreHTTPSErrors: !!process.env.HTTPS_PROXY })).newPage();
  await page.setContent('<!doctype html><html><body></body></html>');
  await page.addScriptTag({ url: MERMAID });
  await page.evaluate((c) => window.mermaid.initialize(c), CONFIG);
  fs.mkdirSync(OUT, { recursive: true });
  for (const n of names) {
    const src = fs.readFileSync(path.join(SRC, n + '.mmd'), 'utf8');
    let svg = await page.evaluate(async ([id, s]) => (await window.mermaid.render(id, s)).svg, ['d-' + n, src]);
    svg = svg.replace('<svg ', '<svg data-source="admin/content/diagrams/' + n + '.mmd" data-source-sha256="' + hash(src) + '" ');
    fs.writeFileSync(path.join(OUT, n + '.svg'), '<?xml version="1.0" encoding="UTF-8"?>\n' + svg + '\n');
    console.log('wrote assets/diagrams/' + n + '.svg', svg.length, 'bytes');
  }
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
