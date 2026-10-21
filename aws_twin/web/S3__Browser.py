"""The S3 browser's Python side: every button on s3/index.html calls one method here, and
every method is OSBot-AWS where it has a helper, boto3 where it does not. The page never
talks to the twin or to AWS itself; it calls these, they call S3, the twin answers.

Every method takes and returns JSON-able values (bytes as base64), so the page can call it
through Pyodide without knowing Python types."""
import base64
import json
import time

from aws_twin.core.Twin                  import Twin
from aws_twin.vfs.Vfs__Provider__Memory  import Vfs__Provider__Memory


class S3__Browser:
    def __init__(self):
        self.twin  = None
        self.s3    = None
        self.calls = []

    # ── lifecycle ────────────────────────────────────────────────────────
    def start(self, files_json='[]', region='eu-west-2'):
        """Start the twin with a journalling memory VFS, seeded from what the page persisted."""
        vfs = Vfs__Provider__Memory(journal=True)
        vfs.load_files((f['path'], base64.b64decode(f['b64'])) for f in json.loads(files_json))
        self.twin = Twin(vfs=vfs, region=region, keep_bodies=False).activate()
        from osbot_aws.aws.s3.S3 import S3
        self.s3 = S3().dont_use_threads()
        return {'files_restored': len(json.loads(files_json)), 'region': region}

    def call(self, name, args_json='{}'):
        """The one entry point the page uses: run a method, return result, the Python
        call as written, the AWS operations it caused, and the VFS changes to persist."""
        args    = json.loads(args_json)
        before  = len(self.twin.traffic.records)
        started = time.time()
        try:
            result, python = getattr(self, 'op_' + name)(**args)
            error = None
        except Exception as e:
            result, python = None, getattr(e, 'python', name)
            code  = getattr(e, 'response', {}).get('Error', {}).get('Code') if hasattr(e, 'response') else None
            error = {'type': type(e).__name__, 'code': code, 'message': str(e)}
        traffic = [{k: r[k] for k in ('seq', 'service', 'operation', 'method', 'url', 'status', 'ms')} for r in self.twin.traffic.records[before:]]
        entry   = {'name': name, 'python': python, 'ms': round((time.time() - started) * 1000, 1), 'traffic': traffic, 'error': error}
        self.calls.append(entry)
        changes = [{'op': c['op'], 'path': c['path'], 'b64': base64.b64encode(c['content']).decode() if 'content' in c else None}
                   for c in self.twin.vfs.drain_journal()]
        return json.dumps({'result': result, 'call': entry, 'changes': changes})

    def client(self):
        return self.s3.client()

    # ── buckets ──────────────────────────────────────────────────────────
    def op_buckets(self):
        rows = self.client().list_buckets()['Buckets']
        return ([{'name': b['Name'], 'region': b.get('BucketRegion', ''), 'created': b['CreationDate'].isoformat()} for b in rows],
                "S3().client().list_buckets()")

    def op_create_bucket(self, name, region):
        r = self.s3.bucket_create(name, region)
        if r.get('status') != 'ok':
            e = Exception(r.get('data'))
            e.python = f"S3().bucket_create({name!r}, {region!r})"
            raise e
        return r, f"S3().bucket_create({name!r}, {region!r})"

    def op_empty_bucket(self, name):
        keys = self.s3.find_files(name)
        if keys:
            self.s3.files_delete(name, keys)
        return {'deleted': len(keys)}, f"S3().files_delete({name!r}, S3().find_files({name!r}))"

    def op_delete_bucket(self, name):
        self.client().delete_bucket(Bucket=name)
        return True, f"S3().client().delete_bucket(Bucket={name!r})"

    def op_bucket_properties(self, name):
        c   = self.client()
        loc = c.get_bucket_location(Bucket=name).get('LocationConstraint') or 'us-east-1'
        ver = self.s3.bucket_versioning__status(name)
        out = {'name': name, 'region': loc, 'versioning': ver, 'arn': self.s3.bucket_arn(name)}
        try:
            out['policy'] = c.get_bucket_policy(Bucket=name)['Policy']
        except Exception:
            out['policy'] = None
        return out, f"S3().bucket_versioning__status({name!r}); S3().client().get_bucket_location(Bucket={name!r})"

    def op_set_versioning(self, name, enabled):
        if enabled:
            self.s3.bucket_versioning__enable(name)
            return True, f"S3().bucket_versioning__enable({name!r})"
        self.client().put_bucket_versioning(Bucket=name, VersioningConfiguration={'Status': 'Suspended'})
        return True, f"S3().client().put_bucket_versioning(Bucket={name!r}, VersioningConfiguration={{'Status': 'Suspended'}})"

    # ── objects ──────────────────────────────────────────────────────────
    def op_list(self, bucket, prefix=''):
        folders, files = [], []
        params = {'Bucket': bucket, 'Delimiter': '/'}
        if prefix:
            params['Prefix'] = prefix
        for page in self.client().get_paginator('list_objects_v2').paginate(**params):
            folders += [p['Prefix'] for p in page.get('CommonPrefixes', [])]
            files   += [{'key': o['Key'], 'size': o['Size'], 'modified': o['LastModified'].isoformat(), 'etag': o['ETag'], 'storage': o.get('StorageClass', 'STANDARD')}
                        for o in page.get('Contents', []) if o['Key'] != prefix]
        return ({'folders': folders, 'files': files},
                f"S3().client().get_paginator('list_objects_v2').paginate(Bucket={bucket!r}, Prefix={prefix!r}, Delimiter='/')")

    def op_upload(self, bucket, key, b64, content_type=None):
        data = base64.b64decode(b64)
        self.s3.file_create_from_bytes(data, bucket, key, content_type=content_type or 'binary/octet-stream')
        return {'key': key, 'size': len(data)}, f"S3().file_create_from_bytes(<{len(data)} bytes>, {bucket!r}, {key!r}, content_type={content_type!r})"

    def op_create_folder(self, bucket, prefix):
        prefix = prefix if prefix.endswith('/') else prefix + '/'
        self.client().put_object(Bucket=bucket, Key=prefix, Body=b'')
        return {'key': prefix}, f"S3().client().put_object(Bucket={bucket!r}, Key={prefix!r}, Body=b'')"

    def op_download(self, bucket, key):
        data = self.s3.file_bytes(bucket, key)
        ctype = self.s3.file_content_type(bucket, key)
        return {'b64': base64.b64encode(data).decode(), 'content_type': ctype, 'size': len(data)}, f"S3().file_bytes({bucket!r}, {key!r})"

    def op_details(self, bucket, key):
        d = self.s3.file_details(bucket, key)
        return ({'key': key, 'size': d['ContentLength'], 'etag': d['ETag'], 'content_type': d.get('ContentType'),
                 'modified': d['LastModified'].isoformat(), 'metadata': d.get('Metadata', {}),
                 'tags': self.client().get_object_tagging(Bucket=bucket, Key=key)['TagSet']},
                f"S3().file_details({bucket!r}, {key!r})")

    def op_delete(self, bucket, keys):
        files   = [k for k in keys if not k.endswith('/')]
        folders = [k for k in keys if k.endswith('/')]
        for prefix in folders:                                     # a folder is every key under it, as the console deletes it
            files += self.s3.find_files(bucket, prefix)
        files = sorted(set(files + folders))
        if files:
            self.s3.files_delete(bucket, files)
        return {'deleted': len(files)}, f"S3().files_delete({bucket!r}, {files[:3]!r}{'…' if len(files) > 3 else ''})"

    def op_copy(self, bucket, key, dest_bucket, dest_key):
        self.s3.file_copy(bucket, key, dest_bucket, dest_key)
        return True, f"S3().file_copy({bucket!r}, {key!r}, {dest_bucket!r}, {dest_key!r})"

    def op_rename(self, bucket, key, new_key):
        self.s3.file_move(bucket, key, bucket, new_key)
        return True, f"S3().file_move({bucket!r}, {key!r}, {bucket!r}, {new_key!r})"

    def op_metadata(self, bucket, key, metadata):
        self.s3.file_metadata_update(bucket, key, metadata)
        return True, f"S3().file_metadata_update({bucket!r}, {key!r}, {metadata!r})"

    # ── the twin itself ──────────────────────────────────────────────────
    def op_traffic(self):
        return self.twin.traffic.records[-300:], 'twin.traffic.records'

    def op_storage(self):
        return ([{'path': e['path'], 'size': e['size']} for e in self.twin.vfs.walk_files('/')], 'twin.vfs.walk_files("/")')
