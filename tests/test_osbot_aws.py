"""OSBot-AWS's S3 helpers against the twin, unchanged: the code that ran against real S3
and LocalStack runs against the twin, in CI and in the browser."""
from aws_twin      import Twin
from tests.helpers import has_module, IN_BROWSER, skip

BUCKET = 'osbot-aws-twin-bucket'


def test_osbot_aws_s3_helpers():
    if not has_module('osbot_aws'):
        skip('osbot_aws not installed')
    with Twin() as twin:
        from osbot_aws.aws.s3.S3 import S3
        s3 = S3()
        if IN_BROWSER:
            s3.dont_use_threads()
        assert s3.bucket_create(BUCKET, 'eu-west-2') == {'status': 'ok', 'data': f'/{BUCKET}'}
        assert s3.bucket_exists(BUCKET) and s3.buckets() == [BUCKET]
        assert s3.file_create_from_bytes(b'abc', BUCKET, 'docs/a.txt', metadata={'x': '1'}, content_type='text/plain')
        assert s3.file_contents(BUCKET, 'docs/a.txt') == 'abc'
        assert s3.file_metadata(BUCKET, 'docs/a.txt')['x'] == '1'
        assert s3.file_create_from_string('{"a": 1}', BUCKET, 'docs/sub/b.json')            # a temp file and upload_file, via s3transfer
        assert s3.file_content_type(BUCKET, 'docs/sub/b.json') == 'application/json; charset=utf-8'
        assert sorted(s3.find_files(BUCKET)) == ['docs/a.txt', 'docs/sub/b.json']
        assert s3.folder_contents(BUCKET, 'docs') == {'folders': ['sub'], 'files': ['a.txt']}
        assert s3.folder_list(BUCKET, '') == ['docs']
        s3.file_copy(BUCKET, 'docs/a.txt', BUCKET, 'copy/a.txt')
        s3.file_metadata_update(BUCKET, 'docs/a.txt', {'y': '2'})
        assert s3.file_metadata(BUCKET, 'docs/a.txt') == {'y': '2'}
        s3.file_move(BUCKET, 'copy/a.txt', BUCKET, 'moved/a.txt')
        assert s3.file_exists(BUCKET, 'moved/a.txt') and not s3.file_exists(BUCKET, 'copy/a.txt')
        assert s3.file_delete(BUCKET, 'moved/a.txt')
        assert s3.files_delete(BUCKET, ['docs/sub/b.json'])
        assert s3.bucket_versioning__enable(BUCKET)
        assert s3.create_pre_signed_url(BUCKET, 'docs/a.txt').startswith('https://')
        assert s3.bucket_delete_all_files(BUCKET)
        assert s3.bucket_delete(BUCKET)
        assert twin.traffic.summary()['calls'] > 20


def test_osbot_aws_sts():
    if not has_module('osbot_aws'):
        skip('osbot_aws not installed')
    with Twin():
        from osbot_aws.aws.sts.STS import STS
        sts = STS()
        assert sts.caller_identity_account() == '111111111111'
        assert sts.caller_identity_arn().endswith(':assumed-role/twin/session')
        assert sts.check_current_session_credentials().get('status') == 'ok'
