# Corrections to the briefs

The briefs are [published as given](briefs/index.html) and never edited. Where one was wrong, unclear, transcribed
differently from what was meant, or overtaken, the finding goes here, dated, newest first. Departures from
[sgit.ai's repository guidance](https://sgit.ai/docs/guidance/repositories.html) are recorded here too, so the
guidance can be corrected from them or this repository brought into line. Content CC BY 4.0.

## 2026-10-21, brief 4: deployment and the guidance (site v0.3.1)

1. **The site was built and pushed to `dev`, and was not live.** `aws.twin.sgit.ai` already resolved to GitHub
   Pages and the github.io address redirected to it, but it answered 404: this repository had no
   `deploy-pages.yml`, and Pages publishes these sites from a workflow, not from the branch. Fixed in v0.3.1 by
   the hub's own workflow, copied from SGit-AI__Website__Twins.
2. **"Auto-tagging on all commits" is, in the estate, a tag on every release, and every push to `dev` is a
   release.** The workflow tags the release commit `vX.Y.Z` from `admin/build/version.txt`, after checking that
   the commit subject reads `site vX.Y.Z: ...` and that the bump is the next minor. Commits between releases are
   not tagged.
3. **The first three releases were not tagged by CI.** Their subjects did not carry the `site vX.Y.Z:` prefix.
   They were tagged by hand on 21 October 2026: `v0.1.0` on `9b4ca27`, `v0.2.0` on `387ddb9`, `v0.3.0` on
   `b98f44a`. `308b2ae`, the commit that added the build scripts, was a push to `dev` without a version bump;
   its content ships in v0.3.1.
4. **The Python `.gitignore` template's `build/` rule hid `admin/build/`** from the first commit until
   `308b2ae`. The scripts the first two articles cite were on the build agent's disk, not in the repository,
   at the commits those articles name.

## 2026-10-21, brief 3: the Python twin (site v0.3.0)

5. **"Biodite" is Pyodide**, the CPython build for the browser.
6. **"Look just like S3"** was built as the console's structure (buckets, breadcrumbs, the objects table, the
   object overview, upload), in this site's colours, saying on every screen that the twin answers, not AWS.
   No AWS logo or brand is used.
7. **Cognito and the other sign-in methods were measured, not built.** The SSO device-code login cannot finish
   in a browser: the portal API that issues role credentials answers "Origin not allowed". Cognito identity
   pools, STS web identity and Roles Anywhere answer a browser. Paste is the method built.
8. **Vaults were not used yet.** The twin's storage is sg-vfs's contract, so a vault provider is one layer away;
   it is not written.
9. **The tools.sgraph.ai virtual file system is used**, vendored unchanged from SGraph-AI__Tools at `a905a5c`.

## 2026-10-21, brief 2: the articles (site v0.2.0)

10. **"newsroom.esky.ai" is newsroom.sgit.ai and "CLI.esky.ai" is cli.sgit.ai**, transcription of "sgit".
11. **"Pydantic" is Pyodide and "bot or three" is boto3**, read so in the article and said so there.
12. **"The JavaScript bot or three libraries"** was read as the AWS SDK for JavaScript v3.

## 2026-10-21, brief 1: the first go (site v0.1.0)

13. **"Use local storage to capture the twin data"**: the JavaScript proof of concept uses `localStorage`; the
    S3 browser of v0.3.0 uses IndexedDB through sg-vfs, which is also local to the browser and holds bytes.
14. **"Whose backend is a vault"**: browser storage stands in for the vault; the vault document is the shape a
    vault holds and is exported by file. sgit sync is not built.
15. **The TODOs for twins.sgit.ai, providers.sgit.ai and the newsroom are those sites' work**, listed on the
    admin page as requests and not done from this repository.

## Departures from the repository guidance, as of v0.3.1

16. **No `review/` folder.** The guidance asks for one from the first commit. Not built; it is the next
    structural item.
17. **No roles file and no board.** One person and one agent have played every role so far.
18. **The Python is not Type_Safe.** The guidance asks for Type_Safe on every data class; `aws_twin` uses plain
    classes so that it has no dependency and loads in a browser without OSBot-Utils. Whether the twin should
    take OSBot-Utils as a dependency is a decision for Dinis Cruz; it already runs in the browser.
19. **The JavaScript is not web components.** The S3 browser and the proof of concept are plain modules, not
    the three-file components on one base the guidance describes.
20. **The leak tripwire runs in the gate, not before each commit.** It scans the whole tree on every release;
    a pre-commit hook is not installed.
21. **No row on nfrs.sgit.ai's honest column yet.**
