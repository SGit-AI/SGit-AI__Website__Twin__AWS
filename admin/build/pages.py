#!/usr/bin/env python3
"""aws.twin.sgit.ai: the page assembler. Writes every hand-written page with one nav and one
footer, so they are byte-identical (modulo the ../ prefix) everywhere; validate.js checks
that. Page bodies too long to keep inline live in admin/content/pages/<name>.html.

Run: python3 admin/build/pages.py   (then python3 admin/build/articles.py, which reads the
nav from index.html)"""
import html, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
from md_twin import to_markdown

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..'))
PAGES = os.path.join(ROOT, 'admin', 'content', 'pages')

def diagram(name, caption, p='../'):
    """A diagram: the SVG rendered at build time by diagrams.js, and its Mermaid source under it."""
    with open(os.path.join(ROOT, 'admin', 'content', 'diagrams', name + '.mmd'), encoding='utf-8') as f:
        src = html.escape(f.read().rstrip())
    alt = html.escape(re.sub(r'<[^>]+>', '', caption), quote=True)
    return (f'<figure class="diagram" id="fig-{name}"><img src="{p}assets/diagrams/{name}.svg" alt="{alt}" loading="lazy">'
            f'<figcaption>{caption}</figcaption>'
            f'<details><summary>The diagram\'s source (Mermaid)</summary><pre class="mermaid-src">{src}</pre></details></figure>')

def body_of(name):
    """A page body from admin/content/pages/; {{diagram NAME | caption}} becomes the figure."""
    with open(os.path.join(PAGES, name), encoding='utf-8') as f:
        return re.sub(r'\{\{diagram (\S+) \| (.*?)\}\}', lambda m: diagram(m.group(1), m.group(2)), f.read())
with open(os.path.join(ROOT, 'admin', 'build', 'version.txt')) as _f:
    VER = _f.read().strip()                         # the one place the version lives; CI tags from it
DATE = '2026-10-21'

def nav(p):
    return f'''<nav class="site"><div class="row">
  <a class="brand" href="{p}index.html">aws.twin<span>.sgit.ai</span></a>
  <a class="parent" href="https://twins.sgit.ai" title="twins.sgit.ai — the hub: the twin primitive, and the catalogue of twins in place">↗ part of <b>twins.sgit.ai</b></a>
  <span class="stage-pill">proof of concept</span>
  <a class="ver" href="{p}admin/versions.html" title="Site release history">{VER}</a>
  <button class="nav-toggle" type="button" aria-expanded="false" aria-label="Menu">Menu</button>
  <div class="nav-items">
    <div class="ni ni-has">
      <a class="nl" href="{p}console/index.html">Console<span class="caret">&#9662;</span></a>
      <div class="sub">
      <a class="sl" href="{p}console/index.html">Overview</a>
      <a class="sl" href="{p}console/s3.html">S3</a>
      <a class="sl" href="{p}console/lambda.html">Lambda</a>
      <a class="sl" href="{p}console/resources.html">All resources</a>
      <a class="sl" href="{p}console/calls.html">Calls: what works where</a>
      <a class="sl" href="{p}console/twin.html">Twin data</a>
      <a class="sl" href="{p}console/plan.html">The plan, and the vault</a>
      </div>
    </div>
    <div class="ni ni-has">
      <a class="nl" href="{p}python/index.html">The twin<span class="caret">&#9662;</span></a>
      <div class="sub">
      <a class="sl" href="{p}sessions/index.html">AWS sessions</a>
      <a class="sl" href="{p}iam/index.html">Least privilege (IAM)</a>
      <a class="sl" href="{p}how-it-works/index.html">How it works: live, step by step</a>
      <a class="sl" href="{p}uptime/index.html">Uptime checks in every region</a>
      <a class="sl" href="{p}python/index.html">The Python twin</a>
      <a class="sl" href="{p}python/tests.html">Run the tests here</a>
      <a class="sl" href="{p}twin/index.html">The JavaScript proof of concept</a>
      <a class="sl" href="{p}design/index.html">The design</a>
      <a class="sl" href="{p}workflow/index.html">The workflow</a>
      </div>
    </div>
    <div class="ni ni-has">
      <a class="nl" href="{p}naming/index.html">Naming<span class="caret">&#9662;</span></a>
      <div class="sub">
      <a class="sl" href="{p}naming/index.html">Why aws.twin</a>
      <a class="sl" href="{p}naming/index.html#convention">The convention</a>
      <a class="sl" href="https://twins.sgit.ai/naming/index.html">The ruling, on the hub ↗</a>
      </div>
    </div>
    <div class="ni ni-has">
      <a class="nl" href="{p}shipped/index.html">Status<span class="caret">&#9662;</span></a>
      <div class="sub">
      <a class="sl" href="{p}shipped/index.html">Built, and designed</a>
      <a class="sl" href="{p}shipped/index.html#next">What is next</a>
      <a class="sl" href="{p}shipped/index.html#claims">What this does not claim</a>
      </div>
    </div>
    <div class="ni ni-has">
      <a class="nl" href="{p}articles/index.html">Articles<span class="caret">&#9662;</span></a>
      <div class="sub">
      <a class="sl" href="{p}articles/index.html">All articles</a>
      <a class="sl" href="{p}articles/a-live-aws-session-from-a-browser-tab.html">A live AWS session from a browser tab</a>
      <a class="sl" href="{p}articles/the-twin-is-python-now.html">The twin is Python now</a>
      <a class="sl" href="{p}articles/boto3-in-the-browser.html">boto3 in the browser</a>
      <a class="sl" href="{p}articles/first-go-at-the-aws-twin.html">A first go at the AWS twin</a>
      <a class="sl" href="{p}about/team.html">The team</a>
      </div>
    </div>
    <div class="ni ni-has">
      <a class="nl" href="{p}admin/index.html">Site<span class="caret">&#9662;</span></a>
      <div class="sub">
      <a class="sl" href="{p}admin/index.html">Admin &amp; engineering</a>
      <a class="sl" href="{p}admin/versions.html">Release history</a>
      <a class="sl" href="{p}briefs/index.html">The briefs</a>
      <a class="sl" href="{p}REALITY.md">Reality: what exists</a>
      <a class="sl" href="{p}BRIEF-CORRECTIONS.md">Corrections</a>
      <a class="sl" href="{p}admin/index.html#requests">Requests to other sites</a>
      <a class="sl" href="{p}llms.txt">llms.txt</a>
      </div>
    </div>
  </div>
  <a class="gh" href="https://github.com/SGit-AI/SGit-AI__Website__Twin__AWS">★ GitHub</a>
  <script src="{p}assets/nav.js" defer></script>
</div></nav>'''

def footer(p):
    return f'''<footer class="site"><div class="cols">
  <div>
    <div class="brandline">aws.twin<span>.sgit.ai</span></div>
    <p>The AWS twin: an AWS-shaped interface (S3, Lambda, EC2, IAM, billing, logs) whose backend is a vault, with a live session as one backend among several. One instance in the twins family; the primitive is defined on <a href="https://twins.sgit.ai" style="display:inline;padding:0"><b>twins.sgit.ai</b></a>. All content CC BY 4.0; the code is Apache-2.0.</p>
    <p class="netline"><a href="https://twins.sgit.ai"><b>↗ twins.sgit.ai</b></a> — the hub · <a href="https://sgit.ai">↗ sgit.ai</a> — the parent project · <a href="https://sg-compute.sgit.ai">↗ sg-compute.sgit.ai</a> — ships the S3 twin · <a href="https://newsroom.sgit.ai/articles/aws-from-the-vault.html">↗ the article</a> · <a href="https://sgit.ai/network/index.html">↗ the network</a></p>
    <p class="partnote">⚠ Participant disclosure: published by the sgit project, which builds the vault this twin stores into and the server components its first job deploys. Not affiliated with, endorsed by, or sponsored by Amazon Web Services; AWS service names identify the interfaces this twin mirrors.</p>
    <p class="verline">site <a href="{p}admin/versions.html">{VER}</a> · <a href="{p}admin/index.html">engineering</a> · no analytics, no cookies; third-party code only where a page says so: Python (Pyodide, and wheels from PyPI) on the twin's pages, and the AWS SDK for JavaScript on the calls page when you measure it</p>
  </div>
  <div>
    <h4>The twin</h4>
    <a href="{p}console/index.html">The console</a>
    <a href="{p}sessions/index.html">AWS sessions</a>
    <a href="{p}iam/index.html">Least privilege (IAM)</a>
    <a href="{p}how-it-works/index.html">How it works</a>
    <a href="{p}uptime/index.html">Uptime checks</a>
    <a href="{p}python/index.html">The Python twin</a>
    <a href="{p}twin/index.html">JavaScript proof of concept</a>
    <a href="{p}design/index.html">The design</a>
    <a href="{p}workflow/index.html">The workflow</a>
  </div>
  <div>
    <h4>Naming</h4>
    <a href="{p}naming/index.html">Why aws.twin</a>
    <a href="{p}naming/index.html#convention">The convention</a>
    <a href="https://twins.sgit.ai/naming/index.html">The ruling ↗</a>
  </div>
  <div>
    <h4>Status</h4>
    <a href="{p}shipped/index.html">Built, and designed</a>
    <a href="{p}shipped/index.html#next">What is next</a>
    <a href="{p}shipped/index.html#claims">What this does not claim</a>
  </div>
  <div>
    <h4>Site</h4>
    <a href="{p}articles/index.html">Articles</a>
    <a href="{p}about/team.html">The team</a>
    <a href="{p}admin/index.html">Admin &amp; engineering</a>
    <a href="{p}admin/versions.html">Release history</a>
    <a href="{p}briefs/index.html">The briefs</a>
    <a href="{p}REALITY.md">Reality</a>
    <a href="{p}llms.txt">llms.txt</a>
  </div>
</div></footer>'''

def page(path, title, desc, body, extra_head='', body_class=''):
    p = '../' if '/' in path else ''
    canon = 'https://aws.twin.sgit.ai/' + path
    html = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{canon}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="aws.twin.sgit.ai">
<meta property="og:url" content="{canon}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta name="twitter:card" content="summary">
<link rel="alternate" type="text/markdown" href="{os.path.basename(path)[:-5]}.md" title="This page as markdown">
<link rel="stylesheet" href="{p}assets/site.css">
{extra_head}</head>
<body{(' class=' + chr(34) + body_class + chr(34)) if body_class else ''}>

{nav(p)}

{body}

{footer(p)}

</body>
</html>
'''
    full = os.path.join(ROOT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, 'w', encoding='utf-8') as f:
        f.write(html)
    with open(full[:-5] + '.md', 'w', encoding='utf-8') as f:     # the markdown twin, from the same body
        f.write(to_markdown(body, title, canon, VER))
    print('wrote', path)

# ---------------------------------------------------------------- index.html
page('index.html',
  'aws.twin.sgit.ai — the AWS twin: an AWS-shaped interface with a vault behind it, and a live session as one backend among several',
  'The AWS twin: S3, Lambda, EC2, IAM, billing and logs as one interface, with a vault as the backend, so everything built against the twin works against the live account once a temporary IAM Identity Center session is put in front of it. A proof of concept in the browser, with localStorage as the vault.',
  f'''<header class="hero">
  <div class="eyebrow">The AWS twin · one instance of the twin primitive · proposed and prototyped {DATE}</div>
  <h1>AWS from the vault,<br>twin first</h1>
  <p class="sub">An AWS-shaped interface, S3, Lambda, EC2, IAM, billing and logs, whose backend is a vault. Build everything against the twin, with no credentials. Then put a temporary session from the AWS access portal in front of the <b>same interface</b> as a second backend, and what you built works against the live account. <b>This site holds the proof of concept</b>: the interface, a vault backend on this browser's localStorage, snapshots as commits, an account graph, and a deployment rehearsal. Since v0.4.0 the Python twin's live route reaches a real account from the browser: a pasted session checked against AWS STS, and <a href="console/index.html">the console</a>, live, directly or through a <a href="how-it-works/index.html#relay">local relay</a>. <a href="how-it-works/index.html">How it works</a>.</p>
  <div class="ctas">
    <a class="cta1" href="console/index.html">Open the console →</a>
    <a class="cta2" href="sessions/index.html">AWS sessions →</a>
    <a class="cta2" href="design/index.html">The design →</a>
    <a class="cta2" href="workflow/index.html">The workflow →</a>
  </div>
