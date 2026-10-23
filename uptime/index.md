<!-- the markdown twin of https://aws.twin.sgit.ai/uptime/index.html, generated from the same source by admin/build/pages.py; site v0.4.2; content CC BY 4.0 -->

[aws.twin.sgit.ai](../index.md) / uptime

# Uptime checks from every region, with reports only a vault can read

Deploy a Lambda function that checks whether websites are up, to as many AWS regions as you pick, on a schedule. Each report is encrypted to a public key and appended to an sgit vault's lane, which only the private key's holder can read. Everything here is boto3 running in this page: against the **twin** by default, so you can deploy, run, break and read it with no AWS account, and against your **account** with the session from [the sessions page](../sessions/index.md). The function is one Node.js file with no dependencies, the same file in the twin and on Lambda. [The plan, and why Node.js →](plan.md)

loading Python…

Python, boto3 and the twin load in this page (about 25 MB the first time).

## 1. What to check, and where from

Websites, one per line http or https; at most 50; private addresses are refused by the function

Schedule

 A function URL per regionfor requests signed by a controller key

 CloudFront in frontone hostname, a path per region

Controller key, optional an ECDSA P-256 public key (PEM; an sgit bundle's `sign` key): function URL requests must be signed by it

## 2. Where the reports go

 RSA-OAEP 4096, as sgit's keys are. The private half is kept in this browser's IndexedDB, not exportable, and never sent anywhere.

Or the public key to encrypt to an sgit public-key bundle (`sgit pki export`) or a PEM; then read the reports with `sgit pki decrypt`

In the twin, a lane is made for you on a twinned `dev.send.sgraph.ai`.

Append server

Vault id

Append token hex, registered as an anchor

Enum key to read the lane back

## 3. The twin's internet

What each website answers when the function checks it from the twin. On AWS, the real sites answer.

| Website | Answers | Delay |
|---|---|---|

## 4. Deploy, run, read

Region

| Region | Function | Invocations |
|---|---|---|

```

```

## 5. The reports, decrypted here

No reports read yet.

## The function

One file, `index.mjs`, zipped and uploaded by boto3 as it is. [On GitHub](https://github.com/SGit-AI/SGit-AI__Website__Twin__AWS/blob/dev/aws_twin/apps/uptime/handler/index.mjs), and the [deploy code](https://github.com/SGit-AI/SGit-AI__Website__Twin__AWS/blob/dev/aws_twin/apps/uptime/Uptime__Deploy.py) this page calls.

Show index.mjs

```
loading…
```

[← The plan](plan.md)[How it works →](../how-it-works/index.md)

---

*[This page as HTML](https://aws.twin.sgit.ai/uptime/index.html) · [The site for agents](https://aws.twin.sgit.ai/llms.txt) · CC BY 4.0*
