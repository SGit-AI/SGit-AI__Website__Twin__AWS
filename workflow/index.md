<!-- the markdown twin of https://aws.twin.sgit.ai/workflow/index.html, generated from the same source by admin/build/pages.py; site v0.4.0; content CC BY 4.0 -->

[aws.twin.sgit.ai](../index.md) / workflow

# The workflow

Two loops. The inner one is a session: an hour with one account and one role, borrowed from the AWS access portal and returned when it ends. The outer one is the vault: what each session found, kept as commits, so the next session starts from the record. In the proof of concept the inner loop is rehearsed against the vault; the outer loop works today.

## 1. The session

1. **Sign in to the AWS access portal.** It is part of IAM Identity Center. Pick the account, and the permission set you have in it. AWS's own distinction: IAM users are granted long-term credentials; users in IAM Identity Center are granted temporary ones, generated every time you sign in. It recommends the second.
2. **Choose "Access keys".** The portal shows the temporary credentials for that role: an access key id, a secret access key and a session token, in four formats. Any of the four pastes into the twin's [session page](../twin/index.md#/session); the credentials-file format also carries the account id and the role in its profile header.
3. **Paste them into the vault.** In this PoC: sessionStorage, for this tab, with the expiry you set. The twin switches its backend to *live*.
4. **Work.** For as long as the session lasts, the live backend can do whatever that role can do, through the same interface the vault answers. When the session ends the credentials are worth nothing, and you sign in again.

How long it lasts is set on the permission set: AWS says the session can be from one to twelve hours, with one hour by default. Copying and pasting is a little more work than the CLI's automatic refresh, and in return the site never sees anything but one short-lived session, for one account and one role.

**In this PoC the live backend is not wired.** Pasting a session proves the slot: the twin accepts it, counts it down, and refuses every call with the exact SDK command it would have sent. Nothing pasted leaves the browser and nothing on this site calls AWS. The work below is rehearsed against the vault backend, which is the twin-first point.

## 2. The work, service by service

What the twin page does today, against the vault, and will do live through the same calls:

| Service | In the twin page | The calls |
|---|---|---|
| S3 | Buckets with their region; objects with prefix listing; put, get, delete | `ListBuckets`, `ListObjectsV2`, `PutObject`, `GetObject`, `DeleteObject`, `CreateBucket`, `DeleteBucket` |
| Lambda | What is deployed in the region, at which image or runtime, with which role and settings; invoke with a payload and read the log | `ListFunctions`, `CreateFunction`, `Invoke`, `DeleteFunction` |
| EC2 | Instances and their state, security groups and their rules, instance profiles; run, stop, start, terminate | `DescribeInstances`, `RunInstances`, `StopInstances`, `DescribeSecurityGroups`, `AuthorizeSecurityGroupIngress` |
| IAM | Roles with their attached policies; create, attach, detach, delete with AWS's conflicts | `ListRoles`, `ListAttachedRolePolicies`, `CreateRole`, `AttachRolePolicy` |
| Billing | Cost by month, grouped by service or by region, as bars and a table | `GetCostAndUsage` |
| Logs | Log groups, events with a filter, your own events | `DescribeLogGroups`, `FilterLogEvents`, `PutLogEvents` |
| Deploy | Stacks with outputs and resources; a rehearsal across accounts and regions | `CreateStack`, `DescribeStacks`, `DeleteStack` |

## 3. The first job: deploying the SG/Send servers

The SG/Send server components, the small API that stores vaults, need to run in many regions and increasingly in many accounts. The pieces exist: CloudFormation templates for Lambda as a container image with a function URL and for ECS Fargate, an S3 storage mode with buckets named per account and region, runbooks for new accounts and regions. What is painful is running them across all of those and knowing afterwards what is deployed where.

In the twin, as of 2026-10-21:

1. Open [Deploy](../twin/index.md#/deploy) with the vault backend and the demo estate seeded. Both illustrative accounts already carry `sg-send-api` in two regions, at two image tags, from the seed.
2. Pick the template, name the stack, set the image tag, tick the accounts and the regions. The twin makes one client per account and region, as the live run will make one session per account.
3. Run it. Each target is a `CreateStack` that expands into the template's calls; the result table shows a stack per target, or AWS's `AlreadyExistsException` where one is already there.
4. Commit the deployment. The commit message names the stack, the template and how many targets took it, and the vault is now the record of the estate: which version, which region, which account, when, and what it produced. The next deployment starts from it.

Live, step 3 is the same calls through the live backend, and step 4 is the same commit. The difference the twin makes is that steps 1 to 4 can be run, broken, and run again with no credentials, until the sequence is right.

## 4. Monday against Friday

Commit on Monday. Work. Commit on Friday. On [Snapshots](../twin/index.md#/snapshots), diff the two: added, removed and changed, resource by resource, per account, with before and after. Because every snapshot is a commit, this works the same for data seeded by hand and, once the wire exists, for data read from the account; and because the vault document exports as a file, the same diff can be run outside the browser on two exported commits.

## 5. What to be careful about

- **A session can do whatever its role can do.** So the roles should be narrow: one for reading, another for deploying, never more than the job needs. The demo estate seeds a `twin-reader` role with a describe-and-list policy as the example to copy.
- **Short sessions are the default.** One hour, unless there is a reason for more. The session page caps at twelve, as the portal does.
- **The site's own code is what holds the session.** So it should be released the way the family's API sites are, each version a fixed, independent copy, so you know exactly which code you trusted. This site is versioned from its first release for that reason.
- **Credentials never go in a page or a repository.** AWS's guidance for browser code is not to hard-code them. Here they are pasted for one session and kept in the vault; this site's name-watch and validator never see one, and the PoC never shows a secret back.
- **Some calls may need a helper.** Where a service will not answer a browser. That is a fourth backend behind the same interface, not a change to the work.

## 6. Is there a PKI way?

Copying credentials from the portal is good enough to start. It would be better if the session came from a key, as everything else in the family now does. AWS has a service for exactly that: IAM Roles Anywhere exchanges X.509 certificates issued by your own certificate authority, registered as a trust anchor, for temporary credentials. Whether it can work from a browser, signing with a key the browser cannot export, and whether its endpoint answers a browser at all, is untested. Its trust anchors are per account and per region. If it works, it is a fifth backend: the same interface, a session minted from a certificate rather than pasted.

[← The design](../design/index.md)[Why aws.twin →](../naming/index.md)

---

*[This page as HTML](https://aws.twin.sgit.ai/workflow/index.html) · [The site for agents](https://aws.twin.sgit.ai/llms.txt) · CC BY 4.0*
