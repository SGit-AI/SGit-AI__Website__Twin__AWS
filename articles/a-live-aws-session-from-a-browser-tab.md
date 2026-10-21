---
title: A live AWS session from a browser tab: Python in the page signed a request with my real Identity Center session, AWS answered, and no server of ours was in the path
date: 2026-10-21
time: 19:00
author: Dinis Cruz
author_url: https://sgit.ai/about/
summary: >
  This morning the AWS twin was an idea in a newsroom article. By the evening I pasted
  a session from my own IAM Identity Center into a page on aws.twin.sgit.ai, pressed
  a button, and Python running inside the browser tab, boto3 under Pyodide with the
  twin's hook in front of it, signed a request with that session and sent it to AWS
  STS, which answered with my account, my role and my user. No backend, no proxy of
  ours, no credentials stored anywhere but the tab, for the session's hour. I think
  that is a major milestone, and this is why. It means the Python I have written for
  years, OSBot-AWS and OSBot-Utils, runs in a page against a real account; that the
  same code and the same tests run in CI against the twin; and that the twin sits in
  front of every call, so we see, record and choose where each one goes. The build
  agent then took it to S3: the S3 browser can go live, directly for STS and for
  buckets with a CORS rule, and through a small relay on my own machine for what S3
  will not answer a browser, such as listing buckets. The relay holds no credentials
  and cannot make a request I did not sign. And because the session I checked was
  AdministratorAccess, it also wrote the page I needed next: least privilege for the
  twin, with IAM Identity Center permission sets that can only list bucket names, or
  read one bucket. Browsing my real buckets with a narrow role is the next thing I do.
version: v0.4.0
license: https://creativecommons.org/licenses/by/4.0/
tags: [aws, twins, python, pyodide, boto3, osbot-aws, s3, sts, cors, relay, iam-identity-center, least-privilege, milestone, article]
status: published
---
!shot live-from-the-tab.svg | /articles/images/ | From a browser tab to a real AWS account. On the left, the tab: the S3 browser, OSBot-AWS and boto3 in Python under Pyodide; the pasted session, in the tab's sessionStorage for its hour; botocore signing every request with SigV4, so the secret key is used in the tab and never leaves it; the twin's hook choosing twin, live or replay; every request recorded, and writes refused in live mode unless allowed. On the right, the account. STS answers any origin, so the request goes straight from the browser, and a real session was checked that way. A bucket with a CORS rule for this site answers directly too. S3's ListBuckets, and buckets without a rule, never answer a browser, so the signed request goes to a one-file relay on the user's own machine, which adds the CORS headers and passes it on unchanged; AWS checks the signature. No server of ours is in the path. | diagram

## In short {#in-short}

- **A real session, from a browser tab, answered by AWS.** I pasted my IAM Identity Center session on [the sessions page](../sessions/index.html), pressed **Check it against AWS**, and STS GetCallerIdentity came back with my account, my role and my user. Signed by botocore in Python, in the page, and sent by the browser.
- **No server of ours in the path.** The tab signs; the browser sends; AWS checks the signature. The session lives in the tab's sessionStorage and nowhere else, and expires in an hour.
- **The same Python everywhere.** OSBot-AWS and boto3 make the same calls in CI, against the twin, and in the page, against the account. One package, one set of tests.
- **The twin sees every call first.** One hook inside botocore decides per service: answer from the twin, send on to AWS, or replay a recording. Every request is recorded either way.
- **S3 is live now too.** The S3 browser goes live directly for buckets with a CORS rule for this site, and through a one-file relay on my own machine for the rest, including listing buckets, which S3 never answers to a browser.
- **The relay cannot act for me.** It holds no credentials, forwards only to AWS, only for this site, only on 127.0.0.1, and sees a signature valid for one request, never the secret key.
- **Read-only by default.** In live mode the S3 browser refuses every write before it sends anything, unless I tick **Allow writes**.
- **And the uncomfortable part.** The session I checked was AdministratorAccess. That is why there is now [a least-privilege page](../iam/index.html): permission sets that can only list bucket names, read one bucket, read one folder, or read and write one bucket, with the commands checked.

## What happened today {#today}

