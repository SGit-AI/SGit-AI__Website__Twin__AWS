"""The S3 twin: S3's REST-XML protocol answered from a virtual file system.

Layout in the VFS, chosen so that S3 semantics hold (keys are flat strings, so 'a' and
'a/b' can both exist, which a folder tree cannot express):

    /s3/<bucket>/bucket.json            name, region, creation date, versioning, subresources
    /s3/<bucket>/data/k=<quoted key>    the object's bytes
    /s3/<bucket>/meta/k=<quoted key>    the object's metadata, JSON
    /s3/<bucket>/uploads/<id>/...       multipart uploads in progress

Covered: ListBuckets, CreateBucket, HeadBucket, DeleteBucket, GetBucketLocation,
Get/PutBucketVersioning, ListObjects, ListObjectsV2 (prefix, delimiter, start-after,
continuation, max-keys, encoding-type=url), ListObjectVersions (one version per object),
PutObject (aws-chunked bodies, metadata, If-None-Match/If-Match), GetObject (Range),
HeadObject, DeleteObject, DeleteObjects, CopyObject (COPY/REPLACE), the multipart upload
set, and bucket/object subresources (policy, cors, tagging, acl) stored as sent.
Not covered, and answered 501 NotImplemented by name: everything else, including real
versioning of object data, lifecycle, replication, SSE behaviour and object lock."""
import base64
import email.utils
import hashlib
import json
import re
import time
import uuid
from urllib.parse import quote, unquote

from aws_twin.core.Twin__Http import Twin__Response, decode_aws_chunked
from aws_twin.s3.S3__Xml      import x, doc, parse, error_xml
from aws_twin.vfs.Vfs__Path   import Vfs__Error

BUCKET_SUBRESOURCES = ('policy', 'cors', 'tagging', 'acl', 'lifecycle', 'website', 'encryption', 'ownershipControls', 'publicAccessBlock')
SUBRESOURCE_MISSING = {'policy': 'NoSuchBucketPolicy', 'cors': 'NoSuchCORSConfiguration', 'tagging': 'NoSuchTagSet',
                       'lifecycle': 'NoSuchLifecycleConfiguration', 'website': 'NoSuchWebsiteConfiguration',
                       'encryption': 'ServerSideEncryptionConfigurationNotFoundError', 'ownershipControls': 'OwnershipControlsNotFoundError',
                       'publicAccessBlock': 'NoSuchPublicAccessBlockConfiguration'}
BUCKET_NAME = re.compile(r'^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$')


class S3__Error(Exception):
    def __init__(self, status, code, message, **extra):
        self.status, self.code, self.message, self.extra = status, code, message, extra
        super().__init__(f'{code}: {message}')


def iso_ms(ts):
    return time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(ts)) + '.%03dZ' % int((ts % 1) * 1000)


def http_date(ts):
    return email.utils.formatdate(ts, usegmt=True)


def key_file(key):
    return 'k=' + quote(key, safe='')


