# Corrections to the briefs

The briefs are [published as given](briefs/index.html) and never edited. Where one was wrong, unclear, transcribed
differently from what was meant, or overtaken, the finding goes here, dated, newest first. Departures from
[sgit.ai's repository guidance](https://sgit.ai/docs/guidance/repositories.html) are recorded here too, so the
guidance can be corrected from them or this repository brought into line. Content CC BY 4.0.

## 2026-10-21, brief 5: a live session, least privilege, how it works (site v0.4.0)

1. **"pic1 shows that the credentials are ok???"**: yes. The sessions page's check is STS GetCallerIdentity,
   signed in the page and answered by AWS; it returned the account, the AdministratorAccess role and the user.
   That is the first call to AWS with a real session from this site. The screenshots are not published, and no
   account, user or instance identifier from them is on any page.
2. **"How can I use the live session here"** needed more than a switch. S3 answers a page only for a bucket
   with a CORS rule for the page's origin, and ListBuckets never answers a page. Built both ways: direct, with
   the rule (a file on the IAM page), and through a local relay, `Twin__Relay.py`, on the user's own machine.
   Read-only by default.
3. **The relay needs the browser's permission.** Chromium asks before a public site reaches a service on the
   user's machine (Local Network Access). A synchronous request, which botocore makes, cannot raise the prompt
   and hangs; the page makes an asynchronous request first so the prompt appears. Found in testing, not in the
   brief.
4. **"A user that can only access the S3 buckets"** was built as permission sets, not users: in IAM Identity
   Center the permissions belong to the role picked in the portal, so a narrow session comes from a narrow
   permission set assigned through a group. The page also covers a separate daily user and moving
   AdministratorAccess out of daily reach, in an order that cannot lock the administrator out.
5. **"The login setup that I have"** was not pasted in the end; the guidance uses placeholders and the
   commands look up the instance and identity store for themselves.
6. **"Vocês vão sofrer, ninguém vai ser user technical documents"** is the transcription's first sentence, in
   Portuguese and garbled ("you will suffer, nobody will be user technical documents"). It was read as the
   start of the request that follows it: technical documents that explain what was done.
7. **"maybe for pattern that you have"** was read as "each pattern you have": the explainer takes each route
   (twin, direct, relay), the guard and the recording in turn.
8. **"Mermaid diagrams and infographics"**: the diagrams are written in Mermaid and rendered to SVG when the
   site is built, so the pages load no diagram script (the site loads no third-party script); each diagram's
   source is under it, and the markdown twins carry it as a mermaid block. The infographics are a numbered
   strip and a hand-drawn figure.
9. **The milestone article is in Dinis's voice** from the memo, and says what was and was not verified: STS
   with his real session, yes; the S3 browser against his real buckets, not yet.

## 2026-10-21, brief 4: deployment and the guidance (site v0.3.1)

10. **The site was built and pushed to `dev`, and was not live.** `aws.twin.sgit.ai` already resolved to GitHub
   Pages and the github.io address redirected to it, but it answered 404: this repository had no
   `deploy-pages.yml`, and Pages publishes these sites from a workflow, not from the branch. Fixed in v0.3.1 by
   the hub's own workflow, copied from SGit-AI__Website__Twins.
11. **"Auto-tagging on all commits" is, in the estate, a tag on every release, and every push to `dev` is a
   release.** The workflow tags the release commit `vX.Y.Z` from `admin/build/version.txt`, after checking that
   the commit subject reads `site vX.Y.Z: ...` and that the bump is the next minor. Commits between releases are
   not tagged.
12. **The first three releases were not tagged by CI.** Their subjects did not carry the `site vX.Y.Z:` prefix.
   They were tagged by hand on 21 October 2026, `v0.1.0` on `9b4ca27`, `v0.2.0` on `387ddb9`, `v0.3.0` on
   `b98f44a`, in the build agent's clone; pushing tags from it was refused (403), so these three wait for a
   maintainer to tag and push them. `v0.3.1` onwards are tagged by CI. `308b2ae`, the commit that added the build scripts, was a push to `dev` without a
   version bump; its content ships in v0.3.1.
13. **The Python `.gitignore` template's `build/` rule hid `admin/build/`** from the first commit until
   `308b2ae`. The scripts the first two articles cite were on the build agent's disk, not in the repository,
   at the commits those articles name.

## 2026-10-21, brief 3: the Python twin (site v0.3.0)

14. **"Biodite" is Pyodide**, the CPython build for the browser.
15. **"Look just like S3"** was built as the console's structure (buckets, breadcrumbs, the objects table, the
   object overview, upload), in this site's colours, saying on every screen that the twin answers, not AWS.
   No AWS logo or brand is used.
16. **Cognito and the other sign-in methods were measured, not built.** The SSO device-code login cannot finish
   in a browser: the portal API that issues role credentials answers "Origin not allowed". Cognito identity
   pools, STS web identity and Roles Anywhere answer a browser. Paste is the method built.
17. **Vaults were not used yet.** The twin's storage is sg-vfs's contract, so a vault provider is one layer away;
   it is not written.
18. **The tools.sgraph.ai virtual file system is used**, vendored unchanged from SGraph-AI__Tools at `a905a5c`.

## 2026-10-21, brief 2: the articles (site v0.2.0)

19. **"newsroom.esky.ai" is newsroom.sgit.ai and "CLI.esky.ai" is cli.sgit.ai**, transcription of "sgit".
20. **"Pydantic" is Pyodide and "bot or three" is boto3**, read so in the article and said so there.
21. **"The JavaScript bot or three libraries"** was read as the AWS SDK for JavaScript v3.

## 2026-10-21, brief 1: the first go (site v0.1.0)

22. **"Use local storage to capture the twin data"**: the JavaScript proof of concept uses `localStorage`; the
    S3 browser of v0.3.0 uses IndexedDB through sg-vfs, which is also local to the browser and holds bytes.
23. **"Whose backend is a vault"**: browser storage stands in for the vault; the vault document is the shape a
    vault holds and is exported by file. sgit sync is not built.
24. **The TODOs for twins.sgit.ai, providers.sgit.ai and the newsroom are those sites' work**, listed on the
    admin page as requests and not done from this repository.

## Departures from the repository guidance, as of v0.4.0

25. **No `review/` folder.** The guidance asks for one from the first commit. Not built; it is the next
    structural item.
26. **No roles file and no board.** One person and one agent have played every role so far.
27. **The Python is not Type_Safe.** The guidance asks for Type_Safe on every data class; `aws_twin` uses plain
    classes so that it has no dependency and loads in a browser without OSBot-Utils. Whether the twin should
    take OSBot-Utils as a dependency is a decision for Dinis Cruz; it already runs in the browser.
28. **The JavaScript is not web components.** The S3 browser and the proof of concept are plain modules, not
    the three-file components on one base the guidance describes.
29. **The leak tripwire runs in the gate, not before each commit.** It scans the whole tree on every release;
    a pre-commit hook is not installed.
30. **No row on nfrs.sgit.ai's honest column yet.**
