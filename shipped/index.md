<!-- the markdown twin of https://aws.twin.sgit.ai/shipped/index.html, generated from the same source by admin/build/pages.py; site v0.3.1; content CC BY 4.0 -->

[aws.twin.sgit.ai](../index.md) / status

# Built, and designed

The family's house rule: the build state leads, every designed thing is labelled as design, and the numbers carry the date they were measured. Measured 2026-10-21, at site v0.3.1, the first release.

## 1. The table

| Artefact | State | Evidence |
|---|---|---|
| **The interface**: 8 AWS-shaped namespaces, 42 operations, plus 3 twin-only, a manifest of accepted params, AWS-shaped results and error codes | PoC, working | `assets/twin/interface.js`; the manifest-coverage test fails if an operation is listed and not implemented, or the reverse |
| **The vault backend** on localStorage: working state, commits, head, checkout, export, import, reset | PoC, working | `assets/twin/vault.js`; the round-trip test reloads from storage and from an exported document |
| **The memory backend** | PoC, working | The same script against both backends, 46 steps, identical after normalising what is random by design |
| **Snapshots and diff**: any commit against any commit or the working state, per account, added, removed, changed | PoC, working | Snapshots page; `diffStates` tested on a three-change Monday-to-Friday |
| **The account graph**: 8 node kinds, 6 relations, SVG and Mermaid | PoC, working | Graph page; node and edge counts tested after seeding |
| **Deployment rehearsal**: two templates, accounts × regions, a commit of the result | PoC, working | Deploy page; `createStack` runs the template through the interface; the Fargate template records the ECS gap on its stack |
| **The demo estate**: two illustrative accounts seeded through the interface | PoC, working | Illustrative account ids and numbers; every seeded resource is a logged call |
| **The session slot**: paste in four formats, expiry, masking, refusal of long-lived keys | PoC, working | Session page; parsing and refusals tested |
| **The live backend**'s wire to AWS | designed | Refuses every call naming the SDK command; what wiring needs is [three listed things](../design/index.md#live) |
| **CORS per service** from a browser | measured, no credentials | STS, Lambda, EC2, IAM, Logs, Cost Explorer and CloudFormation answer any origin with a preflight; S3 is blocked without a bucket rule. [The table, with the data beside it](../articles/boto3-in-the-browser.md#cors) |
| **boto3 under Pyodide** against the twin | experiment, ran | Eleven SigV4-signed calls through one replaced transport, 10.0 s wall, 24.2 MB; one extra step, Pyodide's `ssl` package. [The brief](../articles/boto3-in-the-browser.md#boto3) |
| **IAM Roles Anywhere** from a browser | untested | The PKI path to explore |
| **Sync of the vault document through sgit** | designed | Export and import by file today; the document is already the shape a vault holds |
| **ECS, Route 53, ECR, SSM** in the manifest | not in the interface | Each is a state key, a manifest entry and an ops entry; the Fargate template's stack output names the first gap |
| **The catalogue entry on twins.sgit.ai** | requested | [Requests to other sites](../admin/index.md#requests) |

## 2. The numbers, 2026-10-21

- Interface: 8 AWS-shaped namespaces with 42 operations, and 1 twin-only namespace with 3.
- Tests: 214 assertions, 0 failing, under one second, `node admin/build/test.js`.
- Measured the same day, in the articles: CORS on ten endpoints, boto3 under Pyodide in three runs (10.0, 14.3 and 57.8 s wall, 24.2 MB each). Data under `articles/data/`.
- Code: four files under `assets/twin/`, no dependency, no build step, no third-party script. The page works from a file URL.
- The demo estate, after seeding: 2 accounts, 66 calls through the interface, and about 25 KB in localStorage before the first commit.

## 3. What is next, in order

1. **Wire the live backend** with the SDK for JavaScript v3 for the eight services, as a fixed copy per site version, and write live reads back into the vault as commits.
2. **Make one live call with a real session**, from a laptop browser, to confirm the CORS table from a reader's machine and not a container.
3. **Sync the vault document** through sgit instead of a file, so a session's findings land in the user's vault and travel between devices.
4. **Add ECS** to the manifest so the Fargate template stops recording a gap, then Route 53, ECR and SSM as the first job needs them.
5. **Test Roles Anywhere** from a browser: a session from a certificate, as a backend.
6. **Catalogue this twin on the hub**, and move the hub's build-state table when the wire ships.

## 4. What this does not claim

- **Nothing here calls AWS.** The live backend is a slot. The service names identify interfaces the twin mirrors; AWS's real behaviour is richer and different in places, and the twin's behaviours are the ones a rehearsal needs, chosen, not derived from the service.
- **The demo estate is illustrative.** The account ids are placeholders, the costs are invented round numbers, the AMI ids are not real. Nothing on this site is a measurement of an AWS account.
- **Browser access is not tested service by service.** S3 needs CORS; the rest is to measure.
- **The commit ids are not the vault's.** They are content hashes for the PoC; sgit's own hashes take over once the document is pushed.
- **The templates are stand-ins.** They produce the shape of the SG/Send deployment, not the reviewed CloudFormation. The real templates are in beta on sgit.ai's AWS page.
- **The quotes about sessions, CORS and Roles Anywhere are from AWS's documentation** as read on 2026-10-21 for the article, and are paraphrased here; the article carries them verbatim.

[← Why aws.twin](../naming/index.md)[Admin & engineering →](../admin/index.md)

---

*[This page as HTML](https://aws.twin.sgit.ai/shipped/index.html) · [The site for agents](https://aws.twin.sgit.ai/llms.txt) · CC BY 4.0*
