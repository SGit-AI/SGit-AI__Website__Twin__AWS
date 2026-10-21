"""The twin: one entry point for every AWS request, wherever it comes from.

    Twin().handle(Twin__Request)                       the core: request in, response out
    with Twin() as twin: ...                           the botocore hook: boto3, OSBot-AWS, anything
                                                       built on botocore now talks to the twin
    Twin().serve(port=4566)                            a real HTTP endpoint (CPython): the AWS CLI,
                                                       AWS_ENDPOINT_URL, OSBot-Local-Stack's pattern

Routing: the service comes from the SigV4 credential scope when the request is signed
(Credential=AKID/<date>/<region>/<service>/aws4_request), else from the host. Each
service is sent to its route: 'twin' (answered here), 'live' (sent on to AWS by the hook,
recorded), or 'replay' (answered from a recording). The default is twin for everything.
Services the twin does not have answer 501 NotImplemented with the operation named, so
a gap is visible in the traffic, never a silent success."""
import json
import os
import re
import sys
import time

from aws_twin.core.Twin__Http             import Twin__Request, Twin__Response
from aws_twin.core.Twin__Traffic          import Twin__Traffic
from aws_twin.s3.S3__Twin                 import S3__Twin
from aws_twin.sts.STS__Twin               import STS__Twin
from aws_twin.vfs.Vfs__Provider__Memory   import Vfs__Provider__Memory

TWIN_CREDENTIALS = {'AWS_ACCESS_KEY_ID': 'TWINACCESSKEYID00000', 'AWS_SECRET_ACCESS_KEY': 'twin-secret-key', 'AWS_SESSION_TOKEN': 'twin-session-token'}


