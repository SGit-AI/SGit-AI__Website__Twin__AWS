#!/usr/bin/env python3
"""Zip aws_twin/ and tests/ into assets/py/aws_twin.zip, the file the browser unpacks into
Pyodide's file system. Deterministic (sorted names, fixed timestamps), so the zip only
changes when the code does, and `--check` fails if the committed zip is stale."""
import hashlib
import io
import os
import sys
import zipfile

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..'))
OUT  = os.path.join(ROOT, 'assets', 'py', 'aws_twin.zip')


def build():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        for top in ('aws_twin', 'tests'):
            for folder, dirs, files in os.walk(os.path.join(ROOT, top)):
                dirs[:] = sorted(d for d in dirs if d != '__pycache__')
                for f in sorted(files):
                    if f.endswith(('.py', '.mjs')):                      # .mjs: the Lambda twin's Node.js harness, the uptime function
                        full = os.path.join(folder, f)
                        info = zipfile.ZipInfo(os.path.relpath(full, ROOT).replace(os.sep, '/'), date_time=(2026, 1, 1, 0, 0, 0))
                        info.compress_type = zipfile.ZIP_DEFLATED
                        with open(full, 'rb') as fh:
                            z.writestr(info, fh.read())
    return buf.getvalue()


if __name__ == '__main__':
    data = build()
    if '--check' in sys.argv:
        current = open(OUT, 'rb').read() if os.path.exists(OUT) else b''
        if current != data:
            print('assets/py/aws_twin.zip is stale: run python3 admin/build/py_bundle.py', file=sys.stderr)
            sys.exit(1)
        print(f'py bundle: up to date, {len(data)} bytes, sha256 {hashlib.sha256(data).hexdigest()[:16]}')
        sys.exit(0)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'wb') as f:
        f.write(data)
    print(f'py bundle: wrote assets/py/aws_twin.zip, {len(data)} bytes, sha256 {hashlib.sha256(data).hexdigest()[:16]}')
