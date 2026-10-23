"""Runs a deployed function for the Lambda twin.

nodejs*: node_harness.mjs, the same file in both places. In CPython it runs under node, as a
subprocess, when node is on the PATH. In Pyodide the page imports it and the twin waits for it with
run_sync, which needs the browser's JSPI and Python entered through callPromising or
runPythonAsync. Where neither is possible the invocation fails as Lambda reports a runtime failure,
with errorType Runtime.TwinUnavailable and the reason, never a silent success.

python*: in process. The package is unpacked to a temporary folder, the handler module imported from
it, the function's environment set for the call and restored after, print() captured as logs.
Its outbound HTTP is not intercepted yet: the twin's internet serves Node.js handlers only.

Both get the twin's internet (Twin__Internet): an answer per URL or host, and the sgit append lanes
the twin holds (Append_Lane__Twin), which keep what an invocation wrote to them."""
import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import uuid
import zipfile

HARNESS = os.path.join(os.path.dirname(__file__), 'node_harness.mjs')
_browser_runner = None


class Lambda__Runtime:
    def __init__(self, twin):
        self.twin = twin

    # ── one invocation ──────────────────────────────────────────────────
    def invoke(self, region, conf, zip_bytes, event_bytes):
        request_id = str(uuid.uuid4())
        name       = conf['FunctionName']
        env        = {'AWS_REGION': region, 'AWS_DEFAULT_REGION': region, 'AWS_LAMBDA_FUNCTION_NAME': name,
                      'AWS_LAMBDA_FUNCTION_MEMORY_SIZE': str(conf['MemorySize']), 'AWS_LAMBDA_FUNCTION_VERSION': '$LATEST',
                      'AWS_EXECUTION_ENV': f'AWS_Lambda_{conf["Runtime"]}', 'AWS_LAMBDA_LOG_GROUP_NAME': f'/aws/lambda/{name}',
                      'LAMBDA_TASK_ROOT': '/var/task', 'TZ': ':UTC'}
        env.update(conf.get('Environment', {}).get('Variables', {}))
        context = {'functionName': name, 'invokedFunctionArn': conf['FunctionArn'], 'memoryLimitInMB': conf['MemorySize'],
                   'awsRequestId': request_id, 'logGroupName': f'/aws/lambda/{name}',
                   'logStreamName': time.strftime('%Y/%m/%d', time.gmtime()) + '/[$LATEST]' + uuid.uuid4().hex}
        try:
            event = json.loads(event_bytes or b'{}')
        except ValueError:
            event = {}
        module, _, fn = conf['Handler'].rpartition('.')
        started = time.time()
        if conf['Runtime'].startswith('nodejs'):
            out = self.run_node(zip_bytes, module, fn, event, env, context, conf, region)
        elif conf['Runtime'].startswith('python'):
            out = self.run_python(zip_bytes, module, fn, event, env, context, conf)
        else:
            out = self.failure('Runtime.TwinUnavailable', f'the twin does not run {conf["Runtime"]} functions')
        out.setdefault('ms', round((time.time() - started) * 1000))
        self.keep_lane_writes(out['requests'])
        payload = json.dumps(out['error'] if out['error'] else out['result']).encode()
        log_text = (f'START RequestId: {request_id} Version: $LATEST\n' + ''.join(l + '\n' for l in out['logs']) +
                    f'END RequestId: {request_id}\nREPORT RequestId: {request_id}\tDuration: {out["ms"]:.2f} ms\t'
                    f'Billed Duration: {int(out["ms"]) + 1} ms\tMemory Size: {conf["MemorySize"]} MB\t(the twin: no memory measured)\n')
        return {'request_id': request_id, 'payload': payload, 'error': out['error'], 'result': out['result'],
                'logs': out['logs'], 'log_text': log_text, 'requests': out['requests'], 'ms': out['ms']}

    @staticmethod
    def failure(error_type, message):
        return {'result': None, 'error': {'errorType': error_type, 'errorMessage': message, 'trace': []}, 'logs': [], 'requests': []}

    def keep_lane_writes(self, requests):
        """What the function wrote to an append lane, kept by the lane twin as the server would."""
        lanes = self.twin.append_lanes
        for r in requests:
            if r.get('method') == 'POST' and r.get('status') == 200 and lanes.lane_for_url(r.get('url', '')):
                lanes.write_url(r['url'], r.get('body') or '')

    # ── Node.js ─────────────────────────────────────────────────────────
    def run_node(self, zip_bytes, module, fn, event, env, context, conf, region):
        files = {}
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            for n in z.namelist():
                if n.endswith(('.mjs', '.js', '.cjs', '.json')):
                    files[n] = z.read(n).decode('utf-8', 'replace')
        entry = next((f'{module}{ext}' for ext in ('.mjs', '.js', '.cjs') if f'{module}{ext}' in files), f'{module}.mjs')
        data  = {'files': files, 'module': entry, 'fn': fn, 'event': event, 'env': env, 'context': context,
                 'timeout_ms': int(conf['Timeout']) * 1000, 'revision': conf['RevisionId'],
                 'internet': self.twin.internet.table(self.twin.append_lanes)}
        if sys.platform == 'emscripten':
            return self.run_node_in_browser(data)
        node = shutil.which('node')
        if not node:
            return self.failure('Runtime.TwinUnavailable', f'the twin runs {conf["Runtime"]} functions with node, and there is no node on the PATH')
        try:
            done = subprocess.run([node, HARNESS], input=json.dumps(data), capture_output=True, text=True, timeout=int(conf['Timeout']) + 20)
        except subprocess.TimeoutExpired:
            return self.failure('Sandbox.Timedout', f'Task timed out after {float(conf["Timeout"]):.2f} seconds')
        if done.returncode != 0 or not done.stdout.strip():
            return self.failure('Runtime.TwinUnavailable', f'node exited {done.returncode}: {done.stderr.strip()[-500:]}')
        return json.loads(done.stdout)

    @staticmethod
    def run_node_in_browser(data):
        global _browser_runner
        try:
            from pyodide.code import run_js
            from pyodide.ffi  import run_sync
        except ImportError as e:
            return Lambda__Runtime.failure('Runtime.TwinUnavailable', f'this Pyodide cannot wait for JavaScript: {e}')
        if _browser_runner is None:
            _browser_runner = run_js("""(async (src, input) => {
                const bytes = new TextEncoder().encode(src); let bin = ''; for (const b of bytes) bin += String.fromCharCode(b);
                const m = await import('data:text/javascript;base64,' + btoa(bin));
                return JSON.stringify(await m.runInvocation(JSON.parse(input)));
            })""")
        with open(HARNESS, encoding='utf-8') as f:
            src = f.read()
        try:
            return json.loads(run_sync(_browser_runner(src, json.dumps(data))))
        except Exception as e:                                          # no JSPI, or Python was not entered through callPromising
            return Lambda__Runtime.failure('Runtime.TwinUnavailable',
                                           f'the browser could not run the Node.js handler here ({type(e).__name__}: {str(e)[:200]}); '
                                           'the twin needs JSPI and Python entered through callPromising or runPythonAsync')

    # ── Python ──────────────────────────────────────────────────────────
    def run_python(self, zip_bytes, module, fn, event, env, context, conf):
        folder   = tempfile.mkdtemp(prefix='aws-twin-lambda-')
        logs     = []
        saved    = dict(os.environ)
        started  = time.time()
        deadline = started + int(conf['Timeout'])

        class Context:
            function_name        = context['functionName']
            function_version     = '$LATEST'
            invoked_function_arn = context['invokedFunctionArn']
            memory_limit_in_mb   = int(context['memoryLimitInMB'])
            aws_request_id       = context['awsRequestId']
            log_group_name       = context['logGroupName']
            log_stream_name      = context['logStreamName']

            @staticmethod
            def get_remaining_time_in_millis():
                return max(0, int((deadline - time.time()) * 1000))

        stdout = io.StringIO()
        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
                z.extractall(folder)
            path = os.path.join(folder, *module.split('/')) + '.py'
            if not os.path.exists(path):
                return self.failure('Runtime.ImportModuleError', f"Unable to import module '{module}': No module named '{module}'")
            os.environ.update({k: str(v) for k, v in env.items()})
            sys.path.insert(0, folder)
            spec = importlib.util.spec_from_file_location(f'aws_twin_lambda_{uuid.uuid4().hex}', path)
            mod  = importlib.util.module_from_spec(spec)
            with contextlib.redirect_stdout(stdout):
                spec.loader.exec_module(mod)
                handler = getattr(mod, fn, None)
                if handler is None:
                    return self.failure('Runtime.HandlerNotFound', f"Handler '{fn}' missing on module '{module}'")
                result = handler(event, Context())
            json.dumps(result)
            return {'result': result, 'error': None, 'logs': stdout.getvalue().splitlines(), 'requests': []}
        except Exception as e:
            return {'result': None, 'error': {'errorType': type(e).__name__, 'errorMessage': str(e), 'trace': traceback.format_exc().splitlines()[-10:]},
                    'logs': stdout.getvalue().splitlines(), 'requests': []}
        finally:
            if folder in sys.path:
                sys.path.remove(folder)
            os.environ.clear()
            os.environ.update(saved)
            shutil.rmtree(folder, ignore_errors=True)
