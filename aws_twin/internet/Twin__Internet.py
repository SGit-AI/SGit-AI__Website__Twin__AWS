"""The twin's internet: what a twinned function's outbound requests get back.

An answer per URL, per host, or for '*': a status (and optional body), a delay, or an error such as
ECONNREFUSED or ETIMEDOUT. A request with no answer fails as an unreachable host, by name. Kept in
the VFS (/internet/answers.json) so a page keeps its configured internet across reloads."""
from aws_twin.core.Twin__Service import Twin__Store

ERRORS = ('ENOTFOUND', 'ECONNREFUSED', 'ECONNRESET', 'ETIMEDOUT', 'CERT_HAS_EXPIRED')


class Twin__Internet:
    def __init__(self, vfs):
        self.store = Twin__Store(vfs, 'internet')

    @property
    def answers(self):
        return self.store.read_json('answers.json', default={})

    def answer(self, target, status=200, ms=40, body='', error=None, headers=None):
        """Set what `target` (a URL, a host, or '*') answers. error: one of ERRORS, instead of a status."""
        if error is not None and error not in ERRORS:
            raise ValueError(f'error is one of {ERRORS}')
        answers = self.answers
        answers[target] = {k: v for k, v in {'status': None if error else int(status), 'ms': int(ms), 'body': body,
                                             'error': error, 'headers': headers}.items() if v not in (None, '')}
        self.store.write_json(answers, 'answers.json')
        return answers[target]

    def forget(self, target=None):
        answers = {} if target is None else {k: v for k, v in self.answers.items() if k != target}
        self.store.write_json(answers, 'answers.json')

    def table(self, append_lanes=None):
        """What the Node.js harness reads: the answers, and the append lanes keyed by their write URL."""
        return {'answers': self.answers, 'lanes': append_lanes.table() if append_lanes else {}}
