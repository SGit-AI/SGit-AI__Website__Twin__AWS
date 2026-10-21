"""Run every test_* function in tests/ without pytest: how the browser runs the same
tests CI runs. Returns a JSON-able report."""
import importlib
import time
import traceback

MODULES = ['tests.test_vfs', 'tests.test_s3_twin', 'tests.test_osbot_aws', 'tests.test_server_and_replay', 'tests.test_live_route', 'tests.test_relay', 'tests.test_iam_guidance']


def run(modules=None):
    results = []
    for name in modules or MODULES:
        mod = importlib.import_module(name)
        for attr in sorted(dir(mod)):
            if not attr.startswith('test_'):
                continue
            started = time.time()
            try:
                getattr(mod, attr)()
                results.append({'test': f'{name}.{attr}', 'ok': True, 'ms': round((time.time() - started) * 1000)})
            except Exception as e:
                if type(e).__name__ == 'Skipped':
                    results.append({'test': f'{name}.{attr}', 'ok': True, 'skipped': str(e), 'ms': round((time.time() - started) * 1000)})
                    continue
                results.append({'test': f'{name}.{attr}', 'ok': False, 'ms': round((time.time() - started) * 1000),
                                'error': f'{type(e).__name__}: {e}', 'trace': traceback.format_exc()[-1500:]})
    return {'passed': sum(r['ok'] and not r.get('skipped') for r in results), 'skipped': sum(1 for r in results if r.get('skipped')), 'failed': sum(not r['ok'] for r in results), 'results': results}
