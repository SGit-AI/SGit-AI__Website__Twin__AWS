<!-- the markdown twin of https://aws.twin.sgit.ai/design/index.html, generated from the same source by admin/build/pages.py; site v0.4.2; content CC BY 4.0 -->

[aws.twin.sgit.ai](../index.md) / design

# The design

One AWS-shaped interface, and behind it a backend chosen at runtime: the vault, memory, or the live account. The claim this page has to earn is that consuming code written against the interface does not know which. The PoC earns it the way the S3 container does, by running the same script against two backends and checking the answers match.

## 1. One interface, three backends

**Consumers**: the UI on [the twin page](../twin/index.md), the two deployment templates, the account graph, the snapshot diff, the tests. None of them reads a backend's state; each makes calls.

↓

**The interface**: `AwsTwin.client(backend, {accountId, region})`. Nine namespaces (eight AWS-shaped, one twin-only), 45 operations, a manifest of accepted params. One client per account and region, like an SDK client bound to a session.

↓

**Vault** PoC
The ops over a state document, persisted to localStorage as a document with commits and a head. The twin proper.

**Memory** PoC
The same ops, nothing persisted. The test double, and the third backend in the S3 container's list.

**Live** slot built
Reads a session from the vault; would construct SDK v3 clients per call. In this PoC it refuses each call naming the command it would send.

The vault and memory backends share one implementation of the operations and differ only in `save()`. That is deliberate: it keeps the semantics in one place, and it is what lets the equivalence test hold without a special case.

## 2. The interface

The shape follows the AWS SDK for JavaScript v3, because that is what the live backend will call: every operation takes one params object with the SDK's PascalCase keys (lower camel for CloudWatch Logs, as in AWS), returns a Promise of one result object, and fails with an error whose `code` is the AWS error name (`NoSuchBucket`, `ResourceConflictException`, `InvalidGroup.NotFound`). A param the manifest does not list is refused with `UnknownParam` before any backend sees it, so a typo cannot silently succeed on the vault and fail live.

| Namespace | Operations in the manifest | Scope |
|---|---|---|
| `sts` | getCallerIdentity | global |
| `s3` | listBuckets, createBucket, deleteBucket, headBucket, listObjectsV2, putObject, getObject, deleteObject | global; buckets carry a region |
| `lambda` | listFunctions, getFunction, createFunction, updateFunctionConfiguration, deleteFunction, invoke | per region |
| `ec2` | describeInstances, runInstances, startInstances, stopInstances, terminateInstances, describeSecurityGroups, createSecurityGroup, authorizeSecurityGroupIngress | per region |
| `iam` | listRoles, getRole, createRole, deleteRole, listPolicies, createPolicy, attachRolePolicy, detachRolePolicy, listAttachedRolePolicies | global |
| `logs` | describeLogGroups, createLogGroup, deleteLogGroup, putLogEvents, filterLogEvents | per region |
| `ce` | getCostAndUsage (monthly or daily, grouped by service or region) | global |
| `cloudformation` | listStacks, describeStacks, createStack, deleteStack | per region |
| `twin` | recordCost, snapshot, state | twin-only: never sent live |

The `twin` namespace is the one deliberate departure. AWS has no call that writes a cost; reality does that. The twin needs an input for it, and for reading the whole state to build a graph. Those live under `twin.*`, never under an AWS service name, so the boundary between AWS-shaped and twin-only stays visible in the call log, and the live backend refuses them with `TwinOnly` rather than inventing an endpoint.

Behaviour is kept where it is cheap and telling: a function needs a role that exists; a role cannot be deleted while a policy is attached or a function uses it; a bucket cannot be deleted while it holds objects; a bucket name is validated; instances and functions are per region, so stopping an instance from the wrong region fails with `InvalidInstanceID.NotFound`; invoking a function writes four lines to its log group. These are the behaviours a rehearsal is for.

## 3. The state document

One document per vault, one account record per account inside it. Every resource carries the region it lives in, and the per-region services filter on the client's region at call time.

```
// AwsTwin.emptyState() → one account added
{ "version": 1,
  "accounts": {
    "111111111111": {
      "accountId": "111111111111", "name": "sg-send-dev (illustrative)",
      "s3":             { "buckets": [], "objects": {} },
      "lambda":         { "functions": [] },
      "ec2":            { "instances": [], "securityGroups": [] },
      "iam":            { "roles": [], "policies": [], "attachments": [] },
      "logs":           { "groups": [], "events": {} },
      "ce":             { "records": [] },
      "cloudformation": { "stacks": [] },
      "twin":           { "invocations": [] }
    }
  }
}
```

Add a service by adding a key here, its operations to the manifest, and their implementation to the ops table; the tests fail until the manifest and the ops agree, which is the first test in the file.

## 4. The vault backend

In the PoC the vault is the browser's localStorage, under one key, `aws.twin/vault`, holding one document:

```
// aws.twin/vault@1
{ "format": "aws.twin/vault@1", "name": "aws-twin", "created": "…",
  "head": "<commit id>",
  "commits": [ { "id", "parent", "at", "message", "summary", "state" }, … ],
  "working": { …the state document… } }
```

