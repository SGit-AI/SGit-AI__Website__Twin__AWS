---
title: boto3 in the browser: the JavaScript SDK is mature enough to build on, Pyodide runs boto3 against the twin in ten seconds, and seven of eight AWS services already answer a browser
date: 2026-10-21
time: 13:00
author: Dinis Cruz
author_url: https://sgit.ai/about/
summary: >
  The AWS twin now exists as a proof of concept, and I asked its build agent to try it
  and to answer two questions before we go further. The first: how mature are the AWS
  APIs for JavaScript that a browser site would lean on, since my understanding is that
  the SDK should already give us an abstraction layer. The second, the one I care about
  more: can we run boto3 in the browser, with Pyodide, because if we can then a lot of
  the work in OSBot-Utils and OSBot-AWS carries over, and that only works if boto3 runs
  there. Behind both is the workflow I want: you hit the twin first, so we see all the
  traffic, simulate it, replay it, and in some cases let it continue to the real thing
  instead of to our local re-implementation of AWS. The answers, measured on 21 October
  2026. The AWS SDK for JavaScript v3 has been generally available since 15 December
  2020, shipped version 3.1154.0 on 20 October 2026, released 188 times this year for
  the S3 client alone, and v2 carries an end-of-support notice; it is mature, modular
  and the right thing to put behind the twin's live backend. boto3 runs in the browser:
  under Pyodide 0.28.3 with Python 3.13.2, boto3 1.43.116 installs from PyPI with one
  extra step, loading Pyodide's unvendored ssl package, and then makes eleven signed
  calls against the twin through one replaced transport function, in ten seconds wall
  including a 24 MB download. And the CORS question the article left open is mostly
  answered: from a page in a browser, STS, Lambda, EC2, IAM, CloudWatch Logs, Cost
  Explorer and CloudFormation answer with Access-Control-Allow-Origin set to any
  origin and a preflight that allows the SDK's headers; S3 alone needs a rule on the
  bucket. Nothing here was run with real credentials; that is the next experiment.
version: v0.2.0
license: https://creativecommons.org/licenses/by/4.0/
tags: [aws, boto3, pyodide, sdk-for-javascript, cors, twins, osbot-aws, traffic, replay, research-brief, article]
status: published
---
!shot boto3-traffic-path.svg | /articles/images/ | The path a boto3 call takes in the browser, as measured. On the left, Python in Pyodide: boto3 builds the request and botocore signs it with SigV4, in the browser, from the session in the vault. In the middle, botocore's transport, one function replaced: its four arrows are the four things the twin design wants from the traffic. Down to the twin, the vault re-implementation that answered eleven calls in the experiment. Sideways to a recording and back from a replay, both drawn as designed. Right, through the browser's fetch to AWS, drawn dashed as not yet run, with the CORS measurement beside it: seven service families answer any origin with a preflight that allows the SDK's headers; S3 needs a rule on the bucket. | diagram

## In short {#in-short}

- **The AWS SDK for JavaScript v3 is the layer to build the live backend on.** Generally available since 15 December 2020, at 3.1154.0 on 20 October 2026, one package per service, released almost daily; v2 reached end of support and says so on npm.
- **boto3 runs in the browser.** Pyodide 0.28.3, Python 3.13.2, boto3 1.43.116 from PyPI; one extra step, loading the `ssl` package Pyodide keeps out of its default build; ten seconds wall and 24 MB on the measured run.
- **One function is the whole transport.** botocore's `URLLib3Session.send` replaced with a function that hands the signed request to the twin; eleven calls across three AWS protocols, every one signed with SigV4 in the browser.
- **That function is where the traffic is seen, simulated, replayed or continued.** It is the point the twin design needs: the same hook sends to the vault, to a recording, from a replay, or on to AWS through fetch.
- **Seven of eight service families answer a browser.** Measured with no credentials: STS, Lambda, EC2, IAM, Logs, Cost Explorer and CloudFormation return `Access-Control-Allow-Origin: *` and a preflight allowing `authorization`, `x-amz-date` and `content-type`. S3 does not, until the bucket has a CORS rule.
- **The cost is the model files.** botocore's wheel is 16.1 MB of the 24 MB because it carries the JSON model of every service; a trimmed wheel is the obvious saving.
- **OSBot-AWS can be tried next, and is not tried here.** boto3 running is the precondition; whether OSBot-Utils' own dependencies load under Pyodide is a separate measurement.
- **Nothing was run live.** The experiments used invented credentials and the twin; the first call to a real account with a pasted session is the next thing to do.

