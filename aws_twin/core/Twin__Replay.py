"""Replay: answer from a recording instead of from the twin or the account. A request
matches a recorded one on method, host, path, sorted query and body hash; unmatched
requests get a 501 that names them, so a replay never silently invents an answer."""
import base64

from aws_twin.core.Twin__Http import Twin__Response


class Twin__Replay:
    def __init__(self, records):
        self.answers = {}
        for r in records:
            if 'body_b64' not in r.get('response', {}):
                raise ValueError('replay needs a recording made with keep_bodies=True')
            self.answers.setdefault(self.key_of(r['method'], r['url'], r['request']['body_sha256']), []).append(r)
        self.misses = []

    @staticmethod
    def key_of(method, url, body_sha256):
        from urllib.parse import urlsplit, parse_qsl
        p = urlsplit(url)
        return (method.upper(), (p.hostname or '').lower(), p.path, tuple(sorted(parse_qsl(p.query, keep_blank_values=True))), body_sha256)

    def handle(self, request):
        key  = self.key_of(request.method, request.url, request.body_sha256())
        hits = self.answers.get(key)
        if not hits:
            self.misses.append(request.url)
            return Twin__Response(501, {'content-type': 'application/xml'},
                                  f'<Error><Code>NotInRecording</Code><Message>{request.method} {request.url}</Message></Error>')
        rec = hits.pop(0) if len(hits) > 1 else hits[0]
        return Twin__Response(rec['status'], rec['response']['headers'], base64.b64decode(rec['response']['body_b64']))
