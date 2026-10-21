"""The twin as a real endpoint (CPython only: Pyodide has no sockets), AWS_ENDPOINT_URL
as OSBot-Local-Stack uses it, and replay of a recording."""
import os

import boto3

from aws_twin                   import Twin
from aws_twin.core.Twin__Replay import Twin__Replay
from tests.helpers              import IN_BROWSER, raises, skip


def test_server_with_endpoint_url():
    if IN_BROWSER:
        skip('no sockets in the browser: the twin is reached through the botocore hook there')
    twin = Twin(set_credentials=False)
    with twin.serve(port=0) as server:
        env = {'AWS_ACCESS_KEY_ID': 'k', 'AWS_SECRET_ACCESS_KEY': 's', 'AWS_ENDPOINT_URL': server.url, 'AWS_DEFAULT_REGION': 'eu-west-2'}
        saved = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        try:
            s3 = boto3.client('s3')
            s3.create_bucket(Bucket='over-the-wire', CreateBucketConfiguration={'LocationConstraint': 'eu-west-2'})
            s3.put_object(Bucket='over-the-wire', Key='k', Body=b'sockets')
            assert s3.get_object(Bucket='over-the-wire', Key='k')['Body'].read() == b'sockets'
            raises('NoSuchKey', lambda: s3.get_object(Bucket='over-the-wire', Key='nope'))
            assert boto3.client('sts').get_caller_identity()['Account'] == '111111111111'
        finally:
            for k, v in saved.items():
                if v is None: os.environ.pop(k, None)
                else:         os.environ[k] = v
    assert twin.traffic.summary()['operations']['s3.PutObject'] == 1


def test_disk_provider_keeps_buckets():
    if IN_BROWSER:
        skip('no disk in the browser: the page persists through sg-vfs IndexedDB instead')
    import tempfile
    from aws_twin.vfs.Vfs__Provider__Disk import Vfs__Provider__Disk
    root = tempfile.mkdtemp()
    with Twin(vfs=Vfs__Provider__Disk(root)):
        boto3.client('s3', region_name='eu-west-2').create_bucket(Bucket='on-disk-bucket', CreateBucketConfiguration={'LocationConstraint': 'eu-west-2'})
        boto3.client('s3', region_name='eu-west-2').put_object(Bucket='on-disk-bucket', Key='a/b', Body=b'kept')
    with Twin(vfs=Vfs__Provider__Disk(root)):
        assert boto3.client('s3', region_name='eu-west-2').get_object(Bucket='on-disk-bucket', Key='a/b')['Body'].read() == b'kept'


def test_record_then_replay():
    with Twin(keep_bodies=True) as recorder:
        s3 = boto3.client('s3', region_name='eu-west-2')
        s3.create_bucket(Bucket='recorded-bucket', CreateBucketConfiguration={'LocationConstraint': 'eu-west-2'})
        s3.list_buckets()
    recording = recorder.traffic.records
    replay    = Twin__Replay(recording)
    with Twin(routes={'s3': 'replay'}, replay=replay) as twin:
        s3 = boto3.client('s3', region_name='eu-west-2')
        assert [b['Name'] for b in s3.list_buckets()['Buckets']] == ['recorded-bucket']    # answered from the recording
        raises('NotInRecording', lambda: s3.head_object(Bucket='recorded-bucket', Key='never-recorded'.upper()) or s3.get_object(Bucket='x-bucket-y', Key='z'))
        assert twin.vfs.exists('/s3') is False                                          # the twin's own store was never touched
