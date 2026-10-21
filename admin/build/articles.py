#!/usr/bin/env python3
"""aws.twin.sgit.ai: build the articles section.

Reads admin/content/articles/<slug>.md (the newsroom's format: front matter, a lead
figure as a !shot line, In short, sections with anchors, What this does not claim, Where
this comes from) and writes articles/<slug>.html, articles/<slug>.md (the markdown twin,
the source verbatim), articles/index.html and articles/articles.json.

The nav and the footer are not kept here: they are read from index.html, the hand-written
front page, and re-rooted with ../, so the site has one nav and validate.js keeps it that
way. The gate at the end fails the build on the rules that were each a correction once:
no em-dash, no model name in an article, required front matter present, slug stable.

Run: python3 admin/build/articles.py          (exits non-zero on a gate failure)
"""
import glob
import html
import json
import os
import re
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = os.path.join(ROOT, 'admin', 'content', 'articles')
OUT = os.path.join(ROOT, 'articles')
SITE = 'https://aws.twin.sgit.ai'
REQUIRED = ['title', 'date', 'author', 'author_url', 'summary', 'version', 'license', 'tags', 'status']
MODEL_NAMES = re.compile(r'\b(Claude|Opus|Sonnet|Haiku|Fable|GPT-?\d|Gemini|Llama)\b')
problems = []


def fail(where, msg):
    problems.append(f'{where}: {msg}')


# ---------------------------------------------------------------- front matter
def parse_front_matter(text, where):
    if not text.startswith('---\n'):
        fail(where, 'no front matter')
        return {}, text
    end = text.find('\n---\n', 4)
    if end < 0:
        fail(where, 'front matter not closed')
        return {}, text
    block, body = text[4:end], text[end + 5:]
    fm = {}
    lines = block.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r'^([a-z_]+):\s*(.*)$', line)
        if not m:
            i += 1
            continue
        key, val = m.group(1), m.group(2).strip()
        if val in ('|', '>'):
            buf = []
            i += 1
            while i < len(lines) and (lines[i].startswith('  ') or lines[i] == ''):
                buf.append(lines[i][2:])
                i += 1
            fm[key] = ('\n'.join(buf) if val == '|' else ' '.join(x.strip() for x in buf if x.strip())).strip()
            continue
        val = re.sub(r'\s+#.*$', '', val)  # trailing comment
        if val.startswith('[') and val.endswith(']'):
            fm[key] = [x.strip().strip('"\'') for x in val[1:-1].split(',') if x.strip()]
        else:
            fm[key] = val.strip('"\'')
        i += 1
    return fm, body


# ---------------------------------------------------------------- markdown (the subset the format uses)
def esc(s):
    return html.escape(s, quote=True)