class Twin:
    def __init__(self, vfs=None, account_id='111111111111', region='eu-west-2', routes=None, replay=None,
                 keep_bodies=False, endpoint_hosts=('localhost', '127.0.0.1', 'aws.twin.local'),
                 role_name='twin', session_name='session', set_credentials=True):
        self.vfs               = vfs if vfs is not None else Vfs__Provider__Memory()
        self.account_id        = account_id
        self.region            = region
        self.role_name         = role_name
        self.session_name      = session_name
        self.canonical_user_id = 'twin' + account_id
        self.endpoint_hosts    = tuple(endpoint_hosts)
        self.routes            = dict(routes or {})                    # service -> 'twin' | 'live' | 'replay'
        self.replay            = replay
        self.traffic           = Twin__Traffic(keep_bodies=keep_bodies)
        self.services          = {'s3': S3__Twin(self), 'sts': STS__Twin(self)}
        self.set_credentials   = set_credentials
        self._saved_send       = None
        self._saved_env        = {}

    # ── routing ──────────────────────────────────────────────────────────
    def service_of(self, request):
        scope = request.header('authorization', '') + ' ' + request.query.get('X-Amz-Credential', '')
        m = re.search(r'Credential=[^/\s]+/\d{8}/[a-z0-9-]+/([a-z0-9-]+)/aws4_request', scope) or \
            re.search(r'^[^/]+/\d{8}/[a-z0-9-]+/([a-z0-9-]+)/aws4_request', request.query.get('X-Amz-Credential', ''))
        if m:
            return m.group(1)
        host = request.host
        if re.search(r'(^|\.)s3[.-]', host) or host.startswith('s3.'):
            return 's3'
        label = host.split('.')[0]
        return label if host.endswith('amazonaws.com') else 's3'

    def route_of(self, service):
        return self.routes.get(service, 'twin')

    def operation_hint(self, request):
        target = request.header('x-amz-target')
        if target:
            return target.split('.')[-1]
        if 'Action' in request.query:
            return request.query['Action']
        m = re.search(rb'Action=([A-Za-z]+)', request.body[:200]) if request.body else None
        return m.group(1).decode() if m else 'Unknown'

    def handle(self, request, route=None):
        """Answer one request from the twin (or a replay); 'live' is the hook's job."""
        started = time.time()
        service = self.service_of(request)
        route   = route or self.route_of(service)
        if route == 'replay' and self.replay is not None:
            response  = self.replay.handle(request)
            operation = self.operation_hint(request)
        elif service in self.services:
            operation, response = self.services[service].handle(request)
        else:
            operation = self.operation_hint(request)
            response  = self.not_implemented(request, service, operation)
        response.headers.setdefault('x-amz-request-id', request.request_id)
        response.headers.setdefault('x-amzn-requestid', request.request_id)
        response.headers['x-aws-twin'] = route
        self.traffic.record(request, response, service, operation, route, started)
        return response

    def not_implemented(self, request, service, operation):
        message = f'the twin does not implement {service}.{operation}'
        if request.header('x-amz-target') or 'json' in request.header('content-type', ''):
            return Twin__Response(501, {'content-type': 'application/x-amz-json-1.1', 'x-amzn-errortype': 'NotImplemented'},
                                  json.dumps({'__type': 'NotImplemented', 'message': message}))
        return Twin__Response(501, {'content-type': 'application/xml'},
                              f'<ErrorResponse><Error><Code>NotImplemented</Code><Message>{message}</Message></Error></ErrorResponse>')

    # ── the botocore hook ────────────────────────────────────────────────
    def activate(self):
        from botocore.httpsession import URLLib3Session
        if self._saved_send is not None:
            return self
        twin = self
        original = URLLib3Session.send

        def send(session_self, prepared):
            request = Twin__Request(prepared.method, prepared.url, dict(prepared.headers.items()), prepared.body)
            service = twin.service_of(request)
            if twin.route_of(service) == 'live':
                started  = time.time()
                if sys.platform == 'emscripten':                      # in a browser: botocore's sockets do not exist there
                    from aws_twin.core.Twin__Browser_Http import send_from_browser
                    response = send_from_browser(prepared)
                else:
                    response = original(session_self, prepared)
                twin.traffic.record(request, Twin__Response(response.status_code, dict(response.headers.items()), response.content),
                                    service, twin.operation_hint(request), 'live', started)
                return response
            return to_botocore(prepared.url, twin.handle(request))

        URLLib3Session.send = send
        self._saved_send    = original
        if self.set_credentials:
            for k, v in TWIN_CREDENTIALS.items():
                self._saved_env[k] = os.environ.get(k)
                os.environ.setdefault(k, v)
            self._saved_env['AWS_DEFAULT_REGION'] = os.environ.get('AWS_DEFAULT_REGION')
            os.environ.setdefault('AWS_DEFAULT_REGION', self.region)
        return self

    def deactivate(self):
        from botocore.httpsession import URLLib3Session
        if self._saved_send is not None:
            URLLib3Session.send = self._saved_send
            self._saved_send    = None
        for k, v in self._saved_env.items():
            if v is None: os.environ.pop(k, None)
            else:         os.environ[k] = v
        self._saved_env = {}
        return self

    def __enter__(self):
        return self.activate()

    def __exit__(self, *exc):
        self.deactivate()
        return False

    # ── a real endpoint (CPython) ────────────────────────────────────────
    def serve(self, host='127.0.0.1', port=4566, background=True):
        from aws_twin.core.Twin__Server import Twin__Server
        server = Twin__Server(self, host, port)
        return server.start() if background else server.serve_forever()


class _Raw:
    """The raw body botocore reads: read(amt), stream(), and the attributes it inspects."""
    def __init__(self, data):
        import io
        self._io = io.BytesIO(data)

    def read(self, amt=None, decode_content=True):
        return self._io.read() if amt is None else self._io.read(amt)

    def stream(self, chunk_size=1024, decode_content=True):
        while True:
            chunk = self._io.read(chunk_size)
            if not chunk:
                break
            yield chunk

    def close(self):
        pass


def to_botocore(url, response):
    from botocore.awsrequest import AWSResponse
    return AWSResponse(url, response.status, response.headers, _Raw(response.body))