</header>

<section class="band alt" id="short">
  <h2>In short</h2>
  <div class="cards">
    <a class="card" href="design/index.html#interface"><span class="tag">The interface</span><h3>AWS-shaped, and fixed</h3><p>One client per account and region, one params object per call, AWS-shaped results and error codes, in the shape of the AWS SDK for JavaScript v3. Consuming code is written against this and nothing else.</p><span class="go">Read →</span></a>
    <a class="card" href="design/index.html#backends"><span class="tag">The backends</span><h3>Vault, memory, live</h3><p>The same three the S3 container has. The vault backend is the twin; memory is the test double; live is the real account, borrowed for a session. Swappable from a drop-down in the PoC.</p><span class="go">Read →</span></a>
    <a class="card" href="workflow/index.html#session"><span class="tag">The session</span><h3>From the access portal, into the vault</h3><p>Temporary credentials for one account and one role, one to twelve hours. Pasted, not configured. When it ends it is worth nothing. The twin's interface never holds it; the live backend borrows it.</p><span class="go">Read →</span></a>
    <a class="card" href="design/index.html#snapshots"><span class="tag">The data</span><h3>Snapshots are commits</h3><p>Everything the twin holds is a state document in the vault. Every snapshot is a commit, so "what changed between Monday and Friday" is a diff, the same for hand-seeded and live-sourced data.</p><span class="go">Read →</span></a>
    <a class="card" href="design/index.html#graph"><span class="tag">The graph</span><h3>Resources as nodes, relationships as edges</h3><p>Role → policy, function → bucket, instance → security group, stack → what it created. Built from the state the interface returns, readable as SVG or as Mermaid.</p><span class="go">Read →</span></a>
    <a class="card" href="workflow/index.html#deploy"><span class="tag">The first job</span><h3>Deploy the SG/Send servers</h3><p>One template, one session per account, several regions, every deployment written down in the vault. Rehearsed against the twin in the PoC; the live run is the same calls.</p><span class="go">Read →</span></a>
  </div>
</section>

<section class="band" id="flow">
  <h2>The flow</h2>
  <p class="blurb">The article's diagram, with one change: the site in the browser is a twin, and the live session is a backend behind its interface, not the only way it works.</p>
  <div class="flow">
    <div class="fb aws"><span class="lbl">1 · AWS</span><b>Access portal</b>Sign in, pick the account and the permission set, choose "Access keys".</div>
    <div class="fb aws"><span class="lbl">2 · temporary</span><b>Credentials</b>Access key, secret, session token. One to twelve hours, one by default.</div>
    <div class="fb vault"><span class="lbl">3 · the vault</span><b>The session, and the data</b>Pasted in for the session's lifetime. The same vault holds inventories, logs, costs and snapshots.</div>
    <div class="fb twin"><span class="lbl">4 · the twin</span><b>aws.twin in the browser</b>One AWS-shaped interface. Behind it: the vault, memory, or the live session.</div>
    <div class="fb aws"><span class="lbl">5 · live, when wired</span><b>AWS</b>S3, Lambda, EC2, IAM, billing, logs, through the SDK for JavaScript. Results go back to step 3.</div>
    <div class="fb vault"><span class="lbl">6 · the record</span><b>Graphs and workflows</b>Snapshots as commits, the account graph, deployments written down.</div>
  </div>
</section>

<section class="band alt" id="state">
  <h2>Built, and designed, {DATE}</h2>
  <p class="blurb">A site about a twin owes the reader its build state before anything else. Here it is, unsoftened; the full table with evidence is on <a href="shipped/index.html">the status page</a>.</p>
  <div class="split">
    <table>
      <thead><tr><th>Artefact</th><th class="safe">State</th><th>What it proves</th></tr></thead>
      <tbody>
        <tr><td><b>The Python twin</b>: S3's REST-XML protocol and STS GetCallerIdentity answered from a VFS, a botocore hook, a local endpoint, record and replay</td><td><span class="st st-poc">PoC, working</span></td><td>The same 18 tests under pytest in CPython (18 pass) and under Pyodide in the browser (16 pass, 2 skipped: no sockets or disk). <a href="python/index.html">The Python twin →</a></td></tr>
        <tr><td><b>OSBot-AWS against the twin</b>, unchanged, in CPython and in the browser</td><td><span class="st st-poc">PoC, working</span></td><td>Its S3 helpers, from bucket_create to bucket_delete_all_files, and STS caller identity</td></tr>
        <tr><td><b>The S3 browser</b>: every button a Python call, kept in IndexedDB through sg-vfs</td><td><span class="st st-poc">PoC, working</span></td><td>14 headless checks including a reload that restores the buckets. <a href="console/s3.html">Open it →</a></td></tr>
        <tr><td><b>The session check</b>: a pasted session verified against AWS from the browser, through the twin's live route</td><td><span class="st st-poc">built</span></td><td>A signed STS call from Python in the browser reaches AWS and comes back. <a href="sessions/index.html">Sessions →</a></td></tr>
        <tr><td><b>The JavaScript interface</b>: 8 AWS-shaped namespaces, 42 operations, one manifest</td><td><span class="st st-poc">first PoC, superseded for new work</span></td><td>Still runs <a href="twin/index.html">the twin page</a>. New services go into the Python twin.</td></tr>
        <tr><td><b>The vault backend</b> on localStorage, and the memory backend</td><td><span class="st st-poc">PoC, working</span></td><td>Same script, two backends, same answers: 214 assertions in <code>admin/build/test.js</code></td></tr>
        <tr><td><b>Snapshots as commits</b>, diff between any two</td><td><span class="st st-poc">PoC, working</span></td><td>Monday against Friday, resource by resource. Export and import of the vault document.</td></tr>
        <tr><td><b>The account graph</b></td><td><span class="st st-poc">PoC, working</span></td><td>Eight node kinds, six edge relations, from the state the interface returns</td></tr>
        <tr><td><b>Deployment rehearsal</b>: two templates, accounts × regions</td><td><span class="st st-poc">PoC, working</span></td><td>A template is a sequence of ordinary calls, so the rehearsal and the live run are the same calls. ECS is not in the manifest: the Fargate template records that gap on its stack.</td></tr>
        <tr><td><b>The live backend</b>: the session slot, the refusal naming the SDK command</td><td><span class="st st-design">slot built, wire designed</span></td><td>The same interface; every call says what it would send. Nothing calls AWS yet.</td></tr>
        <tr><td><b>CORS per service</b>, measured from a browser with no credentials</td><td><span class="st st-poc">measured</span></td><td>Seven of eight service families answer any origin with a preflight; S3 needs a bucket rule. <a href="articles/boto3-in-the-browser.html#cors">The table →</a></td></tr>
        <tr><td><b>boto3 in the browser</b> under Pyodide, against the twin</td><td><span class="st st-poc">experiment, ran</span></td><td>Eleven signed calls through one replaced transport function, ten seconds wall. <a href="articles/boto3-in-the-browser.html">The brief →</a></td></tr>
        <tr><td><b>Live, from the browser</b> (the Python twin): a real session checked against AWS STS; the S3 browser live, directly or through the local relay, read-only by default</td><td><span class="st st-poc">built; STS checked with a real session</span></td><td><a href="how-it-works/index.html">How it works</a>; real-account S3 browsing is the next test</td></tr>
        <tr><td>IAM Roles Anywhere from a browser, sgit sync of the vault document</td><td><span class="st st-no">not done</span></td><td>To test and to build. Export and import by file stand in for sync today.</td></tr>
      </tbody>
    </table>
    <p class="cap">The honest headline: <b>the twin works in the browser against a vault; the wire to the live account is the next step, and nothing on this site pretends otherwise.</b> The article of {DATE} said "nothing here is built"; this site is the same day's first go, and <a href="articles/index.html">its articles</a> say what was done and what was measured.</p>
  </div>
</section>

<section class="band" id="why">
  <h2>Why a twin, and not a console</h2>
  <div class="split">
    <blockquote>The S3-compatible vault container works because <b>"code using boto3 believes it is talking to real S3"</b> while the backend is real S3, a vault, or memory, chosen per environment, and <b>"the service's own code does not change."</b></blockquote>
    <p class="cap">The AWS twin is the second instance of that pattern, not an exception to it. Build the twin first, with the vault as its backend, and every workflow, graph and deployment is written against the interface. Then the live connection is one more backend: a temporary session, borrowed for an hour, in front of the same face. Develop and test with no credentials; rehearse a multi-account, multi-region deploy before running it live; and keep one record either way, because snapshots are vault commits whether the data was seeded by hand or read from the account. <a href="naming/index.html">Why that made it <code>aws.twin</code> and not <code>aws.sgit.ai</code> →</a></p>
  </div>
</section>

<section class="band alt" id="stores">
  <h2>What this proof of concept stores, and where</h2>
  <p class="blurb">Nothing leaves the browser. There is no server behind this site, no analytics, and no third-party script.</p>
  <div class="cards">
    <div class="card"><span class="tag">localStorage · aws.twin/vault</span><h3>The twin's data</h3><p>One document: a working state, a list of commits, a head. The shape an sgit vault holds, so the export is what gets pushed there. Illustrative accounts from the seed, or whatever you create.</p></div>
    <div class="card"><span class="tag">sessionStorage · aws.twin/session</span><h3>The session, if you paste one</h3><p>For this tab's lifetime, with the expiry you give it. The secret and the token are never shown back. In this PoC the live backend refuses every call with the command it would have sent, so pasting a session proves the slot and nothing more.</p></div>
    <div class="card"><span class="tag">localStorage · aws.twin/ui</span><h3>Which backend, account and region</h3><p>The three drop-downs, so the page reopens where you left it. Nothing else.</p></div>
  </div>
</section>

<section class="band" id="participant">
  <h2>Who is writing this</h2>
  <p class="blurb">This site is published by the sgit project, which builds the vault this twin stores into and the SG/Send server components its first job deploys. So it is a participant publishing a tool for its own workflow, stated upfront. It is not affiliated with Amazon Web Services; the service names identify the interfaces the twin mirrors, and the quotations about sessions and CORS are from AWS's documentation as read on {DATE} for <a href="https://newsroom.sgit.ai/articles/aws-from-the-vault.html">the article</a>. The build state leads, every designed thing is labelled as design, and <a href="shipped/index.html#claims">what this does not claim</a> is a page of its own.</p>
  <div class="ctas">
    <a class="cta2" href="shipped/index.html">Built, and designed, in full →</a>
    <a class="cta2" href="https://twins.sgit.ai/about/participant.html">The family's participant disclosure ↗</a>
  </div>
