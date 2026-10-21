#!/usr/bin/env python3
"""HTML to markdown for the page twins: every hand-written page gets a .md beside it, made
from the same body the page is built from, so the two cannot drift. Handles the markup
this site writes (headings, paragraphs, lists, tables, pre, blockquotes, links, bold,
italic, code); scripts, styles, forms and buttons are dropped, because an app page's
twin describes the page and does not reproduce the app. Standard library only."""
import html
import re
from html.parser import HTMLParser

SKIP = {'script', 'style', 'noscript', 'svg', 'button', 'select', 'textarea', 'nav', 'form'}
BLOCK = {'p', 'div', 'section', 'main', 'header', 'figure', 'figcaption', 'details', 'summary', 'label', 'fieldset'}


class _Md(HTMLParser):
    def __init__(self, base_url):
        super().__init__(convert_charrefs=True)
        self.base, self.out, self.skip = base_url, [], 0
        self.lists, self.href, self.pre, self.table, self.row, self.cell = [], None, 0, None, None, None
        self.quote = 0
        self.heading = False

    def emit(self, s):
        if self.cell is not None:
            self.cell.append(s)
        else:
            self.out.append(s)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in SKIP:
            self.skip += 1
            return
        if self.skip:
            return
        if tag in ('h1', 'h2', 'h3', 'h4'):
            self.heading = True
            self.emit('\n\n' + '#' * int(tag[1]) + ' ')
        elif tag in BLOCK:
            self.emit('\n\n')
        elif tag == 'br':
            self.emit(' ' if self.heading else '  \n')                  # a heading is one line in markdown
        elif tag in ('ul', 'ol'):
            self.lists.append([tag, 0])
            self.emit('\n')
        elif tag == 'li':
            kind = self.lists[-1] if self.lists else ['ul', 0]
            kind[1] += 1
            self.emit('\n' + '  ' * (len(self.lists) - 1) + ('- ' if kind[0] == 'ul' else f'{kind[1]}. '))
        elif tag == 'pre':
            self.pre += 1
            self.emit('\n\n```' + ('mermaid' if 'mermaid-src' in (a.get('class') or '') else '') + '\n')
        elif tag == 'code' and not self.pre:
            self.emit('`')
        elif tag in ('b', 'strong'):
            self.emit('**')
        elif tag in ('i', 'em'):
            self.emit('*')
        elif tag == 'blockquote':
            self.quote += 1
            self.emit('\n\n> ')
        elif tag == 'a':
            href = a.get('href', '')
            if href and not href.startswith('#') and not href.startswith('javascript:'):
                self.href = href if re.match(r'^[a-z]+:', href) else href.replace('.html', '.md') if href.endswith('.html') or '.html#' in href else href
                self.emit('[')
        elif tag == 'table':
            self.table = []
        elif tag == 'tr':
            self.row = []
        elif tag in ('td', 'th'):
            self.cell = []
        elif tag == 'img':
            self.emit(f"![{a.get('alt', '')}]({a.get('src', '')})")

    def handle_endtag(self, tag):
        if tag in SKIP:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip:
            return
        if tag in ('h1', 'h2', 'h3', 'h4'):
            self.heading = False
            self.emit('\n')
        elif tag in BLOCK:
            self.emit('\n')
        elif tag in ('ul', 'ol'):
            if self.lists:
                self.lists.pop()
            self.emit('\n')
        elif tag == 'pre':
            self.pre = max(0, self.pre - 1)
            self.emit('\n```\n')
        elif tag == 'code' and not self.pre:
            self.emit('`')
        elif tag in ('b', 'strong'):
            self.emit('**')
        elif tag in ('i', 'em'):
            self.emit('*')
        elif tag == 'blockquote':
            self.quote = max(0, self.quote - 1)
            self.emit('\n')
        elif tag == 'a' and self.href is not None:
            self.emit(f']({self.href})')
            self.href = None
        elif tag in ('td', 'th') and self.cell is not None:
            text = re.sub(r'\s+', ' ', ''.join(self.cell)).strip().replace('|', '\\|')
            self.cell = None
            if self.row is not None:
                self.row.append((tag, text))
        elif tag == 'tr' and self.row is not None:
            if self.table is not None:
                self.table.append(self.row)
            self.row = None
        elif tag == 'table' and self.table is not None:
            rows, self.table = self.table, None
            if rows:
                width = max(len(r) for r in rows)
                lines = []
                for i, r in enumerate(rows):
                    cells = [c for _, c in r] + [''] * (width - len(r))
                    lines.append('| ' + ' | '.join(cells) + ' |')
                    if i == 0:
                        lines.append('|' + '---|' * width)
                self.emit('\n\n' + '\n'.join(lines) + '\n\n')

    def handle_data(self, data):
        if self.skip:
            return
        if self.pre:
            self.emit(data)
        else:
            self.emit(re.sub(r'\s+', ' ', data))


def to_markdown(body_html, title, url, version):
    p = _Md(url)
    p.feed(body_html)
    text = ''.join(p.out)
    text = re.sub(r'[ \t]+\n', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    head = (f'<!-- the markdown twin of {url}, generated from the same source by admin/build/pages.py; '
            f'site {version}; content CC BY 4.0 -->\n\n')
    return head + text + f'\n\n---\n\n*[This page as HTML]({url}) · [The site for agents](https://aws.twin.sgit.ai/llms.txt) · CC BY 4.0*\n'