def inline(s):
    s = esc(s)
    s = re.sub(r'`([^`]+)`', r'<code>\1</code>', s)
    s = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', s)
    s = re.sub(r'(?<![\w*])\*([^*\n]+?)\*(?![\w*])', r'<i>\1</i>', s)
    s = re.sub(r'\[([^\]]+)\]\(([^)\s]+)\)', lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', s)
    return s


def md_to_html(body, where):
    out = []
    lines = body.split('\n')
    i = 0
    para = []

    def flush():
        if para:
            out.append('<p>' + inline(' '.join(x.strip() for x in para)) + '</p>')
            para.clear()

    while i < len(lines):
        line = lines[i]
        if not line.strip():
            flush(); i += 1; continue
        if line.startswith('!shot '):
            flush()
            parts = [p.strip() for p in line[6:].split('|')]
            if len(parts) < 3:
                fail(where, f'bad !shot line: {line}')
                i += 1; continue
            name, _folder, caption = parts[0], parts[1], parts[2]
            kind = parts[3] if len(parts) > 3 else 'diagram'
            if not os.path.exists(os.path.join(OUT, 'images', name)):
                fail(where, f'figure missing: articles/images/{name}')
            out.append(f'<figure class="shot {esc(kind)}"><img src="images/{esc(name)}" alt="{esc(caption)}" loading="lazy"><figcaption>{inline(caption)}</figcaption></figure>')
            i += 1; continue
        m = re.match(r'^(#{2,3}) (.+?)(?: \{#([a-z0-9-]+)\})?$', line)
        if m:
            flush()
            level, text, anchor = len(m.group(1)), m.group(2), m.group(3)
            anchor = anchor or re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')[:60]
            out.append(f'<h{level} id="{anchor}">{inline(text)}</h{level}>')
            i += 1; continue
        if line.startswith('```'):
            flush()
            buf = []
            i += 1
            while i < len(lines) and not lines[i].startswith('```'):
                buf.append(lines[i]); i += 1
            out.append('<pre class="shell">' + esc('\n'.join(buf)) + '</pre>')
            i += 1; continue
        if line.startswith('> '):
            flush()
            buf = []
            while i < len(lines) and lines[i].startswith('> '):
                buf.append(lines[i][2:]); i += 1
            out.append('<blockquote class="challenge">' + inline(' '.join(buf)) + '</blockquote>')
            continue
        if line.startswith('|'):
            flush()
            rows = []
            while i < len(lines) and lines[i].startswith('|'):
                rows.append([c.strip() for c in lines[i].strip().strip('|').split('|')]); i += 1
            if len(rows) >= 2 and all(re.match(r'^:?-+:?$', c) for c in rows[1]):
                head, data = rows[0], rows[2:]
            else:
                head, data = None, rows
            t = '<div class="tablewrap"><table>'
            if head:
                t += '<thead><tr>' + ''.join(f'<th>{inline(c)}</th>' for c in head) + '</tr></thead>'
            t += '<tbody>' + ''.join('<tr>' + ''.join(f'<td>{inline(c)}</td>' for c in r) + '</tr>' for r in data) + '</tbody></table></div>'
            out.append(t)
            continue
        if re.match(r'^(- |\d+\. )', line):
            flush()
            ordered = bool(re.match(r'^\d+\. ', line))
            items = []
            while i < len(lines) and re.match(r'^(- |\d+\. )', lines[i]):
                item = re.sub(r'^(- |\d+\. )', '', lines[i])
                i += 1
                while i < len(lines) and lines[i].startswith('  ') and lines[i].strip():
                    item += ' ' + lines[i].strip(); i += 1
                items.append(f'<li>{inline(item)}</li>')
            tag = 'ol' if ordered else 'ul'
            out.append(f'<{tag}>' + ''.join(items) + f'</{tag}>')
            continue
        para.append(line)
        i += 1
    flush()
    return '\n'.join(out)


# ---------------------------------------------------------------- the site's nav and footer, re-rooted
def chrome():
    index = open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
    nav = re.search(r'<nav class="site">[\s\S]*?</nav>', index).group(0)
    foot = re.search(r'<footer class="site">[\s\S]*?</footer>', index).group(0)
    reroot = lambda s: re.sub(r'\b(href|src)="(?!https?:|#|mailto:|\.\./)([^"]+)"', r'\1="../\2"', s)
    ver = re.search(r'<a class="ver"[^>]*>(v[\d.]+)</a>', nav).group(1)
    return reroot(nav), reroot(foot), ver


def page(title, desc, path, body, nav, foot, twin=True):
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{SITE}/{path}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="aws.twin.sgit.ai">
<meta property="og:url" content="{SITE}/{path}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta name="twitter:card" content="summary">
{('<link rel="alternate" type="text/markdown" href="' + os.path.basename(path).replace('.html', '.md') + '" title="This page as markdown">') if twin else ''}
<link rel="stylesheet" href="../assets/site.css">
</head>
<body>

{nav}

{body}

{foot}

</body>
</html>
'''


# ---------------------------------------------------------------- build
def build():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(os.path.join(OUT, 'images'), exist_ok=True)
    nav, foot, site_ver = chrome()
    articles = []
    for src in sorted(glob.glob(os.path.join(SRC, '*.md'))):
        slug = os.path.basename(src)[:-3]
        where = f'admin/content/articles/{slug}.md'
        text = open(src, encoding='utf-8').read()
        if '—' in text:
            fail(where, 'contains an em-dash')
        fm, body = parse_front_matter(text, where)
        for k in REQUIRED:
            if k not in fm:
                fail(where, f'front matter missing {k}')
        if MODEL_NAMES.search(body) or MODEL_NAMES.search(fm.get('summary', '')):
            fail(where, 'names a model; the agent page carries the model, the article does not')
        for anchor in ('{#in-short}', '{#limits}', '{#sources}'):
            if anchor not in body:
                fail(where, f'missing the {anchor} section')
        if not re.search(r'^!shot ', body, re.M):
            fail(where, 'no lead figure (!shot line)')
        if fm.get('status') != 'published':
            continue
        articles.append({'slug': slug, 'fm': fm, 'body': body, 'text': text})

    articles.sort(key=lambda a: (a['fm'].get('date', ''), a['fm'].get('time', '')), reverse=True)
    for n, a in enumerate(articles):
        fm, slug = a['fm'], a['slug']
        kind = 'in his own voice, through an agent' if fm['author'] == 'Dinis Cruz' else 'an agent, in its own voice'
        body_html = md_to_html(a['body'], f'admin/content/articles/{slug}.md')
        newer = articles[n - 1] if n > 0 else None
        older = articles[n + 1] if n + 1 < len(articles) else None
        pagenav = '<div class="pagenav">' + (f'<a href="{older["slug"]}.html">← {esc(older["fm"]["title"])}</a>' if older else '<span></span>') + (f'<a href="{newer["slug"]}.html">{esc(newer["fm"]["title"])} →</a>' if newer else '<a href="index.html">All articles →</a>') + '</div>'
        main = f'''<main class="doc article">
<div class="crumb"><a href="../index.html">aws.twin.sgit.ai</a> / <a href="index.html">Articles</a> / {esc(fm['title'])}</div>
<h1>{esc(fm['title'])}</h1>
<p class="byline">By <a href="{esc(fm['author_url'])}">{esc(fm['author'])}</a> · {esc(fm['date'])} · {esc(fm['status'])} · site {esc(fm['version'])} · <span class="kind">{kind}</span></p>
<p class="lead"><b>Summary:</b> {inline(fm['summary'])}</p>
<p class="chips">{' '.join(f'<span class="chip">{esc(t)}</span>' for t in fm.get('tags', []))}</p>
{body_html}
{pagenav}
<p class="small dim" style="margin-top:2rem">This page as <a href="{slug}.md">markdown</a> · its source, <a href="https://github.com/SGit-AI/SGit-AI__Website__Twin__AWS/blob/main/admin/content/articles/{slug}.md"><code>admin/content/articles/{slug}.md</code></a> · licence <a href="{esc(fm['license'])}">CC BY 4.0</a></p>
</main>'''
        desc = re.sub(r'\s+', ' ', fm['summary'])[:300].rsplit(' ', 1)[0] + '…'
        with open(os.path.join(OUT, slug + '.html'), 'w', encoding='utf-8') as f:
            f.write(page(fm['title'] + ' · aws.twin.sgit.ai', desc, f'articles/{slug}.html', main, nav, foot))
        with open(os.path.join(OUT, slug + '.md'), 'w', encoding='utf-8') as f:
            f.write(a['text'])

    cards = ''.join(f'''<a class="card acard" href="{a['slug']}.html"><span class="tag">article · {esc(a['fm']['author'])}</span><h3>{esc(a['fm']['title'])}</h3><p>{esc(re.sub(r'\s+', ' ', a['fm']['summary'])[:260].rsplit(' ', 1)[0])}…</p><span class="go">{esc(a['fm']['date'])} · read →</span></a>''' for a in articles)
    index_main = f'''<main class="doc">
<div class="crumb"><a href="../index.html">aws.twin.sgit.ai</a> / Articles</div>
<h1>Articles</h1>
<p class="lead">Each article makes one argument about the AWS twin, in the format <a href="https://newsroom.sgit.ai">the newsroom</a> uses, so any of them can be imported there unchanged: a summary a reader can stop at, a lead figure, In short, the argument, what it does not claim, and where it comes from. The format is the one send.sgit.ai's <a href="https://send.sgit.ai/articles/every-site-its-own-articles.html">Every site its own articles</a> sets out for every site in the network.</p>
<p>There are two kinds of author, and the byline says which:</p>
<ul>
<li><b>Dinis Cruz, through an agent</b>: a voice memo or a message of his, written up in his voice, under his name. The editorial responsibility is his.</li>
<li><b>An agent in its own voice</b>: aws-twin.build, this site's build agent, writing about what it delivered, with the commits and the tests to check it against. <a href="../about/team.html">The team</a> says who each is.</li>
</ul>
<p>Data an article was written from is kept beside it under <a href="data/">articles/data/</a>, and the index is machine-readable at <a href="articles.json">articles.json</a>.</p>
<div class="cards" style="padding:0;margin:1.4rem 0">{cards}</div>
</main>'''
    with open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(page('Articles · aws.twin.sgit.ai', 'The articles on aws.twin.sgit.ai: what was asked and what was built, in two voices, in the newsroom\'s format.', 'articles/index.html', index_main, nav, foot))
    with open(os.path.join(OUT, 'index.md'), 'w', encoding='utf-8') as f:          # the index's markdown twin
        f.write(f'<!-- the markdown twin of {SITE}/articles/index.html; site {site_ver}; content CC BY 4.0 -->\n\n# Articles\n\n'
                'Each article makes one argument about the AWS twin, in the newsroom\'s format. Two kinds of author: '
                'Dinis Cruz through an agent, and aws-twin.build, the build agent, in its own voice.\n\n'
                + ''.join(f"- [{a['fm']['title']}]({a['slug']}.md) · {a['fm']['author']} · {a['fm']['date']}\n" for a in articles)
                + '\n*CC BY 4.0*\n')
    with open(os.path.join(OUT, 'articles.json'), 'w', encoding='utf-8') as f:
        json.dump([{'slug': a['slug'], 'url': f'{SITE}/articles/{a["slug"]}.html', 'markdown': f'{SITE}/articles/{a["slug"]}.md', **{k: a['fm'][k] for k in ('title', 'date', 'author', 'author_url', 'summary', 'version', 'tags', 'status')}} for a in articles], f, indent=2, ensure_ascii=False)
        f.write('\n')

    if problems:
        print(f'articles: {len(problems)} problem(s)', file=sys.stderr)
        for p in problems:
            print('  ' + p, file=sys.stderr)
        sys.exit(1)
    print(f'articles: {len(articles)} built, site {site_ver}, gate clean')


if __name__ == '__main__':
    build()