</section>''')

# ---------------------------------------------------------------- twin/index.html
page('twin/index.html',
  'The AWS twin — open it · aws.twin.sgit.ai',
  'The proof of concept: an AWS-shaped interface over a vault in this browser. S3, Lambda, EC2, IAM, billing, logs, CloudFormation, snapshots as commits, the account graph, and a deployment rehearsal. Every call shown as it would go to AWS.',
  '''<main class="tw">
  <p class="tw-intro"><b>The AWS twin, as a proof of concept.</b> Everything on this page is a call through <a href="../design/index.html#interface">the interface</a>; the backend behind it is the drop-down. Nothing calls AWS. Data lives in this browser's localStorage, as a vault document with commits. <b>Start by seeding the demo estate</b>, then commit a snapshot so there is a baseline to diff against.</p>
  <div id="tw-bar"></div>
  <div class="tw-layout">
    <nav id="tw-side" aria-label="services"></nav>
    <div id="tw-main"><p class="tw-empty">loading…</p></div>
  </div>
  <div id="tw-calls"></div>
  <noscript><div class="tw-err">The twin is JavaScript: the interface, the backends and the UI all run in this page, and there is no server to fall back to.</div></noscript>
</main>
<script src="../assets/twin/interface.js"></script>
<script src="../assets/twin/vault.js"></script>
<script src="../assets/twin/templates.js"></script>
<script src="../assets/twin/app.js" defer></script>''',
  extra_head='<link rel="stylesheet" href="../assets/twin/app.css">\n')

# ---------------------------------------------------------------- design/index.html
page('design/index.html',
  'The design — one interface, three backends · aws.twin.sgit.ai',
  'How the AWS twin is built: the interface manifest, the state document, the vault backend with commits, the live backend and what wiring it needs, snapshots and diffs, the account graph, templates as calls, and the tests that hold the two backends to the same answers.',
  f'''<main class="doc">
  <div class="crumb"><a href="../index.html">aws.twin.sgit.ai</a> / design</div>
  <h1>The design</h1>
  <p class="lead">One AWS-shaped interface, and behind it a backend chosen at runtime: the vault, memory, or the live account. The claim this page has to earn is that consuming code written against the interface does not know which. The PoC earns it the way the S3 container does, by running the same script against two backends and checking the answers match.</p>

  <h2 id="stack">1. One interface, three backends</h2>
  <div class="stack">
    <div class="layer consumer"><b>Consumers</b>: the UI on <a href="../twin/index.html">the twin page</a>, the two deployment templates, the account graph, the snapshot diff, the tests. None of them reads a backend's state; each makes calls.</div>
    <div class="down">↓</div>
    <div class="layer iface"><b>The interface</b>: <code>AwsTwin.client(backend, {{accountId, region}})</code>. Nine namespaces (eight AWS-shaped, one twin-only), 45 operations, a manifest of accepted params. One client per account and region, like an SDK client bound to a session.</div>
    <div class="down">↓</div>
    <div class="backs">
      <div class="layer vault"><b>Vault</b> <span class="st st-poc">PoC</span><br>The ops over a state document, persisted to localStorage as a document with commits and a head. The twin proper.</div>
      <div class="layer mem"><b>Memory</b> <span class="st st-poc">PoC</span><br>The same ops, nothing persisted. The test double, and the third backend in the S3 container's list.</div>
      <div class="layer live"><b>Live</b> <span class="st st-design">slot built</span><br>Reads a session from the vault; would construct SDK v3 clients per call. In this PoC it refuses each call naming the command it would send.</div>
    </div>
  </div>
  <p>The vault and memory backends share one implementation of the operations and differ only in <code>save()</code>. That is deliberate: it keeps the semantics in one place, and it is what lets the equivalence test hold without a special case.</p>

  <h2 id="interface">2. The interface</h2>
  <p>The shape follows the AWS SDK for JavaScript v3, because that is what the live backend will call: every operation takes one params object with the SDK's PascalCase keys (lower camel for CloudWatch Logs, as in AWS), returns a Promise of one result object, and fails with an error whose <code>code</code> is the AWS error name (<code>NoSuchBucket</code>, <code>ResourceConflictException</code>, <code>InvalidGroup.NotFound</code>). A param the manifest does not list is refused with <code>UnknownParam</code> before any backend sees it, so a typo cannot silently succeed on the vault and fail live.</p>
  <div class="tablewrap"><table>
    <thead><tr><th>Namespace</th><th>Operations in the manifest</th><th>Scope</th></tr></thead>
    <tbody>
      <tr><td><code>sts</code></td><td>getCallerIdentity</td><td>global</td></tr>
      <tr><td><code>s3</code></td><td>listBuckets, createBucket, deleteBucket, headBucket, listObjectsV2, putObject, getObject, deleteObject</td><td>global; buckets carry a region</td></tr>
      <tr><td><code>lambda</code></td><td>listFunctions, getFunction, createFunction, updateFunctionConfiguration, deleteFunction, invoke</td><td>per region</td></tr>
      <tr><td><code>ec2</code></td><td>describeInstances, runInstances, startInstances, stopInstances, terminateInstances, describeSecurityGroups, createSecurityGroup, authorizeSecurityGroupIngress</td><td>per region</td></tr>
      <tr><td><code>iam</code></td><td>listRoles, getRole, createRole, deleteRole, listPolicies, createPolicy, attachRolePolicy, detachRolePolicy, listAttachedRolePolicies</td><td>global</td></tr>
      <tr><td><code>logs</code></td><td>describeLogGroups, createLogGroup, deleteLogGroup, putLogEvents, filterLogEvents</td><td>per region</td></tr>
      <tr><td><code>ce</code></td><td>getCostAndUsage (monthly or daily, grouped by service or region)</td><td>global</td></tr>
      <tr><td><code>cloudformation</code></td><td>listStacks, describeStacks, createStack, deleteStack</td><td>per region</td></tr>
      <tr><td><code>twin</code></td><td>recordCost, snapshot, state</td><td>twin-only: never sent live</td></tr>
    </tbody>
  </table></div>
  <p>The <code>twin</code> namespace is the one deliberate departure. AWS has no call that writes a cost; reality does that. The twin needs an input for it, and for reading the whole state to build a graph. Those live under <code>twin.*</code>, never under an AWS service name, so the boundary between AWS-shaped and twin-only stays visible in the call log, and the live backend refuses them with <code>TwinOnly</code> rather than inventing an endpoint.</p>
  <p>Behaviour is kept where it is cheap and telling: a function needs a role that exists; a role cannot be deleted while a policy is attached or a function uses it; a bucket cannot be deleted while it holds objects; a bucket name is validated; instances and functions are per region, so stopping an instance from the wrong region fails with <code>InvalidInstanceID.NotFound</code>; invoking a function writes four lines to its log group. These are the behaviours a rehearsal is for.</p>

  <h2 id="state">3. The state document</h2>
  <p>One document per vault, one account record per account inside it. Every resource carries the region it lives in, and the per-region services filter on the client's region at call time.</p>
  <pre class="shell"><span class="d">// AwsTwin.emptyState() → one account added</span>
{{ "version": 1,
  "accounts": {{
    "111111111111": {{
      "accountId": "111111111111", "name": "sg-send-dev (illustrative)",
      "s3":             {{ "buckets": [], "objects": {{}} }},
      "lambda":         {{ "functions": [] }},
      "ec2":            {{ "instances": [], "securityGroups": [] }},
      "iam":            {{ "roles": [], "policies": [], "attachments": [] }},
      "logs":           {{ "groups": [], "events": {{}} }},
      "ce":             {{ "records": [] }},
      "cloudformation": {{ "stacks": [] }},
      "twin":           {{ "invocations": [] }}
    }}
  }}
}}</pre>
  <p>Add a service by adding a key here, its operations to the manifest, and their implementation to the ops table; the tests fail until the manifest and the ops agree, which is the first test in the file.</p>

  <h2 id="backends">4. The vault backend</h2>
  <p>In the PoC the vault is the browser's localStorage, under one key, <code>aws.twin/vault</code>, holding one document:</p>
  <pre class="shell"><span class="d">// aws.twin/vault@1</span>
{{ "format": "aws.twin/vault@1", "name": "aws-twin", "created": "…",
  "head": "&lt;commit id&gt;",
  "commits": [ {{ "id", "parent", "at", "message", "summary", "state" }}, … ],
  "working": {{ …the state document… }} }}</pre>
  <p>That is the shape an sgit vault gives for free: a working tree, commits, a head. The export button on the snapshots page downloads exactly this document, and the import button continues from one, so the hand-off to a real vault is a file today and a sync later. Commit ids in the PoC are content hashes of the commit (not cryptographic; the vault's own hashes take over once the document is pushed through sgit). The full state is kept per commit because the states are small and a diff between any two commits must be cheap.</p>

  <h2 id="snapshots">5. Snapshots, and the diff</h2>
  <p>A snapshot is a commit of the whole state document. A diff flattens each account into resource keys (<code>s3:bucket name</code>, <code>lambda:function region/name</code>, <code>iam:role name</code>, …) with the fields that matter for "has this changed", and reports added, removed, changed and unchanged. The vault's working state can be diffed against any commit, which is how "uncommitted changes" is computed for the bar at the top of the twin page.</p>
  <p>The diff keys are chosen, not derived: a bucket changes when its object count changes, a role when its attachments change, an instance when its state or type changes, the cost total when a record is added. That is the right level for Monday against Friday, and the wrong level for an audit, which would want every field. Both are available: the commit holds everything.</p>

  <h2 id="live">6. The live backend, and what the wire needs</h2>
  <p>The live backend's job is to answer the same manifest by sending each call to AWS with the session in the vault. In this PoC it has its slot and not its wire: it reads the session, checks it is present and unexpired, and then refuses with <code>NotWired</code>, naming the SDK command, the service endpoint, the region, the account and the expiry it would have used. The UI, the templates and the graph can all be pointed at it, and every call shows the gap precisely.</p>
  <p>Wiring it needs three things, and nothing on the consuming side:</p>
  <ol>
    <li><b>The SDK for JavaScript v3 clients</b> for the eight services, constructed per call from the session's three values, with the region from the client's scope. Released as a fixed, independent copy per site version, so the code that holds the session is a known thing.</li>
    <li><b>A CORS measurement per service.</b> Made on {DATE}, with no credentials: STS, Lambda, EC2, IAM, Logs, Cost Explorer and CloudFormation answer any origin with a preflight that allows the SDK's headers; S3 does not until the bucket has a CORS rule, which the deploy template can write when it creates the bucket. <a href="../articles/boto3-in-the-browser.html#cors">The table and the data →</a>. Where a service will not answer, a small helper on the user's own machine, or an SG/Compute node, makes that call behind the same interface: a fourth backend, not a change to the consumers.</li>
    <li><b>Results back into the vault.</b> A live read is a snapshot like any other: the response is written into the state document and committed, so the live backend and the vault backend are not alternatives but a pair.</li>
  </ol>
  <div class="note"><b>Where the credential lives.</b> The twin's interface never holds it. The live backend reads it from the session slot, which is sessionStorage in this PoC: the tab's lifetime, never written to disk by the browser the way localStorage is, with the expiry the user gave it (one to twelve hours). The slot refuses a session without a token, because a long-lived IAM user key is exactly what this design declines to hold. This is the resolution the naming page proposes for the hub's ruling: <a href="../naming/index.html#ruling">a twin can have a live backend; the credential belongs to the backend, not the twin</a>.</div>

  <h2 id="graph">7. The account graph</h2>
  <p>Resources as nodes, relationships as edges, built from the state the interface returns via <code>twin.state</code>. Eight node kinds and six relations in the PoC:</p>
  <div class="tablewrap"><table>
    <thead><tr><th>Edge</th><th>From → to</th><th>Where it comes from</th></tr></thead>
    <tbody>
      <tr><td><code>attached_policy</code></td><td>role → policy</td><td>IAM attachments, including AWS managed policies as nodes</td></tr>
      <tr><td><code>assumes_role</code></td><td>function → role</td><td>the function's <code>Role</code></td></tr>
      <tr><td><code>uses_bucket</code></td><td>function → bucket</td><td>any environment variable whose value is a bucket name in the account</td></tr>
      <tr><td><code>writes_logs</code></td><td>function → log group</td><td><code>/aws/lambda/&lt;name&gt;</code> in the same region</td></tr>
      <tr><td><code>in_security_group</code>, <code>instance_profile</code></td><td>instance → security group, instance → role</td><td>the instance's groups and profile; terminated instances leave the graph</td></tr>
      <tr><td><code>created</code></td><td>stack → resource</td><td>what the template reported creating</td></tr>
    </tbody>
  </table></div>
  <p>The twin page draws it as layered SVG, one column per kind, and prints it as Mermaid for pasting elsewhere. The point is not the drawing. It is that the graph is a function of the state document, so it is the same function for a seeded account and a live snapshot, and a diff of two graphs is a diff of two commits.</p>

  <h2 id="templates">8. Templates are calls</h2>
  <p>A deployment template in the twin is a function given a client and the stack's parameters. It makes ordinary calls: create the role if missing, the per-account-per-region bucket if missing, the policy, attach it, create the function with its image and environment. CloudFormation's <code>createStack</code> runs the template against the interface itself, so the stack's resources are the ARNs those calls produced and the stack's deletion reverses the ones that belong to it. A rehearsal against the vault is therefore the same calls as the live run; only the backend differs.</p>
  <p>Two templates ship, standing in for the SG/Send server components: Lambda as a container image with a function URL, and ECS Fargate. The manifest has no <code>ecs</code> namespace yet, so the Fargate template creates the role, bucket, security group and log group it can, and records the service it cannot as a stack output that says so: <i>not in the interface: tracked gap</i>. That is the discipline the twins hub asks for, applied to the twin's own coverage.</p>

  <h2 id="tests">9. The tests</h2>
  <p><code>node admin/build/test.js</code> runs the same script (bucket, objects, role, policy, function, invoke, instance, cost, two stacks, a deletion) against the memory backend and against the vault backend over a storage shim, normalises what is random by design (ids, timestamps, request ids, the invoke duration) and asserts the answers are identical, step by step. It then checks the expected answers, the commit and checkout round trip, the diff, the graph's node and edge counts after seeding, the session slot's parsing and refusals, and the async client the UI uses. As of {DATE}: 214 assertions, all passing, in under a second. The browser has no test runner; the twin page's call log is the manual one.</p>

  <h2 id="open">10. Open in the design</h2>
  <ul>
    <li><b>Live and vault disagree.</b> When the wire exists, a live read will differ from the last commit. The vault is the record and live is the source; the right move is a commit, with the diff as the message. Nothing enforces that yet.</li>
    <li><b>Staleness.</b> A commit carries its time, and the hub's first open question applies here exactly: a connected twin can be six days stale. The bar shows "uncommitted changes" and not "last read live at", because there is no live read yet.</li>
    <li><b>Which services, which fields.</b> The manifest is what the first job needs plus what the article lists. ECS, Route 53, ECR and SSM are the obvious next namespaces; each is a key in the state document, a manifest entry and an ops entry.</li>
    <li><b>Multi-account is multi-session.</b> A client is bound to one account because a session is. The deploy rehearsal makes one client per target. Live, that is one paste per account, which is the article's deliberate trade.</li>
  </ul>
  <div class="pagenav"><a href="../twin/index.html">← Open the twin</a><a href="../workflow/index.html">The workflow →</a></div>
</main>''')

# ---------------------------------------------------------------- workflow/index.html
page('workflow/index.html',
  'The workflow — a session from the access portal, work in the browser, results in the vault · aws.twin.sgit.ai',
  'The AWS twin workflow: sign in to the AWS access portal, paste the temporary credentials into the vault, work for the session, keep the results as commits. The first job, deploying SG/Send server components to many accounts and regions, rehearsed against the twin. What to be careful about.',
  f'''<main class="doc">
  <div class="crumb"><a href="../index.html">aws.twin.sgit.ai</a> / workflow</div>
  <h1>The workflow</h1>
  <p class="lead">Two loops. The inner one is a session: an hour with one account and one role, borrowed from the AWS access portal and returned when it ends. The outer one is the vault: what each session found, kept as commits, so the next session starts from the record. In the proof of concept the inner loop is rehearsed against the vault; the outer loop works today.</p>

  <h2 id="session">1. The session</h2>
  <ol>
    <li><b>Sign in to the AWS access portal.</b> It is part of IAM Identity Center. Pick the account, and the permission set you have in it. AWS's own distinction: IAM users are granted long-term credentials; users in IAM Identity Center are granted temporary ones, generated every time you sign in. It recommends the second.</li>
    <li><b>Choose "Access keys".</b> The portal shows the temporary credentials for that role: an access key id, a secret access key and a session token, in four formats. Any of the four pastes into the twin's <a href="../twin/index.html#/session">session page</a>; the credentials-file format also carries the account id and the role in its profile header.</li>
    <li><b>Paste them into the vault.</b> In this PoC: sessionStorage, for this tab, with the expiry you set. The twin switches its backend to <i>live</i>.</li>
    <li><b>Work.</b> For as long as the session lasts, the live backend can do whatever that role can do, through the same interface the vault answers. When the session ends the credentials are worth nothing, and you sign in again.</li>
  </ol>
  <p>How long it lasts is set on the permission set: AWS says the session can be from one to twelve hours, with one hour by default. Copying and pasting is a little more work than the CLI's automatic refresh, and in return the site never sees anything but one short-lived session, for one account and one role.</p>
  <div class="warnbox"><b>In this PoC the live backend is not wired.</b> Pasting a session proves the slot: the twin accepts it, counts it down, and refuses every call with the exact SDK command it would have sent. Nothing pasted leaves the browser and nothing on this site calls AWS. The work below is rehearsed against the vault backend, which is the twin-first point.</div>

  <h2 id="work">2. The work, service by service</h2>
  <p>What the twin page does today, against the vault, and will do live through the same calls:</p>
  <div class="tablewrap"><table>
    <thead><tr><th>Service</th><th>In the twin page</th><th>The calls</th></tr></thead>
    <tbody>
      <tr><td>S3</td><td>Buckets with their region; objects with prefix listing; put, get, delete</td><td><code>ListBuckets</code>, <code>ListObjectsV2</code>, <code>PutObject</code>, <code>GetObject</code>, <code>DeleteObject</code>, <code>CreateBucket</code>, <code>DeleteBucket</code></td></tr>
      <tr><td>Lambda</td><td>What is deployed in the region, at which image or runtime, with which role and settings; invoke with a payload and read the log</td><td><code>ListFunctions</code>, <code>CreateFunction</code>, <code>Invoke</code>, <code>DeleteFunction</code></td></tr>
      <tr><td>EC2</td><td>Instances and their state, security groups and their rules, instance profiles; run, stop, start, terminate</td><td><code>DescribeInstances</code>, <code>RunInstances</code>, <code>StopInstances</code>, <code>DescribeSecurityGroups</code>, <code>AuthorizeSecurityGroupIngress</code></td></tr>
      <tr><td>IAM</td><td>Roles with their attached policies; create, attach, detach, delete with AWS's conflicts</td><td><code>ListRoles</code>, <code>ListAttachedRolePolicies</code>, <code>CreateRole</code>, <code>AttachRolePolicy</code></td></tr>
      <tr><td>Billing</td><td>Cost by month, grouped by service or by region, as bars and a table</td><td><code>GetCostAndUsage</code></td></tr>
      <tr><td>Logs</td><td>Log groups, events with a filter, your own events</td><td><code>DescribeLogGroups</code>, <code>FilterLogEvents</code>, <code>PutLogEvents</code></td></tr>
      <tr><td>Deploy</td><td>Stacks with outputs and resources; a rehearsal across accounts and regions</td><td><code>CreateStack</code>, <code>DescribeStacks</code>, <code>DeleteStack</code></td></tr>
    </tbody>
  </table></div>

  <h2 id="deploy">3. The first job: deploying the SG/Send servers</h2>
  <p>The SG/Send server components, the small API that stores vaults, need to run in many regions and increasingly in many accounts. The pieces exist: CloudFormation templates for Lambda as a container image with a function URL and for ECS Fargate, an S3 storage mode with buckets named per account and region, runbooks for new accounts and regions. What is painful is running them across all of those and knowing afterwards what is deployed where.</p>
  <p>In the twin, as of {DATE}:</p>
  <ol>
    <li>Open <a href="../twin/index.html#/deploy">Deploy</a> with the vault backend and the demo estate seeded. Both illustrative accounts already carry <code>sg-send-api</code> in two regions, at two image tags, from the seed.</li>
    <li>Pick the template, name the stack, set the image tag, tick the accounts and the regions. The twin makes one client per account and region, as the live run will make one session per account.</li>
    <li>Run it. Each target is a <code>CreateStack</code> that expands into the template's calls; the result table shows a stack per target, or AWS's <code>AlreadyExistsException</code> where one is already there.</li>
    <li>Commit the deployment. The commit message names the stack, the template and how many targets took it, and the vault is now the record of the estate: which version, which region, which account, when, and what it produced. The next deployment starts from it.</li>
  </ol>
  <p>Live, step 3 is the same calls through the live backend, and step 4 is the same commit. The difference the twin makes is that steps 1 to 4 can be run, broken, and run again with no credentials, until the sequence is right.</p>

  <h2 id="diff">4. Monday against Friday</h2>
  <p>Commit on Monday. Work. Commit on Friday. On <a href="../twin/index.html#/snapshots">Snapshots</a>, diff the two: added, removed and changed, resource by resource, per account, with before and after. Because every snapshot is a commit, this works the same for data seeded by hand and, once the wire exists, for data read from the account; and because the vault document exports as a file, the same diff can be run outside the browser on two exported commits.</p>

  <h2 id="careful">5. What to be careful about</h2>
  <ul>
    <li><b>A session can do whatever its role can do.</b> So the roles should be narrow: one for reading, another for deploying, never more than the job needs. The demo estate seeds a <code>twin-reader</code> role with a describe-and-list policy as the example to copy.</li>
    <li><b>Short sessions are the default.</b> One hour, unless there is a reason for more. The session page caps at twelve, as the portal does.</li>
    <li><b>The site's own code is what holds the session.</b> So it should be released the way the family's API sites are, each version a fixed, independent copy, so you know exactly which code you trusted. This site is versioned from its first release for that reason.</li>
    <li><b>Credentials never go in a page or a repository.</b> AWS's guidance for browser code is not to hard-code them. Here they are pasted for one session and kept in the vault; this site's name-watch and validator never see one, and the PoC never shows a secret back.</li>
    <li><b>Some calls may need a helper.</b> Where a service will not answer a browser. That is a fourth backend behind the same interface, not a change to the work.</li>
  </ul>

  <h2 id="pki">6. Is there a PKI way?</h2>
  <p>Copying credentials from the portal is good enough to start. It would be better if the session came from a key, as everything else in the family now does. AWS has a service for exactly that: IAM Roles Anywhere exchanges X.509 certificates issued by your own certificate authority, registered as a trust anchor, for temporary credentials. Whether it can work from a browser, signing with a key the browser cannot export, and whether its endpoint answers a browser at all, is untested. Its trust anchors are per account and per region. If it works, it is a fifth backend: the same interface, a session minted from a certificate rather than pasted.</p>
  <div class="pagenav"><a href="../design/index.html">← The design</a><a href="../naming/index.html">Why aws.twin →</a></div>
</main>''')

# ---------------------------------------------------------------- naming/index.html
page('naming/index.html',
  'Naming — why aws.twin.sgit.ai, and the hub-and-family convention · aws.twin.sgit.ai',
  'The naming decision for the AWS site: aws.twin.sgit.ai, repo SGit-AI__Website__Twin__AWS, hub twins.sgit.ai. Why a twin and not a console, the options rejected, the plural-hub singular-instance convention, and the paragraph proposed for the ruling on twins.sgit.ai.',
  f'''<main class="doc">
  <div class="crumb"><a href="../index.html">aws.twin.sgit.ai</a> / naming</div>
  <h1>Why <code>aws.twin</code></h1>
  <p class="lead">The article proposed <code>aws.sgit.ai</code> "or something wider", and said the name was not decided. It was decided on {DATE}, and the decision is the design: the site is a twin first, so it is named as one.</p>

  <h2 id="decision">1. The decision</h2>
  <div class="tablewrap"><table>
    <tbody>
      <tr><th>Domain</th><td><code>aws.twin.sgit.ai</code></td></tr>
      <tr><th>Repository</th><td><code>SGit-AI__Website__Twin__AWS</code>, following <code>SGit-AI__Website__Hook__Tokens</code></td></tr>
      <tr><th>Hub</th><td><a href="https://twins.sgit.ai">twins.sgit.ai</a>, which defines the primitive and will catalogue the twins in place</td></tr>
    </tbody>
  </table></div>
  <p>The site is designed twin-first, in three steps. Build the twin: an AWS-shaped interface whose backend is a vault. Put the real connection in front of it as a second backend behind the same interface: a temporary IAM Identity Center session pasted into the user's vault. Then everything built against the twin works against the live account, because consuming code is written against the interface, not the backend. That is the pattern of the one working twin today, the S3-compatible vault container, where boto3 cannot tell the difference and the backend is swappable between real S3, a vault and memory. <code>aws.twin</code> is the second instance of that pattern, not an exception to it.</p>

  <h3>Options considered, and rejected</h3>
  <div class="tablewrap"><table>
    <thead><tr><th>Option</th><th>Why not</th></tr></thead>
    <tbody>
      <tr><td><code>aws.sgit.ai</code></td><td>Loses the twin-first framing, which is the core of the design. A console with a credential bar is what the name suggests, and it is what the design refuses to be.</td></tr>
      <tr><td><code>aws.platform.sgit.ai</code></td><td>"Platform" names nothing in the estate; a namespace with one occupant.</td></tr>
      <tr><td><code>aws.provider.sgit.ai</code></td><td>Provider sites are reports, not tools: where the key lives, what it cost on a named workload, what broke. An AWS report may come later, separately (see below).</td></tr>
    </tbody>
  </table></div>

  <h2 id="convention">2. The convention, by design</h2>
  <ul>
    <li><b>Plural is the hub, the family:</b> <code>twins.sgit.ai</code>, <code>hooks.sgit.ai</code>, <code>providers.sgit.ai</code>.</li>
    <li><b>Singular is one instance, at that moment in time:</b> <code>aws.twin.sgit.ai</code>, <code>tokens.hook.sgit.ai</code>, <code>elevenlabs.provider.sgit.ai</code>.</li>
    <li><b>Repositories:</b> <code>SGit-AI__Website__&lt;Family&gt;__&lt;Instance&gt;</code>, with the family name singular: <code>Hook__Tokens</code>, <code>Provider__ElevenLabs</code>, <code>Twin__AWS</code>.</li>
  </ul>
  <div class="note"><b>Ops note.</b> Each singular namespace needs its own wildcard certificate (<code>*.twin.sgit.ai</code>, <code>*.hook.sgit.ai</code>, <code>*.provider.sgit.ai</code>), because <code>*.sgit.ai</code> does not cover second-level subdomains.</div>

  <h2 id="ruling">3. The ruling on the hub, and the paragraph this site proposes</h2>
  <p><a href="https://twins.sgit.ai/naming/index.html">The naming ruling on twins.sgit.ai</a> says a corpus twin is the graph's endpoint into reality and holds no credentials, and that the S3 container blurs the line by also holding backend access. The AWS twin is a second case of the same blur, and it resolves it the same way the S3 container does in practice. This site proposes the following paragraph be added to the ruling:</p>
  <blockquote class="challenge">A twin's interface never holds credentials. A twin can have a live backend; when it does, the credential belongs to that backend, not to the twin, and lives in the user's vault for the lifetime of the session (for AWS: a temporary IAM Identity Center session, 1–12 hours, 1 hour by default). The S3 container and the AWS twin are the two worked examples of this: interface first, backends swappable, live access as one backend among several.</blockquote>
  <p>Two things stay distinct under that paragraph. The <b>execution broker</b> is a standing, credential-holding intermediary, and the hub's concentration-risk question about it stands. A twin with a live backend <b>borrows</b> a user-held, time-bounded session; it never stands, and it holds nothing when the session ends. The PoC makes the distinction mechanical: the session slot is a separate store from the twin's data, with an expiry, and the twin's interface has no method that returns it.</p>

  <h2 id="watch">4. The name-watch on this site</h2>
  <p>The hub fails its build on any capitalised <i>&lt;Word&gt; Twin</i> that has not been ruled on, and this site runs the same check in <code>admin/build/validate.js</code>, with the hub's four permitted terms as the allow-list. This site uses lower case throughout, <i>the AWS twin</i>, rather than adding a fifth term; if a capitalised form is ever wanted, it is added to the hub's table with its meaning first, and to this site's allow-list second.</p>

  <h2 id="later">5. Later, and separate: an AWS provider report</h2>
  <p>The providers family answers one question per provider: where the credential lives and what bounds it. For AWS the bound is a clock, and a report could also carry the CORS results per service and the cost of a named workload. That would be <code>aws.provider.sgit.ai</code>, a report, separate from this twin, a tool. Before adding it, the providers hub's "no commercial relationship" disclosure has to be checked against sgit.ai's partnerships page for AWS, because a report that is not independent must say so.</p>
  <div class="pagenav"><a href="../workflow/index.html">← The workflow</a><a href="../shipped/index.html">Built, and designed →</a></div>
</main>''')

# ---------------------------------------------------------------- shipped/index.html
page('shipped/index.html',
  'Built, and designed — the build state of the AWS twin, unsoftened · aws.twin.sgit.ai',
  'What works in the AWS twin proof of concept, what is a slot without a wire, what is not done, what is next, and what this site does not claim. Measured on 21 October 2026.',
  f'''<main class="doc">
  <div class="crumb"><a href="../index.html">aws.twin.sgit.ai</a> / status</div>
  <h1>Built, and designed</h1>
  <p class="lead">The family's house rule: the build state leads, every designed thing is labelled as design, and the numbers carry the date they were measured. Measured {DATE}, at site {VER}, the first release.</p>

  <h2 id="table">1. The table</h2>
  <div class="tablewrap"><table>
    <thead><tr><th>Artefact</th><th>State</th><th>Evidence</th></tr></thead>
    <tbody>
      <tr><td><b>The interface</b>: 8 AWS-shaped namespaces, 42 operations, plus 3 twin-only, a manifest of accepted params, AWS-shaped results and error codes</td><td><span class="st st-poc">PoC, working</span></td><td><code>assets/twin/interface.js</code>; the manifest-coverage test fails if an operation is listed and not implemented, or the reverse</td></tr>
      <tr><td><b>The vault backend</b> on localStorage: working state, commits, head, checkout, export, import, reset</td><td><span class="st st-poc">PoC, working</span></td><td><code>assets/twin/vault.js</code>; the round-trip test reloads from storage and from an exported document</td></tr>
      <tr><td><b>The memory backend</b></td><td><span class="st st-poc">PoC, working</span></td><td>The same script against both backends, 46 steps, identical after normalising what is random by design</td></tr>
      <tr><td><b>Snapshots and diff</b>: any commit against any commit or the working state, per account, added, removed, changed</td><td><span class="st st-poc">PoC, working</span></td><td>Snapshots page; <code>diffStates</code> tested on a three-change Monday-to-Friday</td></tr>
      <tr><td><b>The account graph</b>: 8 node kinds, 6 relations, SVG and Mermaid</td><td><span class="st st-poc">PoC, working</span></td><td>Graph page; node and edge counts tested after seeding</td></tr>
      <tr><td><b>Deployment rehearsal</b>: two templates, accounts × regions, a commit of the result</td><td><span class="st st-poc">PoC, working</span></td><td>Deploy page; <code>createStack</code> runs the template through the interface; the Fargate template records the ECS gap on its stack</td></tr>
      <tr><td><b>The demo estate</b>: two illustrative accounts seeded through the interface</td><td><span class="st st-poc">PoC, working</span></td><td>Illustrative account ids and numbers; every seeded resource is a logged call</td></tr>
      <tr><td><b>The session slot</b>: paste in four formats, expiry, masking, refusal of long-lived keys</td><td><span class="st st-poc">PoC, working</span></td><td>Session page; parsing and refusals tested</td></tr>
      <tr><td><b>The JavaScript proof of concept's live backend</b>: its wire to AWS</td><td><span class="st st-design">designed</span></td><td>Refuses every call naming the SDK command; what wiring needs is <a href="../design/index.html#live">three listed things</a>. The Python twin's live route, below, is what reaches AWS</td></tr>
      <tr><td><b>The Python twin's live route</b> from the browser: a pasted session, signed in the page; direct where AWS allows the origin, through <a href="../how-it-works/index.html#relay">the local relay</a> where it does not</td><td><span class="st st-poc">built; STS checked with a real session</span></td><td>The sessions page's check returned a real account, role and user; the S3 browser live against a stand-in for AWS behind the relay, ten browser checks; real-account S3 browsing not yet done</td></tr>
      <tr><td><b>Uptime checks in every region</b>: a Node.js Lambda function, sgit-encrypted reports to an append lane, deployed with boto3; twins of Lambda, IAM roles, EventBridge, CloudFront and the append lane</td><td><span class="st st-poc">built, in the twin</span></td><td><a href="../uptime/index.html">The uptime page</a>; deploy, run, schedule and decrypt tested in CI and in the browser; not yet deployed to AWS (<a href="../uptime/plan.html#phases">phase 2</a>)</td></tr>
      <tr><td><b>Least-privilege guidance</b>: four S3 permission sets, the CLI, a policy simulator step</td><td><span class="st st-poc">written, commands checked</span></td><td><a href="../iam/index.html">The IAM page</a>; every command through the AWS CLI against the twin, in CI</td></tr>
      <tr><td><b>CORS per service</b> from a browser</td><td><span class="st st-poc">measured, no credentials</span></td><td>STS, Lambda, EC2, IAM, Logs, Cost Explorer and CloudFormation answer any origin with a preflight; S3 is blocked without a bucket rule. <a href="../articles/boto3-in-the-browser.html#cors">The table, with the data beside it</a></td></tr>
      <tr><td><b>boto3 under Pyodide</b> against the twin</td><td><span class="st st-poc">experiment, ran</span></td><td>Eleven SigV4-signed calls through one replaced transport, 10.0 s wall, 24.2 MB; one extra step, Pyodide's <code>ssl</code> package. <a href="../articles/boto3-in-the-browser.html#boto3">The brief</a></td></tr>
      <tr><td><b>IAM Roles Anywhere</b> from a browser</td><td><span class="st st-no">untested</span></td><td>The PKI path to explore</td></tr>
      <tr><td><b>Sync of the vault document through sgit</b></td><td><span class="st st-design">designed</span></td><td>Export and import by file today; the document is already the shape a vault holds</td></tr>
      <tr><td><b>ECS, Route 53, ECR, SSM</b> in the manifest</td><td><span class="st st-no">not in the interface</span></td><td>Each is a state key, a manifest entry and an ops entry; the Fargate template's stack output names the first gap</td></tr>
      <tr><td><b>The catalogue entry on twins.sgit.ai</b></td><td><span class="st st-no">requested</span></td><td><a href="../admin/index.html#requests">Requests to other sites</a></td></tr>
    </tbody>
  </table></div>

  <h2 id="numbers">2. The numbers, {DATE}</h2>
  <ul>
    <li>Interface: 8 AWS-shaped namespaces with 42 operations, and 1 twin-only namespace with 3.</li>
    <li>Tests: 214 assertions, 0 failing, under one second, <code>node admin/build/test.js</code>.</li>
    <li>Measured the same day, in the articles: CORS on ten endpoints, boto3 under Pyodide in three runs (10.0, 14.3 and 57.8 s wall, 24.2 MB each). Data under <code>articles/data/</code>.</li>
    <li>Code: four files under <code>assets/twin/</code>, no dependency, no build step, no third-party script. The page works from a file URL.</li>
    <li>The demo estate, after seeding: 2 accounts, 66 calls through the interface, and about 25 KB in localStorage before the first commit.</li>
  </ul>

  <h2 id="next">3. What is next, in order</h2>
  <ol>
    <li><b>Wire the live backend</b> with the SDK for JavaScript v3 for the eight services, as a fixed copy per site version, and write live reads back into the vault as commits.</li>
    <li><b>Browse a real account's buckets</b> with a list-only permission set, then read one bucket, directly and through the relay; record that session and replay it against the twin. (One live call with a real session was made on {DATE}: STS, from a laptop browser.)</li>
    <li><b>Sync the vault document</b> through sgit instead of a file, so a session's findings land in the user's vault and travel between devices.</li>
    <li><b>Add ECS</b> to the manifest so the Fargate template stops recording a gap, then Route 53, ECR and SSM as the first job needs them.</li>
    <li><b>Test Roles Anywhere</b> from a browser: a session from a certificate, as a backend.</li>
    <li><b>Catalogue this twin on the hub</b>, and move the hub's build-state table when the wire ships.</li>
  </ol>

  <h2 id="claims">4. What this does not claim</h2>
  <ul>
    <li><b>Nothing here calls AWS unless you give it a session.</b> The JavaScript proof of concept's live backend is a slot; the Python twin's live route calls AWS only with a session you paste, from your browser or your own machine, read-only in the S3 browser unless you allow writes. The service names identify interfaces the twin mirrors; AWS's real behaviour is richer and different in places, and the twin's behaviours are the ones a rehearsal needs, chosen, not derived from the service.</li>
    <li><b>The demo estate is illustrative.</b> The account ids are placeholders, the costs are invented round numbers, the AMI ids are not real. Nothing on this site is a measurement of an AWS account.</li>
    <li><b>Browser access was measured without credentials, per endpoint.</b> STS was then confirmed with a real session; S3 against a real bucket is still to do.</li>
    <li><b>The commit ids are not the vault's.</b> They are content hashes for the PoC; sgit's own hashes take over once the document is pushed.</li>
    <li><b>The templates are stand-ins.</b> They produce the shape of the SG/Send deployment, not the reviewed CloudFormation. The real templates are in beta on sgit.ai's AWS page.</li>
    <li><b>The quotes about sessions, CORS and Roles Anywhere are from AWS's documentation</b> as read on {DATE} for the article, and are paraphrased here; the article carries them verbatim.</li>
  </ul>
  <div class="pagenav"><a href="../naming/index.html">← Why aws.twin</a><a href="../admin/index.html">Admin &amp; engineering →</a></div>
</main>''')

# ---------------------------------------------------------------- admin/index.html
page('admin/index.html',
  'Admin & engineering — how this site is built, tested and released · aws.twin.sgit.ai',
  'The repository layout, how to run the AWS twin locally, the tests, the validator and name-watch, what is stored where, the release process, and the requests this site makes of other sites in the family.',
  f'''<main class="doc">
  <div class="crumb"><a href="../index.html">aws.twin.sgit.ai</a> / admin</div>
  <h1>Admin &amp; engineering</h1>
  <p class="lead">A static site and a browser application in one repository, with no build step to serve and two scripts to check. Source at <a href="https://github.com/SGit-AI/SGit-AI__Website__Twin__AWS">SGit-AI/SGit-AI__Website__Twin__AWS</a>.</p>

  <h2 id="layout">1. The repository</h2>
  <pre class="shell"><span class="g">index.html</span>                 the front page
<span class="g">twin/index.html</span>            the twin: the application page
<span class="g">design/ workflow/ naming/ shipped/</span>   the reference pages
<span class="g">assets/site.css  assets/nav.js</span>       the family's shared stylesheet and nav
<span class="cy">assets/twin/interface.js</span>   the interface: manifest, ops, StateBackend, MemoryBackend, LiveBackend, diff, graph
<span class="cy">assets/twin/vault.js</span>       VaultBackend over a key/value store, with commits; SessionStore
<span class="cy">assets/twin/templates.js</span>   the two deployment templates and the demo estate
<span class="cy">assets/twin/app.js  app.css</span> the UI
<span class="y">admin/build/test.js</span>        the interface tests (node)
<span class="y">admin/build/validate.js</span>    links, nav, versions, name-watch (node)
<span class="y">admin/build/version.txt</span>    the version, the only place it is typed
<span class="y">admin/build/release.py</span>     bump, build, check, commit, push, verify live
<span class="y">.github/workflows/</span>         deploy-pages.yml (gate, tag, publish), ci.yml (tests, browser)
<span class="d">briefs/  BRIEF-CORRECTIONS.md  REALITY.md  CNAME  sitemap.xml  robots.txt  llms.txt</span></pre>

  <h2 id="run">2. Run it</h2>
  <pre class="shell"><span class="d"># serve the tree; any static server does, and file:// works for the twin page too</span>
python3 -m http.server 8080
<span class="d"># then open http://localhost:8080/twin/index.html</span>

<span class="d"># the interface tests: the same script against the memory and vault backends</span>
node admin/build/test.js
<span class="d"># the site checks: internal links resolve, nav identical on every page, one version string, name-watch</span>
node admin/build/validate.js</pre>
  <p>Both scripts exit non-zero on a failure and are the release gate. There is no dependency to install: the twin's code runs in Node and in the browser unchanged.</p>

  <h2 id="storage">3. What the twin stores in the browser</h2>
  <div class="tablewrap"><table>
    <thead><tr><th>Key</th><th>Store</th><th>Holds</th></tr></thead>
    <tbody>
      <tr><td><code>aws.twin/vault</code></td><td>localStorage</td><td>The vault document: working state, commits, head. Exportable as JSON from the snapshots page; reset from the same page.</td></tr>
      <tr><td><code>aws.twin/session</code></td><td>sessionStorage</td><td>A pasted session, with its expiry, for the tab's lifetime. Cleared from the session page or by closing the tab.</td></tr>
      <tr><td><code>aws.twin/ui</code></td><td>localStorage</td><td>The chosen backend, account and region.</td></tr>
    </tbody>
  </table></div>
  <p>No cookies, no analytics, no request to any host: the twin page makes no network call after it loads.</p>

  <h2 id="validate">4. The validator, and the name-watch</h2>
  <p><code>admin/build/validate.js</code> walks every HTML page and checks: a title, a description and a canonical link; every relative <code>href</code> and <code>src</code> resolves to a file in the tree; the nav block is identical on every page once the <code>../</code> prefix is removed; the version string on every page matches the latest row of <a href="versions.html">the release history</a>; and the name-watch, the hub's check, that no capitalised <i>&lt;Word&gt; Twin</i> appears outside the allow-list of terms ruled on at <a href="https://twins.sgit.ai/naming/index.html">twins.sgit.ai/naming</a>. This site's own usage is lower case, <i>the AWS twin</i>, so the allow-list is the hub's four terms and nothing else.</p>

  <h2 id="release">5. Releases, tags and deployment</h2>
  <p>The same pipeline as every <code>*.sgit.ai</code> site, copied from the twins hub, and the release discipline in <a href="https://sgit.ai/docs/guidance/repositories.html">sgit.ai's repository guidance</a>:</p>
  <ul>
    <li><b>One version, in one file.</b> <code>admin/build/version.txt</code>; every page's badge, <code>assets/version.js</code> and <code>llms.txt</code> are built from it, and the gate fails if any disagree or if <a href="versions.html">the release history</a> lacks its row.</li>
    <li><b>Every push to <code>dev</code> is a release.</b> The commit subject reads <code>site vX.Y.Z: ...</code>; <code>.github/workflows/deploy-pages.yml</code> runs the gate, checks the subject and the file agree and that the bump is the next minor, tags the commit <code>vX.Y.Z</code>, and publishes the tree to GitHub Pages. A push to <code>main</code> deploys without tagging. A failed gate stops both.</li>
    <li><b>A release is done when the live site serves it.</b> <code>python3 admin/build/release.py "what changed"</code> bumps the version, builds, runs every check, commits with the right subject, pushes to <code>dev</code>, and polls <code>https://aws.twin.sgit.ai/assets/version.js</code> until it shows the new version.</li>
    <li><b>Where the work started.</b> <a href="../briefs/index.html">The briefs</a>, in full; <a href="../BRIEF-CORRECTIONS.md">the corrections</a>, including where this repository departs from the estate guidance; <a href="../REALITY.md">the reality file</a>, what exists.</li>
  </ul>
  <h2 id="requests">6. Requests to other sites</h2>
  <p>The naming decision touched four sites. The work on the others is theirs; it is listed here so that it is not lost, and ticked here when it is seen done.</p>
  <div class="tablewrap"><table>
    <thead><tr><th>Site</th><th>Request</th><th>State</th></tr></thead>
    <tbody>
      <tr><td>twins.sgit.ai</td><td>Add the paragraph <a href="../naming/index.html#ruling">proposed on the naming page</a> to the ruling: a twin's interface never holds credentials; a twin can have a live backend; the credential belongs to the backend. Keep the execution broker distinct.</td><td class="todo">open</td></tr>
      <tr><td>twins.sgit.ai</td><td>Become definition and hub: a "The twins" page or section cataloguing S3 (sg-compute ships it, working), AWS (<code>aws.twin.sgit.ai</code>, PoC), and the designed twins, each with its build state. Decide whether the S3 container gets <code>s3.twin.sgit.ai</code>. Update the front page's build-state table when the wire ships.</td><td class="todo">open</td></tr>
      <tr><td>twins.sgit.ai</td><td>Name-watch: no new term needed while this site writes <i>the AWS twin</i> in lower case; if a capitalised form is wanted, add it to the allow-list in <code>admin/build/validate.js</code> with its meaning.</td><td class="todo">open</td></tr>
      <tr><td>providers.sgit.ai</td><td>Fix the family to the singular convention: <code>elevenlabs.provider.sgit.ai</code>, <code>openrouter.provider.sgit.ai</code>, and the UnGovr repository description; point <code>*.provider.sgit.ai</code> and keep the plural hosts as redirects; switch the canonical hosts before <code>bin/sync-providers.py</code> locks in the plural form.</td><td class="todo">open</td></tr>
      <tr><td>newsroom.sgit.ai</td><td>In the article of {DATE}: replace <code>aws.sgit.ai</code> with <code>aws.twin.sgit.ai</code> in the title, abstract, body and Mermaid source; update "its name is not decided"; add the twin-first framing; link to twins.sgit.ai and the updated ruling.</td><td class="todo">open</td></tr>
      <tr><td>sgit.ai</td><td>Before any <code>aws.provider.sgit.ai</code> report, check the providers hub's "no commercial relationship" disclosure against <code>/partnerships/aws.html</code>.</td><td class="todo">open</td></tr>
    </tbody>
  </table></div>
  <div class="pagenav"><a href="../shipped/index.html">← Built, and designed</a><a href="versions.html">Release history →</a></div>
</main>''')

# ---------------------------------------------------------------- about/team.html
page('about/team.html',
  'The team · aws.twin.sgit.ai',
  'Who writes and builds aws.twin.sgit.ai: Dinis Cruz, and aws-twin.build, the site\'s build agent.',
  f'''<main class="doc">
  <div class="crumb"><a href="../index.html">aws.twin.sgit.ai</a> / about / team</div>
  <h1>The team</h1>
  <p class="lead">Two authors write on this site, and every byline says which. Neither claims the other's work.</p>
  <h2 id="dinis">Dinis Cruz</h2>
  <p>Runs the sgit project and decides what this site is for. Articles under his name are his voice memos and messages, written up by the build agent in his voice; <i>I</i> in them is him, and the editorial responsibility for everything on the site is his. <a href="https://sgit.ai/about/">About, on sgit.ai ↗</a></p>
  <h2 id="build">aws-twin.build</h2>
  <p>This site's build agent: a Claude Code session, run by Dinis, which built the site and the proof of concept on {DATE} and writes articles in its own voice about what it delivered, with the commits and the tests to check against. It is the only place on this site that names the model; the articles do not. What it decides alone is reversible, and it says so in each article. It did not read the S3 container's code, has not used the twin as a person would, and has made no call to AWS with real credentials.</p>
  <p>Write to either through <a href="mailto:agent@riskmandate.ai">agent@riskmandate.ai</a>, the address every article on the network ends with.</p>
  <div class="pagenav"><a href="../articles/index.html">← Articles</a><a href="../admin/index.html">Admin &amp; engineering →</a></div>
</main>''')

# ---------------------------------------------------------------- briefs/index.html
page('briefs/index.html',
  'The briefs · aws.twin.sgit.ai',
  'The briefs that commissioned aws.twin.sgit.ai, published in full and as written, with their status, and where the corrections to them live.',
  f'''<main class="doc">
  <div class="crumb"><a href="../index.html">aws.twin.sgit.ai</a> / briefs</div>
  <h1>The briefs</h1>
  <p class="lead">Every piece of work on this site started from a message of Dinis Cruz's. Each is published here in full and as written, including the voice memos as they were transcribed, and none is ever edited. Where one was wrong, transcribed differently from what was meant, or overtaken, the finding is in <a href="../BRIEF-CORRECTIONS.md">the corrections</a>; what exists is in <a href="../REALITY.md">the reality file</a>.</p>
  <div class="tablewrap"><table>
    <thead><tr><th>Brief</th><th>Date</th><th>What it asked</th><th>Status</th></tr></thead>
    <tbody>
      <tr><td><a href="2026-10-21__01__the-first-go.md">1. The first go</a></td><td>2026-10-21</td><td>The site and a proof of concept from the newsroom article and the naming decision; the naming document in full</td><td><span class="st st-built">built, v0.1.0</span></td></tr>
      <tr><td><a href="2026-10-21__02__articles-and-the-research-brief.md">2. Try it, and write it up</a></td><td>2026-10-21</td><td>An article in the agent's name, a research brief in Dinis's: the JavaScript SDK's maturity, boto3 in the browser</td><td><span class="st st-built">built, v0.2.0</span></td></tr>
      <tr><td><a href="2026-10-21__03__the-python-twin.md">3. The Python twin</a></td><td>2026-10-21</td><td>An S3 browser on Python, OSBot-AWS in the browser, the same tests in CI and the browser, the twin in Python, AWS sessions</td><td><span class="st st-built">built, v0.3.0</span> <span class="st st-design">Cognito measured, not built</span></td></tr>
      <tr><td><a href="2026-10-23__08__the-console.md">8. The console</a></td><td>2026-10-23</td><td>A console, a page per service, the mode top left; a Lambda viewer first; a request pane that shows everything; a way to browse the twin's data; a plan for the vault; which calls work from the CLI, code, Pyodide and the JS SDK, and a Postman-like way to send and replay them</td><td><span class="st st-built">built, v0.4.2</span> <span class="st st-design">vault: planned</span></td></tr>
      <tr><td><a href="2026-10-23__07__uptime-lambda-in-every-region.md">7. An uptime Lambda in every region</a></td><td>2026-10-23</td><td>A plan, then the build: twins for Lambda and CloudFront, a function that checks websites from many regions and appends PKI-encrypted results to an sgit lane, tested from the page with boto3; Python or Node.js, no dependencies</td><td><span class="st st-built">phase 1 built, v0.4.1</span> <span class="st st-design">live deploy: phase 2</span></td></tr>
      <tr><td><a href="2026-10-21__06__versions-and-the-browser-only-question.md">6. Versions, and doing it from the browser</a></td><td>2026-10-21</td><td>dev releases minors, main releases majors; how a browser request differs from any other; listing buckets without the relay</td><td><span class="st st-built">versioning built, v0.4.1</span> <span class="st st-design">Cloud Control listing: proposed</span></td></tr>
      <tr><td><a href="2026-10-21__05__live-session-least-privilege-and-how-it-works.md">5. A live session, least privilege, how it works</a></td><td>2026-10-21</td><td>Browse real files with the pasted session in the S3 browser; guidance and commands for IAM Identity Center users that can only list buckets or read one; an article on the milestone; a step-by-step explanation of the relay, with diagrams</td><td><span class="st st-built">built, v0.4.0</span> <span class="st st-design">real-account S3 browse: next</span></td></tr>
      <tr><td><a href="2026-10-21__04__deploy-and-the-guidance.md">4. Deploy, and the guidance</a></td><td>2026-10-21</td><td>Deploy on push to <code>dev</code>; follow sgit.ai's guidance for <code>*.sgit.ai</code> sites, including tagging</td><td><span class="st st-built">built, v0.3.1</span></td></tr>
    </tbody>
  </table></div>
  <p class="small dim">The briefs are markdown files, served as written. Content CC BY 4.0.</p>
  <div class="pagenav"><a href="../admin/index.html">← Admin &amp; engineering</a><a href="../admin/versions.html">Release history →</a></div>
</main>''')

# ---------------------------------------------------------------- admin/versions.html
page('admin/versions.html',
  'Release history · aws.twin.sgit.ai',
  'Every release of aws.twin.sgit.ai, with what changed.',
  f'''<main class="doc">
  <div class="crumb"><a href="../index.html">aws.twin.sgit.ai</a> / <a href="index.html">admin</a> / versions</div>
  <h1>Release history</h1>
  <p class="lead">One row per release. The version in the nav and footer of every page must match the top row, and the validator checks that it does.</p>
  <div class="tablewrap"><table class="vers">
    <thead><tr><th>Version</th><th>Date</th><th>What changed</th></tr></thead>
    <tbody>
      <tr><td class="vnum">v0.4.2</td><td>2026-10-23</td><td>The console: <a href="../console/index.html">/console/</a>, a page per service (Overview, S3, Lambda, All resources, Calls, Twin data), twin or live switched top left, the region beside it, and a request pane on the right with every call and every request, its headers and bodies, a replay in the call editor, and, for a live read, what the twin would have answered. Lambda: functions per region, a scan of every region, configuration, environment, triggers, URL, code, a test invoke, logs, permissions. All resources and the S3 bucket list go through the Cloud Control API, which answers a browser. <a href="../console/calls.html">Calls</a>: 34 operations measured five ways (AWS CLI, boto3, boto3 under Pyodide, the AWS SDK for JavaScript, the twin); in a browser only three S3 calls are blocked, for both libraries alike; a call editor for any operation. A Cloud Control twin. The S3 twin refuses a bucket created at the wrong regional endpoint, as S3 does, which found the same bug in the S3 browser. botocore pinned with boto3. <a href="../console/plan.html">The plan, and the vault</a>.</td></tr>
      <tr><td class="vnum">v0.4.1</td><td>2026-10-23</td><td>Uptime checks in every region, twin first. A Node.js 22 Lambda function, one file with no dependencies, that checks websites and appends each report, encrypted as sgit's envelope v2 (RSA-OAEP SHA-256 wrapping AES-256-GCM, decrypted in CI by sgit's own construction), to an sgit append lane; scheduled by EventBridge, invokable with IAM, and through a function URL only with a controller-signed request. New twins: Lambda (running Node.js functions through one harness, with node in CI and the browser's JSPI in the page, and Python in process), IAM roles, EventBridge rules, CloudFront distributions, the sgit append lane and the internet a function reaches. <code>Uptime__Deploy</code>: one boto3 deploy for the twin and the account, to any number of regions. <a href="../uptime/index.html">The uptime page</a> and <a href="../uptime/plan.html">the plan</a>. Versions: a push to <code>dev</code> may only bump the minor, a push to <code>main</code> only the major; v0.4.0, released from <code>dev</code>, was the last exception. Browser tests run on a secure origin.</td></tr>
      <tr><td class="vnum">v0.4.0</td><td>{DATE}</td><td>Live, from the browser. The S3 browser goes live with the session pasted in the same tab: directly where AWS allows this site's origin (a bucket with a CORS rule), and through <code>Twin__Relay.py</code>, a one-file local relay that holds no credentials, for what S3 never answers a browser, such as ListBuckets. Read-only unless writes are allowed. <a href="../how-it-works/index.html">How it works</a>, step by step, with diagrams written in Mermaid and rendered to SVG at build time. <a href="../iam/index.html">Least privilege for the twin</a>: four S3 permission sets as policy files, the IAM Identity Center CLI, checked through the AWS CLI in CI (<code>check_cli.py</code>). The article <a href="../articles/a-live-aws-session-from-a-browser-tab.html">A live AWS session from a browser tab</a>, after the first real session was checked against AWS STS from this site. Three live-path bugs fixed before any real use: chunked uploads hung, uploads went empty, downloads failed.</td></tr>
      <tr><td class="vnum">v0.3.1</td><td>{DATE}</td><td>Deployed, and tagged on every release. aws.twin.sgit.ai resolved to GitHub Pages and answered 404, because this repository had no deploy workflow; <code>deploy-pages.yml</code> is now the twins hub's own (validate, tag <code>vX.Y.Z</code> on every push to <code>dev</code>, publish), with this site's tests added to its gate. The version lives in <code>admin/build/version.txt</code>; <code>CNAME</code>, <code>assets/version.js</code>, a markdown twin for every page, <code>sitemap.xml</code> and <code>robots.txt</code> added; the four briefs published in full; <code>BRIEF-CORRECTIONS.md</code> and <code>REALITY.md</code> written; a release script that checks the live site. Also ships <code>308b2ae</code>, which committed the build scripts a <code>.gitignore</code> rule had hidden. Releases v0.1.0 to v0.3.0 were tagged by hand.</td></tr>
      <tr><td class="vnum">v0.3.0</td><td>{DATE}</td><td>The twin moves to Python. <code>aws_twin</code>: S3's REST-XML protocol and STS GetCallerIdentity over a Python mirror of sg-vfs, a botocore hook with twin, live and replay routes, a local endpoint, traffic recording. One test suite, run by pytest in CI and by Pyodide in the browser. OSBot-AWS runs against it unchanged in both. <a href="../s3/index.html">The S3 browser</a>, every button a Python call, persisted through sg-vfs's IndexedDB provider (vendored). <a href="../sessions/index.html">AWS sessions</a>: setup, paste and a live check, and measured CORS for the better methods. The article <a href="../articles/the-twin-is-python-now.html">The twin is Python now</a>. CI on GitHub Actions.</td></tr>
      <tr><td class="vnum">v0.2.0</td><td>{DATE}</td><td>The articles section, in the newsroom's format: <a href="../articles/first-go-at-the-aws-twin.html">A first go at the AWS twin</a> (the build agent, in its own voice) and <a href="../articles/boto3-in-the-browser.html">boto3 in the browser</a> (Dinis Cruz, from a voice memo: the JavaScript SDK's maturity, boto3 under Pyodide against the twin, and the CORS measurement). The experiments and their data under <code>articles/data/</code>. The team page. Build-state rows updated for what was measured.</td></tr>
      <tr><td class="vnum">v0.1.0</td><td>{DATE}</td><td>First release. The site: front page, design, workflow, naming, status, admin. The proof of concept: the interface (8 AWS-shaped namespaces, 42 operations, plus 3 twin-only), the vault backend on localStorage with commits and diff, the memory backend, the live backend's session slot, two deployment templates, the demo estate, the account graph, and the UI. 214 test assertions. Captured the naming decision of the same day: <code>aws.twin.sgit.ai</code>, repo <code>SGit-AI__Website__Twin__AWS</code>, hub <code>twins.sgit.ai</code>.</td></tr>
    </tbody>
  </table></div>
  <div class="pagenav"><a href="index.html">← Admin &amp; engineering</a><a href="../index.html">The front page →</a></div>
