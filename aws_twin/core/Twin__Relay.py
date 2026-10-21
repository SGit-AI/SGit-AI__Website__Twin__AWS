#!/usr/bin/env python3
"""The AWS twin's local relay: lets a page on aws.twin.sgit.ai reach AWS services that do not answer a
browser, such as S3's ListBuckets, by forwarding the page's already-signed requests from this machine.

    curl -sO https://aws.twin.sgit.ai/aws_twin/core/Twin__Relay.py
    python3 Twin__Relay.py                   # listens on http://127.0.0.1:4567

What it does, and does not do:
  - It holds no credentials. The page signs every request with the session pasted into it (SigV4, in the
    browser); the relay forwards the request byte for byte to the AWS host named in the x-twin-target header,
    and returns AWS's answer with the CORS headers a browser needs. A signature it cannot alter is its only
    authority, so it can do nothing the session could not.
  - It forwards only to *.amazonaws.com over HTTPS, so it is not an open proxy.
  - It answers only the origins it is told to (https://aws.twin.sgit.ai by default), and listens on 127.0.0.1
    only, so nothing else on the network can use it.
  - It logs one line per request (method, host, path, status), never a header or a body.

Standard library only, one file, so it can be read in full before it is run. Content CC BY 4.0, code Apache-2.0.
"""
import argparse
import http.client
import re
import ssl
import sys
import threading
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DEFAULT_ORIGINS = ('https://aws.twin.sgit.ai',)
AWS_HOST        = re.compile(r'^([a-z0-9-]+\.)+amazonaws\.com$')
DROP_REQUEST    = {'host', 'origin', 'referer', 'connection', 'content-length', 'accept-encoding', 'cookie',
                   'x-twin-target', 'keep-alive', 'transfer-encoding', 'te', 'upgrade', 'proxy-connection'}
DROP_RESPONSE   = {'connection', 'keep-alive', 'transfer-encoding', 'content-length', 'access-control-allow-origin',
                   'access-control-expose-headers', 'access-control-allow-headers', 'access-control-allow-methods'}


