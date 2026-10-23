"""What the JSON and query-protocol twins share: an error that carries its AWS code, the region a
request is for, and JSON documents kept in the VFS."""
import json
import random
import re
import string
import time

from aws_twin.core.Twin__Http import Twin__Response
from aws_twin.vfs.Vfs__Path   import Vfs__Error


class Twin__Error(Exception):
    """An AWS error: the HTTP status, the code botocore raises as, and the message."""
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message
        super().__init__(f'{code}: {message}')


def region_of(request, default):
    """The region a request is for: from its SigV4 scope, else from the host (service.region.amazonaws.com)."""
    scope = request.header('authorization', '') + ' ' + request.query.get('X-Amz-Credential', '')
    m = re.search(r'Credential=[^/\s]+/\d{8}/([a-z0-9-]+)/[a-z0-9-]+/aws4_request', scope)
    if m:
        return m.group(1)
    m = re.match(r'^[a-z0-9-]+\.([a-z]{2}(?:-[a-z]+)+-\d)\.amazonaws\.com$', request.host)
    return m.group(1) if m else default


def iso_now(ts=None, millis=True, offset='Z'):
    ts = time.time() if ts is None else ts
    s  = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(ts))
    return s + ('.%03d' % int((ts % 1) * 1000) if millis else '') + offset


def random_id(n, alphabet=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(alphabet) for _ in range(n))


def json_response(status, data, content_type='application/json', headers=None):
    return Twin__Response(status, dict({'content-type': content_type}, **(headers or {})),
                          b'' if data is None else json.dumps(data, default=str))


def json_error(error, request, content_type='application/json'):
    """The rest-json and json-1.1 error shape: the code in x-amzn-ErrorType and __type, as AWS sends both."""
    return Twin__Response(error.status, {'content-type': content_type, 'x-amzn-errortype': error.code},
                          json.dumps({'__type': error.code, 'Type': 'User', 'message': error.message, 'Message': error.message}))


class Twin__Store:
    """JSON documents and bytes under one VFS root."""
    def __init__(self, vfs, root):
        self.vfs, self.root = vfs, '/' + root.strip('/')

    def path(self, *parts):
        return '/'.join([self.root] + [str(p).strip('/') for p in parts])

    def exists(self, *parts):
        return self.vfs.exists(self.path(*parts))

    def read_json(self, *parts, default=None):
        try:
            return json.loads(self.vfs.read_file(self.path(*parts)))
        except Vfs__Error:
            return default

    def write_json(self, data, *parts):
        self.vfs.write_file(self.path(*parts), json.dumps(data, indent=1, default=str))

    def read_bytes(self, *parts):
        return self.vfs.read_file(self.path(*parts))

    def write_bytes(self, data, *parts):
        self.vfs.write_file(self.path(*parts), data)

    def delete(self, *parts):
        if self.vfs.exists(self.path(*parts)):
            self.vfs.delete_file(self.path(*parts))

    def folders(self, *parts):
        p = self.path(*parts)
        if not self.vfs.exists(p):
            return []
        return [e['name'] for e in self.vfs.list_folder(p) if e['type'] == 'folder']

    def files(self, *parts):
        p = self.path(*parts)
        if not self.vfs.exists(p):
            return []
        return [e['name'] for e in self.vfs.list_folder(p) if e['type'] == 'file']