class S3__Twin:
    service = 's3'

    def __init__(self, twin):
        self.twin = twin

    @property
    def vfs(self):
        return self.twin.vfs

    # ── addressing ───────────────────────────────────────────────────────
    def bucket_and_key(self, request):
        """Virtual-hosted style (bucket in the host) or path style (bucket in the path)."""
        host   = request.host
        bucket = None
        m = re.match(r'^(.+?)\.s3[.-]', host)                                   # <bucket>.s3.<region>.amazonaws.com
        if m and host.endswith('amazonaws.com'):
            bucket = m.group(1)
        else:
            for base in self.twin.endpoint_hosts:
                if host.endswith('.' + base):
                    bucket = host[:-(len(base) + 1)]
        path = request.path
        if bucket:
            key = path[1:] if path.startswith('/') else path
        else:
            parts  = path.lstrip('/').split('/', 1)
            bucket = parts[0] or None
            key    = parts[1] if len(parts) > 1 else ''
        return bucket, key

    def region_of(self, request):
        m = re.search(r'Credential=[^/]+/\d{8}/([a-z0-9-]+)/', request.header('authorization', '') + ' ' + request.query.get('X-Amz-Credential', '').replace('%2F', '/'))
        if m:
            return m.group(1)
        m = re.search(r's3[.-]([a-z]{2}-[a-z]+-\d)\.', request.host)
        return m.group(1) if m else self.twin.region

    # ── entry point ──────────────────────────────────────────────────────
    def handle(self, request):
        try:
            op, response = self.dispatch(request)
            return op, response
        except S3__Error as e:
            if request.method == 'HEAD':
                return self._op, Twin__Response(e.status, {'x-amz-request-id': request.request_id}, b'')
            body = error_xml(e.code, e.message, request.request_id, **e.extra)
            return self._op, Twin__Response(e.status, {'content-type': 'application/xml', 'x-amz-request-id': request.request_id}, body)

    def dispatch(self, request):
        bucket, key = self.bucket_and_key(request)
        q, m = request.query, request.method
        self._op = 'Unknown'

        def op(name):
            self._op = name
            return name

        if not bucket:
            if m == 'GET':
                return op('ListBuckets'), self.list_buckets(request)
            raise S3__Error(405, 'MethodNotAllowed', f'{m} on the service root')

        if not key:
            for sub in BUCKET_SUBRESOURCES:
                if sub in q:
                    name = sub[0].upper() + sub[1:]
                    verb = {'GET': 'Get', 'PUT': 'Put', 'DELETE': 'Delete'}.get(m)
                    if not verb:
                        break
                    return op(f'{verb}Bucket{name}'), self.bucket_subresource(request, bucket, sub)
            if 'versioning' in q:
                if m == 'GET': return op('GetBucketVersioning'), self.get_versioning(request, bucket)
                if m == 'PUT': return op('PutBucketVersioning'), self.put_versioning(request, bucket)
            if 'location' in q and m == 'GET':
                return op('GetBucketLocation'), self.get_location(request, bucket)
            if 'versions' in q and m == 'GET':
                return op('ListObjectVersions'), self.list_object_versions(request, bucket)
            if 'uploads' in q and m == 'GET':
                return op('ListMultipartUploads'), self.list_multipart_uploads(request, bucket)
            if 'delete' in q and m == 'POST':
                return op('DeleteObjects'), self.delete_objects(request, bucket)
            unknown = [k for k in q if k not in ('list-type', 'prefix', 'delimiter', 'max-keys', 'continuation-token', 'start-after', 'encoding-type', 'marker', 'fetch-owner', 'x-id')]
            if unknown and m in ('GET', 'PUT', 'DELETE', 'POST'):
                raise S3__Error(501, 'NotImplemented', f'the twin does not implement the bucket subresource ?{unknown[0]} for {m}')
            if m == 'PUT':    return op('CreateBucket'), self.create_bucket(request, bucket)
            if m == 'HEAD':   return op('HeadBucket'),   self.head_bucket(request, bucket)
            if m == 'DELETE': return op('DeleteBucket'), self.delete_bucket(request, bucket)
            if m == 'GET':
                if q.get('list-type') == '2':
                    return op('ListObjectsV2'), self.list_objects(request, bucket, v2=True)
                return op('ListObjects'), self.list_objects(request, bucket, v2=False)
            raise S3__Error(405, 'MethodNotAllowed', f'{m} on a bucket')

        if 'tagging' in q:
            verb = {'GET': 'Get', 'PUT': 'Put', 'DELETE': 'Delete'}.get(m, '')
            return op(f'{verb}ObjectTagging'), self.object_tagging(request, bucket, key)
        if 'uploads' in q and m == 'POST':
            return op('CreateMultipartUpload'), self.create_multipart(request, bucket, key)
        if 'uploadId' in q:
            if m == 'PUT' and 'partNumber' in q: return op('UploadPart'),              self.upload_part(request, bucket, key)
            if m == 'POST':                      return op('CompleteMultipartUpload'), self.complete_multipart(request, bucket, key)
            if m == 'DELETE':                    return op('AbortMultipartUpload'),    self.abort_multipart(request, bucket, key)
            if m == 'GET':                       return op('ListParts'),               self.list_parts(request, bucket, key)
        unknown = [k for k in q if k not in ('versionId', 'x-id', 'response-content-type', 'response-content-disposition', 'partNumber',
                                                    'X-Amz-Algorithm', 'X-Amz-Credential', 'X-Amz-Date', 'X-Amz-Expires', 'X-Amz-SignedHeaders',
                                                    'X-Amz-Signature', 'X-Amz-Security-Token')]
        if unknown:
            raise S3__Error(501, 'NotImplemented', f'the twin does not implement the object subresource ?{unknown[0]} for {m}')
        if m == 'PUT':
            if request.header('x-amz-copy-source'):
                return op('CopyObject'), self.copy_object(request, bucket, key)
            return op('PutObject'), self.put_object(request, bucket, key)
        if m == 'GET':    return op('GetObject'),    self.get_object(request, bucket, key)
        if m == 'HEAD':   return op('HeadObject'),   self.head_object(request, bucket, key)
        if m == 'DELETE': return op('DeleteObject'), self.delete_object(request, bucket, key)
        raise S3__Error(405, 'MethodNotAllowed', f'{m} on an object')

    # ── bucket storage ───────────────────────────────────────────────────
    def _bucket_path(self, bucket):
        return f'/s3/{bucket}/bucket.json'

    def _bucket(self, bucket):
        try:
            return json.loads(self.vfs.read_file(self._bucket_path(bucket)))
        except Vfs__Error:
            raise S3__Error(404, 'NoSuchBucket', 'The specified bucket does not exist', BucketName=bucket)

    def _save_bucket(self, info):
        self.vfs.write_file(self._bucket_path(info['Name']), json.dumps(info, sort_keys=True).encode())

    def bucket_names(self):
        if not self.vfs.exists('/s3'):
            return []
        return sorted(e['name'] for e in self.vfs.list_folder('/s3') if e['type'] == 'folder' and self.vfs.exists(self._bucket_path(e['name'])))

    def _meta(self, bucket, key):
        try:
            return json.loads(self.vfs.read_file(f'/s3/{bucket}/meta/{key_file(key)}'))
        except Vfs__Error:
            return None

    def _all_meta(self, bucket):
        folder = f'/s3/{bucket}/meta'
        if not self.vfs.exists(folder):
            return []
        metas = [json.loads(self.vfs.read_file(e['path'])) for e in self.vfs.list_folder(folder) if e['type'] == 'file']
        metas.sort(key=lambda mm: mm['Key'].encode('utf-8'))
        return metas

    def _write_object(self, bucket, key, data, meta):
        self.vfs.write_file(f'/s3/{bucket}/data/{key_file(key)}', data)
        self.vfs.write_file(f'/s3/{bucket}/meta/{key_file(key)}', json.dumps(meta, sort_keys=True).encode())

    def _delete_object_files(self, bucket, key):
        for kind in ('data', 'meta'):
            path = f'/s3/{bucket}/{kind}/{key_file(key)}'
            if self.vfs.exists(path):
                self.vfs.delete_file(path)

    def _delete_tree(self, path):
        if not self.vfs.exists(path):
            return
        for entry in self.vfs.list_folder(path):
            if entry['type'] == 'folder':
                self._delete_tree(entry['path'])
            else:
                self.vfs.delete_file(entry['path'])

    # ── service ──────────────────────────────────────────────────────────
    def list_buckets(self, request):
        inner = ''.join('<Bucket>' + x('Name', b['Name']) + x('CreationDate', iso_ms(b['Created'])) + x('BucketRegion', b['Region']) + '</Bucket>'
                        for b in (self._bucket(n) for n in self.bucket_names()))
        owner = '<Owner>' + x('ID', self.twin.canonical_user_id) + x('DisplayName', 'twin') + '</Owner>'
        return self._xml(request, doc('ListAllMyBucketsResult', owner + '<Buckets>' + inner + '</Buckets>'))

    # ── buckets ──────────────────────────────────────────────────────────
    def create_bucket(self, request, bucket):
        if not BUCKET_NAME.match(bucket) or '..' in bucket or re.match(r'^\d+\.\d+\.\d+\.\d+$', bucket):
            raise S3__Error(400, 'InvalidBucketName', 'The specified bucket is not valid.', BucketName=bucket)
        region = self.region_of(request)
        if request.body.strip():
            try:
                lc = parse(request.body).find('LocationConstraint')
            except Exception:
                raise S3__Error(400, 'MalformedXML', 'The XML you provided was not well-formed')
            if lc is not None and lc.text:
                region = lc.text
        if self.vfs.exists(self._bucket_path(bucket)):
            if region == 'us-east-1':                                       # AWS answers 200 there, 409 elsewhere
                return self._ok(request, {'location': f'/{bucket}'})
            raise S3__Error(409, 'BucketAlreadyOwnedByYou', 'Your previous request to create the named bucket succeeded and you already own it.', BucketName=bucket)
        self._save_bucket({'Name': bucket, 'Region': region, 'Created': time.time(), 'Versioning': '', 'Sub': {}})
        self.vfs.create_folder(f'/s3/{bucket}/meta')
        self.vfs.create_folder(f'/s3/{bucket}/data')
        return self._ok(request, {'location': f'/{bucket}'})

    def head_bucket(self, request, bucket):
        info = self._bucket(bucket)
        return self._ok(request, {'x-amz-bucket-region': info['Region']})

    def delete_bucket(self, request, bucket):
        self._bucket(bucket)
        if self._all_meta(bucket):
            raise S3__Error(409, 'BucketNotEmpty', 'The bucket you tried to delete is not empty', BucketName=bucket)
        self._delete_tree(f'/s3/{bucket}')
        return self._ok(request, status=204)

    def get_location(self, request, bucket):
        region = self._bucket(bucket)['Region']
        value  = '' if region == 'us-east-1' else region
        return self._xml(request, f'<?xml version="1.0" encoding="UTF-8"?>\n<LocationConstraint xmlns="http://s3.amazonaws.com/doc/2006-03-01/">{value}</LocationConstraint>')

    def get_versioning(self, request, bucket):
        status = self._bucket(bucket).get('Versioning')
        return self._xml(request, doc('VersioningConfiguration', x('Status', status) if status else ''))

    def put_versioning(self, request, bucket):
        info = self._bucket(bucket)
        el   = parse(request.body).find('Status')
        info['Versioning'] = el.text if el is not None else ''
        self._save_bucket(info)
        return self._ok(request)

    def bucket_subresource(self, request, bucket, sub):
        info = self._bucket(bucket)
        subs = info.setdefault('Sub', {})
        if request.method == 'PUT':
            body = decode_aws_chunked(request.body) if 'aws-chunked' in request.header('content-encoding', '') else request.body
            subs[sub] = base64.b64encode(body).decode()
            self._save_bucket(info)
            return self._ok(request, status=204 if sub == 'policy' else 200)
        if request.method == 'DELETE':
            subs.pop(sub, None)
            self._save_bucket(info)
            return self._ok(request, status=204)
        if sub in subs:
            body = base64.b64decode(subs[sub])
            ctype = 'application/json' if sub == 'policy' else 'application/xml'
            return Twin__Response(200, {'content-type': ctype, 'x-amz-request-id': request.request_id}, body)
        if sub == 'acl':
            owner = '<Owner>' + x('ID', self.twin.canonical_user_id) + '</Owner>'
            grant = ('<AccessControlList><Grant><Grantee xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="CanonicalUser">'
                     + x('ID', self.twin.canonical_user_id) + '</Grantee>' + x('Permission', 'FULL_CONTROL') + '</Grant></AccessControlList>')
            return self._xml(request, doc('AccessControlPolicy', owner + grant))
        raise S3__Error(404, SUBRESOURCE_MISSING.get(sub, 'NoSuchConfiguration'), f'The {sub} configuration does not exist', BucketName=bucket)

    # ── listing ──────────────────────────────────────────────────────────
    def _listing(self, bucket, prefix, delimiter, after, max_keys):
        """Keys after `after`, filtered by prefix, grouped by delimiter; returns
        (contents, common_prefixes, truncated, last_key_seen)."""
        contents, prefixes, seen_prefixes, last = [], [], set(), None
        count = 0
        for meta in self._all_meta(bucket):
            k = meta['Key']
            if prefix and not k.startswith(prefix):
                continue
            if after is not None and k.encode('utf-8') <= after.encode('utf-8'):
                continue
            if delimiter:
                rest = k[len(prefix):]
                i    = rest.find(delimiter)
                if i >= 0:
                    cp = prefix + rest[:i + len(delimiter)]
                    if after is not None and cp.encode('utf-8') <= after.encode('utf-8'):
                        continue
                    if cp in seen_prefixes:
                        continue
                    if count >= max_keys:
                        return contents, prefixes, True, last
                    seen_prefixes.add(cp)
                    prefixes.append(cp)
                    count += 1
                    last   = cp
                    continue
            if count >= max_keys:
                return contents, prefixes, True, last
            contents.append(meta)
            count += 1
            last   = k
        return contents, prefixes, False, last

    def list_objects(self, request, bucket, v2):
        self._bucket(bucket)
        q         = request.query
        prefix    = q.get('prefix', '')
        delimiter = q.get('delimiter', '')
        max_keys  = int(q.get('max-keys', '1000') or 1000)
        url       = q.get('encoding-type') == 'url'
        enc       = (lambda s: quote(s, safe='/')) if url else (lambda s: s)
        if v2:
            token = q.get('continuation-token')
            after = base64.urlsafe_b64decode(token.encode()).decode() if token else (q.get('start-after') or None)
        else:
            after = q.get('marker') or None
        contents, prefixes, truncated, last = self._listing(bucket, prefix, delimiter, after, max_keys)
        owner = ('<Owner>' + x('ID', self.twin.canonical_user_id) + x('DisplayName', 'twin') + '</Owner>') if (not v2 or q.get('fetch-owner') == 'true') else ''
        body  = x('Name', bucket) + x('Prefix', enc(prefix)) + x('MaxKeys', max_keys) + x('IsTruncated', 'true' if truncated else 'false')
        if delimiter:
            body += x('Delimiter', enc(delimiter))
        if url:
            body += x('EncodingType', 'url')
        if v2:
            body += x('KeyCount', len(contents) + len(prefixes))
            if q.get('continuation-token'): body += x('ContinuationToken', q['continuation-token'])
            if q.get('start-after'):        body += x('StartAfter', enc(q['start-after']))
            if truncated:                   body += x('NextContinuationToken', base64.urlsafe_b64encode(last.encode()).decode())
        else:
            body += x('Marker', enc(q.get('marker', '')))
            if truncated and delimiter:     body += x('NextMarker', enc(last))
        for mt in contents:
            body += ('<Contents>' + x('Key', enc(mt['Key'])) + x('LastModified', iso_ms(mt['LastModified'])) + x('ETag', mt['ETag'])
                     + x('Size', mt['Size']) + x('StorageClass', 'STANDARD') + owner + '</Contents>')
        for cp in prefixes:
            body += '<CommonPrefixes>' + x('Prefix', enc(cp)) + '</CommonPrefixes>'
        return self._xml(request, doc('ListBucketResult', body))

    def list_object_versions(self, request, bucket):
        """One version per object, VersionId 'null': the twin does not keep old versions yet."""
        self._bucket(bucket)
        q         = request.query
        prefix    = q.get('prefix', '')
        url       = q.get('encoding-type') == 'url'
        enc       = (lambda s: quote(s, safe='/')) if url else (lambda s: s)
        contents, prefixes, truncated, last = self._listing(bucket, prefix, q.get('delimiter', ''), q.get('key-marker') or None, int(q.get('max-keys', '1000') or 1000))
        body = x('Name', bucket) + x('Prefix', enc(prefix)) + x('KeyMarker', '') + x('VersionIdMarker', '') + x('MaxKeys', q.get('max-keys', '1000')) + x('IsTruncated', 'true' if truncated else 'false')
        if url:
            body += x('EncodingType', 'url')
        if truncated:
            body += x('NextKeyMarker', enc(last)) + x('NextVersionIdMarker', 'null')
        for mt in contents:
            body += ('<Version>' + x('Key', enc(mt['Key'])) + x('VersionId', 'null') + x('IsLatest', 'true') + x('LastModified', iso_ms(mt['LastModified']))
                     + x('ETag', mt['ETag']) + x('Size', mt['Size']) + x('StorageClass', 'STANDARD') + '<Owner>' + x('ID', self.twin.canonical_user_id) + '</Owner></Version>')
        for cp in prefixes:
            body += '<CommonPrefixes>' + x('Prefix', enc(cp)) + '</CommonPrefixes>'
        return self._xml(request, doc('ListVersionsResult', body))

    # ── objects ──────────────────────────────────────────────────────────
    def _body(self, request):
        if 'aws-chunked' in request.header('content-encoding', '') or request.header('x-amz-content-sha256', '').startswith('STREAMING-'):
            return decode_aws_chunked(request.body)
        return request.body

    def _check_preconditions(self, request, existing):
        if request.header('if-none-match') == '*' and existing is not None:
            raise S3__Error(412, 'PreconditionFailed', 'At least one of the pre-conditions you specified did not hold', Condition='If-None-Match')
        im = request.header('if-match')
        if im is not None and (existing is None or im.strip() != existing['ETag']):
            if existing is None:
                raise S3__Error(404, 'NoSuchKey', 'The specified key does not exist.')
            raise S3__Error(412, 'PreconditionFailed', 'At least one of the pre-conditions you specified did not hold', Condition='If-Match')

    def _user_meta(self, request):
        return {k[len('x-amz-meta-'):]: v for k, v in request.headers.items() if k.startswith('x-amz-meta-')}

    def put_object(self, request, bucket, key):
        self._bucket(bucket)
        data     = self._body(request)
        existing = self._meta(bucket, key)
        self._check_preconditions(request, existing)
        md5 = hashlib.md5(data).hexdigest()
        cmd5 = request.header('content-md5')
        if cmd5 and base64.b64decode(cmd5).hex() != md5:
            raise S3__Error(400, 'BadDigest', 'The Content-MD5 you specified did not match what we received.')
        meta = {'Key': key, 'Size': len(data), 'ETag': f'"{md5}"', 'LastModified': time.time(),
                'ContentType': request.header('content-type') or 'binary/octet-stream', 'Metadata': self._user_meta(request),
                'CacheControl': request.header('cache-control'), 'ContentDisposition': request.header('content-disposition'),
                'Tagging': request.header('x-amz-tagging')}
        self._write_object(bucket, key, data, meta)
        return self._ok(request, {'etag': meta['ETag']})

    def _object_headers(self, meta):
        h = {'etag': meta['ETag'], 'last-modified': http_date(meta['LastModified']), 'content-type': meta['ContentType'],
             'accept-ranges': 'bytes'}
        for k in ('CacheControl', 'ContentDisposition'):
            if meta.get(k):
                h[re.sub(r'(?<!^)([A-Z])', r'-\1', k).lower()] = meta[k]
        for k, v in (meta.get('Metadata') or {}).items():
            h[f'x-amz-meta-{k}'] = v
        return h

    def _existing(self, bucket, key):
        self._bucket(bucket)
        meta = self._meta(bucket, key)
        if meta is None:
            raise S3__Error(404, 'NoSuchKey', 'The specified key does not exist.', Key=key)
        return meta

    def get_object(self, request, bucket, key):
        meta = self._existing(bucket, key)
        inm  = request.header('if-none-match')
        if inm and inm.strip() == meta['ETag']:
            return Twin__Response(304, {'etag': meta['ETag'], 'x-amz-request-id': request.request_id}, b'')
        data = self.vfs.read_file(f'/s3/{bucket}/data/{key_file(key)}')
        h    = self._object_headers(meta)
        h['x-amz-request-id'] = request.request_id
        for q, hk in (('response-content-type', 'content-type'), ('response-content-disposition', 'content-disposition')):
            if q in request.query:
                h[hk] = request.query[q]
        rng = request.header('range')
        if rng:
            m = re.match(r'bytes=(\d*)-(\d*)$', rng.strip())
            size = len(data)
            if not m or (m.group(1) == '' and m.group(2) == ''):
                raise S3__Error(416, 'InvalidRange', 'The requested range is not satisfiable', RangeRequested=rng)
            if m.group(1) == '':
                start, end = max(0, size - int(m.group(2))), size - 1
            else:
                start = int(m.group(1))
                end   = min(int(m.group(2)) if m.group(2) else size - 1, size - 1)
            if start >= size or start > end:
                raise S3__Error(416, 'InvalidRange', 'The requested range is not satisfiable', RangeRequested=rng)
            h['content-range'] = f'bytes {start}-{end}/{size}'
            return Twin__Response(206, h, data[start:end + 1])
        return Twin__Response(200, h, data)

    def head_object(self, request, bucket, key):
        meta = self._existing(bucket, key)
        h    = self._object_headers(meta)
        h['x-amz-request-id'] = request.request_id
        r = Twin__Response(200, h, b'')
        r.headers['content-length'] = str(meta['Size'])
        return r

    def delete_object(self, request, bucket, key):
        self._bucket(bucket)
        self._delete_object_files(bucket, key)
        return self._ok(request, status=204)

    def delete_objects(self, request, bucket):
        self._bucket(bucket)
        root  = parse(self._body(request))
        quiet = (root.findtext('Quiet') or '').lower() == 'true'
        body  = ''
        for obj in root.findall('Object'):
            k = obj.findtext('Key')
            self._delete_object_files(bucket, k)
            if not quiet:
                body += '<Deleted>' + x('Key', k) + '</Deleted>'
        return self._xml(request, doc('DeleteResult', body))

    def copy_object(self, request, bucket, key):
        self._bucket(bucket)
        src = unquote(request.header('x-amz-copy-source')).split('?', 1)[0].lstrip('/')
        if '/' not in src:
            raise S3__Error(400, 'InvalidArgument', 'Copy Source must mention the source bucket and key: sourcebucket/sourcekey')
        sbucket, skey = src.split('/', 1)
        smeta     = self._existing(sbucket, skey)
        directive = (request.header('x-amz-metadata-directive') or 'COPY').upper()
        if sbucket == bucket and skey == key and directive != 'REPLACE':
            raise S3__Error(400, 'InvalidRequest', 'This copy request is illegal because it is trying to copy an object to itself without changing the object\'s metadata, storage class, website redirect location or encryption attributes.')
        data = self.vfs.read_file(f'/s3/{sbucket}/data/{key_file(skey)}')
        meta = dict(smeta, Key=key, LastModified=time.time())
        if directive == 'REPLACE':
            meta['Metadata']    = self._user_meta(request)
            meta['ContentType'] = request.header('content-type') or 'binary/octet-stream'
        self._write_object(bucket, key, data, meta)
        return self._xml(request, doc('CopyObjectResult', x('LastModified', iso_ms(meta['LastModified'])) + x('ETag', meta['ETag'])))

    def object_tagging(self, request, bucket, key):
        meta = self._existing(bucket, key)
        if request.method == 'PUT':
            tags = parse(self._body(request))
            meta['TagSet'] = [{'Key': t.findtext('Key'), 'Value': t.findtext('Value')} for t in tags.iter('Tag')]
        elif request.method == 'DELETE':
            meta['TagSet'] = []
        else:
            inner = ''.join('<Tag>' + x('Key', t['Key']) + x('Value', t['Value']) + '</Tag>' for t in meta.get('TagSet') or [])
            return self._xml(request, doc('Tagging', '<TagSet>' + inner + '</TagSet>'))
        self.vfs.write_file(f'/s3/{bucket}/meta/{key_file(key)}', json.dumps(meta, sort_keys=True).encode())
        return self._ok(request, status=204 if request.method == 'DELETE' else 200)

    # ── multipart ────────────────────────────────────────────────────────
    def _upload(self, bucket, upload_id):
        try:
            return json.loads(self.vfs.read_file(f'/s3/{bucket}/uploads/{upload_id}/upload.json'))
        except Vfs__Error:
            raise S3__Error(404, 'NoSuchUpload', 'The specified upload does not exist. The upload ID may be invalid, or the upload may have been aborted or completed.', UploadId=upload_id)

    def create_multipart(self, request, bucket, key):
        self._bucket(bucket)
        upload_id = uuid.uuid4().hex
        info = {'Key': key, 'UploadId': upload_id, 'Initiated': time.time(),
                'ContentType': request.header('content-type') or 'binary/octet-stream', 'Metadata': self._user_meta(request)}
        self.vfs.write_file(f'/s3/{bucket}/uploads/{upload_id}/upload.json', json.dumps(info).encode())
        return self._xml(request, doc('InitiateMultipartUploadResult', x('Bucket', bucket) + x('Key', key) + x('UploadId', upload_id)))

    def upload_part(self, request, bucket, key):
        upload_id = request.query['uploadId']
        self._upload(bucket, upload_id)
        n    = int(request.query['partNumber'])
        data = self._body(request)
        self.vfs.write_file(f'/s3/{bucket}/uploads/{upload_id}/part-{n:05d}', data)
        return self._ok(request, {'etag': f'"{hashlib.md5(data).hexdigest()}"'})

    def complete_multipart(self, request, bucket, key):
        upload_id = request.query['uploadId']
        info      = self._upload(bucket, upload_id)
        root      = parse(self._body(request))
        data, digests = b'', b''
        for part in root.findall('Part'):
            n = int(part.findtext('PartNumber'))
            try:
                chunk = self.vfs.read_file(f'/s3/{bucket}/uploads/{upload_id}/part-{n:05d}')
            except Vfs__Error:
                raise S3__Error(400, 'InvalidPart', f'One or more of the specified parts could not be found: part {n}')
            data    += chunk
            digests += hashlib.md5(chunk).digest()
        etag = f'"{hashlib.md5(digests).hexdigest()}-{len(root.findall("Part"))}"'
        meta = {'Key': key, 'Size': len(data), 'ETag': etag, 'LastModified': time.time(),
                'ContentType': info['ContentType'], 'Metadata': info['Metadata']}
        self._write_object(bucket, key, data, meta)
        self._delete_tree(f'/s3/{bucket}/uploads/{upload_id}')
        return self._xml(request, doc('CompleteMultipartUploadResult', x('Location', f'/{bucket}/{key}') + x('Bucket', bucket) + x('Key', key) + x('ETag', etag)))

    def abort_multipart(self, request, bucket, key):
        self._upload(bucket, request.query['uploadId'])
        self._delete_tree(f'/s3/{bucket}/uploads/{request.query["uploadId"]}')
        return self._ok(request, status=204)

    def list_parts(self, request, bucket, key):
        upload_id = request.query['uploadId']
        self._upload(bucket, upload_id)
        body = x('Bucket', bucket) + x('Key', key) + x('UploadId', upload_id) + x('IsTruncated', 'false')
        for e in self.vfs.list_folder(f'/s3/{bucket}/uploads/{upload_id}'):
            if e['name'].startswith('part-'):
                chunk = self.vfs.read_file(e['path'])
                body += '<Part>' + x('PartNumber', int(e['name'][5:])) + x('ETag', f'"{hashlib.md5(chunk).hexdigest()}"') + x('Size', len(chunk)) + '</Part>'
        return self._xml(request, doc('ListPartsResult', body))

    def list_multipart_uploads(self, request, bucket):
        self._bucket(bucket)
        body = x('Bucket', bucket) + x('IsTruncated', 'false')
        folder = f'/s3/{bucket}/uploads'
        if self.vfs.exists(folder):
            for e in self.vfs.list_folder(folder):
                info = self._upload(bucket, e['name'])
                body += '<Upload>' + x('Key', info['Key']) + x('UploadId', info['UploadId']) + x('Initiated', iso_ms(info['Initiated'])) + '</Upload>'
        return self._xml(request, doc('ListMultipartUploadsResult', body))

    # ── responses ────────────────────────────────────────────────────────
    def _xml(self, request, body):
        return Twin__Response(200, {'content-type': 'application/xml', 'x-amz-request-id': request.request_id}, body)

    def _ok(self, request, headers=None, status=200):
        h = {'x-amz-request-id': request.request_id}
        h.update(headers or {})
        return Twin__Response(status, h, b'')
