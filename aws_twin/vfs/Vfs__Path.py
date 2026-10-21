"""Path rules, the same as sg-vfs-path.js in SGraph-AI__Tools: absolute, '/'-separated,
no trailing slash except the root, no '.' or '..' segments."""


class Vfs__Error(Exception):
    def __init__(self, code, path, message=None):
        self.code = code
        self.path = path
        super().__init__(message or f'{code}: {path}')


def normalise_path(path: str) -> str:
    if not isinstance(path, str) or not path:
        raise Vfs__Error('EINVAL', str(path), 'a path is a non-empty string')
    if not path.startswith('/'):
        path = '/' + path
    parts = []
    for segment in path.split('/'):
        if segment in ('', '.'):
            continue
        if segment == '..':
            raise Vfs__Error('EINVAL', path, 'a path may not contain ..')
        parts.append(segment)
    return '/' + '/'.join(parts)


def dirname(path: str) -> str:
    path = normalise_path(path)
    if path == '/':
        return '/'
    parent = path.rsplit('/', 1)[0]
    return parent or '/'


def basename(path: str) -> str:
    return normalise_path(path).rsplit('/', 1)[-1]


def ancestors(path: str) -> list:
    """Every ancestor folder of path, root first, not including path itself."""
    path   = normalise_path(path)
    result = ['/']
    parts  = path.strip('/').split('/')[:-1]
    for i in range(len(parts)):
        result.append('/' + '/'.join(parts[:i + 1]))
    return result
