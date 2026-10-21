# Reality: what exists on aws.twin.sgit.ai, at v0.3.1 (21 October 2026)

The rule, from the SG/Send repository's Librarian: a feature that is not in this file does not exist, and nobody
may say a thing works because a brief describes it. Kept current by whoever ships. Content CC BY 4.0.

## Exists

| | |
|---|---|
| **The site** | Static HTML from `admin/build/pages.py` (bodies in `admin/content/pages/`) and `admin/build/articles.py`; a markdown twin beside every page; `llms.txt`, `sitemap.xml`, `robots.txt`; CNAME `aws.twin.sgit.ai` |
| **Deployment** | `.github/workflows/deploy-pages.yml`: validate, tag `vX.Y.Z` on every push to `dev`, publish to GitHub Pages; copied from the twins hub. Live from v0.3.1, checked against `assets/version.js` after the deploy |
| **Versioning** | `admin/build/version.txt`, the badge on every page, `assets/version.js`, the release history, tags made by CI (v0.1.0 to v0.3.0 tagged by hand) |
| **The gate** | `admin/build/validate.js` (version agreement, canonical host, links, nav, twins, licence stamps, name-watch, leak tripwire) plus the JavaScript tests, pytest and the bundle check, in the deploy workflow before any tag |
| **The Python twin** | `aws_twin/`: S3's REST-XML protocol and STS GetCallerIdentity over a Python mirror of sg-vfs, a botocore hook with twin, live and replay routes, a local endpoint, traffic recording |
| **Tests** | 19 plain-function tests: pytest 18 pass, 1 opt-in live; under Pyodide in headless Chromium 16 pass, 3 skipped. CI runs both (`ci.yml`) |
| **OSBot-AWS against the twin** | Its S3 helpers and STS caller identity, unchanged, in CPython and in the browser, pinned at 2.39.10 |
| **The S3 browser** | `/s3/`: every button an OSBot-AWS call in Pyodide; buckets in IndexedDB through vendored sg-vfs |
| **The sessions page** | `/sessions/`: setup steps, paste, a live STS check from the browser (verified with invented keys); measured CORS for other sign-in methods |
| **The JavaScript proof of concept** | `/twin/`: the first, SDK-shaped twin over localStorage, its 214 assertions |
| **Articles** | Three, in the newsroom's format: two by the build agent, one from Dinis Cruz's memo |
| **The briefs** | Four, published in full under `/briefs/` |

## Does not exist

- A call to AWS with a real session from this site. Only invented keys have been used.
- Lambda, EC2, IAM, Logs, Cost Explorer or CloudFormation in the Python twin.
- Signature verification in the twin; real object versions.
- Cognito, web identity or Roles Anywhere sign-in; the SSO device-code flow (blocked in a browser).
- A vault provider, or sgit sync of anything this site holds.
- `review/`, roles and a board; see BRIEF-CORRECTIONS.md for the other departures from the guidance.