This morning, the newsroom published [AWS from the vault](https://newsroom.sgit.ai/articles/aws-from-the-vault.html), and the naming was decided: aws.twin.sgit.ai. Through the day the agent built [a first proof of concept](first-go-at-the-aws-twin.html), measured [boto3 running in the browser](boto3-in-the-browser.html) under Pyodide, and then [moved the twin itself to Python](the-twin-is-python-now.html), so that the twin, OSBot-AWS and the tests are one Python codebase that runs both under pytest and in the page.

Then I wired GitHub Pages to the repository, the site deployed, and I did the obvious thing. I signed in to my AWS access portal, picked the account and the role, copied the access keys block, and pasted it into the sessions page. The check came back with the account id, the role, and my user. My first reaction, honestly, was that this is a bit insane. Not because calling STS is hard, but because of everything that had to be true for it to work from a static page.

## Why I think it is a milestone {#why}

Look at what that one request needed. A CPython interpreter, compiled to WebAssembly, running in the tab. boto3 and botocore, unmodified, from PyPI. The twin's own Python package, unpacked from a zip the site serves. SigV4 signing, done by botocore, in the browser, with a secret that was pasted a minute before and never sent anywhere. A route table that said "STS goes live". And AWS answering a browser, which STS does, for any origin.

None of that involved a server of ours. That matters to me for three reasons.

**The code I already have carries over.** I have years of AWS tooling in Python, most of it in OSBot-AWS and OSBot-Utils. If boto3 runs in a page, then that code runs in a page, and the agent showed OSBot-AWS doing exactly that against the twin earlier today. Now the same calls reach a real account.

**The twin is in front of everything.** This was the point of the design: you hit the twin first. Every call goes through one hook, which records it and decides where it goes. Against the twin it costs nothing and needs no credentials. Against the account it is the same call, the same code, recorded the same way. So what we build and test against the twin is what runs against the account, and a recording of the account becomes a test that needs no account.

**Credentials stay where they should.** The session is temporary, comes from Identity Center, lives in one tab for one hour, and is used only to compute signatures inside that tab. There is no place on our side where it could leak from, because there is no our side in the path.

## Then S3 {#s3}

STS answers a browser. S3 mostly does not: a bucket answers a page only when the bucket has a CORS rule naming that page's origin, and the call that lists all buckets never answers a browser at all. So I asked how I could browse my real files with the S3 browser, and the agent built both ways.

**Directly**, for buckets with a CORS rule for aws.twin.sgit.ai. The rule is a file on the site and one CLI command; it grants nothing by itself, it only lets the page read answers my session is already allowed to get.

**Through a local relay**, for everything else. This is the part I asked to have explained properly, and it now has [its own page, with diagrams](../how-it-works/index.html#relay). In short: it is one Python file, standard library only, that I download, read and run on my own machine. The page sends it the already-signed request with the real AWS address in a header; it checks that the address is AWS over HTTPS and that the request comes from aws.twin.sgit.ai; it sends the request on unchanged and gives the answer back with the CORS headers the browser wants. AWS checks the signature exactly as it would from anywhere. The relay never sees the secret key, so it cannot make a request I did not sign. Chrome asks once whether the site may talk to something on my machine, and I allow it.

The agent tested that path end to end in a headless browser without an AWS account, with the twin's own server standing in for AWS behind the relay, and that caught three bugs that would each have broken the first real upload or download. Those are on the explainer page too, and I like that they were found by a stand-in rather than by my buckets.

The S3 browser is **read-only by default** in live mode. Upload, delete, rename and the rest are refused before any request is made, unless I tick **Allow writes**. That is a brake on the twin's mistakes and on mine.

## The uncomfortable part: AdministratorAccess {#admin}

The session I checked was AdministratorAccess. That is the role I have been signing in with, because it was the one that was there, and it has a ridiculous amount of power for browsing a few buckets. So the other page the agent wrote today is [least privilege for the twin](../iam/index.html).

The idea that changed how I think about it: in Identity Center the power is not in the user I sign in as, it is in the role I pick after signing in. Each permission set assigned to me shows up as a role in the portal. So the fix is to have narrow permission sets and pick them by default, and to move AdministratorAccess to a separate sign-in that my daily session cannot reach. The page has the four S3 recipes as policy files (list bucket names and nothing else, read one bucket, read one folder, read and write one bucket), the CLI to create the permission sets, groups and assignments, how to test a policy with the IAM simulator before anyone has it, and the order to do things in so I do not lock myself out. Every command on it was run through the AWS CLI's own parameter checks against the twin before it was published, and CI now checks them on every push.

## What is next {#next}

- **Browse my real buckets with a list-only role.** Create S3-List-Bucket-Names, sign in, pick it, paste the session, start the relay, go live. Bucket names should appear, and opening one should say AccessDenied. That is the least-privilege setup working, and it is the first real-account S3 test.
- **Then read one bucket**, with the read recipe, directly with a CORS rule and through the relay, and compare the traffic.
- **Move the administrator role** to its own user, as the page says, in that order.
- **Record a live session and replay it** against the twin, which is the workflow this whole thing exists for.
- **Keep the session somewhere better than a tab.** A vault is the slot the design has for it, and Cognito identity pools or web identity are the measured ways to get one without pasting.

## What this does not claim {#limits}

- That the S3 browser has browsed a real account. It has browsed the twin, and a stand-in for AWS behind the relay; my real session has been checked against STS. The real-account S3 browse is the next step above.
- That the relay is safe to expose. It listens on 127.0.0.1 and answers one site; running it any other way is not what it was written for.
- That the IAM commands were run against a real organisation. They were validated by the AWS CLI against the twin; AWS validates the policy grammar when it is put.
- That this is how sessions should be obtained long term. Pasting works today and holds nothing; it is the first method, not the last.

## Where this comes from {#sources}

My voice memo and messages of 21 October 2026, after checking my own session, published in full in [the briefs](../briefs/index.html). What was built is on [How it works](../how-it-works/index.html) and [Least privilege for the twin](../iam/index.html); the code is in [the repository](https://github.com/SGit-AI/SGit-AI__Website__Twin__AWS). Earlier today: [AWS from the vault](https://newsroom.sgit.ai/articles/aws-from-the-vault.html), [A first go at the AWS twin](first-go-at-the-aws-twin.html), [boto3 in the browser](boto3-in-the-browser.html), [The twin is Python now](the-twin-is-python-now.html).
