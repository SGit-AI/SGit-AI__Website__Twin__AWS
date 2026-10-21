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
    if (name === '.git' || name === 'node_modules' || name === '__pycache__') return;
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

/* 4. the latest version */
var versionsHtml = fs.readFileSync(path.join(ROOT, 'admin/versions.html'), 'utf8');
var latest = (/<td class="vnum">(v[\d.]+)<\/td>/.exec(versionsHtml) || [])[1];
if (!latest) fail('admin/versions.html', 'no version row found');

var navs = {};
pages.forEach(function (f) {
  var html = fs.readFileSync(f, 'utf8');
  var name = rel(f);
  var dir = path.dirname(f);

  /* 1. head */
  if (!/<title>[^<]+<\/title>/.test(html)) fail(name, 'no <title>');
  if (!/<meta name="description" content="[^"]+">/.test(html)) fail(name, 'no description');
  if (!/<link rel="canonical" href="https:\/\/aws\.twin\.sgit\.ai\/[^"]+">/.test(html)) fail(name, 'no canonical link');

  /* 2. links */
  var re = /\b(?:href|src)="([^"#]+)(?:#[^"]*)?"/g, m;
  while ((m = re.exec(html))) {
    var target = m[1];
    if (/^(https?:|mailto:|javascript:|data:)/.test(target)) continue;
    var resolved = path.resolve(dir, target);
    if (!fs.existsSync(resolved)) fail(name, 'broken link ' + target);
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
  var k = /\b(AKIA|ASIA)[A-Z0-9]{16}\b/.exec(s);
  if (k) fail(name, 'looks like an AWS access key id: ' + k[0]);
  var sec = /aws_secret_access_key\s*=\s*[A-Za-z0-9/+]{40}\b/i.exec(s);
  if (sec) fail(name, 'looks like an AWS secret access key assignment');
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
console.log('aws.twin validate: ' + pages.length + ' pages, nav identical, version ' + latest + ', links resolve, name-watch clean, no credential-shaped strings in ' + files.length + ' files');
