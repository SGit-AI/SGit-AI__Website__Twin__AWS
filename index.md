<!-- the markdown twin of https://aws.twin.sgit.ai/index.html, generated from the same source by admin/build/pages.py; site v0.4.2; content CC BY 4.0 -->

The AWS twin · one instance of the twin primitive · proposed and prototyped 2026-10-21

# AWS from the vault, twin first

An AWS-shaped interface, S3, Lambda, EC2, IAM, billing and logs, whose backend is a vault. Build everything against the twin, with no credentials. Then put a temporary session from the AWS access portal in front of the **same interface** as a second backend, and what you built works against the live account. **This site holds the proof of concept**: the interface, a vault backend on this browser's localStorage, snapshots as commits, an account graph, and a deployment rehearsal. Since v0.4.0 the Python twin's live route reaches a real account from the browser: a pasted session checked against AWS STS, and [the console](console/index.md), live, directly or through a [local relay](how-it-works/index.md#relay). [How it works](how-it-works/index.md).

 [Open the console →](console/index.md) [AWS sessions →](sessions/index.md) [The design →](design/index.md) [The workflow →](workflow/index.md)

## In short

 [The interface

### AWS-shaped, and fixed

One client per account and region, one params object per call, AWS-shaped results and error codes, in the shape of the AWS SDK for JavaScript v3. Consuming code is written against this and nothing else.
Read →](design/index.md#interface) [The backends

### Vault, memory, live

The same three the S3 container has. The vault backend is the twin; memory is the test double; live is the real account, borrowed for a session. Swappable from a drop-down in the PoC.
Read →](design/index.md#backends) [The session

### From the access portal, into the vault

Temporary credentials for one account and one role, one to twelve hours. Pasted, not configured. When it ends it is worth nothing. The twin's interface never holds it; the live backend borrows it.
Read →](workflow/index.md#session) [The data

### Snapshots are commits

Everything the twin holds is a state document in the vault. Every snapshot is a commit, so "what changed between Monday and Friday" is a diff, the same for hand-seeded and live-sourced data.
Read →](design/index.md#snapshots) [The graph

### Resources as nodes, relationships as edges

Role → policy, function → bucket, instance → security group, stack → what it created. Built from the state the interface returns, readable as SVG or as Mermaid.
Read →](design/index.md#graph) [The first job

### Deploy the SG/Send servers

One template, one session per account, several regions, every deployment written down in the vault. Rehearsed against the twin in the PoC; the live run is the same calls.
Read →](workflow/index.md#deploy)

## The flow

The article's diagram, with one change: the site in the browser is a twin, and the live session is a backend behind its interface, not the only way it works.

1 · AWS**Access portal**Sign in, pick the account and the permission set, choose "Access keys".

2 · temporary**Credentials**Access key, secret, session token. One to twelve hours, one by default.

3 · the vault**The session, and the data**Pasted in for the session's lifetime. The same vault holds inventories, logs, costs and snapshots.

4 · the twin**aws.twin in the browser**One AWS-shaped interface. Behind it: the vault, memory, or the live session.

5 · live, when wired**AWS**S3, Lambda, EC2, IAM, billing, logs, through the SDK for JavaScript. Results go back to step 3.

6 · the record**Graphs and workflows**Snapshots as commits, the account graph, deployments written down.

## Built, and designed, 2026-10-21

A site about a twin owes the reader its build state before anything else. Here it is, unsoftened; the full table with evidence is on [the status page](shipped/index.md).

| Artefact | State | What it proves |
|---|---|---|
| **The Python twin**: S3's REST-XML protocol and STS GetCallerIdentity answered from a VFS, a botocore hook, a local endpoint, record and replay | PoC, working | The same 18 tests under pytest in CPython (18 pass) and under Pyodide in the browser (16 pass, 2 skipped: no sockets or disk). [The Python twin →](python/index.md) |
| **OSBot-AWS against the twin**, unchanged, in CPython and in the browser | PoC, working | Its S3 helpers, from bucket_create to bucket_delete_all_files, and STS caller identity |
| **The S3 browser**: every button a Python call, kept in IndexedDB through sg-vfs | PoC, working | 14 headless checks including a reload that restores the buckets. [Open it →](console/s3.md) |
| **The session check**: a pasted session verified against AWS from the browser, through the twin's live route | built | A signed STS call from Python in the browser reaches AWS and comes back. [Sessions →](sessions/index.md) |
| **The JavaScript interface**: 8 AWS-shaped namespaces, 42 operations, one manifest | first PoC, superseded for new work | Still runs [the twin page](twin/index.md). New services go into the Python twin. |
| **The vault backend** on localStorage, and the memory backend | PoC, working | Same script, two backends, same answers: 214 assertions in `admin/build/test.js` |
| **Snapshots as commits**, diff between any two | PoC, working | Monday against Friday, resource by resource. Export and import of the vault document. |
| **The account graph** | PoC, working | Eight node kinds, six edge relations, from the state the interface returns |
| **Deployment rehearsal**: two templates, accounts × regions | PoC, working | A template is a sequence of ordinary calls, so the rehearsal and the live run are the same calls. ECS is not in the manifest: the Fargate template records that gap on its stack. |
| **The live backend**: the session slot, the refusal naming the SDK command | slot built, wire designed | The same interface; every call says what it would send. Nothing calls AWS yet. |
| **CORS per service**, measured from a browser with no credentials | measured | Seven of eight service families answer any origin with a preflight; S3 needs a bucket rule. [The table →](articles/boto3-in-the-browser.md#cors) |
| **boto3 in the browser** under Pyodide, against the twin | experiment, ran | Eleven signed calls through one replaced transport function, ten seconds wall. [The brief →](articles/boto3-in-the-browser.md) |
| **Live, from the browser** (the Python twin): a real session checked against AWS STS; the S3 browser live, directly or through the local relay, read-only by default | built; STS checked with a real session | [How it works](how-it-works/index.md); real-account S3 browsing is the next test |
| IAM Roles Anywhere from a browser, sgit sync of the vault document | not done | To test and to build. Export and import by file stand in for sync today. |

The honest headline: **the twin works in the browser against a vault; the wire to the live account is the next step, and nothing on this site pretends otherwise.** The article of 2026-10-21 said "nothing here is built"; this site is the same day's first go, and [its articles](articles/index.md) say what was done and what was measured.

## Why a twin, and not a console

> The S3-compatible vault container works because **"code using boto3 believes it is talking to real S3"** while the backend is real S3, a vault, or memory, chosen per environment, and **"the service's own code does not change."**

The AWS twin is the second instance of that pattern, not an exception to it. Build the twin first, with the vault as its backend, and every workflow, graph and deployment is written against the interface. Then the live connection is one more backend: a temporary session, borrowed for an hour, in front of the same face. Develop and test with no credentials; rehearse a multi-account, multi-region deploy before running it live; and keep one record either way, because snapshots are vault commits whether the data was seeded by hand or read from the account. [Why that made it `aws.twin` and not `aws.sgit.ai` →](naming/index.md)

## What this proof of concept stores, and where

Nothing leaves the browser. There is no server behind this site, no analytics, and no third-party script.

localStorage · aws.twin/vault

### The twin's data

One document: a working state, a list of commits, a head. The shape an sgit vault holds, so the export is what gets pushed there. Illustrative accounts from the seed, or whatever you create.

sessionStorage · aws.twin/session

### The session, if you paste one

For this tab's lifetime, with the expiry you give it. The secret and the token are never shown back. In this PoC the live backend refuses every call with the command it would have sent, so pasting a session proves the slot and nothing more.

localStorage · aws.twin/ui

### Which backend, account and region

The three drop-downs, so the page reopens where you left it. Nothing else.

## Who is writing this

This site is published by the sgit project, which builds the vault this twin stores into and the SG/Send server components its first job deploys. So it is a participant publishing a tool for its own workflow, stated upfront. It is not affiliated with Amazon Web Services; the service names identify the interfaces the twin mirrors, and the quotations about sessions and CORS are from AWS's documentation as read on 2026-10-21 for [the article](https://newsroom.sgit.ai/articles/aws-from-the-vault.html). The build state leads, every designed thing is labelled as design, and [what this does not claim](shipped/index.md#claims) is a page of its own.

 [Built, and designed, in full →](shipped/index.md) [The family's participant disclosure ↗](https://twins.sgit.ai/about/participant.html)

---

*[This page as HTML](https://aws.twin.sgit.ai/index.html) · [The site for agents](https://aws.twin.sgit.ai/llms.txt) · CC BY 4.0*
