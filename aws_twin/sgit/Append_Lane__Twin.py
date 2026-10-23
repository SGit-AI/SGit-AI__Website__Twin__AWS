"""The sgit append lane, twinned: the write-only channel on a vault that a function posts its
encrypted reports to (https://sgit.ai/docs/vault-messaging.md).

    /sgit/append/<vault_id>/lane.json                     host, anchors (sha256 of each append token), enum key hash
    /sgit/append/<vault_id>/<anchor>/pending/<file_id>    a payload, as written
    /sgit/append/<vault_id>/<anchor>/processed/<file_id>  after mark_processed

The server's rules, as sgit.ai documents them (api/append-lanes.md, checked 26 September 2026): the
token is 16 to 128 hex characters (400), a payload is at most 5 MB (413), an unknown vault or a token
whose sha256 is not an anchor is a 404 with an HTML page, and the answer to a write is blind:
exactly {"ok": true}. Owners list, fetch and mark processed with the enum key.
File ids are {epoch_ms}_{24 hex}.enc, so they sort by time."""
import hashlib
import re
import secrets
import time

from aws_twin.core.Twin__Service import Twin__Store

TOKEN     = re.compile(r'^[0-9a-f]{16,128}$')
WRITE_URL = re.compile(r'^https://([^/]+)/api/vault/append/write/([A-Za-z0-9_-]+)$')
MAX_BYTES = 5 * 1024 * 1024


def sha256_hex(text):
    return hashlib.sha256(text.encode()).hexdigest()


class Append_Lane__Twin:
    def __init__(self, vfs):
        self.store = Twin__Store(vfs, 'sgit/append')

    # ── the owner's side: a vault with a lane ───────────────────────────
    def create_lane(self, vault_id=None, append_token=None, enum_key=None, host='dev.send.sgraph.ai'):
        vault_id     = vault_id or secrets.token_hex(6)
        append_token = append_token or secrets.token_hex(32)
        enum_key     = enum_key or secrets.token_hex(32)
        lane         = self.store.read_json(vault_id, 'lane.json', default={'vault_id': vault_id, 'host': host, 'anchors': []})
        if sha256_hex(append_token) not in lane['anchors']:
            lane['anchors'].append(sha256_hex(append_token))
        lane['enum_key_hash'] = sha256_hex(enum_key)
        self.store.write_json(lane, vault_id, 'lane.json')
        return {'vault_id': vault_id, 'append_token': append_token, 'enum_key': enum_key, 'host': host,
                'write_url': f'https://{host}/api/vault/append/write/{vault_id}'}

    def lanes(self):
        return [self.store.read_json(v, 'lane.json') for v in self.store.folders() if self.store.exists(v, 'lane.json')]

    def table(self):
        return {f'https://{l["host"]}/api/vault/append/write/{l["vault_id"]}': {'anchors': l['anchors']} for l in self.lanes()}

    def lane_for_url(self, url):
        m = WRITE_URL.match(url.split('?')[0])
        if not m:
            return None
        lane = self.store.read_json(m.group(2), 'lane.json')
        return lane if lane and lane['host'] == m.group(1) else None

    # ── the sender's side: write ────────────────────────────────────────
    def write(self, vault_id, append_token, payload):
        """Returns (status, answer) as the server would."""
        if not isinstance(append_token, str) or not TOKEN.match(append_token):
            return 400, {'detail': 'append_token must be 16 to 128 hex characters'}
        if not isinstance(payload, str) or not payload:
            return 400, {'detail': 'payload is required'}
        if len(payload) > MAX_BYTES:
            return 413, {'detail': 'payload too large'}
        lane   = self.store.read_json(vault_id, 'lane.json')
        anchor = sha256_hex(append_token)
        if lane is None or anchor not in lane['anchors']:
            return 404, None                                           # the server's HTML 404, for either
        file_id = f'{int(time.time() * 1000)}_{secrets.token_hex(12)}.enc'
        self.store.write_bytes(payload.encode(), vault_id, anchor, 'pending', file_id)
        return 200, {'ok': True}

    def write_url(self, url, body):
        import json
        lane = self.lane_for_url(url)
        try:
            doc = json.loads(body)
        except ValueError:
            return 400, {'detail': 'the body is not JSON'}
        return self.write(lane['vault_id'], doc.get('append_token'), doc.get('payload'))

    # ── the owner's side: read ──────────────────────────────────────────
    def owner_lane(self, vault_id, enum_key):
        lane = self.store.read_json(vault_id, 'lane.json')
        if lane is None or lane.get('enum_key_hash') != sha256_hex(enum_key or ''):
            raise PermissionError('unknown vault, or the wrong enum key')
        return lane

    def list(self, vault_id, enum_key, folder='pending'):
        self.owner_lane(vault_id, enum_key)
        out = []
        for anchor in self.store.folders(vault_id):
            for file_id in sorted(self.store.files(vault_id, anchor, folder)):
                out.append({'anchor': anchor, 'file_id': file_id, 'size': len(self.store.read_bytes(vault_id, anchor, folder, file_id))})
        return out

    def fetch(self, vault_id, enum_key, file_ids=None):
        self.owner_lane(vault_id, enum_key)
        want = set(file_ids) if file_ids else None
        return [dict(e, content=self.store.read_bytes(vault_id, e['anchor'], 'pending', e['file_id']).decode())
                for e in self.list(vault_id, enum_key) if want is None or e['file_id'] in want]

    def mark_processed(self, vault_id, enum_key, file_ids):
        moved = []
        for e in self.list(vault_id, enum_key):
            if e['file_id'] in file_ids:
                data = self.store.read_bytes(vault_id, e['anchor'], 'pending', e['file_id'])
                self.store.write_bytes(data, vault_id, e['anchor'], 'processed', e['file_id'])
                self.store.delete(vault_id, e['anchor'], 'pending', e['file_id'])
                moved.append(e['file_id'])
        return {'processed': moved, 'missing': [f for f in file_ids if f not in moved]}
