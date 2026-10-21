"""Send a botocore request on to AWS from the live route: from a browser (Pyodide), or through the local relay.

botocore opens connections through its own urllib3 connection classes, which use sockets; Pyodide's urllib3
only teaches urllib3's default classes to use the browser, so botocore's own send makes no request at all there
(it raises EndpointConnectionError). send_from_browser sends the already-signed request through urllib3's
browser fetch instead: a synchronous XMLHttpRequest on the page's main thread, or JSPI where the browser has
it. The browser sets Host and Content-Length itself, to the values botocore signed.

A browser can only read the answer when AWS allows the page's origin (CORS). STS, Lambda, EC2, IAM, Logs, Cost
Explorer and CloudFormation do for any origin; S3 does per bucket, with a CORS rule, and never for
ListBuckets. When the browser blocks the answer, Twin__Browser_Blocked says so by name, instead of a
connection error that looks like an outage.

send_via_relay sends the same signed request to the local relay (Twin__Relay.py) with the real URL in
x-twin-target; the relay forwards it unchanged and adds the CORS headers. It works the same way from CPython,
which is how the tests exercise it."""
import sys


class Twin__Browser_Blocked(Exception):
    """The browser refused to let the page read AWS's answer: CORS, not AWS, said no."""
    def __init__(self, method, url, detail=''):
        self.method, self.url = method, url
        host = url.split('/')[2] if '://' in url else url
        hint = ('S3 never allows ListBuckets from a browser; start the local relay to list buckets, or open a bucket by name'
                if host.startswith('s3.') and url.rstrip('/').count('/') <= 2 else
                'the bucket needs a CORS rule for this site (see /iam/#cors), or start the local relay')
        super().__init__(f'the browser blocked the answer from {host} (CORS): {hint}. {detail}'.strip())


def _body_and_headers(prepared):
    body = prepared.body
    if hasattr(body, 'read'):
        body = body.read()
    if isinstance(body, str):
        body = body.encode('utf-8')
    headers = {k: (v.decode() if isinstance(v, bytes) else str(v)) for k, v in prepared.headers.items()
               if k.lower() not in ('transfer-encoding', 'content-length', 'connection', 'expect')}   # framing: the sender recomputes it from the bytes
    return body, headers


def send_from_browser(prepared, timeout=0):
    from urllib3.contrib.emscripten.fetch   import send_request
    from urllib3.contrib.emscripten.request import EmscriptenRequest
    from botocore.awsrequest                import AWSResponse
    from aws_twin.core.Twin                 import _Raw

    body, headers = _body_and_headers(prepared)
    try:
        response = send_request(EmscriptenRequest(method=prepared.method, url=prepared.url, body=body or None,
                                                  headers=headers, timeout=timeout))
    except Exception as e:                                          # a sync XHR blocked by CORS raises NetworkError
        raise Twin__Browser_Blocked(prepared.method, prepared.url, type(e).__name__) from None
    if response.status_code == 0:
        raise Twin__Browser_Blocked(prepared.method, prepared.url)
    return AWSResponse(prepared.url, response.status_code, dict(response.headers), _Raw(response.body))


def send_via_relay(prepared, relay_url, timeout=60):
    from botocore.awsrequest import AWSResponse
    from aws_twin.core.Twin  import _Raw

    body, headers = _body_and_headers(prepared)
    headers['x-twin-target'] = prepared.url
    target = relay_url.rstrip('/') + '/relay'
    if sys.platform == 'emscripten':
        from urllib3.contrib.emscripten.fetch   import send_request
        from urllib3.contrib.emscripten.request import EmscriptenRequest
        try:
            r = send_request(EmscriptenRequest(method=prepared.method, url=target, body=body or None, headers=headers, timeout=0))
        except Exception as e:
            raise Twin__Browser_Blocked(prepared.method, prepared.url,
                                        f'the local relay at {relay_url} did not answer ({type(e).__name__}): is Twin__Relay.py running?') from None
        status, rheaders, rbody = r.status_code, dict(r.headers), r.body
    else:
        import http.client
        import urllib.parse
        p    = urllib.parse.urlsplit(target)
        conn = http.client.HTTPConnection(p.hostname, p.port or 80, timeout=timeout)
        try:
            conn.request(prepared.method, p.path, body=body if (body or prepared.method in ('PUT', 'POST')) else None, headers=headers)
            resp = conn.getresponse()
            status, rheaders, rbody = resp.status, dict(resp.getheaders()), resp.read()
        finally:
            conn.close()
    return AWSResponse(prepared.url, status, rheaders, _Raw(rbody))