</main>''')

# ---------------------------------------------------------------- python/tests.html
page('python/tests.html',
  'The twin\'s tests, in this browser · aws.twin.sgit.ai',
  'The Python twin\'s test suite, the same files CI runs with pytest, run in the browser under Pyodide with boto3, OSBot-Utils and OSBot-AWS.',
  body_of('python-tests.html'))

# ---------------------------------------------------------------- s3/index.html: moved into the console
page('s3/index.html',
  'S3 browser, now in the console · aws.twin.sgit.ai',
  'The S3 browser is now the console\'s S3 page.',
  '''<main class="doc">
  <div class="crumb"><a href="../index.html">aws.twin.sgit.ai</a> / s3</div>
  <h1>The S3 browser is now part of the console</h1>
  <p class="lead">Same buckets, same objects, the same twin store in this browser: <a href="../console/s3.html">the console's S3 page</a>, beside Lambda, every other resource type, and a pane that shows every request.</p>
</main>
<script>location.replace('../console/s3.html' + location.hash);</script>''')

# ---------------------------------------------------------------- console/
CONSOLE_TABS = [('index', 'Overview'), ('s3', 'S3'), ('lambda', 'Lambda'), ('resources', 'All resources'), ('calls', 'Calls'), ('twin', 'Twin data')]

def console_page(name, title, desc, intro):
    tabs = ''.join(f'<a href="{n}.html"{" class=" + chr(34) + "here" + chr(34) if n == name else ""}>{label}</a>' for n, label in CONSOLE_TABS)
    module = 'overview' if name == 'index' else name
    body = f'''<main class="cx">
  <p class="cx-intro">{intro} <a href="plan.html">The plan →</a></p>
  <div class="s3 cx-shell">
    <div class="s3-top cx-top">
      <div class="cx-mode" id="cx-mode" title="Where calls go: the twin in this page, or the account with the session from the sessions page"><button type="button" data-mode="twin" class="on">Twin</button><button type="button" data-mode="live">Live</button></div>
      <nav class="cx-tabs" aria-label="Console">{tabs}</nav>
      <span class="grow"></span>
      <span class="pill" id="cx-who">loading…</span>
      <label>Region <select id="cx-region"><option>eu-west-2</option></select></label>
      <span class="pill" id="cx-state">loading Python…</span>
      <button class="cx-pane-btn" type="button" data-cx="pane" title="Every call and every request, twin or live">Requests<span id="cx-count">0</span></button>
    </div>
    <div id="cx-live-form" hidden></div>
    <div class="cx-body">
      <div class="s3-main" id="cx-app"><div class="s3-loading">Starting Python, boto3 and the twin in this page (about 25 MB the first time, then from the browser's cache)…<br><pre class="steps" id="cx-steps"></pre></div></div>
      <aside class="cx-pane" id="cx-pane" hidden aria-label="Requests">
        <div class="cx-pane-h"><b>Requests</b><button type="button" data-cx="pane-clear">Clear</button><button type="button" data-cx="pane-export">Export JSON</button><button type="button" data-cx="pane">Close</button><input id="cx-pane-filter" placeholder="filter: service.op, twin or live, an error code" autocomplete="off"></div>
        <div class="cx-pane-note">One line per Python call, newest first; open it for the requests it sent (to the twin, or to AWS) and open a request for its headers and bodies, a replay, and, for a live read, what the twin would have answered.</div>
        <div id="cx-pane-list"></div>
      </aside>
    </div>
  </div>
  <noscript><div class="s3-flash err">The console is Python running in this page through Pyodide; it needs JavaScript.</div></noscript>
</main>
<script src="../assets/py/twin-pyodide.js"></script>
<script type="module" src="../assets/console/page-{module}.js"></script>'''
    page(f'console/{name}.html', title, desc, body, extra_head='<link rel="stylesheet" href="../assets/console/console.css">\n')

console_page('index', 'Console · aws.twin.sgit.ai',
  'The AWS twin\'s console: S3, Lambda and every other resource type, against the twin in this page or a live account, with every request visible.',
  'The console: one page per service, every button a Python call (boto3 and OSBot-AWS) answered by the twin in this page, or by an account in live mode.')
console_page('s3', 'S3 · console · aws.twin.sgit.ai',
  'Buckets and objects in the twin or a live account; live, buckets are listed through the Cloud Control API because S3\'s ListBuckets never answers a browser.',
  'S3: buckets, objects, upload, properties. Live, buckets are listed through Cloud Control, every region\'s; a bucket\'s objects need a CORS rule on it.')
console_page('lambda', 'Lambda · console · aws.twin.sgit.ai',
  'Lambda functions per region and across every region, with each function\'s configuration, code, permissions, triggers, logs and a test invoke, in the twin or a live account.',
  'Lambda: functions per region, a scan of every region, each function\'s configuration, code, test, logs and permissions. In the twin the functions really run.')
console_page('resources', 'All resources · console · aws.twin.sgit.ai',
  'Any AWS resource type, listed and read through the Cloud Control API from the browser, against the twin or a live account.',
  'All resources: any type, through the Cloud Control API, which answers a browser from any origin.')
console_page('calls', 'Calls: what works where · console · aws.twin.sgit.ai',
  'Which AWS calls work from the AWS CLI, boto3, boto3 in the browser under Pyodide, the AWS SDK for JavaScript in the browser, and the twin, measured; and a call editor to send any operation by hand.',
  'Calls: the same AWS calls made five ways, measured, and an editor to send any operation of any service, or replay one from the request pane.')
console_page('twin', 'Twin data · console · aws.twin.sgit.ai',
  'What the AWS twin holds in this browser, file by file: buckets, functions, roles, rules, distributions, lanes.',
  'Twin data: the twin\'s store in this browser, as files.')
page('console/plan.html',
  'The console plan, and the vault · aws.twin.sgit.ai',
  'What the console is for, how it is built, what works where, what is next, and the plan for keeping the twin\'s state in an sgit vault.',
  body_of('console-plan.html'))

# ---------------------------------------------------------------- python/index.html
page('python/index.html',
  'The Python twin · aws.twin.sgit.ai',
  'The AWS twin in Python: AWS wire protocols answered from a virtual file system, the same package in CI, as a local endpoint, and in the browser under Pyodide.',
  body_of('python.html'))

# ---------------------------------------------------------------- sessions/index.html
page('sessions/index.html',
  'AWS sessions · aws.twin.sgit.ai',
  'Set up IAM Identity Center for one-hour sessions, paste one and check it against AWS from the browser, and the measured comparison of better ways: the SSO device code, Cognito identity pools, web identity and Roles Anywhere.',
  body_of('sessions.html'))

# ---------------------------------------------------------------- iam/index.html
page('iam/index.html',
  'Least privilege for the twin: IAM Identity Center users, groups and permission sets · aws.twin.sgit.ai',
  'Set up IAM Identity Center so the session you paste every day can only list bucket names, read one bucket, read one folder, or read and write one bucket: the policies as files, the CLI commands checked, testing before assigning, and moving the administrator role out of daily reach.',
  body_of('iam.html'))

# ---------------------------------------------------------------- how-it-works/index.html
page('how-it-works/index.html',
  'How it works: a live AWS session in a browser tab, step by step · aws.twin.sgit.ai',
  'What happens when the S3 browser goes live: Python in the tab, signing, the twin\'s hook and its routes, what CORS allows, the local relay and what it can see, the local-network prompt, the read-only guard, and how each was checked. With diagrams.',
  body_of('how-it-works.html'))

# ---------------------------------------------------------------- uptime/
page('uptime/index.html',
  'Uptime checks from every region · aws.twin.sgit.ai',
  'Deploy a Lambda function that checks whether websites are up, to as many AWS regions as you choose, on a schedule, with each report encrypted to a vault key and appended to an sgit lane. boto3 in the page, against the twin or your account.',
  body_of('uptime.html'),
  extra_head='<link rel="stylesheet" href="../assets/uptime/uptime.css">\n')
page('uptime/plan.html',
  'The plan: uptime checks in every region · aws.twin.sgit.ai',
  'The plan for the uptime Lambda, written before the code: why Node.js 22 (WebCrypto, no dependencies), the function, the twins it needs (Lambda, IAM, EventBridge, CloudFront, the sgit append lane, the internet), the deployment, the page, the phases and what to watch.',
  body_of('uptime-plan.html'))

# ---------------------------------------------------------------- assets/version.js
# what the release script polls on the live site, and what a page can read at run time
with open(os.path.join(ROOT, 'assets', 'version.js'), 'w', encoding='utf-8') as f:
    f.write(f'window.SITE_VERSION = "{VER}";\n')
print('wrote assets/version.js', VER)
