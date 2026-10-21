"""The memory provider: a dict, as sg-vfs-provider-memory.js is a Map, plus a change
journal. The journal is how the browser persists: after each call the page drains it and
writes the same changes to sg-vfs's IndexedDB provider, which is the layered provider's
write-through, done across the Python/JavaScript boundary."""
import time

from aws_twin.vfs.Vfs__Path           import Vfs__Error, normalise_path, dirname, basename, ancestors
from aws_twin.vfs.Vfs__Provider__Base import Vfs__Provider__Base


def _now_ms():
    return int(time.time() * 1000)


class Vfs__Provider__Memory(Vfs__Provider__Base):
    name = 'memory'

    def __init__(self, journal=False):
        self._store   = {'/': {'type': 'folder', 'created': _now_ms(), 'modified': _now_ms()}}
        self._journal = [] if journal else None

    # ── helpers ──────────────────────────────────────────────────────────
    def _record(self, op, path, **extra):
        if self._journal is not None:
            self._journal.append(dict(op=op, path=path, **extra))

    def _get(self, path):
        return self._store.get(normalise_path(path))

    def _assert_exists(self, path):
        entry = self._get(path)
        if entry is None:
            raise Vfs__Error('ENOENT', path, f'Not found: {path}')
        return entry

    def _assert_file(self, path):
        entry = self._assert_exists(path)
        if entry['type'] != 'file':
            raise Vfs__Error('EISDIR', path, f'Not a file: {path}')
        return entry

    def _assert_folder(self, path):
        entry = self._assert_exists(path)
        if entry['type'] != 'folder':
            raise Vfs__Error('ENOTDIR', path, f'Not a folder: {path}')
        return entry

    def _ensure_ancestors(self, path):
        for anc in ancestors(path):
            existing = self._store.get(anc)
            if existing is None:
                now = _now_ms()
                self._store[anc] = {'type': 'folder', 'created': now, 'modified': now}
            elif existing['type'] != 'folder':
                raise Vfs__Error('ENOTDIR', anc, f'Not a folder: {anc}')

    def _touch_parent(self, path):
        parent = self._store.get(dirname(path))
        if parent:
            parent['modified'] = _now_ms()

    # ── the contract ─────────────────────────────────────────────────────
    def read_file(self, path):
        return self._assert_file(normalise_path(path))['content']

    def write_file(self, path, content):
        p = normalise_path(path)
        if isinstance(content, str):
            content = content.encode('utf-8')
        if not isinstance(content, (bytes, bytearray)):
            raise Vfs__Error('EINVAL', p, 'content is bytes or str')
        self._ensure_ancestors(p)
        existing = self._store.get(p)
        if existing and existing['type'] == 'folder':
            raise Vfs__Error('EISDIR', p, f'Is a folder: {p}')
        now = _now_ms()
        self._store[p] = {'type': 'file', 'content': bytes(content), 'size': len(content),
                          'created': existing['created'] if existing else now, 'modified': now}
        self._touch_parent(p)
        self._record('write', p, content=bytes(content))

    def delete_file(self, path):
        p = normalise_path(path)
        self._assert_file(p)
        del self._store[p]
        self._touch_parent(p)
        self._record('delete', p)

    def list_folder(self, path):
        p = normalise_path(path)
        self._assert_folder(p)
        prefix  = '/' if p == '/' else p + '/'
        results = []
        for key, entry in self._store.items():
            if key == p or not key.startswith(prefix) or '/' in key[len(prefix):]:
                continue
            results.append({'name': basename(key), 'path': key, 'type': entry['type'],
                            'size': entry.get('size', 0), 'modified': entry['modified']})
        results.sort(key=lambda e: (e['type'] != 'folder', e['name']))
        return results

    def stat(self, path):
        p     = normalise_path(path)
        entry = self._assert_exists(p)
        return {'path': p, 'type': entry['type'], 'size': entry.get('size', 0),
                'created': entry['created'], 'modified': entry['modified']}

    def create_folder(self, path):
        p = normalise_path(path)
        self._ensure_ancestors(p)
        existing = self._store.get(p)
        if existing is None:
            now = _now_ms()
            self._store[p] = {'type': 'folder', 'created': now, 'modified': now}
        elif existing['type'] != 'folder':
            raise Vfs__Error('ENOTDIR', p, f'Not a folder: {p}')

    def copy_file(self, src, dst):
        self.write_file(dst, self._assert_file(normalise_path(src))['content'])

    def rename(self, src, dst):
        s, d  = normalise_path(src), normalise_path(dst)
        entry = self._assert_file(s)
        self.write_file(d, entry['content'])
        self.delete_file(s)

    def exists(self, path):
        return normalise_path(path) in self._store

    # ── extras ───────────────────────────────────────────────────────────
    def drain_journal(self):
        """The changes since the last drain, oldest first; empties the journal."""
        if self._journal is None:
            return []
        changes, self._journal = self._journal, []
        return changes

    def load_files(self, files):
        """Seed from (path, bytes) pairs without journalling them: how a page restores
        what it persisted on the last visit."""
        journal, self._journal = self._journal, None
        try:
            for path, content in files:
                self.write_file(path, content)
        finally:
            self._journal = journal

    @property
    def size(self):
        return len(self._store)
