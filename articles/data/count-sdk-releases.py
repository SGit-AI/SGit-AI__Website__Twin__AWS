#!/usr/bin/env python3
"""The counts in 'boto3 in the browser', made from the registries' own JSON.
Run with network: python3 -I count-sdk-releases.py  (reads npm and PyPI, prints the table)."""
import json, urllib.request
def get(u):
    with urllib.request.urlopen(u, timeout=60) as r: return json.load(r)
for name in ['client-s3', 'client-sts', 'client-lambda', 'client-ec2', 'client-iam', 'client-cloudwatch-logs', 'client-cost-explorer', 'client-cloudformation']:
    d = get('https://registry.npmjs.org/@aws-sdk%2F' + name); t = d['time']; latest = d['dist-tags']['latest']
    stable3 = [v for v in d['versions'] if v.startswith('3.') and not any(x in v for x in ['alpha', 'beta', 'rc', 'gamma', 'preview'])]
    first = min(stable3, key=lambda v: t[v])
    this_year = sum(1 for v in stable3 if t[v][:4] == '2026')
    print(f'@aws-sdk/{name}: latest {latest} ({t[latest][:10]}), first stable 3.x {first} ({t[first][:10]}), {len(d["versions"])} versions, {this_year} releases in 2026, unpacked {d["versions"][latest]["dist"].get("unpackedSize")} bytes')
d = get('https://registry.npmjs.org/aws-sdk'); latest = d['dist-tags']['latest']
print(f'aws-sdk (v2): latest {latest} ({d["time"][latest][:10]}); deprecated: {d["versions"][latest].get("deprecated")}')
for name in ['boto3', 'botocore', 'urllib3']:
    d = get(f'https://pypi.org/pypi/{name}/json'); v = d['info']['version']
    for f in d['releases'][v]:
        if f['filename'].endswith('.whl'): print(f'{name} {v}: {f["filename"]} {f["size"]} bytes, {f["upload_time"][:10]}')
