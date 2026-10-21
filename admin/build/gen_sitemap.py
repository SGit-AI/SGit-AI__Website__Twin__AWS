#!/usr/bin/env python3
"""sitemap.xml from the tree: every .html page under the site, skipping experiment data and page sources.
Run after pages.py and articles.py. Deterministic: lastmod is the release date in version history."""
import os
import re

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..'))
HOST = open(os.path.join(ROOT, 'CNAME')).read().strip()
SKIP = ('.git', '.github', 'node_modules', 'admin/content', 'articles/data', 'assets')

pages = []
for folder, dirs, files in os.walk(ROOT):
    rel = os.path.relpath(folder, ROOT).replace(os.sep, '/')
    dirs[:] = sorted(d for d in dirs if not any((rel + '/' + d).lstrip('./').startswith(s) for s in SKIP) and d not in SKIP)
    for f in sorted(files):
        if f.endswith('.html'):
            pages.append((rel + '/' + f).lstrip('./') if rel != '.' else f)
versions = open(os.path.join(ROOT, 'admin', 'versions.html'), encoding='utf-8').read()
date = (re.search(r'class="vnum">v[\d.]+</td><td>(\d{4}-\d\d-\d\d)<', versions) or [None, '2026-10-21'])[1]
xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
xml += [f'  <url><loc>https://{HOST}/{p}</loc><lastmod>{date}</lastmod></url>' for p in sorted(pages)]
xml.append('</urlset>')
with open(os.path.join(ROOT, 'sitemap.xml'), 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(xml) + '\n')
print(f'sitemap.xml: {len(pages)} pages on {HOST}')
