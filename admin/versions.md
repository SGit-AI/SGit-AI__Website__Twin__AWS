<!-- the markdown twin of https://aws.twin.sgit.ai/admin/versions.html, generated from the same source by admin/build/pages.py; site v0.4.0; content CC BY 4.0 -->

[aws.twin.sgit.ai](../index.md) / [admin](index.md) / versions

# Release history

One row per release. The version in the nav and footer of every page must match the top row, and the validator checks that it does.

| Version | Date | What changed |
|---|---|---|
| v0.4.0 | 2026-10-21 | Live, from the browser. The S3 browser goes live with the session pasted in the same tab: directly where AWS allows this site's origin (a bucket with a CORS rule), and through `Twin__Relay.py`, a one-file local relay that holds no credentials, for what S3 never answers a browser, such as ListBuckets. Read-only unless writes are allowed. [How it works](../how-it-works/index.md), step by step, with diagrams written in Mermaid and rendered to SVG at build time. [Least privilege for the twin](../iam/index.md): four S3 permission sets as policy files, the IAM Identity Center CLI, checked through the AWS CLI in CI (`check_cli.py`). The article [A live AWS session from a browser tab](../articles/a-live-aws-session-from-a-browser-tab.md), after the first real session was checked against AWS STS from this site. Three live-path bugs fixed before any real use: chunked uploads hung, uploads went empty, downloads failed. |
| v0.3.1 | 2026-10-21 | Deployed, and tagged on every release. aws.twin.sgit.ai resolved to GitHub Pages and answered 404, because this repository had no deploy workflow; `deploy-pages.yml` is now the twins hub's own (validate, tag `vX.Y.Z` on every push to `dev`, publish), with this site's tests added to its gate. The version lives in `admin/build/version.txt`; `CNAME`, `assets/version.js`, a markdown twin for every page, `sitemap.xml` and `robots.txt` added; the four briefs published in full; `BRIEF-CORRECTIONS.md` and `REALITY.md` written; a release script that checks the live site. Also ships `308b2ae`, which committed the build scripts a `.gitignore` rule had hidden. Releases v0.1.0 to v0.3.0 were tagged by hand. |
| v0.3.0 | 2026-10-21 | The twin moves to Python. `aws_twin`: S3's REST-XML protocol and STS GetCallerIdentity over a Python mirror of sg-vfs, a botocore hook with twin, live and replay routes, a local endpoint, traffic recording. One test suite, run by pytest in CI and by Pyodide in the browser. OSBot-AWS runs against it unchanged in both. [The S3 browser](../s3/index.md), every button a Python call, persisted through sg-vfs's IndexedDB provider (vendored). [AWS sessions](../sessions/index.md): setup, paste and a live check, and measured CORS for the better methods. The article [The twin is Python now](../articles/the-twin-is-python-now.md). CI on GitHub Actions. |
| v0.2.0 | 2026-10-21 | The articles section, in the newsroom's format: [A first go at the AWS twin](../articles/first-go-at-the-aws-twin.md) (the build agent, in its own voice) and [boto3 in the browser](../articles/boto3-in-the-browser.md) (Dinis Cruz, from a voice memo: the JavaScript SDK's maturity, boto3 under Pyodide against the twin, and the CORS measurement). The experiments and their data under `articles/data/`. The team page. Build-state rows updated for what was measured. |
| v0.1.0 | 2026-10-21 | First release. The site: front page, design, workflow, naming, status, admin. The proof of concept: the interface (8 AWS-shaped namespaces, 42 operations, plus 3 twin-only), the vault backend on localStorage with commits and diff, the memory backend, the live backend's session slot, two deployment templates, the demo estate, the account graph, and the UI. 214 test assertions. Captured the naming decision of the same day: `aws.twin.sgit.ai`, repo `SGit-AI__Website__Twin__AWS`, hub `twins.sgit.ai`. |

[← Admin & engineering](index.md)[The front page →](../index.md)

---

*[This page as HTML](https://aws.twin.sgit.ai/admin/versions.html) · [The site for agents](https://aws.twin.sgit.ai/llms.txt) · CC BY 4.0*
