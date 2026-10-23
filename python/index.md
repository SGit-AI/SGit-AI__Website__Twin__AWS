<!-- the markdown twin of https://aws.twin.sgit.ai/python/index.html, generated from the same source by admin/build/pages.py; site v0.4.2; content CC BY 4.0 -->

[aws.twin.sgit.ai](../index.md) / python

# The Python twin

The twin is now Python. It answers the HTTP requests boto3, OSBot-AWS or the AWS CLI send, signed as they would be for AWS, from a virtual file system instead of an account. The same package runs in CI under pytest, on a laptop as a local endpoint, and in this browser under Pyodide, where it is what [the console](../console/index.md) talks to.

## 1. Why Python, and why the wire

The first proof of concept was a JavaScript object with an SDK-shaped interface. That was the wrong layer for the twin, for three reasons that became clear once boto3 ran in the browser:

- **The backend code is Python.** OSBot-AWS, OSBot-Utils and the earlier twin experiments are Python; a twin in the same language can be tested with the same tools and reused by the same projects.
- **The wire is the only interface every client shares.** A twin that answers S3's REST-XML protocol serves boto3, OSBot-AWS, the AWS CLI and the JavaScript SDK alike, unchanged. A twin that answers an SDK's shape serves one SDK.
- **The same code runs in CI and in the browser.** Pyodide runs CPython; the twin uses only the standard library; boto3, OSBot-Utils and OSBot-AWS install from PyPI in both places at the same pinned versions.

## 2. What is in the package

| Module | What it does |
|---|---|
| `aws_twin/core/Twin.py` | The router and the botocore hook. `with Twin():` sends every botocore request to the twin; the service comes from the SigV4 credential scope; each service has a route: **twin**, **live** (sent on to AWS and recorded) or **replay** |
| `aws_twin/s3/S3__Twin.py` | S3's REST-XML protocol over the VFS: buckets, objects, listing with delimiters and continuation, ranges, conditional writes, copy, delete-many, multipart, tagging, policy and CORS stored as sent |
| `aws_twin/sts/STS__Twin.py` | GetCallerIdentity, so code that asks who it is before acting gets an answer |
| `aws_twin/vfs/` | The storage: sg-vfs's provider contract from SGraph-AI__Tools, in Python. Memory (with a change journal) and disk providers |
| `aws_twin/core/Twin__Traffic.py`, `Twin__Replay.py` | Every request and answer recorded; a recording played back as a backend |
| `aws_twin/core/Twin__Server.py` | The twin as a real HTTP endpoint (CPython): `python -m aws_twin --port 4566` |
| `aws_twin/web/` | The browser pages' Python sides: the S3 browser's API and the live session check |

Services the twin does not have answer `501 NotImplemented` with the operation named, so a gap shows in the traffic and never as a silent success.

## 3. Use it

```
# in a test, in-process: no port, no server, no credentials
from aws_twin import Twin
with Twin() as twin:
    from osbot_aws.aws.s3.S3 import S3
    S3().bucket_create('my-bucket', 'eu-west-2')
    print(twin.traffic.summary())

# as a local endpoint, for the AWS CLI or anything that reads AWS_ENDPOINT_URL
python -m aws_twin --port 4566 --root ./twin-data
export AWS_ENDPOINT_URL=http://127.0.0.1:4566
aws s3 mb s3://my-bucket

# send STS on to the real account, keep S3 on the twin
with Twin(routes={'sts': 'live'}): ...
```

The endpoint form is the one OSBot-Local-Stack uses for LocalStack: OSBot-AWS reads `AWS_ENDPOINT_URL`, so code written for LocalStack runs against the twin with no change.

## 4. One suite, two interpreters

The tests are plain functions with plain asserts, so pytest runs them in CI and a 27-line runner runs them here. Measured on 21 October 2026:

| Where | Interpreter | Result |
|---|---|---|
| pytest, CPython | Python 3.13, boto3 1.43.116, OSBot-AWS 2.39.10, OSBot-Utils 3.75.0 | 18 passed |
| this browser, Pyodide 0.28.3 | Python 3.13.2, the same three packages from PyPI | 16 passed, 2 skipped (the local endpoint and the disk provider: no sockets or disk in a browser) |

[Run them in this browser →](tests.md) CI runs both: pytest on every push, and the same suite in headless Chromium.

## 5. What it does not do yet

- **Two services.** S3 and STS GetCallerIdentity. Lambda, EC2, IAM, CloudWatch Logs, Cost Explorer and CloudFormation are in the JavaScript proof of concept's manifest and are the next to move.
- **No signature check.** The twin reads the credential scope to route, and does not verify the signature. A twin that checks signatures against pasted keys would also prove the client signed correctly.
- **No object versions.** Versioning is stored and listed as one version per object.
- **Live from the browser is STS only, measured.** The live route works for any service that answers a browser; S3's service endpoint does not without a bucket CORS rule.

[← AWS sessions](../sessions/index.md)[Run the tests →](tests.md)

---

*[This page as HTML](https://aws.twin.sgit.ai/python/index.html) · [The site for agents](https://aws.twin.sgit.ai/llms.txt) · CC BY 4.0*
