# Corrections to the briefs

The briefs are [published as given](briefs/index.html) and never edited. Where one was wrong, unclear, transcribed
differently from what was meant, or overtaken, the finding goes here, dated, newest first. Departures from
[sgit.ai's repository guidance](https://sgit.ai/docs/guidance/repositories.html) are recorded here too, so the
guidance can be corrected from them or this repository brought into line. Content CC BY 4.0.

## 2026-10-23, brief 8: the console (site v0.4.2)

1. **"The listing for the lambda function that exists"** was built as the console's Lambda page, and the console
   as a whole: a page per service rather than one page with views, as Dinis preferred, with the mode top left.
2. **"Unless you feel that it's not going to work"**: it works, at a cost measured and stated on
   [the plan](console/plan.html#pages): every page starts Python again, 17 seconds the first time and 15 after
   in headless Chromium here. State is not lost between pages (IndexedDB, the tab); the start-up is the next fix.
3. **"Invisibility what's going on"** is "visibility", transcription. Built as the request pane: every call and
   request, both ways. "The difference between the live server" was built as a button on each live read that
   sends the same request to the twin and shows its answer beside AWS's.
4. **"A way to reply whose calls"** is "replay those calls": every request carries the boto3 call that made it,
   and opens in the call editor. "Some will need some state": the editor runs against the twin's shared store, so
   a call needing a function or a bucket works once one exists there, and says so by name when it does not.
5. **"pyodite" is Pyodide**, transcription.
6. **"S3 list buckets" is not working from a browser, confirmed**, and not only for Pyodide: the official AWS SDK
   for JavaScript is blocked on exactly the same three calls (ListBuckets, and a bucket's own calls without a CORS
   rule), measured with invented keys on 23 October 2026. From the CLI and from code every call reaches AWS. The
   console lists buckets through Cloud Control, as Dinis's CloudShell check showed it can: every region's buckets.
7. **The JavaScript proof of concept's live backend** (the screenshots) is still a slot that refuses with the SDK
   command it would send; its page now points to the console, which is wired.
8. **The footer said "no third-party scripts on the site's pages"**, which stopped being true when Pyodide arrived
   in v0.3.0. It now says what the twin's pages load, and when.

## 2026-10-23, brief 7: the uptime Lambda (site v0.4.1)

9. **"S-kit to AI" is sgit.ai, "both of three" is boto3**, transcription. "The append lane" is sgit's append lane
   (sgit.ai/docs/vault-messaging.md): a write-only channel on a vault, gated by an append token.
10. **"Encrypted with the public key of the append lane"**: a lane has no key of its own. The report is encrypted to
   the vault owner's public key (an sgit identity's `encrypt` key), and the lane only carries it. The intended
   lane address is a hash of that public key, but sgit has not shipped the derivation, so today the token is
   agreed out of band, as sgit.ai says.
11. **"Pure Python or pure Node.js, no dependencies"** was decided for Node.js 22, because sgit's envelope needs
   RSA-OAEP and AES-256-GCM, which Node.js has in WebCrypto and Python's standard library does not. The reasons
   and the alternatives are on [the plan](uptime/plan.html#language). The Lambda twin runs Python functions too,
   so the choice can be revisited.
12. **"An API key", then "give the Lambda the public key it receives data from"**: built as the second. A function
   URL request must be signed with the controller's ECDSA P-256 key, whose public half is in the function's
   configuration; the function holds no private key. A direct Invoke needs no key of ours: AWS checks the
   caller's IAM authority.
13. **"A digital twin for the CloudFront, minimum configuration to make this happen"**: CloudFront is not needed for
   the checks or the reports. It is built as an option, one hostname in front of every region's function URL,
   and the twin covers the distribution operations a deployment uses. Requests to a distribution's domain are
   not served by the twin yet.
14. **Not run against AWS.** The deployment is the same boto3 for the twin and the account, and the twin enforces the
   rules that usually bite (an execution role Lambda can assume, a schedule needs the invoke permission, ETags,
   disable before delete); a first real deploy is phase 2.
15. **sgit's append server answers a bad token with a 404 HTML page**, not a 403 (sgit.ai/api/append-lanes.md,
   checked 26 September 2026). The twin of the lane does the same.

## 2026-10-21, brief 6: versions, and doing it from the browser (site v0.4.1)

16. **"Commit to dev, increment a minor; commit to main, increment a major"**, with v0.3.1 to v0.3.6 minors and
   v0.4.0, v0.5.0 majors: v0.4.0 was released from `dev` as a major, against that rule. It stays, since moving a
   published tag is worse; from v0.4.1 the deploy workflow refuses anything but the next minor on `dev` and the
   next major on `main`.
17. **"Pydantic" is Pyodide and "the tween" is the twin**, transcription.
18. **"How is the web server distinguishing a raw HTTP request versus one from the browser"**: it is the browser
    that enforces the difference. A page's request carries an `Origin` the page cannot change, and for signed
    requests the browser first asks the server (a CORS preflight); without the server's yes it never sends the
    request. S3's ListBuckets endpoint never says yes; the JavaScript SDK has ListBuckets and hits the same wall.
19. **"That local relay doesn't work"**: agreed as a product answer, and kept only as an option. The way proposed
    instead is the Cloud Control API, which answers any origin and can list buckets
    (`ListResources AWS::S3::Bucket`); whether it lists every region's buckets is waiting on a check in CloudShell.

## 2026-10-21, brief 5: a live session, least privilege, how it works (site v0.4.0)

20. **"pic1 shows that the credentials are ok???"**: yes. The sessions page's check is STS GetCallerIdentity,
   signed in the page and answered by AWS; it returned the account, the AdministratorAccess role and the user.
   That is the first call to AWS with a real session from this site. The screenshots are not published, and no
   account, user or instance identifier from them is on any page.
21. **"How can I use the live session here"** needed more than a switch. S3 answers a page only for a bucket
   with a CORS rule for the page's origin, and ListBuckets never answers a page. Built both ways: direct, with
   the rule (a file on the IAM page), and through a local relay, `Twin__Relay.py`, on the user's own machine.
   Read-only by default.
22. **The relay needs the browser's permission.** Chromium asks before a public site reaches a service on the
   user's machine (Local Network Access). A synchronous request, which botocore makes, cannot raise the prompt
   and hangs; the page makes an asynchronous request first so the prompt appears. Found in testing, not in the
   brief.
23. **"A user that can only access the S3 buckets"** was built as permission sets, not users: in IAM Identity
   Center the permissions belong to the role picked in the portal, so a narrow session comes from a narrow
   permission set assigned through a group. The page also covers a separate daily user and moving
   AdministratorAccess out of daily reach, in an order that cannot lock the administrator out.
24. **"The login setup that I have"** was not pasted in the end; the guidance uses placeholders and the
   commands look up the instance and identity store for themselves.
25. **"Vocês vão sofrer, ninguém vai ser user technical documents"** is the transcription's first sentence, in
   Portuguese and garbled ("you will suffer, nobody will be user technical documents"). It was read as the
   start of the request that follows it: technical documents that explain what was done.
26. **"maybe for pattern that you have"** was read as "each pattern you have": the explainer takes each route
   (twin, direct, relay), the guard and the recording in turn.
27. **"Mermaid diagrams and infographics"**: the diagrams are written in Mermaid and rendered to SVG when the
   site is built, so the pages load no diagram script (the site loads no third-party script); each diagram's
   source is under it, and the markdown twins carry it as a mermaid block. The infographics are a numbered
   strip and a hand-drawn figure.
28. **The milestone article is in Dinis's voice** from the memo, and says what was and was not verified: STS
   with his real session, yes; the S3 browser against his real buckets, not yet.

## 2026-10-21, brief 4: deployment and the guidance (site v0.3.1)

29. **The site was built and pushed to `dev`, and was not live.** `aws.twin.sgit.ai` already resolved to GitHub
   Pages and the github.io address redirected to it, but it answered 404: this repository had no
   `deploy-pages.yml`, and Pages publishes these sites from a workflow, not from the branch. Fixed in v0.3.1 by
   the hub's own workflow, copied from SGit-AI__Website__Twins.
30. **"Auto-tagging on all commits" is, in the estate, a tag on every release, and every push to `dev` is a
   release.** The workflow tags the release commit `vX.Y.Z` from `admin/build/version.txt`, after checking that
   the commit subject reads `site vX.Y.Z: ...` and that the bump is the next minor. Commits between releases are
   not tagged.
31. **The first three releases were not tagged by CI.** Their subjects did not carry the `site vX.Y.Z:` prefix.
   They were tagged by hand on 21 October 2026, `v0.1.0` on `9b4ca27`, `v0.2.0` on `387ddb9`, `v0.3.0` on
   `b98f44a`, in the build agent's clone; pushing tags from it was refused (403), so these three wait for a
   maintainer to tag and push them. `v0.3.1` onwards are tagged by CI. `308b2ae`, the commit that added the build scripts, was a push to `dev` without a
   version bump; its content ships in v0.3.1.
32. **The Python `.gitignore` template's `build/` rule hid `admin/build/`** from the first commit until
   `308b2ae`. The scripts the first two articles cite were on the build agent's disk, not in the repository,
   at the commits those articles name.

## 2026-10-21, brief 3: the Python twin (site v0.3.0)

33. **"Biodite" is Pyodide**, the CPython build for the browser.
34. **"Look just like S3"** was built as the console's structure (buckets, breadcrumbs, the objects table, the
   object overview, upload), in this site's colours, saying on every screen that the twin answers, not AWS.
   No AWS logo or brand is used.
