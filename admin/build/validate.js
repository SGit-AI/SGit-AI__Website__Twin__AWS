#!/usr/bin/env node
/* aws.twin.sgit.ai — the site checks, run with `node admin/build/validate.js`.

   1. Every HTML page has a title, a description and a canonical link.
   2. Every relative href and src resolves to a file in the tree (fragments ignored).
   3. The nav block is identical on every page once the ../ prefix is removed.
   4. The version string on every page matches the latest row of admin/versions.html.
   5. The name-watch, the hub's check: no capitalised "<Word> Twin" outside the terms
      ruled on at twins.sgit.ai/naming. This site writes "the AWS twin" in lower case,
      so the allow-list is the hub's four terms and nothing else.
   6. No credential-shaped string anywhere in the tree (an AKIA/ASIA key id, a secret
      key assignment), because the design says they never go in a page or a repository.
   Exits non-zero on any failure. */
'use strict';
var fs = require('fs'), path = require('path');
var ROOT = path.join(__dirname, '../..');
var problems = [];
var fail = function (file, msg) { problems.push(file + ': ' + msg); };

/* the hub's permitted terms; adding one here means adding it to the hub's table first */
var ALLOW = ['Digital Twin', 'Agent Twin', 'Org Twin', 'Service Twin'];

function walk(dir, out) {
  fs.readdirSync(dir).forEach(function (name) {
    if (name === '.git' || name === 'node_modules' || name === '__pycache__' || name === '.pytest_cache') return;
    var p = path.join(dir, name);
    if (fs.statSync(p).isDirectory()) walk(p, out);
    else out.push(p);
  });
  return out;
}
var files = walk(ROOT, []);
/* articles/data/ holds experiment pages and data an article was written from: not site pages, so
   they skip the page checks, and still get the credential scan below */
var pages = files.filter(function (f) { return /\.html$/.test(f) && !/[\\/]articles[\\/]data[\\/]/.test(f) && !/[\\/]admin[\\/]content[\\/]/.test(f); });
var rel = function (f) { return path.relative(ROOT, f); };

/* 4. the version: admin/build/version.txt is the only place it is typed; the release history's newest row,
      every nav badge, assets/version.js and llms.txt must agree with it, and each release appears once */
var latest = fs.readFileSync(path.join(ROOT, 'admin/build/version.txt'), 'utf8').trim();
if (!/^v\d+\.\d+\.\d+$/.test(latest)) fail('admin/build/version.txt', 'not a vX.Y.Z version: ' + latest);
var versionsHtml = fs.readFileSync(path.join(ROOT, 'admin/versions.html'), 'utf8');
var rows = (versionsHtml.match(/<td class="vnum">v[\d.]+<\/td>/g) || []).map(function (r) { return r.replace(/<[^>]+>/g, ''); });
if (rows[0] !== latest) fail('admin/versions.html', 'the newest release row is ' + rows[0] + ', version.txt says ' + latest);
rows.forEach(function (v, i) { if (rows.indexOf(v) !== i) fail('admin/versions.html', v + ' is listed more than once'); });
var versionJs = fs.existsSync(path.join(ROOT, 'assets/version.js')) ? fs.readFileSync(path.join(ROOT, 'assets/version.js'), 'utf8') : '';
if (versionJs.indexOf('"' + latest + '"') < 0) fail('assets/version.js', 'does not carry ' + latest + ' (run admin/build/pages.py)');
if (fs.readFileSync(path.join(ROOT, 'llms.txt'), 'utf8').indexOf(latest) < 0) fail('llms.txt', 'does not mention ' + latest);

/* the canonical host, from CNAME */
var HOST = fs.existsSync(path.join(ROOT, 'CNAME')) ? fs.readFileSync(path.join(ROOT, 'CNAME'), 'utf8').trim() : '';
if (!/^[a-z0-9.-]+$/.test(HOST)) fail('CNAME', 'does not carry a hostname: "' + HOST + '"');
['robots.txt', 'sitemap.xml'].forEach(function (f) {
  var p = path.join(ROOT, f);
  if (!fs.existsSync(p)) fail(f, 'missing');
  else if (fs.readFileSync(p, 'utf8').indexOf('https://' + HOST + '/') < 0) fail(f, 'does not point at https://' + HOST + '/');
});
var linkedTo = {};

