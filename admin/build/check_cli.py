#!/usr/bin/env python3
"""Check that every AWS CLI command a page prints is one the AWS CLI accepts.

Takes the <pre class="shell"> blocks of the given page sources (default: the IAM and sessions pages), joins
continued lines, and runs each `aws ...` command, with placeholder values for its variables, against the
twin's local endpoint. The CLI validates parameter names, shapes and required values before it sends
anything, so a wrong flag fails before the request. A command passes when it exits 0 or the twin answered it
with an AWS error code (it answers S3 and STS, and NotImplemented, by name, for the rest); anything else, a
shell error included, fails.

Needs the AWS CLI on the PATH (or AWS_CLI=/path/to/aws) and the repository's aws_twin importable.

    python3 admin/build/check_cli.py [admin/content/pages/iam.html ...]
"""
import html, os, re, shutil, subprocess, sys, tempfile, threading

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)

PLACEHOLDERS = {
    'AWS_REGION': 'eu-west-2', 'BUCKET': 'my-bucket',
    'INSTANCE_ARN': 'arn:aws:sso:::instance/ssoins-0000000000000000', 'IDENTITY_STORE_ID': 'd-0000000000',
    'ACCOUNT_ID': '111122223333', 'USER_ID': '00000000-0000-0000-0000-000000000000',
    'G_LIST': '11111111-1111-1111-1111-111111111111', 'G_READ': '22222222-2222-2222-2222-222222222222',
    'INSTANCE': 'arn:aws:sso:::instance/ssoins-0000000000000000',
}
PS = 'arn:aws:sso:::permissionSet/ssoins-0000000000000000/ps-0000000000000000'
REFUSED = re.compile(r'Parameter validation failed|Unknown options|usage: aws|Invalid choice|Error parsing|arguments are required|Unable to load paramfile')


def commands(page):
    with open(page, encoding='utf-8') as f:
        src = f.read()
    for block in re.findall(r'<pre class="shell">(.*?)</pre>', src, re.S):
        text = html.unescape(re.sub(r'<[^>]+>', '', block)).replace('\\\n', ' ')
        for line in text.splitlines():
            line = re.sub(r'\s+#.*$', '', line).strip()                        # trailing comments
            m = re.match(r'^(?:\w+=\$\()?(aws .*?)\)?$', line)                  # X=$(aws ...) runs as aws ...
            if m:
                yield re.sub(r'\s+', ' ', m.group(1))


def main(pages):
    cli = os.environ.get('AWS_CLI') or shutil.which('aws')
    if not cli:
        print('check_cli: no AWS CLI found (set AWS_CLI); skipped')
        return 0
    from aws_twin import Twin
    twin = Twin(set_credentials=False)
    server = twin.serve(port=0)
    work = tempfile.mkdtemp()
    for f in os.listdir(os.path.join(ROOT, 'iam', 'policies')):                # the files the commands read, filled in
        if f.endswith('.json'):
            with open(os.path.join(ROOT, 'iam', 'policies', f)) as s, open(os.path.join(work, f), 'w') as d:
                d.write(s.read().replace('BUCKET_NAME', PLACEHOLDERS['BUCKET']).replace('FOLDER', 'reports'))
    env = dict(os.environ, AWS_ACCESS_KEY_ID='k', AWS_SECRET_ACCESS_KEY='s', AWS_SESSION_TOKEN='t', AWS_DEFAULT_REGION='eu-west-2',
               **PLACEHOLDERS, **{k: PS for k in ('PS_LIST', 'PS_READ', 'PS_READ_ALL', 'PS_ADMIN', 'PS')})
    env.pop('AWS_PROFILE', None)
    subprocess.run([cli, '--endpoint-url', server.url, 's3api', 'create-bucket', '--bucket', PLACEHOLDERS['BUCKET'],
                    '--create-bucket-configuration', 'LocationConstraint=eu-west-2'], env=env, cwd=work, capture_output=True)
    bad = n = 0
    try:
        for page in pages:
            for cmd in commands(page):
                n += 1
                full = cmd.replace('aws ', f'"{cli}" --endpoint-url {server.url} ', 1)
                r = subprocess.run(['bash', '-c', full], env=env, cwd=work, capture_output=True, text=True, timeout=60)
                out = (r.stdout + r.stderr).strip()
                if REFUSED.search(out) or not (r.returncode == 0 or 'An error occurred (' in out):   # passed the CLI, and reached the twin
                    bad += 1
                    print('REFUSED', os.path.relpath(page, ROOT), '\n   ', cmd, '\n   ', out.splitlines()[0] if out else '')
                else:
                    print('ok     ', cmd[:110])
    finally:
        server.stop()
        shutil.rmtree(work, ignore_errors=True)
    print(f'check_cli: {n - bad} of {n} commands accepted by {os.path.basename(cli)}')
    return 1 if bad or not n else 0


if __name__ == '__main__':
    args = sys.argv[1:] or [os.path.join(ROOT, 'admin', 'content', 'pages', p) for p in ('iam.html', 'sessions.html')]
    sys.exit(main(args))
