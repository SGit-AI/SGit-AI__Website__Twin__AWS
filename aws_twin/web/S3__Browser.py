"""The S3 browser's Python side: every button on s3/index.html calls one method here, and
every method is OSBot-AWS where it has a helper, boto3 where it does not. The page never
talks to the twin or to AWS itself; it calls these, they call S3, the twin answers.

Every method takes and returns JSON-able values (bytes as base64), so the page can call it
through Pyodide without knowing Python types.

Two modes, same methods. **Twin**: the Python twin in the page answers, kept in IndexedDB. **Live**: the
same calls go to the real account with the session pasted on /sessions/, signed in the page, sent from the
browser directly (S3 answers a browser only for a bucket with a CORS rule, and never for ListBuckets) or
through the local relay (Twin__Relay.py), which holds no credentials. Live mode is read-only unless writes are
allowed explicitly: a page that can delete a real bucket should have to be asked twice."""
import base64
import json
import os
import time

from aws_twin.core.Twin                  import Twin
from aws_twin.core.Twin__Browser_Http    import Twin__Browser_Blocked
from aws_twin.vfs.Vfs__Provider__Memory  import Vfs__Provider__Memory


WRITES = {'create_bucket', 'empty_bucket', 'delete_bucket', 'set_versioning', 'upload', 'create_folder', 'delete', 'copy', 'rename', 'metadata'}
SESSION_ENV = ('AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN', 'AWS_DEFAULT_REGION')


class S3__Browser:
    def __init__(self):
        self.twin         = None
        self.s3           = None
        self.calls        = []
        self.vfs          = None
        self.live         = False
        self.allow_writes = False
        self.relay        = None

    # ── lifecycle ────────────────────────────────────────────────────────
    def start(self, files_json='[]', region='eu-west-2'):
        """Start the twin with a journalling memory VFS, seeded from what the page persisted."""
        self.vfs = Vfs__Provider__Memory(journal=True)
        self.vfs.load_files((f['path'], base64.b64decode(f['b64'])) for f in json.loads(files_json))
        self.region = region
        self.use_twin()
        return {'files_restored': len(json.loads(files_json)), 'region': region}

    def _swap(self, twin):
        if self.twin is not None:
            self.twin.deactivate()
        self.twin = twin.activate()
        from osbot_aws.aws.s3.S3 import S3
        self.s3 = S3().dont_use_threads()                          # a fresh client: it reads the credentials now

    def use_twin(self):
        """Back to the Python twin in the page; the pasted session's variables are removed."""
        for k in SESSION_ENV:
            os.environ.pop(k, None)
        self.live, self.allow_writes, self.relay = False, False, None
        self._swap(Twin(vfs=self.vfs, region=self.region, keep_bodies=False))
        return {'mode': 'twin'}

    def use_live(self, session_json, relay_url='', allow_writes=False):
        """Send the same calls to the real account, with the session pasted on /sessions/."""
        s = json.loads(session_json)
        if not s.get('sessionToken'):
            raise ValueError('a live session needs a session token: paste one from the AWS access portal on /sessions/')
        os.environ.update({'AWS_ACCESS_KEY_ID': s['accessKeyId'], 'AWS_SECRET_ACCESS_KEY': s['secretAccessKey'],
                           'AWS_SESSION_TOKEN': s['sessionToken'], 'AWS_DEFAULT_REGION': s.get('region') or self.region})
        self.live, self.allow_writes, self.relay = True, bool(allow_writes), (relay_url or None)
        self._swap(Twin(vfs=self.vfs, region=s.get('region') or self.region, set_credentials=False,
                        routes={'s3': 'live', 'sts': 'live'}, live_relay=self.relay))
        who = self.client_sts().get_caller_identity()
        return {'mode': 'live', 'account': who['Account'], 'arn': who['Arn'], 'relay': self.relay, 'allow_writes': self.allow_writes}

    def client_sts(self):
        import boto3
        return boto3.client('sts', region_name=os.environ.get('AWS_DEFAULT_REGION', self.region))

    def call(self, name, args_json='{}'):
        """The one entry point the page uses: run a method, return result, the Python
        call as written, the AWS operations it caused, and the VFS changes to persist."""
        args    = json.loads(args_json)
        before  = len(self.twin.traffic.records)
        started = time.time()
        try:
            if self.live and name in WRITES and not self.allow_writes:
                e = PermissionError(f'{name} would change the real account, and live mode is read-only: allow writes first')
                e.code = 'ReadOnly'
                raise e
            result, python = getattr(self, 'op_' + name)(**args)
            error = None
        except Exception as e:
            result, python = None, getattr(e, 'python', name)
            code  = getattr(e, 'response', {}).get('Error', {}).get('Code') if hasattr(e, 'response') else getattr(e, 'code', None)
            if isinstance(e, Twin__Browser_Blocked):
                code = 'BrowserBlocked'
            error = {'type': type(e).__name__, 'code': code, 'message': str(e)}
        traffic = [{k: r[k] for k in ('seq', 'service', 'operation', 'method', 'url', 'status', 'ms')} for r in self.twin.traffic.records[before:]]
        entry   = {'name': name, 'python': python, 'ms': round((time.time() - started) * 1000, 1), 'traffic': traffic, 'error': error,
                   'mode': 'live' if self.live else 'twin'}
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

    def op_open_bucket(self, name):
        """Check a bucket by name: how the page reaches a bucket when ListBuckets is blocked or not allowed."""
        r = self.client().head_bucket(Bucket=name)
        region = r.get('ResponseMetadata', {}).get('HTTPHeaders', {}).get('x-amz-bucket-region') or r.get('BucketRegion') or ''
        return {'name': name, 'region': region}, f"S3().client().head_bucket(Bucket={name!r})"

    def op_bucket_properties(self, name):
        c   = self.client()
        try:
            loc = c.get_bucket_location(Bucket=name).get('LocationConstraint') or 'us-east-1'
        except Exception as e:
            loc = f'unknown ({getattr(e, "response", {}).get("Error", {}).get("Code", type(e).__name__)})'
        try:
            ver = self.s3.bucket_versioning__status(name)
        except Exception as e:
            ver = f'unknown ({getattr(e, "response", {}).get("Error", {}).get("Code", type(e).__name__)})'
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
        params = {'Bucket': bucket, 'Delimiter': '/', 'Prefix': prefix}     # sent even when empty, as the S3 console does, so a
                                                                             # policy conditioned on s3:prefix "" allows the bucket's root
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
        try:
            tags = self.client().get_object_tagging(Bucket=bucket, Key=key)['TagSet']
        except Exception:
            tags = []                                              # a narrow role may not have s3:GetObjectTagging
        return ({'key': key, 'size': d['ContentLength'], 'etag': d['ETag'], 'content_type': d.get('ContentType'),
                 'modified': d['LastModified'].isoformat(), 'metadata': d.get('Metadata', {}), 'tags': tags},
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

    def op_mode(self):
        return {'mode': 'live' if self.live else 'twin', 'relay': self.relay, 'allow_writes': self.allow_writes}, 'S3__Browser.mode'

    def op_storage(self):
        return ([{'path': e['path'], 'size': e['size']} for e in self.twin.vfs.walk_files('/')], 'twin.vfs.walk_files("/")')
