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