## First, try the twin {#try}

The proof of concept is at [/twin/](../twin/index.html), and I asked the agent to try it before anything else, if it had not already. It had: a headless browser had walked every view, seeded, deployed, committed and diffed, 29 checks, with no console errors. Its own account of that is in [A first go at the AWS twin](first-go-at-the-aws-twin.html). What I want from the twin is on the front page in one sentence, and it is the reason the two questions below matter: everything built against the twin's interface should work against the live account, because the live connection is one backend among several.

## The two kinds of article {#articles}

Every site in the network now carries its own articles, in the shape [send.sgit.ai set out](https://send.sgit.ai/articles/every-site-its-own-articles.html) and cli.sgit.ai runs: articles the agent writes in its own name about what it delivered, and articles written as me, from a voice memo. This is the second kind, and it is also what we call a research brief: the agent documents the current support, which the first article already does in part, and then expands on the question I asked. The memo was transcribed with "Pydantic" and "bot or three"; the agent read them as Pyodide and boto3, and that reading is the one this article answers.

## Question A: how mature are the JavaScript AWS APIs? {#sdk}

My understanding was that the JavaScript SDK should already give us the abstraction layer, so that the twin's live backend is a thin thing. The npm registry, read on 21 October 2026, says the understanding is right.

| Fact | Value | Counted from |
|---|---|---|
| First stable v3 release | 3.0.0 on 15 December 2020 | the registry's time map for @aws-sdk/client-s3 |
| Latest release | 3.1154.0 on 20 October 2026, all eight clients the twin names | the same, for each client |
| Releases of client-s3 in 2026 | 188 to 20 October | count of 3.x versions dated 2026 |
| Versions of client-s3 ever | 795 | the registry's version list |
| Unpacked size | client-s3 3.3 MB, client-lambda 2.0 MB, client-sts 0.47 MB | dist.unpackedSize of the latest |
| v2, the `aws-sdk` package | 2.1693.0 on 9 December 2025, deprecated | the registry's deprecation notice |

The deprecation notice on v2 reads, in full: "The AWS SDK for JavaScript (v2) has reached end-of-support, and no longer receives updates. Please migrate your code to use AWS SDK for JavaScript (v3)." So the choice is made for us, and it is the right one for a twin: v3 is one package per service, one command class per operation, one `send()` with a params object, which is the shape the twin's interface already copies. The twin's manifest was written against it, so wiring the live backend is constructing eight clients from the session and passing each call through. What the SDK does not give is the thing the article of the same day flagged, and the next section measures it.

## The CORS question, measured {#cors}

AWS's own guide says it plainly: "CORS is an important consideration when developing browser applications with the AWS SDK for JavaScript because most requests to resources are sent to an external domain, such as the endpoint for a web service." The article said S3 needs a bucket configuration and the rest was to measure. The agent measured it: from a page served on localhost in a headless browser, two fetches per endpoint, a plain GET and one shaped like the SDK's, with `authorization`, `x-amz-date` and `content-type` headers so the browser sends a preflight. No credentials, so AWS answers with an error when it answers; the question is only whether the browser is allowed to read the answer.

| Service endpoint | Plain GET | SDK-shaped, with preflight | Readable by a browser |
|---|---|---|---|
| sts.amazonaws.com and sts.eu-west-2 | 403 | 403 | yes |
| lambda.eu-west-2 | 403 | 403 | yes |
| ec2.eu-west-2 | 400 | 401 | yes |
| iam.amazonaws.com | 403 | 403 | yes |
| logs.eu-west-2 | 404 | 400 | yes |
| ce.us-east-1 (Cost Explorer) | 400 | 400 | yes |
| cloudformation.eu-west-2 | 403 | 403 | yes |
| s3.eu-west-2, service root and a bucket path | blocked | blocked | no |
| control: example.com | blocked | blocked | no |

"Readable" means the fetch resolved and the status and body could be read; "blocked" means the browser refused it as a cross-origin response without permission. The control row is there because the container the agent runs in reaches the internet through a proxy, and a proxy could add headers; example.com, which sends none, was blocked as it should be. The headers themselves, read with curl against STS, Lambda and IAM, are AWS's: `Access-Control-Allow-Origin: *`, and on the preflight `Access-Control-Allow-Headers: authorization,x-amz-date,content-type`, `Access-Control-Allow-Methods: GET` and `Access-Control-Max-Age: 172800`.

So the helper the article kept in reserve, a small process on the user's machine or an SG/Compute node for services that will not answer a browser, is needed for S3 only, and for S3 the alternative is the one AWS documents: a CORS rule on the bucket, which the deploy template can write when it creates the bucket. Every other service the twin names today answers the browser directly.

## Question B: can we run boto3 in the browser? {#boto3}

This is the one I care about more. If boto3 runs in the browser, then OSBot-AWS, the Python library most of my AWS tooling lives in, and OSBot-Utils underneath it, are candidates to run there too, and the twin becomes the thing they hit first.

The agent built a page that loads Pyodide from its CDN, installs boto3 with micropip from PyPI, and replaces botocore's transport with one function. That function hands each prepared request to the twin's interface, which is the same JavaScript the twin page runs. Then a boto3 script makes eleven calls: STS, S3 and Lambda, which are three different AWS protocols on the wire, query, rest-xml and rest-json.

```
from botocore.httpsession import URLLib3Session
from js import twinBridge                      # the twin, in the same page

def _send(self, request):                      # one function is the transport
    r = twinBridge(request.method, request.url,
                   json.dumps(dict(request.headers)), body_of(request)).to_py()
    return AWSResponse(request.url, r['status'], r['headers'], Raw(r['body']))

URLLib3Session.send = _send
```

| Step | Result | Time |
|---|---|---|
| Load Pyodide 0.28.3 (Python 3.13.2) | loaded | 2.7 s |
| Load the `ssl` and `hashlib` packages | loaded | 0.5 s |
| `micropip.install('boto3')` | boto3 1.43.116, botocore 1.43.116, urllib3 2.5.0, s3transfer, jmespath, dateutil, six | 4.4 s |
| Eleven boto3 calls against the twin | 8 as expected, 3 errors as expected | 1.7 s |
| Whole page, from open to result | | 10.0 s |
| Bytes downloaded | 24.2 MB: Pyodide 6.65 MB, PyPI index 1.22 MB, wheels 16.37 MB | |

Every call was signed: the bridge saw `Authorization: AWS4-HMAC-SHA256 Credential=TWINACCESSKEY/...` on all eleven, computed by botocore in the browser. `sts.get_caller_identity` returned the twin's ARN; `s3.create_bucket`, `put_object`, `list_objects_v2` and `get_object` round-tripped a file; a second `create_bucket` raised `BucketAlreadyOwnedByYou` and a missing key raised `NoSuchKey`, both as boto3 exceptions, because the bridge answered with the XML S3 would send; `lambda.list_functions` came back as JSON. The one 501 was deliberate: `lambda.get_function` is not in the bridge, and boto3 reported it as a `ClientError` with the request the bridge could not answer.

Three things were learned on the way, each a line in the page:

- **Pyodide keeps `ssl` out of its default build**, and botocore imports it on the first line of its HTTP session, through `urllib3.util.ssl_`. The first run failed with "cannot import name 'ssl' from 'urllib3.util.ssl_'". The fix is `pyodide.loadPackage(['ssl', 'hashlib'])` before the import, half a second.
- **boto3 since 1.36 sends `put_object` as an aws-chunked body with a CRC32 trailer** by default. The bridge stored the framing as the object until the client was built with `request_checksum_calculation='when_required'`. A bridge that wants the default must decode the chunked body; a twin that mirrors S3 should.
- **The 16 MB is the models.** botocore's wheel carries the JSON definition of every AWS service, which is how boto3 knows every operation without code per service. A wheel trimmed to the services the twin names would be a fraction of it; nobody has built that trim yet, and the agent did not.

And one thing not learned: the agent did not run OSBot-AWS or OSBot-Utils under Pyodide. boto3 running is the precondition, and it holds; whether those libraries' own imports load is a separate measurement, and it should be the first thing tried next. The article quotes OSBot-AWS at about 1,180 commits, and that is the figure I would want to carry over.

## What the transport hook is for {#hook}

The reason I asked question B is not boto3 for its own sake. It is the workflow. You hit the twin first. That gives us four things, and the experiment shows they all live in the one function:

1. **See all the traffic.** The bridge logged every request with its method, URL, signed headers and body. That is the same call log the twin page shows for its own interface, now for boto3's wire format, which is what the real account would see.
2. **Simulate it.** The twin answered from the vault re-implementation, in the browser, with no account.
3. **Replay it.** A recording of the bridge's requests and responses is a fixture; playing it back is a backend that answers from the recording. Designed, not built; the recording format is the log the bridge already keeps.
4. **Continue it to the real thing.** The same function, calling the browser's fetch instead of the twin, with the signed request as it stands and the CORS table above saying which services will answer. Pyodide's documentation is clear about the limits: "No raw socket access: Browser security prevents direct socket operations" and "CORS restrictions: Cross-origin requests are limited by browser CORS policies". Both are met by fetch and by the measurement.

The twin in the current proof of concept speaks the SDK's shape, `client.s3.listBuckets({})`, not the wire's. For boto3 the bridge translates the wire into the shape, and the experiment's bridge covers three protocols for eleven calls. A twin that answers the wire for every operation in the manifest is bigger than that, and it is also what makes the twin usable from any SDK, boto3 or the JavaScript one, by the same hook. That is the design question this brief leaves open, and I would like it decided before the bridge grows: whether the twin's interface stays SDK-shaped with a wire adapter in front, or moves to the wire with the SDK shape as one client of it.

## What this does not claim {#limits}

- **Nothing was run with real credentials.** The CORS probe was unauthenticated and the boto3 run signed with invented keys against the twin. A real call from a pasted session is the next experiment, not this one.
- **One browser, one machine, one day.** Headless Chromium in a container, through a proxy that terminates TLS, on 21 October 2026. The control row and the curl headers are the evidence the proxy did not add what was measured; a reader's browser on a laptop is the measurement that matters and has not been made.
- **The times vary with the network.** Three runs of the boto3 page took 10.0, 14.3 and 57.8 seconds wall; the slow one spent 52 seconds downloading from PyPI. The bytes were the same each time.
- **"Mature" is from release data, not from use.** Cadence, size and the v2 notice are facts; whether the v3 clients behave well in a browser for the twin's operations is what wiring the live backend will show.
- **OSBot-AWS and OSBot-Utils were not run.** The brief asks whether they could be; the answer here is that their precondition holds.
- **The memo was transcribed, and two words were read, not heard:** Pyodide for "Pydantic", boto3 for "bot or three". If I meant something else, this article answers the wrong question well.

If you have run boto3 under Pyodide against a real account, or trimmed botocore's models to a subset, write to agent@riskmandate.ai.

## Where this comes from {#sources}

A voice memo of mine on 21 October 2026, written up by aws-twin.build, this site's build agent, in the same session that built the proof of concept; the editorial responsibility is mine. The memo's order is kept: try the twin, the two kinds of article, the JavaScript SDK, boto3 under Pyodide and OSBot, the workflow. The experiments and their data are kept beside this article: [articles/data/boto3-twin.html](data/boto3-twin.html), the page that loads Pyodide and boto3 and runs the bridge (it loads from cdn.jsdelivr.net and PyPI, the one page on this site that loads anything from elsewhere); [data/run-boto3.js](data/run-boto3.js), the headless runner; [data/boto3-result.json](data/boto3-result.json), the measured run; [data/cors-probe.js](data/cors-probe.js) and [data/cors-result.json](data/cors-result.json), the CORS measurement; [data/count-sdk-releases.py](data/count-sdk-releases.py), which counted the npm and PyPI facts from the registries' JSON read the same day. Quotations: the npm deprecation notice on `aws-sdk` 2.1693.0; AWS's [CORS page for the SDK for JavaScript v3](https://docs.aws.amazon.com/sdk-for-javascript/v3/developer-guide/cors.html), read 21 October 2026; [Pyodide's pyodide.http documentation](https://pyodide.org/en/stable/usage/api/python-api/http.html), read the same day. The OSBot-AWS commit count is quoted from [AWS from the vault](https://newsroom.sgit.ai/articles/aws-from-the-vault.html) and was not recounted here.
