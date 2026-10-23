# SGit-AI__Website__Twin__AWS

The repository for **aws.twin.sgit.ai**: the AWS twin.

An AWS-shaped interface (S3, Lambda, EC2, IAM, billing, logs, CloudFormation) whose
backend is a vault, so that everything built against the twin works against the live
account once a temporary IAM Identity Center session is put in front of the same
interface as a second backend. One instance in the twins family; the primitive is defined
on [twins.sgit.ai](https://twins.sgit.ai). The design comes from the article
[AWS from the vault](https://newsroom.sgit.ai/articles/aws-from-the-vault.html)
(21 October 2026) and the naming decision of the same day.

Since v0.3.0 the twin is **Python** (`aws_twin/`): it answers AWS's wire protocols (S3
REST-XML, STS GetCallerIdentity) from a virtual file system, so boto3, OSBot-AWS and the AWS
CLI reach it unchanged. The same package and the same tests run under pytest in CI and
under Pyodide in the browser, where it powers the console (`console/`). A live route per
service sends chosen calls on to the real account with a pasted session; the sessions page
(`sessions/`) checks one against AWS STS from the browser, and since v0.4.0 the S3 browser goes
live, directly or through a one-file local relay (`aws_twin/core/Twin__Relay.py`) for what S3
will not answer a browser. `how-it-works/` explains the live path step by step; `iam/` is the
least-privilege guidance. Since v0.4.2 `console/` is where it is used: a page per service, twin or
live, a request pane, Lambda, every resource type through Cloud Control, and `console/calls.html`,
which measures which calls work from the CLI, code, Pyodide and the JS SDK. Since v0.4.1 the twin also has IAM roles, Lambda (running the deployed code),
EventBridge, CloudFront and sgit's append lane, and `uptime/` deploys an uptime-check function to many
regions with boto3 (`aws_twin/apps/uptime/`), against the twin or an account. The first, JavaScript
proof of concept is still at `twin/`.

```sh
pip install boto3 osbot-aws osbot-utils pytest
pip install cryptography             # test-only: the uptime tests decrypt reports as sgit does
python -m pytest                     # 41 pass (node on the PATH runs the Node.js functions); AWS_TWIN_LIVE_TESTS=1 adds live calls
python aws_twin/core/Twin__Relay.py  # the local relay, for the S3 browser's live mode (127.0.0.1:4567)
python -m aws_twin --port 4566       # the twin as a local endpoint: export AWS_ENDPOINT_URL=http://127.0.0.1:4566
```

```python
from aws_twin import Twin
with Twin() as twin:                 # every botocore request now goes to the twin
    from osbot_aws.aws.s3.S3 import S3
    S3().bucket_create('my-bucket', 'eu-west-2')
    print(twin.traffic.summary())
```

## Layout

```
aws_twin/                       the Python twin: core (router, botocore hook, traffic, replay, server), s3, sts, vfs, web
tests/                          its tests: plain functions, run by pytest and by tests/browser_runner.py in Pyodide
pyproject.toml                  the package; no runtime dependency
index.html                      the front page
console/                        the console: index s3 lambda resources calls twin plan (.html), assets/console/
sessions/index.html             AWS sessions: setup, paste, a live check, better methods measured
iam/index.html  iam/policies/   least privilege: S3 permission sets, the CLI, the bucket CORS rule
how-it-works/index.html         the live path step by step, with diagrams
uptime/index.html  plan.html    uptime checks in every region: the page, and the plan written before it
aws_twin/apps/uptime/           the uptime function (handler/index.mjs, Node.js 22) and Uptime__Deploy.py
python/index.html  tests.html   the Python twin, and its tests in the browser
twin/index.html                 the JavaScript proof of concept
design/ workflow/ naming/ shipped/   the reference pages
assets/site.css  assets/nav.js  the family's shared stylesheet and nav
assets/twin/interface.js        the interface: manifest, ops, StateBackend, MemoryBackend, LiveBackend, diff, graph
assets/twin/vault.js            VaultBackend over a key/value store, with commits; SessionStore
assets/twin/templates.js        the two deployment templates and the demo estate
assets/twin/app.js  app.css     the JavaScript proof of concept's UI
assets/py/                      the Pyodide loader and aws_twin.zip, the bundle the browser unpacks
assets/console/                 the console's code: core.js, a page-*.js per page, console.css, call-matrix.json
assets/vendor/sg-vfs/v0.1.0/    sg-vfs from SGraph-AI__Tools, vendored unchanged
articles/                       the articles (built), their data under data/, figures under images/
admin/content/articles/*.md     the articles' sources, in the newsroom's format
admin/build/pages.py            builds every hand-written page with one nav and footer (bodies in admin/content/pages/)
admin/build/articles.py         builds articles/ from the sources; the gate for the writing rules
admin/build/py_bundle.py        builds assets/py/aws_twin.zip; --check fails if it is stale
admin/build/diagrams.js         renders admin/content/diagrams/*.mmd (Mermaid) to assets/diagrams/*.svg
admin/build/check_cli.py        runs every AWS CLI command the pages print through the AWS CLI, against the twin
admin/build/browser_tests.js    runs the Python tests in headless Chromium under Pyodide
admin/build/test.js             the interface tests (node, no dependencies)
admin/build/validate.js         the gate: version, canonical host, links, nav, twins, orphans, licence, name-watch, leak tripwire
admin/build/version.txt         the version, the only place it is typed
admin/build/release.py          bump, build, check, commit, push, verify live
admin/build/md_twin.py  gen_sitemap.py   the markdown twins and sitemap.xml
briefs/  BRIEF-CORRECTIONS.md  REALITY.md   the briefs in full, the corrections, what exists
admin/versions.html  llms.txt  CNAME  sitemap.xml  robots.txt
```

## Run

```sh
python3 -m http.server 8080          # any static server; file:// works for the twin page too
# open http://localhost:8080/twin/index.html

python3 admin/build/pages.py         # build the pages
python3 admin/build/articles.py      # build articles/ from admin/content/articles/
python3 admin/build/py_bundle.py     # rebuild the browser bundle after changing aws_twin/ or tests/
node admin/build/browser_tests.js    # the Python tests in a browser (needs Playwright)
node admin/build/test.js             # the same script against the memory and vault backends
node admin/build/validate.js         # the site checks; CI runs all of these (.github/workflows/ci.yml)
node admin/build/uptime_page_test.js # the uptime page end to end against the twin (needs Playwright)
node admin/build/console_test.js     # the console end to end; MEASURE=1 RECORD=1 also measures the browser columns
python3 admin/build/call_matrix.py   # the calls page's CLI, code and twin columns (needs network to AWS)
node admin/build/diagrams.js         # after editing a diagram (needs Playwright and cdn.jsdelivr.net)
AWS_CLI=aws python3 admin/build/check_cli.py   # after editing a command on the IAM or sessions page
```

No build step to serve and no dependency. Third-party code only where a page says so: Pyodide and wheels from PyPI on the twin's pages, and the AWS SDK for JavaScript on the calls page when it measures (the diagrams are SVG, rendered when the site is built). The
twin's code is UMD and runs unchanged in Node and in the browser. The one page that loads
from elsewhere is the experiment under `articles/data/boto3-twin.html` (Pyodide from
cdn.jsdelivr.net, boto3 from PyPI), which an article was written from.

## Release

Every push to `dev` is a minor release (v0.4.1, v0.4.2) and every push to `main` a major one
(v0.5.0); the workflow refuses any other bump. Each is deployed to GitHub Pages and tagged by
`.github/workflows/deploy-pages.yml` (copied from the twins hub): the gate runs, the commit
subject must read `site vX.Y.Z: ...` and agree with `admin/build/version.txt`, the commit is
tagged `vX.Y.Z`, and the tree is published to https://aws.twin.sgit.ai.

1. Add the release's row to the history in `admin/build/pages.py` (one sentence: what changed and why).
2. `python3 admin/build/release.py "what changed"`: bumps the minor in `version.txt`, builds, runs
   every check, commits as `site vX.Y.Z: what changed`, pushes to `dev`, and polls
   https://aws.twin.sgit.ai/assets/version.js until it serves the new version.

The briefs this site was built from are in `briefs/`, in full; where they were wrong, and
where this repository departs from [sgit.ai's repository guidance](https://sgit.ai/docs/guidance/repositories.html),
is in `BRIEF-CORRECTIONS.md`; what exists is in `REALITY.md`.

## What the twin stores in the browser

| Key                | Store          | Holds                                                     |
|--------------------|----------------|-----------------------------------------------------------|
| `aws.twin/vault`   | localStorage   | the vault document: working state, commits, head           |
| `aws.twin/session` | sessionStorage | a pasted session with its expiry, for the tab's lifetime   |
| `aws.twin/ui`      | localStorage   | the chosen backend, account and region                     |
| `aws-twin-s3`      | IndexedDB      | the twin's store, as sg-vfs entries, shared by every console page |
| `aws.twin/console-mode`, `aws.twin/editor-history` | sessionStorage | the console's mode (twin or live) and the call editor's history, for the tab |
| `aws.twin/console-region`, `aws.twin/console-pane` | localStorage | the console's region, and whether the request pane is open |

## Licence

Content CC BY 4.0; code Apache-2.0 (see `LICENSE`).
