"""python -m aws_twin [--port 4566] [--root ./twin-data]: the twin as a local endpoint."""
import argparse

from aws_twin.core.Twin import Twin


def main():
    p = argparse.ArgumentParser(prog='aws_twin', description='The AWS twin as a local endpoint (S3 and STS GetCallerIdentity).')
    p.add_argument('--host', default='127.0.0.1')
    p.add_argument('--port', type=int, default=4566)
    p.add_argument('--root', help='keep buckets in this folder (default: in memory)')
    a = p.parse_args()
    vfs = None
    if a.root:
        from aws_twin.vfs.Vfs__Provider__Disk import Vfs__Provider__Disk
        vfs = Vfs__Provider__Disk(a.root)
    print(f'aws_twin on http://{a.host}:{a.port}  (export AWS_ENDPOINT_URL=http://{a.host}:{a.port})')
    Twin(vfs=vfs).serve(a.host, a.port, background=False)


if __name__ == '__main__':
    main()
