# SGit-AI__Website__Twin__AWS

The repository for **aws.twin.sgit.ai**: the AWS twin.

An AWS-shaped interface (S3, Lambda, EC2, IAM, billing, logs, CloudFormation) whose
backend is a vault, so that everything built against the twin works against the live
account once a temporary IAM Identity Center session is put in front of the same
interface as a second backend. One instance in the twins family; the primitive is defined
on [twins.sgit.ai](https://twins.sgit.ai). The design comes from the article
[AWS from the vault](https://newsroom.sgit.ai/articles/aws-from-the-vault.html)
(21 October 2026) and the naming decision of the same day.

This repository holds the site and a proof of concept that runs in the browser with
`localStorage` as the vault. **Nothing here calls AWS.** The live backend has its session
slot and not its wire: it accepts a pasted session and refuses every call naming the SDK
command it would have sent.

## Layout

```
index.html                      the front page
twin/index.html                 the twin: the application page
design/ workflow/ naming/ shipped/   the reference pages
assets/site.css  assets/nav.js  the family's shared stylesheet and nav
assets/twin/interface.js        the interface: manifest, ops, StateBackend, MemoryBackend, LiveBackend, diff, graph
assets/twin/vault.js            VaultBackend over a key/value store, with commits; SessionStore
assets/twin/templates.js        the two deployment templates and the demo estate
assets/twin/app.js  app.css     the UI
admin/build/test.js             the interface tests (node, no dependencies)
admin/build/validate.js         links, nav, versions, name-watch, no credential-shaped strings
admin/versions.html  llms.txt
```

## Run

```sh
python3 -m http.server 8080          # any static server; file:// works for the twin page too
# open http://localhost:8080/twin/index.html

node admin/build/test.js             # the same script against the memory and vault backends
node admin/build/validate.js         # the site checks; both are the release gate
```

No build step, no dependency, no third-party script. The twin's code is UMD and runs
unchanged in Node and in the browser.

## What the twin stores in the browser

| Key                | Store          | Holds                                                     |
|--------------------|----------------|-----------------------------------------------------------|
| `aws.twin/vault`   | localStorage   | the vault document: working state, commits, head           |
| `aws.twin/session` | sessionStorage | a pasted session with its expiry, for the tab's lifetime   |
| `aws.twin/ui`      | localStorage   | the chosen backend, account and region                     |

## Licence

Content CC BY 4.0; code Apache-2.0 (see `LICENSE`).
