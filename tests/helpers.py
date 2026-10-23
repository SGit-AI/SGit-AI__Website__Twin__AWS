"""Shared by the tests, with no pytest import: the same test files run under pytest in CI
and under tests/browser_runner.py in Pyodide, so a test may only use plain asserts."""
import sys

IN_BROWSER = sys.platform == 'emscripten'


def raises(code, fn):
    """Call fn, expect a botocore ClientError (or an exception with .code) whose code is `code`."""
    try:
        fn()
    except Exception as e:
        got = getattr(e, 'response', {}).get('Error', {}).get('Code') if hasattr(e, 'response') else getattr(e, 'code', None)
        assert got == code, f'expected {code}, got {got}: {e}'
        return e
    raise AssertionError(f'expected {code}, nothing was raised')


def has_module(name):
    try:
        __import__(name)
        return True
    except Exception:
        return False


class Skipped(Exception):
    """Raised by skip(); pytest's own skip when pytest is running, this otherwise."""


def skip(reason):
    try:
        import pytest
    except ImportError:
        raise Skipped(reason)
    pytest.skip(reason)


def needs_node_runtime():
    """Skip unless the Lambda twin can run Node.js handlers here: node on the PATH (CPython), or the
    browser's JSPI with Python entered through runPythonAsync (Pyodide; checked by trying)."""
    import shutil
    if IN_BROWSER:
        try:
            import pyodide.ffi
            if not hasattr(pyodide.ffi, 'run_sync'):
                skip('this Pyodide has no run_sync')
        except ImportError:
            skip('no pyodide.ffi')
        return
    if not shutil.which('node'):
        skip('no node on the PATH: the Lambda twin runs Node.js handlers with it')


def skip_if_twin_unavailable(payload):
    """In a browser without JSPI the twin reports Runtime.TwinUnavailable rather than run the handler."""
    if isinstance(payload, dict) and payload.get('errorType') == 'Runtime.TwinUnavailable':
        skip(payload.get('errorMessage', 'the twin cannot run Node.js here'))