class Twin__Relay:
    def __init__(self, host='127.0.0.1', port=4567, origins=DEFAULT_ORIGINS, allow_hosts=None, quiet=False, upstream=None):
        self.host, self.port, self.quiet = host, port, quiet
        self.origins     = tuple(o.rstrip('/') for o in origins)
        self.allow_hosts = allow_hosts                                  # tests only: a host:port to allow besides AWS
        self.upstream    = upstream                                     # tests only, never from the command line: send every
                                                                        # request to this http://host:port instead, keeping its Host
        self.httpd       = None

    # ── policy ───────────────────────────────────────────────────────────
    def origin_ok(self, origin):
        return origin is not None and origin.rstrip('/') in self.origins

    def target_ok(self, url):
        p = urllib.parse.urlsplit(url)
        if p.scheme == 'https' and AWS_HOST.match(p.hostname or ''):
            return True
        return bool(self.allow_hosts) and p.netloc in self.allow_hosts

    # ── forwarding ───────────────────────────────────────────────────────
    def forward(self, method, url, headers, body):
        """Send the signed request on exactly as received: http.client adds nothing but Host and
        Content-Length, both the values botocore signed, and follows no redirects (botocore handles S3's
        region redirects itself). Tunnels through HTTPS_PROXY when one is set."""
        p     = urllib.parse.urlsplit(url)
        path  = p.path or '/'
        if p.query:
            path += '?' + p.query
        if self.upstream:                                               # the test stand-in for AWS: same request, same Host
            u    = urllib.parse.urlsplit(self.upstream)
            conn = http.client.HTTPConnection(u.hostname, u.port, timeout=60)
            try:
                conn.request(method, path, body=body if (body or method in ('PUT', 'POST')) else None, headers=dict(headers, Host=p.netloc))
                resp = conn.getresponse()
                return resp.status, resp.getheaders(), resp.read()
            finally:
                conn.close()
        proxy = urllib.request.getproxies().get(p.scheme)
        bypass = urllib.request.proxy_bypass(p.hostname or '')
        if p.scheme == 'https':
            ctx = ssl.create_default_context()
            if proxy and not bypass:
                pp   = urllib.parse.urlsplit(proxy)
                conn = http.client.HTTPSConnection(pp.hostname, pp.port or 80, timeout=60, context=ctx)
                conn.set_tunnel(p.hostname, p.port or 443)
            else:
                conn = http.client.HTTPSConnection(p.hostname, p.port or 443, timeout=60, context=ctx)
        else:
            conn = http.client.HTTPConnection(p.hostname, p.port or 80, timeout=60)
        try:
            conn.request(method, path, body=body if (body or method in ('PUT', 'POST')) else None, headers=headers)
            resp = conn.getresponse()
            return resp.status, resp.getheaders(), resp.read()
        finally:
            conn.close()

    def handler(self):
        relay = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'

            def cors(self):
                origin = self.headers.get('origin')
                if relay.origin_ok(origin):
                    self.send_header('access-control-allow-origin', origin)
                    self.send_header('vary', 'origin')
                    self.send_header('access-control-expose-headers', '*')
                return relay.origin_ok(origin)

            def reply(self, status, headers, body):
                self.send_response(status)
                self.cors()
                for k, v in headers:
                    if k.lower() not in DROP_RESPONSE:
                        self.send_header(k, v)
                self.send_header('content-length', str(len(body)))
                self.end_headers()
                if self.command != 'HEAD':
                    self.wfile.write(body)

            def do_OPTIONS(self):
                self.send_response(204 if relay.origin_ok(self.headers.get('origin')) else 403)
                if self.cors():
                    self.send_header('access-control-allow-methods', 'GET, PUT, POST, DELETE, HEAD')
                    self.send_header('access-control-allow-headers', self.headers.get('access-control-request-headers', '*'))
                    self.send_header('access-control-allow-private-network', 'true')
                    self.send_header('access-control-max-age', '600')
                self.send_header('content-length', '0')
                self.end_headers()

            def relay_request(self):
                origin = self.headers.get('origin')
                if self.command == 'GET' and self.path.split('?')[0] == '/health':  # the page asks this first, without credentials:
                    if origin is not None and not relay.origin_ok(origin):         # it raises the browser's local-network prompt
                        return self.reply(403, [('content-type', 'text/plain')], b'origin not allowed\n')
                    return self.reply(200, [('content-type', 'application/json')],
                                      b'{"relay": "aws.twin", "forwards_to": "*.amazonaws.com", "holds_credentials": false}')
                target = self.headers.get('x-twin-target', '')
                length = int(self.headers.get('content-length') or 0)
                body   = self.rfile.read(length) if length else b''
                if origin is not None and not relay.origin_ok(origin):
                    return self.reply(403, [('content-type', 'text/plain')], f'origin not allowed: {origin}\n'.encode())
                if not relay.target_ok(target):
                    return self.reply(400, [('content-type', 'text/plain')], b'x-twin-target must be an https://*.amazonaws.com URL\n')
                headers = {k: v for k, v in self.headers.items() if k.lower() not in DROP_REQUEST and not k.lower().startswith('sec-')}
                try:
                    status, rheaders, rbody = relay.forward(self.command, target, headers, body)
                except Exception as e:
                    return self.reply(502, [('content-type', 'text/plain')], f'relay could not reach {urllib.parse.urlsplit(target).hostname}: {e}\n'.encode())
                if not relay.quiet:
                    p = urllib.parse.urlsplit(target)
                    print(f'{self.command:6} {p.hostname}{p.path[:80]} -> {status}', flush=True)
                self.reply(status, rheaders, rbody)

            do_GET = do_PUT = do_POST = do_DELETE = do_HEAD = relay_request

            def log_message(self, *args):
                pass

        return Handler

    def start(self):
        self.httpd = ThreadingHTTPServer((self.host, self.port), self.handler())
        self.port  = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        return self

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


def main(argv=None):
    p = argparse.ArgumentParser(prog='Twin__Relay.py', description='The AWS twin local relay: forwards signed requests from aws.twin.sgit.ai to AWS. Holds no credentials.')
    p.add_argument('--port', type=int, default=4567)
    p.add_argument('--origin', action='append', help='an origin allowed to use the relay (repeatable; default https://aws.twin.sgit.ai)')
    a = p.parse_args(argv)
    relay = Twin__Relay(port=a.port, origins=tuple(a.origin or DEFAULT_ORIGINS))
    relay.httpd = ThreadingHTTPServer((relay.host, relay.port), relay.handler())
    print(f'aws.twin relay on {relay.url} for {", ".join(relay.origins)}; forwards signed requests to *.amazonaws.com only; Ctrl+C to stop', flush=True)
    try:
        relay.httpd.serve_forever()
    except KeyboardInterrupt:
        print('stopped')


if __name__ == '__main__':
    sys.exit(main())
