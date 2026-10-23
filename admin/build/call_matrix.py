#!/usr/bin/env python3
"""Measure the calls page's matrix for the ways outside a browser, and the twin; write
assets/console/call-matrix.json, which the calls page shows beside what it measures in the
reader's own browser.

    python3 admin/build/call_matrix.py                    # code (boto3 here) and the twin
    AWS_CLI=/path/to/aws python3 admin/build/call_matrix.py   # and the AWS CLI

Every call uses invented keys: AWS answering with an error (InvalidClientTokenId and the like)
means the request reached AWS and its answer was read. Needs network to AWS. Keeps the browser
columns already in the file (admin/build/call_matrix_browser.js writes those)."""
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)
OUT  = os.path.join(ROOT, 'assets', 'console', 'call-matrix.json')


def measure_code(row):
    import boto3
    from aws_twin.web.Call__Matrix import PROBE_KEYS, classify
    from botocore import xform_name
    client = boto3.client(row['service'], region_name=row['region'], **PROBE_KEYS)
    params = dict(row['params'])
    if 'Payload' in params:
        params['Payload'] = params['Payload'].encode()
    started = time.time()
    try:
        getattr(client, xform_name(row['operation']))(**params)
        out = classify()
    except Exception as e:
        out = classify(e)
    return dict(out, ms=round((time.time() - started) * 1000))


def measure_twin(row):
    import boto3
    from aws_twin import Twin
    from aws_twin.web.Call__Matrix import classify
    from botocore import xform_name
    with Twin():
        client = boto3.client(row['service'], region_name=row['region'])
        params = dict(row['params'])
        if 'Payload' in params:
            params['Payload'] = params['Payload'].encode()
        try:
            getattr(client, xform_name(row['operation']))(**params)
            return {'status': 'twinned'}
        except Exception as e:
            out = classify(e)
            if out.get('code') == 'NotImplemented':
                return {'status': 'not twinned'}
            return {'status': 'twinned', 'code': out.get('code')}       # an answer (often: needs state) is the twin's own


def measure_cli(row, cli):
    env = dict(os.environ, AWS_ACCESS_KEY_ID='INVENTED-KEY-FOR-PROBE', AWS_SECRET_ACCESS_KEY='invented-for-the-call-matrix',
               AWS_SESSION_TOKEN='invented-session-token', AWS_DEFAULT_REGION=row['region'], AWS_PAGER='')
    env.pop('AWS_PROFILE', None)
    started = time.time()
    done = subprocess.run([cli] + row['cli'] + ['--region', row['region']], env=env, capture_output=True, text=True, timeout=120)
    ms, err = round((time.time() - started) * 1000), (done.stderr or '')
    import re
    m = re.search(r'An error occurred \(([\w.]+)\)', err)
    if done.returncode == 0:
        return {'status': 'ok', 'ms': ms}
    if m:
        return {'status': 'reached', 'code': m.group(1), 'ms': ms}
    return {'status': 'error', 'code': 'cli', 'message': err.strip().splitlines()[-1][:200] if err.strip() else f'exit {done.returncode}', 'ms': ms}


def main():
    import boto3
    from aws_twin.web.Call__Matrix import rows
    old  = json.load(open(OUT)) if os.path.exists(OUT) else {'rows': []}
    prev = {r['id']: r for r in old.get('rows', [])}
    cli  = os.environ.get('AWS_CLI') or shutil.which('aws')
    cli_version = subprocess.run([cli, '--version'], capture_output=True, text=True).stdout.strip() if cli else None
    out_rows = []
    for row in rows():
        r = {'id': row['id'], 'code': measure_code(row), 'twin': measure_twin(row)}
        r['cli'] = measure_cli(row, cli) if cli else prev.get(row['id'], {}).get('cli')
        for k in ('pyodide', 'jssdk'):
            if prev.get(row['id'], {}).get(k):
                r[k] = prev[row['id']][k]
        out_rows.append(r)
        print(f"{row['id']:38} code {r['code']['status']:8} cli {(r['cli'] or {}).get('status', '-'):8} twin {r['twin']['status']}")
    doc = {'measured': {'code': time.strftime('%Y-%m-%d'), 'cli': time.strftime('%Y-%m-%d') if cli else old.get('measured', {}).get('cli'),
                        'browser': old.get('measured', {}).get('browser')},
           'versions': {'boto3': boto3.__version__, 'aws_cli': cli_version or old.get('versions', {}).get('aws_cli'),
                        'pyodide': old.get('versions', {}).get('pyodide'), 'js_sdk': old.get('versions', {}).get('js_sdk'),
                        'browser': old.get('versions', {}).get('browser')},
           'rows': out_rows}
    with open(OUT, 'w') as f:
        json.dump(doc, f, indent=1)
    print(f'wrote {os.path.relpath(OUT, ROOT)}: {len(out_rows)} calls')


if __name__ == '__main__':
    main()
