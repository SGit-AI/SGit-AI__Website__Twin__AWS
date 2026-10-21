"""The twin's HTTP: a request in, a response out, nothing else. Every adapter (the botocore
hook, the local HTTP server, a replay) turns its own world into these two and back."""
import hashlib
import uuid
from urllib.parse import urlsplit, parse_qsl, unquote


class Twin__Request:
    def __init__(self, method, url, headers=None, body=b''):
        self.method  = method.upper()
        self.url     = url
        self.headers = {k.lower(): (v.decode() if isinstance(v, bytes) else str(v)) for k, v in (headers or {}).items()}
        if body is None:
            body = b''
        if hasattr(body, 'read'):
            body = body.read()
        if isinstance(body, str):
            body = body.encode('utf-8')
        self.body    = bytes(body)
        parts        = urlsplit(url)
        self.scheme  = parts.scheme or 'https'
        self.host    = (parts.hostname or self.headers.get('host', '').split(':')[0]).lower()
        self.port    = parts.port
        self.raw_path = parts.path or '/'
        self.path    = unquote(self.raw_path)
        self.query   = dict(parse_qsl(parts.query, keep_blank_values=True))
        self.request_id = uuid.uuid4().hex[:16].upper()

    def header(self, name, default=None):
        return self.headers.get(name.lower(), default)

    def body_sha256(self):
        return hashlib.sha256(self.body).hexdigest()


class Twin__Response:
    def __init__(self, status=200, headers=None, body=b''):
        self.status  = int(status)
        self.headers = dict(headers or {})
        if isinstance(body, str):
            body = body.encode('utf-8')
        self.body    = bytes(body or b'')
        self.headers.setdefault('content-length', str(len(self.body)))

    def __repr__(self):
        return f'<Twin__Response {self.status} {len(self.body)} bytes>'


def decode_aws_chunked(body: bytes) -> bytes:
    """Decode the aws-chunked framing boto3 uses for put_object since 1.36:
    '<hex size>[;chunk-signature=...]\\r\\n<data>\\r\\n ... 0\\r\\n<trailers>\\r\\n\\r\\n'."""
    out, i, n = bytearray(), 0, len(body)
    while i < n:
        eol = body.find(b'\r\n', i)
        if eol < 0:
            break
        size = int(body[i:eol].split(b';', 1)[0].strip() or b'0', 16)
        i    = eol + 2
        if size == 0:
            break
        out += body[i:i + size]
        i   += size + 2
    return bytes(out)
