# Reality: what exists on aws.twin.sgit.ai, at v0.4.0 (21 October 2026)

The rule, from the SG/Send repository's Librarian: a feature that is not in this file does not exist, and nobody
may say a thing works because a brief describes it. Kept current by whoever ships. Content CC BY 4.0.

## Exists

| | |
|---|---|
| **The site** | Static HTML from `admin/build/pages.py` (bodies in `admin/content/pages/`) and `admin/build/articles.py`; a markdown twin beside every page; `llms.txt`, `sitemap.xml`, `robots.txt`; CNAME `aws.twin.sgit.ai` |
| **Deployment** | `.github/workflows/deploy-pages.yml`: validate, tag `vX.Y.Z` on every push to `dev`, publish to GitHub Pages; copied from the twins hub. Live from v0.3.1, checked against `assets/version.js` after the deploy |
| **Versioning** | `admin/build/version.txt`, the badge on every page, `assets/version.js`, the release history, tags made by CI from v0.3.1 (v0.1.0 to v0.3.0 tagged in the build agent's clone only; pushing them was refused, so a maintainer must) |
| **The gate** | `admin/build/validate.js` (version agreement, canonical host, links, nav, twins, licence stamps, name-watch, leak tripwire, diagrams rendered from their current source) plus the JavaScript tests, pytest and the bundle check, in the deploy workflow before any tag |
| **The Python twin** | `aws_twin/`: S3's REST-XML protocol and STS GetCallerIdentity over a Python mirror of sg-vfs, a botocore hook with twin, live and replay routes, a local endpoint, traffic recording |
| **Tests** | 26 plain-function tests: pytest 24 pass, 2 opt-in live; under Pyodide in headless Chromium 18 pass, 8 skipped (sockets, site files, opt-in). CI runs both (`ci.yml`), and `admin/build/check_cli.py` runs every AWS CLI command the IAM and sessions pages print through the AWS CLI against the twin |
| **OSBot-AWS against the twin** | Its S3 helpers and STS caller identity, unchanged, in CPython and in the browser, pinned at 2.39.10 |
| **The S3 browser** | `/s3/`: every button an OSBot-AWS call in Pyodide; buckets in IndexedDB through vendored sg-vfs |
| **The sessions page** | `/sessions/`: setup steps, paste, a live STS check from the browser; verified with invented keys, and on 21 October 2026 with Dinis Cruz's real Identity Center session (account, role, user returned); measured CORS for other sign-in methods |
| **Live S3 in the S3 browser** | `/s3/#/live`: the session from the same tab; directly for buckets with a CORS rule for this origin, through the local relay for the rest and for ListBuckets; read-only unless writes are allowed; tested in headless Chromium against the twin's server standing in for AWS behind the relay (10 checks), and with invented keys against real AWS |
| **The local relay** | `aws_twin/core/Twin__Relay.py`: stdlib, one file, 127.0.0.1:4567, this origin only, `https://*.amazonaws.com` only, no credentials, one log line per request; served at `/aws_twin/core/Twin__Relay.py` |
| **Least-privilege guidance** | `/iam/`: four S3 permission sets as files under `/iam/policies/`, the TwinReader policy, the bucket CORS rule; the IAM Identity Center CLI, checked by the AWS CLI |
| **How it works** | `/how-it-works/`: the live path step by step, six diagrams (a seventh on `/iam/`) written in Mermaid (`admin/content/diagrams/`) and rendered to SVG by `admin/build/diagrams.js` |
| **The JavaScript proof of concept** | `/twin/`: the first, SDK-shaped twin over localStorage, its 214 assertions |
| **Articles** | Four, in the newsroom's format: two by the build agent, two from Dinis Cruz's memos |
| **The briefs** | Five, published in full under `/briefs/` |

## Does not exist

- The S3 browser against a real account's buckets. A real session has been checked against STS only; S3 has been tested against a stand-in and with invented keys.
- A recording of a live session replayed against the twin.
- The JavaScript proof of concept's live backend: still a slot; the Python twin is what reaches AWS.
- Lambda, EC2, IAM, Logs, Cost Explorer or CloudFormation in the Python twin.
- Signature verification in the twin; real object versions.
- Cognito, web identity or Roles Anywhere sign-in; the SSO device-code flow (blocked in a browser).
- A vault provider, or sgit sync of anything this site holds.
- `review/`, roles and a board; see BRIEF-CORRECTIONS.md for the other departures from the guidance.
