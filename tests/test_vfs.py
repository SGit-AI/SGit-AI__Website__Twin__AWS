"""The Python VFS keeps sg-vfs's contract and semantics."""
from aws_twin.vfs.Vfs__Path             import Vfs__Error, normalise_path, ancestors
from aws_twin.vfs.Vfs__Provider__Memory import Vfs__Provider__Memory
from tests.helpers                      import raises


def test_paths():
    assert normalise_path('a/b/') == '/a/b'
    assert normalise_path('/a//./b') == '/a/b'
    assert ancestors('/a/b/c') == ['/', '/a', '/a/b']
    raises('EINVAL', lambda: normalise_path('/a/../b'))


def test_memory_contract():
    v = Vfs__Provider__Memory()
    v.write_file('/x/y/z.txt', b'hi')
    assert v.read_file('/x/y/z.txt') == b'hi'
    assert v.exists('/x/y') and v.stat('/x/y')['type'] == 'folder'
    assert [e['name'] for e in v.list_folder('/x')] == ['y']
    v.write_file('/x/a.txt', 'text')
    assert [e['name'] for e in v.list_folder('/x')] == ['y', 'a.txt']               # folders first
    v.copy_file('/x/a.txt', '/x/b.txt')
    v.rename('/x/b.txt', '/x/c.txt')
    assert not v.exists('/x/b.txt') and v.read_file('/x/c.txt') == b'text'
    raises('EISDIR', lambda: v.read_file('/x/y'))
    raises('ENOENT', lambda: v.read_file('/nope'))
    raises('ENOTDIR', lambda: v.write_file('/x/a.txt/inner', b''))
    assert sorted(e['path'] for e in v.walk_files('/')) == ['/x/a.txt', '/x/c.txt', '/x/y/z.txt']


def test_journal():
    v = Vfs__Provider__Memory(journal=True)
    v.write_file('/a', b'1')
    v.delete_file('/a')
    changes = v.drain_journal()
    assert [(c['op'], c['path']) for c in changes] == [('write', '/a'), ('delete', '/a')]
    assert v.drain_journal() == []
    v.load_files([('/b', b'2')])
    assert v.read_file('/b') == b'2' and v.drain_journal() == []                   # seeding is not journalled
