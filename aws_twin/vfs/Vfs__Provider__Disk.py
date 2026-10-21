"""The disk provider: the same contract over a real folder, for a twin that runs as a
local endpoint and should keep its buckets between runs. CPython only (Pyodide's file
system is in memory unless mounted)."""
import os
import shutil

from aws_twin.vfs.Vfs__Path           import Vfs__Error, normalise_path
from aws_twin.vfs.Vfs__Provider__Base import Vfs__Provider__Base


class Vfs__Provider__Disk(Vfs__Provider__Base):
    name = 'disk'

    def __init__(self, root):
        self.root = os.path.abspath(root)
        os.makedirs(self.root, exist_ok=True)

    def _real(self, path):
        return os.path.join(self.root, normalise_path(path).lstrip('/'))

    def read_file(self, path):
        real = self._real(path)
        if os.path.isdir(real):     raise Vfs__Error('EISDIR', path)
        if not os.path.isfile(real): raise Vfs__Error('ENOENT', path)
        with open(real, 'rb') as f:
            return f.read()

    def write_file(self, path, content):
        if isinstance(content, str):
            content = content.encode('utf-8')
        real = self._real(path)
        if os.path.isdir(real):
            raise Vfs__Error('EISDIR', path)
        os.makedirs(os.path.dirname(real), exist_ok=True)
        with open(real, 'wb') as f:
            f.write(content)

    def delete_file(self, path):
        real = self._real(path)
        if not os.path.isfile(real):
            raise Vfs__Error('ENOENT', path)
        os.remove(real)

    def list_folder(self, path):
        p, real = normalise_path(path), self._real(path)
        if not os.path.isdir(real):
            raise Vfs__Error('ENOTDIR' if os.path.exists(real) else 'ENOENT', path)
        out = []
        for name in os.listdir(real):
            full = os.path.join(real, name)
            st   = os.stat(full)
            out.append({'name': name, 'path': (p.rstrip('/') + '/' + name), 'type': 'folder' if os.path.isdir(full) else 'file',
                        'size': 0 if os.path.isdir(full) else st.st_size, 'modified': int(st.st_mtime * 1000)})
        out.sort(key=lambda e: (e['type'] != 'folder', e['name']))
        return out

    def stat(self, path):
        real = self._real(path)
        if not os.path.exists(real):
            raise Vfs__Error('ENOENT', path)
        st = os.stat(real)
        return {'path': normalise_path(path), 'type': 'folder' if os.path.isdir(real) else 'file',
                'size': 0 if os.path.isdir(real) else st.st_size, 'created': int(st.st_ctime * 1000), 'modified': int(st.st_mtime * 1000)}

    def create_folder(self, path):
        os.makedirs(self._real(path), exist_ok=True)

    def copy_file(self, src, dst):
        self.write_file(dst, self.read_file(src))

    def rename(self, src, dst):
        real_dst = self._real(dst)
        os.makedirs(os.path.dirname(real_dst), exist_ok=True)
        shutil.move(self._real(src), real_dst)

    def exists(self, path):
        return os.path.exists(self._real(path))