var navs = {};
pages.forEach(function (f) {
  var html = fs.readFileSync(f, 'utf8');
  var name = rel(f);
  var dir = path.dirname(f);

  /* 1. head */
  if (!/<title>[^<]+<\/title>/.test(html)) fail(name, 'no <title>');
  if (!/<meta name="description" content="[^"]+">/.test(html)) fail(name, 'no description');
  var canon = (/<link rel="canonical" href="([^"]+)">/.exec(html) || [])[1];
  if (!canon) fail(name, 'no canonical link');
  else if (canon !== 'https://' + HOST + '/' + name.replace(/\\/g, '/')) fail(name, 'canonical ' + canon + ' is not https://' + HOST + '/' + name);
  (html.match(/<meta property="og:url" content="([^"]+)">/g) || []).forEach(function (m) { if (m.indexOf('https://' + HOST + '/') < 0) fail(name, 'og:url not on ' + HOST); });

  /* the markdown twin */
  if (!fs.existsSync(f.replace(/\.html$/, '.md'))) fail(name, 'no markdown twin (' + name.replace(/\.html$/, '.md') + ')');

  /* 2. links */
  var re = /\b(?:href|src)="([^"#]+)(?:#[^"]*)?"/g, m;
  while ((m = re.exec(html))) {
    var target = m[1];
    if (/^(https?:|mailto:|javascript:|data:)/.test(target)) continue;
    var resolved = path.resolve(dir, target);
    if (!fs.existsSync(resolved)) fail(name, 'broken link ' + target);
    else if (resolved !== f) linkedTo[path.relative(ROOT, resolved)] = true;
  }

  /* 3. nav */
  var nav = (/<nav class="site">[\s\S]*?<\/nav>/.exec(html) || [''])[0];
  if (!nav) fail(name, 'no site nav');
  else {
    var prefix = name.indexOf('/') >= 0 ? '../' : '';
    var canon = nav.split('href="' + prefix).join('href="').split('src="' + prefix).join('src="');
    navs[name] = canon;
  }

  /* 4. version */
  if (latest) {
    var navVer = (/<a class="ver"[^>]*>(v[\d.]+)<\/a>/.exec(html) || [])[1];
    if (navVer !== latest) fail(name, 'nav version ' + navVer + ' is not the latest release ' + latest);
    /* only claims about this site's own version: 'site vX.Y.Z' outside the release history (other projects' versions are facts, not claims) */
    var siteVers = html.replace(/<[^>]+>/g, ' ').match(/\bsite v\d+\.\d+\.\d+\b/g) || [];
    if (!/versions\.html/.test(name) && !/^articles\//.test(name)) siteVers.forEach(function (v) { if (v.slice(5) !== latest) fail(name, 'stale site version: ' + v); });
  }

  /* 5. name-watch, on the page's text */
  var text = html.replace(/<script[\s\S]*?<\/script>/g, '').replace(/<[^>]+>/g, ' ');
  var nw = /\b([A-Z][A-Za-z0-9/-]*) Twin\b/g, w;
  while ((w = nw.exec(text))) {
    var term = w[1] + ' Twin';
    if (ALLOW.indexOf(term) < 0) fail(name, 'name-watch: "' + term + '" has not been ruled on; use lower case or add it to the hub\'s table and this allow-list');
  }
});

/* orphans: a page nothing links to was published and is unfindable */
pages.forEach(function (f) { var n = rel(f); if (n !== 'index.html' && !linkedTo[n]) fail(n, 'orphan: no page links to it'); });

/* licence stamp on every markdown file this site authors (vendored code keeps its own) */
files.filter(function (f) { return /\.md$/.test(f) && !/[\\/]assets[\\/]vendor[\\/]/.test(f); }).forEach(function (f) {
  var t = fs.readFileSync(f, 'utf8');
  if (!/CC BY 4\.0|creativecommons\.org\/licenses\/by\/4\.0/.test(t)) fail(rel(f), 'no CC BY 4.0 licence stamp');
});

/* 3. nav identical */
var navKeys = Object.keys(navs);
if (navKeys.length > 1) {
  var first = navs[navKeys[0]];
  navKeys.slice(1).forEach(function (k) { if (navs[k] !== first) fail(k, 'nav differs from ' + navKeys[0]); });
}

/* 6. no credential-shaped strings anywhere */
files.forEach(function (f) {
  if (/\.(png|jpg|jpeg|gif|ico|woff2?)$/i.test(f)) return;
  var s = fs.readFileSync(f, 'utf8');
  var name = rel(f);
  /* a real key id is AKIA/ASIA + 16 upper-case alphanumerics; the docs' "ASIA..." placeholders are shorter */
  if (/[A-Za-z0-9_-]{20,}:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/.test(s)) fail(name, 'looks like an sgit vault key');
  var k = /\b(AKIA|ASIA)[A-Z0-9]{16}\b/.exec(s);
  if (k) fail(name, 'looks like an AWS access key id: ' + k[0]);
  var sec = /aws_secret_access_key\s*=\s*[A-Za-z0-9/+]{40}\b/i.exec(s);
  if (sec) fail(name, 'looks like an AWS secret access key assignment');
});

/* the diagrams: every Mermaid source has its rendered SVG, stamped with the source's hash (node admin/build/diagrams.js) */
var DIAG = path.join(ROOT, 'admin/content/diagrams');
if (fs.existsSync(DIAG)) fs.readdirSync(DIAG).filter(function (f) { return /\.mmd$/.test(f); }).forEach(function (f) {
  var svg = path.join(ROOT, 'assets/diagrams', f.replace(/\.mmd$/, '.svg'));
  var want = require('crypto').createHash('sha256').update(fs.readFileSync(path.join(DIAG, f), 'utf8')).digest('hex').slice(0, 16);
  if (!fs.existsSync(svg)) fail('admin/content/diagrams/' + f, 'not rendered (node admin/build/diagrams.js)');
  else if (fs.readFileSync(svg, 'utf8').indexOf('data-source-sha256="' + want + '"') < 0) fail(rel(svg), 'stale: its source changed since it was rendered (node admin/build/diagrams.js)');
});

/* the scripts the twin page loads must parse in Node too (they are UMD on purpose) */
['assets/twin/interface.js', 'assets/twin/vault.js', 'assets/twin/templates.js'].forEach(function (p) {
  try { require(path.join(ROOT, p)); } catch (e) { fail(p, 'does not load in Node: ' + e.message); }
});

if (problems.length) {
  console.error('aws.twin validate: ' + problems.length + ' problem' + (problems.length === 1 ? '' : 's'));
  problems.forEach(function (p) { console.error('  ' + p); });
  process.exit(1);
}
console.log('aws.twin validate: ' + latest + ' on ' + HOST + ', ' + pages.length + ' pages with twins, nav identical, links resolve, no orphans, licence stamped, name-watch clean, no credential-shaped strings in ' + files.length + ' files');
