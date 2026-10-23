<!-- the markdown twin of https://aws.twin.sgit.ai/admin/index.html, generated from the same source by admin/build/pages.py; site v0.4.2; content CC BY 4.0 -->

[aws.twin.sgit.ai](../index.md) / admin

# Admin & engineering

A static site and a browser application in one repository, with no build step to serve and two scripts to check. Source at [SGit-AI/SGit-AI__Website__Twin__AWS](https://github.com/SGit-AI/SGit-AI__Website__Twin__AWS).

## 1. The repository

```
index.html                 the front page
twin/index.html            the twin: the application page
design/ workflow/ naming/ shipped/   the reference pages
assets/site.css  assets/nav.js       the family's shared stylesheet and nav
assets/twin/interface.js   the interface: manifest, ops, StateBackend, MemoryBackend, LiveBackend, diff, graph
assets/twin/vault.js       VaultBackend over a key/value store, with commits; SessionStore
assets/twin/templates.js   the two deployment templates and the demo estate
assets/twin/app.js  app.css the UI
admin/build/test.js        the interface tests (node)
admin/build/validate.js    links, nav, versions, name-watch (node)
admin/build/version.txt    the version, the only place it is typed
admin/build/release.py     bump, build, check, commit, push, verify live
.github/workflows/         deploy-pages.yml (gate, tag, publish), ci.yml (tests, browser)
briefs/  BRIEF-CORRECTIONS.md  REALITY.md  CNAME  sitemap.xml  robots.txt  llms.txt
```

## 2. Run it

```
# serve the tree; any static server does, and file:// works for the twin page too
python3 -m http.server 8080
# then open http://localhost:8080/twin/index.html

# the interface tests: the same script against the memory and vault backends
node admin/build/test.js
# the site checks: internal links resolve, nav identical on every page, one version string, name-watch
node admin/build/validate.js
```

Both scripts exit non-zero on a failure and are the release gate. There is no dependency to install: the twin's code runs in Node and in the browser unchanged.

## 3. What the twin stores in the browser

| Key | Store | Holds |
|---|---|---|
| `aws.twin/vault` | localStorage | The vault document: working state, commits, head. Exportable as JSON from the snapshots page; reset from the same page. |
| `aws.twin/session` | sessionStorage | A pasted session, with its expiry, for the tab's lifetime. Cleared from the session page or by closing the tab. |
| `aws.twin/ui` | localStorage | The chosen backend, account and region. |

No cookies, no analytics, no request to any host: the twin page makes no network call after it loads.

## 4. The validator, and the name-watch

`admin/build/validate.js` walks every HTML page and checks: a title, a description and a canonical link; every relative `href` and `src` resolves to a file in the tree; the nav block is identical on every page once the `../` prefix is removed; the version string on every page matches the latest row of [the release history](versions.md); and the name-watch, the hub's check, that no capitalised *<Word> Twin* appears outside the allow-list of terms ruled on at [twins.sgit.ai/naming](https://twins.sgit.ai/naming/index.html). This site's own usage is lower case, *the AWS twin*, so the allow-list is the hub's four terms and nothing else.

## 5. Releases, tags and deployment

The same pipeline as every `*.sgit.ai` site, copied from the twins hub, and the release discipline in [sgit.ai's repository guidance](https://sgit.ai/docs/guidance/repositories.html):

- **One version, in one file.** `admin/build/version.txt`; every page's badge, `assets/version.js` and `llms.txt` are built from it, and the gate fails if any disagree or if [the release history](versions.md) lacks its row.
- **Every push to `dev` is a release.** The commit subject reads `site vX.Y.Z: ...`; `.github/workflows/deploy-pages.yml` runs the gate, checks the subject and the file agree and that the bump is the next minor, tags the commit `vX.Y.Z`, and publishes the tree to GitHub Pages. A push to `main` deploys without tagging. A failed gate stops both.
- **A release is done when the live site serves it.** `python3 admin/build/release.py "what changed"` bumps the version, builds, runs every check, commits with the right subject, pushes to `dev`, and polls `https://aws.twin.sgit.ai/assets/version.js` until it shows the new version.
- **Where the work started.** [The briefs](../briefs/index.md), in full; [the corrections](../BRIEF-CORRECTIONS.md), including where this repository departs from the estate guidance; [the reality file](../REALITY.md), what exists.

## 6. Requests to other sites

The naming decision touched four sites. The work on the others is theirs; it is listed here so that it is not lost, and ticked here when it is seen done.

| Site | Request | State |
|---|---|---|
| twins.sgit.ai | Add the paragraph [proposed on the naming page](../naming/index.md#ruling) to the ruling: a twin's interface never holds credentials; a twin can have a live backend; the credential belongs to the backend. Keep the execution broker distinct. | open |
| twins.sgit.ai | Become definition and hub: a "The twins" page or section cataloguing S3 (sg-compute ships it, working), AWS (`aws.twin.sgit.ai`, PoC), and the designed twins, each with its build state. Decide whether the S3 container gets `s3.twin.sgit.ai`. Update the front page's build-state table when the wire ships. | open |
| twins.sgit.ai | Name-watch: no new term needed while this site writes *the AWS twin* in lower case; if a capitalised form is wanted, add it to the allow-list in `admin/build/validate.js` with its meaning. | open |
| providers.sgit.ai | Fix the family to the singular convention: `elevenlabs.provider.sgit.ai`, `openrouter.provider.sgit.ai`, and the UnGovr repository description; point `*.provider.sgit.ai` and keep the plural hosts as redirects; switch the canonical hosts before `bin/sync-providers.py` locks in the plural form. | open |
| newsroom.sgit.ai | In the article of 2026-10-21: replace `aws.sgit.ai` with `aws.twin.sgit.ai` in the title, abstract, body and Mermaid source; update "its name is not decided"; add the twin-first framing; link to twins.sgit.ai and the updated ruling. | open |
| sgit.ai | Before any `aws.provider.sgit.ai` report, check the providers hub's "no commercial relationship" disclosure against `/partnerships/aws.html`. | open |

[← Built, and designed](../shipped/index.md)[Release history →](versions.md)

---

*[This page as HTML](https://aws.twin.sgit.ai/admin/index.html) · [The site for agents](https://aws.twin.sgit.ai/llms.txt) · CC BY 4.0*
