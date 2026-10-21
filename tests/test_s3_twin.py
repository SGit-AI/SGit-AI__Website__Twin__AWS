"""boto3 against the S3 twin: the protocol, the semantics, the errors."""
import boto3
from botocore.config import Config

from aws_twin  import Twin
from tests.helpers import raises

BUCKET = 'twin-tests-bucket'


def client(twin=None, **cfg):
    return boto3.client('s3', region_name='eu-west-2', config=Config(**cfg) if cfg else None)


def new_bucket(s3):
    s3.create_bucket(Bucket=BUCKET, CreateBucketConfiguration={'LocationConstraint': 'eu-west-2'})


def test_buckets():
    with Twin() as twin:
        s3 = client()
        assert s3.list_buckets()['Buckets'] == []
        new_bucket(s3)
        raises('BucketAlreadyOwnedByYou', lambda: new_bucket(s3))
        raises('InvalidBucketName', lambda: s3.create_bucket(Bucket='Bad_Name'))
        assert [b['Name'] for b in s3.list_buckets()['Buckets']] == [BUCKET]
        assert s3.head_bucket(Bucket=BUCKET)['ResponseMetadata']['HTTPHeaders']['x-amz-bucket-region'] == 'eu-west-2'
        assert s3.get_bucket_location(Bucket=BUCKET)['LocationConstraint'] == 'eu-west-2'
        raises('404', lambda: s3.head_bucket(Bucket='no-such-bucket-here'))
        s3.put_object(Bucket=BUCKET, Key='k', Body=b'v')
        raises('BucketNotEmpty', lambda: s3.delete_bucket(Bucket=BUCKET))
        s3.delete_object(Bucket=BUCKET, Key='k')
        s3.delete_bucket(Bucket=BUCKET)
        assert s3.list_buckets()['Buckets'] == []


def test_objects_and_metadata():
    with Twin():
        s3 = client()
        new_bucket(s3)
        put = s3.put_object(Bucket=BUCKET, Key='a/b.txt', Body=b'hello twin', ContentType='text/plain', Metadata={'owner': 'dinis'})
        assert put['ETag'] == '"7ea4f2f4cc0fd3e7f3a5a4d7d56d0b80"' or len(put['ETag']) == 34
        got = s3.get_object(Bucket=BUCKET, Key='a/b.txt')
        assert got['Body'].read() == b'hello twin'
        assert got['ContentType'] == 'text/plain' and got['Metadata'] == {'owner': 'dinis'} and got['ContentLength'] == 10
        head = s3.head_object(Bucket=BUCKET, Key='a/b.txt')
        assert head['ContentLength'] == 10 and head['ETag'] == put['ETag']
        raises('NoSuchKey', lambda: s3.get_object(Bucket=BUCKET, Key='missing'))
        raises('404', lambda: s3.head_object(Bucket=BUCKET, Key='missing'))
        raises('NoSuchBucket', lambda: s3.get_object(Bucket='no-such-bucket-here', Key='x'))


def test_ranges_and_conditions():
    with Twin():
        s3 = client()
        new_bucket(s3)
        s3.put_object(Bucket=BUCKET, Key='r', Body=b'0123456789')
        assert s3.get_object(Bucket=BUCKET, Key='r', Range='bytes=2-4')['Body'].read() == b'234'
        assert s3.get_object(Bucket=BUCKET, Key='r', Range='bytes=-3')['Body'].read() == b'789'
        assert s3.get_object(Bucket=BUCKET, Key='r', Range='bytes=7-')['Body'].read() == b'789'
        raises('InvalidRange', lambda: s3.get_object(Bucket=BUCKET, Key='r', Range='bytes=20-30'))
        raises('PreconditionFailed', lambda: s3.put_object(Bucket=BUCKET, Key='r', Body=b'x', IfNoneMatch='*'))
        s3.put_object(Bucket=BUCKET, Key='new', Body=b'x', IfNoneMatch='*')
        etag = s3.head_object(Bucket=BUCKET, Key='new')['ETag']
        s3.put_object(Bucket=BUCKET, Key='new', Body=b'y', IfMatch=etag)
        raises('PreconditionFailed', lambda: s3.put_object(Bucket=BUCKET, Key='new', Body=b'z', IfMatch=etag))


def test_listing():
    with Twin():
        s3 = client()
        new_bucket(s3)
        keys = ['a.txt', 'docs/1.md', 'docs/2.md', 'docs/sub/3.md', 'img/x.png', 'z', 'spaces and+plus/é.txt']
        for k in keys:
            s3.put_object(Bucket=BUCKET, Key=k, Body=k.encode())
        assert sorted(o['Key'] for o in s3.list_objects_v2(Bucket=BUCKET)['Contents']) == sorted(keys)
        r = s3.list_objects_v2(Bucket=BUCKET, Delimiter='/')
        assert [o['Key'] for o in r['Contents']] == ['a.txt', 'z']
        assert [p['Prefix'] for p in r['CommonPrefixes']] == ['docs/', 'img/', 'spaces and+plus/']
        r = s3.list_objects_v2(Bucket=BUCKET, Prefix='docs/', Delimiter='/')
        assert [o['Key'] for o in r['Contents']] == ['docs/1.md', 'docs/2.md'] and [p['Prefix'] for p in r['CommonPrefixes']] == ['docs/sub/']
        pages = list(s3.get_paginator('list_objects_v2').paginate(Bucket=BUCKET, PaginationConfig={'PageSize': 2}))
        assert len(pages) == 4 and sum(len(p.get('Contents', [])) for p in pages) == len(keys)
        assert [o['Key'] for o in s3.list_objects_v2(Bucket=BUCKET, StartAfter='img/x.png')['Contents']] == ['spaces and+plus/é.txt', 'z']
        v1 = s3.list_objects(Bucket=BUCKET, Prefix='docs/', MaxKeys=2)
        assert v1['IsTruncated'] and len(v1['Contents']) == 2