That is the shape an sgit vault gives for free: a working tree, commits, a head. The export button on the snapshots page downloads exactly this document, and the import button continues from one, so the hand-off to a real vault is a file today and a sync later. Commit ids in the PoC are content hashes of the commit (not cryptographic; the vault's own hashes take over once the document is pushed through sgit). The full state is kept per commit because the states are small and a diff between any two commits must be cheap.

## 5. Snapshots, and the diff

A snapshot is a commit of the whole state document. A diff flattens each account into resource keys (`s3:bucket name`, `lambda:function region/name`, `iam:role name`, …) with the fields that matter for "has this changed", and reports added, removed, changed and unchanged. The vault's working state can be diffed against any commit, which is how "uncommitted changes" is computed for the bar at the top of the twin page.

The diff keys are chosen, not derived: a bucket changes when its object count changes, a role when its attachments change, an instance when its state or type changes, the cost total when a record is added. That is the right level for Monday against Friday, and the wrong level for an audit, which would want every field. Both are available: the commit holds everything.

## 6. The live backend, and what the wire needs

The live backend's job is to answer the same manifest by sending each call to AWS with the session in the vault. In this PoC it has its slot and not its wire: it reads the session, checks it is present and unexpired, and then refuses with `NotWired`, naming the SDK command, the service endpoint, the region, the account and the expiry it would have used. The UI, the templates and the graph can all be pointed at it, and every call shows the gap precisely.

Wiring it needs three things, and nothing on the consuming side:

1. **The SDK for JavaScript v3 clients** for the eight services, constructed per call from the session's three values, with the region from the client's scope. Released as a fixed, independent copy per site version, so the code that holds the session is a known thing.
2. **A CORS measurement per service.** Made on 2026-10-21, with no credentials: STS, Lambda, EC2, IAM, Logs, Cost Explorer and CloudFormation answer any origin with a preflight that allows the SDK's headers; S3 does not until the bucket has a CORS rule, which the deploy template can write when it creates the bucket. [The table and the data →](../articles/boto3-in-the-browser.md#cors). Where a service will not answer, a small helper on the user's own machine, or an SG/Compute node, makes that call behind the same interface: a fourth backend, not a change to the consumers.
3. **Results back into the vault.** A live read is a snapshot like any other: the response is written into the state document and committed, so the live backend and the vault backend are not alternatives but a pair.

**Where the credential lives.** The twin's interface never holds it. The live backend reads it from the session slot, which is sessionStorage in this PoC: the tab's lifetime, never written to disk by the browser the way localStorage is, with the expiry the user gave it (one to twelve hours). The slot refuses a session without a token, because a long-lived IAM user key is exactly what this design declines to hold. This is the resolution the naming page proposes for the hub's ruling: [a twin can have a live backend; the credential belongs to the backend, not the twin](../naming/index.md#ruling).

## 7. The account graph

Resources as nodes, relationships as edges, built from the state the interface returns via `twin.state`. Eight node kinds and six relations in the PoC:

| Edge | From → to | Where it comes from |
|---|---|---|
| `attached_policy` | role → policy | IAM attachments, including AWS managed policies as nodes |
| `assumes_role` | function → role | the function's `Role` |
| `uses_bucket` | function → bucket | any environment variable whose value is a bucket name in the account |
| `writes_logs` | function → log group | `/aws/lambda/<name>` in the same region |
| `in_security_group`, `instance_profile` | instance → security group, instance → role | the instance's groups and profile; terminated instances leave the graph |
| `created` | stack → resource | what the template reported creating |

The twin page draws it as layered SVG, one column per kind, and prints it as Mermaid for pasting elsewhere. The point is not the drawing. It is that the graph is a function of the state document, so it is the same function for a seeded account and a live snapshot, and a diff of two graphs is a diff of two commits.

## 8. Templates are calls

A deployment template in the twin is a function given a client and the stack's parameters. It makes ordinary calls: create the role if missing, the per-account-per-region bucket if missing, the policy, attach it, create the function with its image and environment. CloudFormation's `createStack` runs the template against the interface itself, so the stack's resources are the ARNs those calls produced and the stack's deletion reverses the ones that belong to it. A rehearsal against the vault is therefore the same calls as the live run; only the backend differs.

Two templates ship, standing in for the SG/Send server components: Lambda as a container image with a function URL, and ECS Fargate. The manifest has no `ecs` namespace yet, so the Fargate template creates the role, bucket, security group and log group it can, and records the service it cannot as a stack output that says so: *not in the interface: tracked gap*. That is the discipline the twins hub asks for, applied to the twin's own coverage.

## 9. The tests

`node admin/build/test.js` runs the same script (bucket, objects, role, policy, function, invoke, instance, cost, two stacks, a deletion) against the memory backend and against the vault backend over a storage shim, normalises what is random by design (ids, timestamps, request ids, the invoke duration) and asserts the answers are identical, step by step. It then checks the expected answers, the commit and checkout round trip, the diff, the graph's node and edge counts after seeding, the session slot's parsing and refusals, and the async client the UI uses. As of 2026-10-21: 214 assertions, all passing, in under a second. The browser has no test runner; the twin page's call log is the manual one.

## 10. Open in the design

- **Live and vault disagree.** When the wire exists, a live read will differ from the last commit. The vault is the record and live is the source; the right move is a commit, with the diff as the message. Nothing enforces that yet.
- **Staleness.** A commit carries its time, and the hub's first open question applies here exactly: a connected twin can be six days stale. The bar shows "uncommitted changes" and not "last read live at", because there is no live read yet.
- **Which services, which fields.** The manifest is what the first job needs plus what the article lists. ECS, Route 53, ECR and SSM are the obvious next namespaces; each is a key in the state document, a manifest entry and an ops entry.
- **Multi-account is multi-session.** A client is bound to one account because a session is. The deploy rehearsal makes one client per target. Live, that is one paste per account, which is the article's deliberate trade.

[← Open the twin](../twin/index.md)[The workflow →](../workflow/index.md)

---

*[This page as HTML](https://aws.twin.sgit.ai/design/index.html) · [The site for agents](https://aws.twin.sgit.ai/llms.txt) · CC BY 4.0*
