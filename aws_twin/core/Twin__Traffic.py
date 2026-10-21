"""Every request the twin saw and what it answered: the call log, and the recording a
replay plays back. Bodies are kept as sizes and hashes by default, and in full when asked."""
import base64
import json
import time


class Twin__Traffic:
    def __init__(self, keep_bodies=False, limit=5000):
        self.records     = []
        self.keep_bodies = keep_bodies
        self.limit       = limit
        self._seq        = 0

    def record(self, request, response, service, operation, target, started):
        self._seq += 1
        rec = {'seq'       : self._seq,
               'at'        : time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(started)) + 'Z',
               'ms'        : round((time.time() - started) * 1000, 2),
               'target'    : target,                                    # twin | live | replay
               'service'   : service,
               'operation' : operation,
               'method'    : request.method,
               'url'       : request.url,
               'signed'    : request.header('authorization', '').startswith('AWS4-HMAC-SHA256'),
               'request'   : {'headers': {k: v for k, v in request.headers.items() if k != 'authorization'},
                              'body_bytes': len(request.body), 'body_sha256': request.body_sha256()},
               'status'    : response.status,
               'response'  : {'headers': dict(response.headers), 'body_bytes': len(response.body)}}
        if self.keep_bodies:
            rec['request' ]['body_b64'] = base64.b64encode(request.body ).decode()
            rec['response']['body_b64'] = base64.b64encode(response.body).decode()
        self.records.append(rec)
        if len(self.records) > self.limit:
            self.records.pop(0)
        return rec

    def clear(self):
        self.records = []

    def summary(self):
        ops = {}
        for r in self.records:
            key = f"{r['service']}.{r['operation']}"
            ops[key] = ops.get(key, 0) + 1
        return {'calls': len(self.records), 'operations': ops,
                'errors': sum(1 for r in self.records if r['status'] >= 400)}

    def to_json(self):
        return json.dumps(self.records, indent=2)