35. **Cognito and the other sign-in methods were measured, not built.** The SSO device-code login cannot finish
   in a browser: the portal API that issues role credentials answers "Origin not allowed". Cognito identity
   pools, STS web identity and Roles Anywhere answer a browser. Paste is the method built.
36. **Vaults were not used yet.** The twin's storage is sg-vfs's contract, so a vault provider is one layer away;
   it is not written.
37. **The tools.sgraph.ai virtual file system is used**, vendored unchanged from SGraph-AI__Tools at `a905a5c`.

## 2026-10-21, brief 2: the articles (site v0.2.0)

38. **"newsroom.esky.ai" is newsroom.sgit.ai and "CLI.esky.ai" is cli.sgit.ai**, transcription of "sgit".
39. **"Pydantic" is Pyodide and "bot or three" is boto3**, read so in the article and said so there.
40. **"The JavaScript bot or three libraries"** was read as the AWS SDK for JavaScript v3.

## 2026-10-21, brief 1: the first go (site v0.1.0)

41. **"Use local storage to capture the twin data"**: the JavaScript proof of concept uses `localStorage`; the
    S3 browser of v0.3.0 uses IndexedDB through sg-vfs, which is also local to the browser and holds bytes.
42. **"Whose backend is a vault"**: browser storage stands in for the vault; the vault document is the shape a
    vault holds and is exported by file. sgit sync is not built.
43. **The TODOs for twins.sgit.ai, providers.sgit.ai and the newsroom are those sites' work**, listed on the
    admin page as requests and not done from this repository.

## Departures from the repository guidance, as of v0.4.2

44. **No `review/` folder.** The guidance asks for one from the first commit. Not built; it is the next
    structural item.
45. **No roles file and no board.** One person and one agent have played every role so far.
46. **The Python is not Type_Safe.** The guidance asks for Type_Safe on every data class; `aws_twin` uses plain
    classes so that it has no dependency and loads in a browser without OSBot-Utils. Whether the twin should
    take OSBot-Utils as a dependency is a decision for Dinis Cruz; it already runs in the browser.
47. **The JavaScript is not web components.** The S3 browser and the proof of concept are plain modules, not
    the three-file components on one base the guidance describes.
48. **The leak tripwire runs in the gate, not before each commit.** It scans the whole tree on every release;
    a pre-commit hook is not installed.
49. **No row on nfrs.sgit.ai's honest column yet.**