def test_copy_delete_many_and_tagging():
    with Twin():
        s3 = client()
        new_bucket(s3)
        s3.put_object(Bucket=BUCKET, Key='src', Body=b'data', Metadata={'a': '1'})
        s3.copy_object(Bucket=BUCKET, Key='dst', CopySource={'Bucket': BUCKET, 'Key': 'src'})
        assert s3.get_object(Bucket=BUCKET, Key='dst')['Metadata'] == {'a': '1'}
        raises('InvalidRequest', lambda: s3.copy_object(Bucket=BUCKET, Key='src', CopySource={'Bucket': BUCKET, 'Key': 'src'}))
        s3.copy_object(Bucket=BUCKET, Key='src', CopySource={'Bucket': BUCKET, 'Key': 'src'}, Metadata={'b': '2'}, MetadataDirective='REPLACE')
        assert s3.head_object(Bucket=BUCKET, Key='src')['Metadata'] == {'b': '2'}
        s3.put_object_tagging(Bucket=BUCKET, Key='src', Tagging={'TagSet': [{'Key': 'env', 'Value': 'twin'}]})
        assert s3.get_object_tagging(Bucket=BUCKET, Key='src')['TagSet'] == [{'Key': 'env', 'Value': 'twin'}]
        r = s3.delete_objects(Bucket=BUCKET, Delete={'Objects': [{'Key': 'src'}, {'Key': 'dst'}]})
        assert sorted(d['Key'] for d in r['Deleted']) == ['dst', 'src']
        assert 'Contents' not in s3.list_objects_v2(Bucket=BUCKET)


def test_multipart_and_upload_file():
    with Twin():
        s3 = client()
        new_bucket(s3)
        up    = s3.create_multipart_upload(Bucket=BUCKET, Key='big', ContentType='application/octet-stream')
        parts = []
        for n, chunk in enumerate([b'a' * (5 * 1024 * 1024), b'b' * 10], start=1):
            etag = s3.upload_part(Bucket=BUCKET, Key='big', UploadId=up['UploadId'], PartNumber=n, Body=chunk)['ETag']
            parts.append({'PartNumber': n, 'ETag': etag})
        done = s3.complete_multipart_upload(Bucket=BUCKET, Key='big', UploadId=up['UploadId'], MultipartUpload={'Parts': parts})
        assert done['ETag'].endswith('-2"')
        assert s3.head_object(Bucket=BUCKET, Key='big')['ContentLength'] == 5 * 1024 * 1024 + 10
        raises('NoSuchUpload', lambda: s3.abort_multipart_upload(Bucket=BUCKET, Key='big', UploadId=up['UploadId']))


def test_bucket_config_and_versioning():
    with Twin():
        s3 = client()
        new_bucket(s3)
        assert s3.get_bucket_versioning(Bucket=BUCKET).get('Status') is None
        s3.put_bucket_versioning(Bucket=BUCKET, VersioningConfiguration={'Status': 'Enabled'})
        assert s3.get_bucket_versioning(Bucket=BUCKET)['Status'] == 'Enabled'
        raises('NoSuchBucketPolicy', lambda: s3.get_bucket_policy(Bucket=BUCKET))
        s3.put_bucket_policy(Bucket=BUCKET, Policy='{"Version":"2012-10-17","Statement":[]}')
        assert '2012-10-17' in s3.get_bucket_policy(Bucket=BUCKET)['Policy']
        s3.put_bucket_cors(Bucket=BUCKET, CORSConfiguration={'CORSRules': [{'AllowedMethods': ['GET'], 'AllowedOrigins': ['*']}]})
        assert s3.get_bucket_cors(Bucket=BUCKET)['CORSRules'][0]['AllowedOrigins'] == ['*']
        s3.put_object(Bucket=BUCKET, Key='v', Body=b'1')
        v = s3.list_object_versions(Bucket=BUCKET)
        assert v['Versions'][0]['Key'] == 'v' and v['Versions'][0]['VersionId'] == 'null'


def test_traffic_and_gaps():
    with Twin() as twin:
        s3 = client()
        new_bucket(s3)
        boto3.client('sts', region_name='eu-west-2').get_caller_identity()
        raises('NotImplemented', lambda: boto3.client('sqs', region_name='eu-west-2').list_queues())
        ops = [(r['service'], r['operation'], r['status'], r['signed']) for r in twin.traffic.records]
        assert ('s3', 'CreateBucket', 200, True) in ops
        assert ('sts', 'GetCallerIdentity', 200, True) in ops
        assert any(s == 'sqs' and st == 501 for s, o, st, sg in ops)          # the gap is in the traffic, by name


def test_checksum_modes():
    """boto3's default aws-chunked uploads and the plain ones store the same bytes."""
    with Twin():
        for mode in ('when_supported', 'when_required'):
            s3 = client(request_checksum_calculation=mode)
            if not s3.list_buckets()['Buckets']:
                new_bucket(s3)
            s3.put_object(Bucket=BUCKET, Key=mode, Body=b'same bytes')
            assert s3.get_object(Bucket=BUCKET, Key=mode)['Body'].read() == b'same bytes'


def test_hook_restores_botocore():
    from botocore.httpsession import URLLib3Session
    before = URLLib3Session.send
    with Twin():
        assert URLLib3Session.send is not before
    assert URLLib3Session.send is before
