#!/usr/bin/env python3
"""Bump, build, validate, push, verify: one release of aws.twin.sgit.ai, in the order sgit.ai's repository
guidance gives. A clean push is not a release; a release is done when the live site serves the new version.

    python3 admin/build/release.py "what changed, in a sentence"          # bump the minor, release
    python3 admin/build/release.py --no-bump "..."                         # version.txt already bumped
    python3 admin/build/release.py --dry-run "..."                         # everything up to the commit

The release history row for the new version is written by hand in admin/build/pages.py first; the gate fails
without it, which is the point: every release says what changed and why."""
import os
import re
import subprocess
import sys
import time
import urllib.request

ROOT    = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..'))
VERFILE = os.path.join(ROOT, 'admin', 'build', 'version.txt')
HOST    = open(os.path.join(ROOT, 'CNAME')).read().strip()


def run(*cmd, **kw):
    print('$', ' '.join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True, **kw)


def main():
    args    = [a for a in sys.argv[1:] if not a.startswith('--')]
    dry     = '--dry-run' in sys.argv
    if not args:
        sys.exit(__doc__)
    message = args[0].strip().rstrip('.')
    version = open(VERFILE).read().strip()
    if '--no-bump' not in sys.argv:
        r, ma, mi = map(int, version.lstrip('v').split('.'))
        version = f'v{r}.{ma}.{mi + 1}'
        with open(VERFILE, 'w') as f:
            f.write(version + '\n')
        print(f'version.txt -> {version}')
    for step in (['python3', 'admin/build/py_bundle.py'], ['python3', 'admin/build/pages.py'], ['python3', 'admin/build/articles.py'],
                 ['python3', 'admin/build/gen_sitemap.py'], ['node', 'admin/build/validate.js'], ['node', 'admin/build/test.js'],
                 ['python3', '-m', 'pytest', '-q', '-p', 'no:cacheprovider']):
        run(*step)
    subject = f'site {version}: {message}'
    if dry:
        print(f'dry run: would commit "{subject}" and push to dev')
        return
    run('git', 'add', '-A')
    run('git', 'commit', '-q', '-m', subject)
    run('git', 'push', 'origin', 'HEAD:dev')
    url, deadline = f'https://{HOST}/assets/version.js', time.time() + 600
    while time.time() < deadline:
        try:
            body = urllib.request.urlopen(url + f'?t={int(time.time())}', timeout=20).read().decode()
            live = (re.search(r'"(v[\d.]+)"', body) or [None, None])[1]
            print(f'live: {live}')
            if live == version:
                print(f'released: {url} serves {version}')
                return
        except Exception as e:
            print(f'live check: {e}')
        time.sleep(20)
    sys.exit(f'pushed, but {url} did not serve {version} within 10 minutes: the release is not done; check the deploy-pages run')


if __name__ == '__main__':
    main()
