<!-- the markdown twin of https://aws.twin.sgit.ai/naming/index.html, generated from the same source by admin/build/pages.py; site v0.4.1; content CC BY 4.0 -->

[aws.twin.sgit.ai](../index.md) / naming

# Why `aws.twin`

The article proposed `aws.sgit.ai` "or something wider", and said the name was not decided. It was decided on 2026-10-21, and the decision is the design: the site is a twin first, so it is named as one.

## 1. The decision

| Domain | `aws.twin.sgit.ai` |
|---|---|
| Repository | `SGit-AI__Website__Twin__AWS`, following `SGit-AI__Website__Hook__Tokens` |
| Hub | [twins.sgit.ai](https://twins.sgit.ai), which defines the primitive and will catalogue the twins in place |

The site is designed twin-first, in three steps. Build the twin: an AWS-shaped interface whose backend is a vault. Put the real connection in front of it as a second backend behind the same interface: a temporary IAM Identity Center session pasted into the user's vault. Then everything built against the twin works against the live account, because consuming code is written against the interface, not the backend. That is the pattern of the one working twin today, the S3-compatible vault container, where boto3 cannot tell the difference and the backend is swappable between real S3, a vault and memory. `aws.twin` is the second instance of that pattern, not an exception to it.

### Options considered, and rejected

| Option | Why not |
|---|---|
| `aws.sgit.ai` | Loses the twin-first framing, which is the core of the design. A console with a credential bar is what the name suggests, and it is what the design refuses to be. |
| `aws.platform.sgit.ai` | "Platform" names nothing in the estate; a namespace with one occupant. |
| `aws.provider.sgit.ai` | Provider sites are reports, not tools: where the key lives, what it cost on a named workload, what broke. An AWS report may come later, separately (see below). |

## 2. The convention, by design

- **Plural is the hub, the family:** `twins.sgit.ai`, `hooks.sgit.ai`, `providers.sgit.ai`.
- **Singular is one instance, at that moment in time:** `aws.twin.sgit.ai`, `tokens.hook.sgit.ai`, `elevenlabs.provider.sgit.ai`.
- **Repositories:** `SGit-AI__Website__<Family>__<Instance>`, with the family name singular: `Hook__Tokens`, `Provider__ElevenLabs`, `Twin__AWS`.

**Ops note.** Each singular namespace needs its own wildcard certificate (`*.twin.sgit.ai`, `*.hook.sgit.ai`, `*.provider.sgit.ai`), because `*.sgit.ai` does not cover second-level subdomains.

## 3. The ruling on the hub, and the paragraph this site proposes

[The naming ruling on twins.sgit.ai](https://twins.sgit.ai/naming/index.html) says a corpus twin is the graph's endpoint into reality and holds no credentials, and that the S3 container blurs the line by also holding backend access. The AWS twin is a second case of the same blur, and it resolves it the same way the S3 container does in practice. This site proposes the following paragraph be added to the ruling:

> A twin's interface never holds credentials. A twin can have a live backend; when it does, the credential belongs to that backend, not to the twin, and lives in the user's vault for the lifetime of the session (for AWS: a temporary IAM Identity Center session, 1–12 hours, 1 hour by default). The S3 container and the AWS twin are the two worked examples of this: interface first, backends swappable, live access as one backend among several.

Two things stay distinct under that paragraph. The **execution broker** is a standing, credential-holding intermediary, and the hub's concentration-risk question about it stands. A twin with a live backend **borrows** a user-held, time-bounded session; it never stands, and it holds nothing when the session ends. The PoC makes the distinction mechanical: the session slot is a separate store from the twin's data, with an expiry, and the twin's interface has no method that returns it.

## 4. The name-watch on this site

The hub fails its build on any capitalised *<Word> Twin* that has not been ruled on, and this site runs the same check in `admin/build/validate.js`, with the hub's four permitted terms as the allow-list. This site uses lower case throughout, *the AWS twin*, rather than adding a fifth term; if a capitalised form is ever wanted, it is added to the hub's table with its meaning first, and to this site's allow-list second.

## 5. Later, and separate: an AWS provider report

The providers family answers one question per provider: where the credential lives and what bounds it. For AWS the bound is a clock, and a report could also carry the CORS results per service and the cost of a named workload. That would be `aws.provider.sgit.ai`, a report, separate from this twin, a tool. Before adding it, the providers hub's "no commercial relationship" disclosure has to be checked against sgit.ai's partnerships page for AWS, because a report that is not independent must say so.

[← The workflow](../workflow/index.md)[Built, and designed →](../shipped/index.md)

---

*[This page as HTML](https://aws.twin.sgit.ai/naming/index.html) · [The site for agents](https://aws.twin.sgit.ai/llms.txt) · CC BY 4.0*
