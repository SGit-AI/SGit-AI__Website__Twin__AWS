"""The twin as a real HTTP endpoint, standard library only (CPython; Pyodide has no
sockets). Point anything at it with AWS_ENDPOINT_URL=http://127.0.0.1:4566, as
OSBot-Local-Stack does for LocalStack, or `aws --endpoint-url ...`."""
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from aws_twin.core.Twin__Http import Twin__Request


class Twin__Server:
    def __init__(self, twin, host='127.0.0.1', port=4566):
        self.twin, self.host, self.port = twin, host, port
        self.httpd, self.thread = None, None

    def handler(self):
        twin = self.twin
        lock = threading.Lock()

        class Handler(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'

            def _any(self):
                length = int(self.headers.get('content-length') or 0)
                body   = self.rfile.read(length) if length else b''
                host   = self.headers.get('host', f'{twin.endpoint_hosts[0]}')
                req    = Twin__Request(self.command, f'http://{host}{self.path}', dict(self.headers.items()), body)
                with lock:                                             # the VFS is not thread safe; one request at a time
                    resp = twin.handle(req)
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    if k.lower() != 'content-length':
                        self.send_header(k, v)
                self.send_header('content-length', str(len(resp.body)) if self.command != 'HEAD' else resp.headers.get('content-length', '0'))
                self.end_headers()
                if self.command != 'HEAD' and resp.body:
                    self.wfile.write(resp.body)

            do_GET = do_PUT = do_POST = do_DELETE = do_HEAD = do_PATCH = _any

            def log_message(self, *args):
                pass

        return Handler

    def start(self):
        self.httpd  = ThreadingHTTPServer((self.host, self.port), self.handler())
        self.port   = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        return self

    def serve_forever(self):
        self.httpd = ThreadingHTTPServer((self.host, self.port), self.handler())
        self.httpd.serve_forever()

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()

    @property
    def url(self):
        return f'http://{self.host}:{self.port}'

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.stop()
