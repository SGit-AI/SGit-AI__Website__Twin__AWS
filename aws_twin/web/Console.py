"""The console's Python side: every page under /console/ calls one method here, through call(name,
args_json). It is the S3 browser's bridge (S3__Browser, so S3 works as it did) with more services:
Lambda, every resource type through the Cloud Control API, the twin's own data, and the request log
behind the console's request pane.

Two modes, the same methods. Twin: the Python twin in the page answers, its store kept in this
browser's IndexedDB, shared by every console page. Live: the same calls go to the account with the
session pasted on /sessions/, signed in the page and sent from the browser: Lambda, IAM, EventBridge,
CloudFront, CloudWatch Logs, STS and Cloud Control all answer a browser; S3 does for a bucket with a
CORS rule, and lists buckets here through Cloud Control, which answers any origin and returns every
bucket in the account (measured on 23 October 2026). Live is read-only unless writes are allowed."""
import base64
import io
import json
import zipfile

from aws_twin.web.S3__Browser import S3__Browser, WRITES

REGIONS = ['us-east-1', 'us-east-2', 'us-west-1', 'us-west-2', 'ca-central-1', 'sa-east-1', 'eu-west-1', 'eu-west-2', 'eu-west-3',
           'eu-central-1', 'eu-north-1', 'ap-south-1', 'ap-northeast-1', 'ap-northeast-2', 'ap-northeast-3', 'ap-southeast-1', 'ap-southeast-2']
RESOURCE_TYPES = [                                                     # (type, global?): a starting list; any Cloud Control type can be typed in
    ('AWS::S3::Bucket', True), ('AWS::Lambda::Function', False), ('AWS::IAM::Role', True), ('AWS::Events::Rule', False),
    ('AWS::CloudFront::Distribution', True), ('AWS::Logs::LogGroup', False), ('AWS::DynamoDB::Table', False), ('AWS::SQS::Queue', False),
    ('AWS::SNS::Topic', False), ('AWS::EC2::Instance', False), ('AWS::EC2::VPC', False), ('AWS::ECR::Repository', False),
    ('AWS::CloudFormation::Stack', False), ('AWS::KMS::Key', False), ('AWS::Route53::HostedZone', True), ('AWS::ECS::Cluster', False)]
SECRET_HEADERS = ('x-amz-security-token',)
TEXT_FILES = ('.js', '.mjs', '.cjs', '.py', '.json', '.txt', '.md', '.html', '.css', '.yml', '.yaml', '.toml', '.cfg', '.sh')


def masked(headers):
    return {k: (v[:6] + '…' + v[-4:] + f' ({len(v)} chars, masked)' if k in SECRET_HEADERS and len(v) > 12 else v) for k, v in headers.items()}


def body_preview(b64, limit=8192):
    if not b64:
        return None
    data = base64.b64decode(b64)
    try:
        text = data[:limit].decode('utf-8')
        return {'text': text, 'bytes': len(data), 'truncated': len(data) > limit}
    except UnicodeDecodeError:
        return {'text': None, 'bytes': len(data), 'truncated': False, 'binary': True}


class Console(S3__Browser):
    WRITES      = WRITES | {'lambda_invoke', 'lambda_seed', 'twin_reset'}    # op_send guards itself, by operation
    LIVE_ROUTES = ('s3', 'sts', 'lambda', 'iam', 'events', 'cloudfront', 'cloudcontrolapi', 'logs')

    def _swap(self, twin):
        twin.traffic.keep_bodies, twin.traffic.limit = True, 400       # the request pane shows bodies; the last 400 requests
        super()._swap(twin)

    def boto(self, service, region=None):
        import boto3
        return boto3.client(service, region_name=region or self.region)

    # ── the console itself ──────────────────────────────────────────────
    def op_status(self):
        out = {'mode': 'live' if self.live else 'twin', 'region': self.region, 'relay': self.relay, 'allow_writes': self.allow_writes,
               'regions': REGIONS, 'resource_types': [t for t, _ in RESOURCE_TYPES]}
        return out, 'Console.status'

    def op_set_region(self, region):
        if region not in REGIONS:
            raise ValueError(f'{region} is not one of the console\'s regions')
        self.region = region
        return {'region': region}, f'Console.region = {region!r}'

    def op_overview(self):
        """A count per service, for the overview page; a service the role cannot read says so."""
        out = {}
        for key, fn in (('buckets', lambda: len(self.op_buckets()[0])), ('functions', lambda: len(self.lambda_rows(self.region))),
                        ('rules', lambda: len(self.boto('events').list_rules().get('Rules', []))),
                        ('roles', lambda: len(self.boto('cloudcontrol').list_resources(TypeName='AWS::IAM::Role').get('ResourceDescriptions', [])))):
            try:
                out[key] = fn()
            except Exception as e:
                out[key] = {'error': getattr(e, 'response', {}).get('Error', {}).get('Code') or type(e).__name__}
        return out, f'counts in {self.region}: S3 buckets, Lambda functions, EventBridge rules, IAM roles'

    # ── S3: buckets through Cloud Control when live ─────────────────────
    def op_buckets(self):
        if not self.live or self.relay:
            return super().op_buckets()
        cc, names, token = self.boto('cloudcontrol'), [], None
        while True:
            page = cc.list_resources(TypeName='AWS::S3::Bucket', **({'NextToken': token} if token else {}))
            names += [r['Identifier'] for r in page.get('ResourceDescriptions', [])]
            token = page.get('NextToken')
            if not token:
                break
        return ([{'name': n, 'region': '', 'created': ''} for n in names],
                "boto3.client('cloudcontrol').list_resources(TypeName='AWS::S3::Bucket')   # S3's own ListBuckets never answers a browser")

    # ── Lambda ──────────────────────────────────────────────────────────
    def lambda_rows(self, region):
        rows = []
        for page in self.boto('lambda', region).get_paginator('list_functions').paginate():
            for f in page['Functions']:
                rows.append({'name': f['FunctionName'], 'runtime': f.get('Runtime') or f.get('PackageType'), 'handler': f.get('Handler'),
                             'memory': f.get('MemorySize'), 'timeout': f.get('Timeout'), 'code_size': f.get('CodeSize'),
                             'modified': f.get('LastModified'), 'description': f.get('Description', ''), 'arch': (f.get('Architectures') or ['x86_64'])[0]})
        return sorted(rows, key=lambda r: r['name'])

    def op_lambda_list(self, region=None):
        region = region or self.region
        return {'region': region, 'functions': self.lambda_rows(region)}, f"boto3.client('lambda', region_name={region!r}).get_paginator('list_functions').paginate()"

    def op_lambda_count(self, region):
        try:
            return {'region': region, 'count': len(self.lambda_rows(region))}, f"lambda.list_functions() in {region}"
        except Exception as e:
            return {'region': region, 'error': getattr(e, 'response', {}).get('Error', {}).get('Code') or type(e).__name__}, f"lambda.list_functions() in {region}"

    def op_lambda_get(self, region, name):
        lam = self.boto('lambda', region)
        got = lam.get_function(FunctionName=name)
        out = {'region': region, 'configuration': got['Configuration'], 'code': got.get('Code', {}), 'tags': got.get('Tags', {}),
               'concurrency': got.get('Concurrency', {}), 'url': None, 'policy': None, 'rules': []}
        for key, call in (('url', lambda: lam.get_function_url_config(FunctionName=name)),
                          ('policy', lambda: json.loads(lam.get_policy(FunctionName=name)['Policy']))):
            try:
                out[key] = call()
                if key == 'url':
                    out[key].pop('ResponseMetadata', None)
            except Exception as e:
                code = getattr(e, 'response', {}).get('Error', {}).get('Code')
                out[key] = None if code == 'ResourceNotFoundException' else {'error': code or type(e).__name__}
        try:                                                          # what triggers it on a schedule: rules whose target it is
            events = self.boto('events', region)
            arn = got['Configuration']['FunctionArn']
            for rule in events.list_rules().get('Rules', []):
                if any(t['Arn'] == arn for t in events.list_targets_by_rule(Rule=rule['Name']).get('Targets', [])):
                    out['rules'].append({k: rule.get(k) for k in ('Name', 'Arn', 'ScheduleExpression', 'State')})
        except Exception as e:
            out['rules'] = {'error': getattr(e, 'response', {}).get('Error', {}).get('Code') or type(e).__name__}
        return out, f"lambda.get_function(FunctionName={name!r}); get_function_url_config; get_policy; events.list_rules + list_targets_by_rule"

    def op_lambda_code(self, region, name):
        """The package's files. The twin holds them; AWS keeps them in its own bucket, which does not
        answer a browser, so live gives the time-limited download link instead."""
        if self.live:
            loc = self.boto('lambda', region).get_function(FunctionName=name).get('Code', {})
            return {'files': None, 'location': loc.get('Location'), 'repository': loc.get('RepositoryType'),
                    'why': "AWS keeps the package in its own S3 bucket, which has no CORS rule: a page cannot read it, but a link can download it (valid for 10 minutes)"}, \
                   f"lambda.get_function(FunctionName={name!r})['Code']['Location']"
        data, files = self.twin.services['lambda'].code(region, name), []
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for i in z.infolist():
                text = None
                if i.filename.endswith(TEXT_FILES) and i.file_size <= 256 * 1024:
                    text = z.read(i.filename).decode('utf-8', 'replace')
                files.append({'name': i.filename, 'size': i.file_size, 'text': text})
        return {'files': files, 'zip_b64': base64.b64encode(data).decode(), 'location': None}, f"the twin's store: /lambda/{region}/functions/{name}/code.zip"

    def op_lambda_invoke(self, region, name, payload='{}'):
        json.loads(payload or '{}')
        r = self.boto('lambda', region).invoke(FunctionName=name, Payload=(payload or '{}').encode(), LogType='Tail')
        body = r['Payload'].read().decode('utf-8', 'replace')
        return {'status': r['StatusCode'], 'function_error': r.get('FunctionError'), 'payload': body,
                'log': base64.b64decode(r.get('LogResult', '')).decode('utf-8', 'replace'), 'version': r.get('ExecutedVersion')}, \
               f"lambda.invoke(FunctionName={name!r}, Payload=<{len(payload or '')} bytes>, LogType='Tail')"

    def op_lambda_logs(self, region, name):
        """Recent log lines: CloudWatch Logs when live; the twin keeps each invocation's log itself."""
        if not self.live:
            inv = self.twin.services['lambda'].invocations(region, name)
            return {'source': 'twin', 'invocations': list(reversed(inv))}, f"the twin's record: /lambda/{region}/functions/{name}/invocations.json"
        logs, group = self.boto('logs', region), f'/aws/lambda/{name}'
        streams = logs.describe_log_streams(logGroupName=group, orderBy='LastEventTime', descending=True, limit=3).get('logStreams', [])
        out = []
        for s in streams:
            ev = logs.get_log_events(logGroupName=group, logStreamName=s['logStreamName'], limit=60, startFromHead=False).get('events', [])
            out.append({'stream': s['logStreamName'], 'last': s.get('lastEventTimestamp'), 'events': [{'t': e['timestamp'], 'm': e['message']} for e in ev]})
        return {'source': 'cloudwatch', 'group': group, 'streams': out}, f"logs.describe_log_streams(logGroupName={group!r}, …); logs.get_log_events(…)"

    def op_lambda_seed(self, region=None):
        """Two example functions in the twin, so the browser has something to show: Python and Node.js,
        an environment, a function URL, a schedule with its permission, and the twin's internet answering."""
        if self.live:
            raise PermissionError('the examples are for the twin')
        region = region or self.region
        import boto3
        iam, lam, ev = boto3.client('iam'), self.boto('lambda', region), self.boto('events', region)
        trust = json.dumps({'Version': '2012-10-17', 'Statement': [{'Effect': 'Allow', 'Principal': {'Service': 'lambda.amazonaws.com'}, 'Action': 'sts:AssumeRole'}]})
        try:
            role = iam.create_role(RoleName='example-lambda-role', AssumeRolePolicyDocument=trust)['Role']['Arn']
            iam.attach_role_policy(RoleName='example-lambda-role', PolicyArn='arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole')
        except Exception:
            role = iam.get_role(RoleName='example-lambda-role')['Role']['Arn']
        zipped = lambda name, code: self._zip({name: code})
        made = []
        for fn, runtime, handler, code, env in (
                ('example-hello-python', 'python3.13', 'app.handler', {'app.py': 'import os, json\n\ndef handler(event, context):\n    """Says hello, from the twin or from Lambda."""\n    print("event", json.dumps(event))\n    return {"hello": event.get("name", "world"), "greeting": os.environ.get("GREETING"), "region": os.environ["AWS_REGION"]}\n'},
                 {'GREETING': 'hello from the twin'}),
                ('example-site-check', 'nodejs22.x', 'index.handler', {'index.mjs': '// checks one website, as the uptime function does for many\nexport const handler = async (event) => {\n  const url = event.url || process.env.TARGET;\n  const t = Date.now();\n  try {\n    const r = await fetch(url, { signal: AbortSignal.timeout(5000) });\n    console.log(url, r.status);\n    return { url, status: r.status, ms: Date.now() - t };\n  } catch (e) {\n    return { url, error: String(e.cause?.code || e.message) };\n  }\n};\n'},
                 {'TARGET': 'https://sgit.ai/'})):
            try:
                lam.get_function(FunctionName=fn)
            except Exception:
                lam.create_function(FunctionName=fn, Runtime=runtime, Role=role, Handler=handler, Code={'ZipFile': self._zip(code)},
                                    Environment={'Variables': env}, Description=f'An example in the twin ({runtime})', Timeout=10)
                made.append(fn)
        self.twin.internet.answer('https://sgit.ai/', status=200, ms=60)
        try:
            lam.create_function_url_config(FunctionName='example-site-check', AuthType='AWS_IAM')
            arn = ev.put_rule(Name='example-site-check-every-15-minutes', ScheduleExpression='rate(15 minutes)')['RuleArn']
            lam.add_permission(FunctionName='example-site-check', StatementId='events', Action='lambda:InvokeFunction', Principal='events.amazonaws.com', SourceArn=arn)
            ev.put_targets(Rule='example-site-check-every-15-minutes', Targets=[{'Id': 'check', 'Arn': lam.get_function(FunctionName='example-site-check')['Configuration']['FunctionArn']}])
        except Exception:
            pass                                                     # already there
        return {'region': region, 'created': made}, f"iam.create_role(…); lambda.create_function(…) ×2; create_function_url_config; events.put_rule; lambda.add_permission; events.put_targets  (in {region})"

    @staticmethod
    def _zip(files):
        out = io.BytesIO()
        with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
            for name, text in files.items():
                z.writestr(zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0)), text)
        return out.getvalue()

    # ── every resource, through Cloud Control ───────────────────────────
    def cc_region(self, type_name):
        return 'us-east-1' if type_name in ('AWS::CloudFront::Distribution', 'AWS::Route53::HostedZone') else self.region

    def op_resources(self, type_name):
        cc, out, token = self.boto('cloudcontrol', self.cc_region(type_name)), [], None
        while len(out) < 500:
            page = cc.list_resources(TypeName=type_name, **({'NextToken': token} if token else {}))
            out += [{'identifier': r['Identifier'], 'properties': json.loads(r.get('Properties') or '{}')} for r in page.get('ResourceDescriptions', [])]
            token = page.get('NextToken')
            if not token:
                break
        return {'type': type_name, 'region': self.cc_region(type_name), 'resources': out}, f"boto3.client('cloudcontrol').list_resources(TypeName={type_name!r})"

    def op_resource(self, type_name, identifier):
        r = self.boto('cloudcontrol', self.cc_region(type_name)).get_resource(TypeName=type_name, Identifier=identifier)['ResourceDescription']
        return {'type': type_name, 'identifier': r['Identifier'], 'properties': json.loads(r.get('Properties') or '{}')}, \
               f"cloudcontrol.get_resource(TypeName={type_name!r}, Identifier={identifier!r})"

    # ── the twin's own data ─────────────────────────────────────────────
    def op_twin_tree(self):
        files = [{'path': e['path'], 'size': e['size']} for e in self.twin.vfs.walk_files('/')]
        groups = {}
        for f in files:
            top = f['path'].strip('/').split('/')[0]
            g = groups.setdefault(top, {'files': 0, 'bytes': 0})
            g['files'] += 1; g['bytes'] += f['size']
        return {'files': files, 'groups': groups}, 'twin.vfs.walk_files("/")'

    def op_twin_file(self, path):
        data = self.twin.vfs.read_file(path)
        out = {'path': path, 'size': len(data)}
        if path.endswith('.zip'):
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                out['zip'] = [{'name': i.filename, 'size': i.file_size} for i in z.infolist()]
        else:
            try:
                text = data.decode('utf-8')
                try:
                    out['json'] = json.loads(text)
                except ValueError:
                    out['text'] = text[:65536]
            except UnicodeDecodeError:
                out['b64'] = base64.b64encode(data[:65536]).decode()
        return out, f'twin.vfs.read_file({path!r})'

    def op_twin_reset(self, prefix):
        """Delete everything under one of the twin's top folders (/s3, /lambda, …), in this browser."""
        if self.live:
            raise PermissionError('reset is for the twin')
        prefix = '/' + prefix.strip('/')
        if prefix == '/':
            raise ValueError('name a top folder: /s3, /lambda, /iam, /events, /cloudfront, /sgit, /internet')
        doomed = [e['path'] for e in self.twin.vfs.walk_files(prefix)] if self.twin.vfs.exists(prefix) else []
        for p in doomed:
            self.twin.vfs.delete_file(p)
        return {'deleted': len(doomed), 'prefix': prefix}, f'twin.vfs: delete every file under {prefix}'

    # ── the request pane ────────────────────────────────────────────────
    def op_requests(self, after=0):
        rows = [{k: r[k] for k in ('seq', 'at', 'ms', 'target', 'service', 'operation', 'method', 'url', 'status', 'signed')}
                for r in self.twin.traffic.records if r['seq'] > after]
        return rows, 'twin.traffic.records'

    def op_request(self, seq):
        r = next((r for r in self.twin.traffic.records if r['seq'] == seq), None)
        if r is None:
            raise KeyError(f'request {seq} is no longer kept (the pane keeps the last 400)')
        out = {k: r[k] for k in ('seq', 'at', 'ms', 'target', 'service', 'operation', 'method', 'url', 'status', 'signed')}
        out['api']      = r.get('api')                                   # the boto3 call, for the call editor's replay
        out['request']  = {'headers': masked(r['request']['headers']), 'body': body_preview(r['request'].get('body_b64'))}
        out['response'] = {'headers': r['response']['headers'], 'body': body_preview(r['response'].get('body_b64'))}
        return out, f'twin.traffic.records[seq={seq}]'


    # ── the calls page: what works where, and any operation by hand ─────
    def op_matrix(self):
        from aws_twin.web.Call__Matrix import rows
        return rows(), 'aws_twin.web.Call__Matrix.rows()'

    def op_probe(self, id):
        """Send one matrix call from this browser (Pyodide, boto3) with invented keys, straight to AWS:
        reached, or blocked by the browser. The twin's route for the service is live for this one call."""
        import time
        import boto3
        from aws_twin.core.Twin__Browser_Http import Twin__Browser_Blocked
        from aws_twin.web.Call__Matrix        import PROBE_KEYS, classify, rows
        row = next(r for r in rows() if r['id'] == id)
        saved_routes, saved_relay = dict(self.twin.routes), self.twin.live_relay
        client = boto3.client(row['service'], region_name=row['region'], **PROBE_KEYS)
        self.twin.routes[client.meta.service_model.signing_name] = 'live'   # routes go by signing name: cloudwatch signs as monitoring
        self.twin.live_relay = None
        started = time.time()
        try:
            params = dict(row['params'])
            if 'Payload' in params:
                params['Payload'] = params['Payload'].encode()
            getattr(client, xform(row['operation']))(**params)
            out = classify()
        except Twin__Browser_Blocked:
            out = classify(blocked=True)
        except Exception as e:
            out = classify(e)
        finally:
            self.twin.routes, self.twin.live_relay = saved_routes, saved_relay
        out['ms'] = round((time.time() - started) * 1000)
        return dict(out, id=id), f"boto3.client({row['service']!r}, <invented keys>).{xform(row['operation'])}(**{row['params']!r})"

    def op_services(self):
        import boto3
        return boto3.session.Session().get_available_services(), 'boto3.session.Session().get_available_services()'

    def op_operations(self, service):
        import boto3
        model = boto3.client(service, region_name=self.region, **_dummy_keys()).meta.service_model
        return {'service': service, 'operations': list(model.operation_names), 'protocol': model.protocol,
                'signing_name': model.signing_name, 'api_version': model.api_version}, f'{service}: the botocore service model'

    def op_skeleton(self, service, operation):
        import boto3
        model = boto3.client(service, region_name=self.region, **_dummy_keys()).meta.service_model.operation_model(operation)
        shape = model.input_shape
        return {'params': skeleton(shape) if shape is not None else {}, 'required': list(getattr(shape, 'required_members', []) or []),
                'members': list(shape.members) if shape is not None else [], 'doc': doc_line(model.documentation),
                'write': not is_read(operation)}, f'{service}.{operation}: its input shape'

    def op_send(self, service, operation, params, region=None):
        """Any operation, by hand: the console's mode decides where it goes (the twin, or the account)."""
        import boto3
        if self.live and not is_read(operation) and not self.allow_writes:
            e = PermissionError(f'{operation} may change the account, and live mode is read-only: allow writes first')
            e.code = 'ReadOnly'
            raise e
        client = boto3.client(service, region_name=region or self.region)
        result = getattr(client, xform(operation))(**params)
        meta   = result.pop('ResponseMetadata', {})
        for k, v in list(result.items()):
            if hasattr(v, 'read'):
                data = v.read(262144)
                try:
                    result[k] = data.decode('utf-8')
                except UnicodeDecodeError:
                    result[k] = {'base64': base64.b64encode(data).decode(), 'bytes': len(data)}
        from aws_twin.core.Twin import api_params_json
        return {'result': api_params_json(result), 'status': meta.get('HTTPStatusCode'), 'request_id': meta.get('RequestId')}, \
               f"boto3.client({service!r}, region_name={region or self.region!r}).{xform(operation)}(**{json.dumps(params)[:300]})"

    def op_request_twin(self, seq):
        """A live read, sent again to the twin: what the twin would have answered, beside what AWS did."""
        from aws_twin.core.Twin__Http import Twin__Request
        r = next((r for r in self.twin.traffic.records if r['seq'] == seq), None)
        if r is None:
            raise KeyError(f'request {seq} is no longer kept')
        if not is_read(r['operation']):
            raise PermissionError('only reads are sent to the twin to compare: a write would change the twin')
        body = base64.b64decode(r['request'].get('body_b64') or '')
        resp = self.twin.handle(Twin__Request(r['method'], r['url'], r['request']['headers'], body), route='twin')
        try:
            text = resp.body[:8192].decode('utf-8')
        except UnicodeDecodeError:
            text = f'<{len(resp.body)} bytes, binary>'
        return {'status': resp.status, 'live_status': r['status'], 'same_status': resp.status == r['status'], 'body': text}, \
               f'twin.handle(<request {seq}, as sent to AWS>, route="twin")'


READ_PREFIXES = ('List', 'Get', 'Describe', 'Head', 'Search', 'Lookup', 'Query', 'Scan', 'BatchGet', 'Select', 'Check', 'Test', 'Simulate', 'Estimate', 'Preview')


def is_read(operation):
    return operation.startswith(READ_PREFIXES)


def xform(operation):
    from botocore import xform_name
    return xform_name(operation)


def _dummy_keys():
    return {'aws_access_key_id': 'MODEL-ONLY-KEY', 'aws_secret_access_key': 'x'}


def doc_line(html_doc):
    import re
    text = re.sub(r'<[^>]+>', '', html_doc or '').strip()
    return re.split(r'(?<=\.)\s', text, maxsplit=1)[0][:300] if text else ''


def skeleton(shape, depth=0):
    """The required members of an input shape, with a placeholder of the right type."""
    if depth > 4:
        return None
    t = shape.type_name
    if t == 'structure':
        return {m: skeleton(shape.members[m], depth + 1) for m in (getattr(shape, 'required_members', []) or [])}
    if t == 'list':
        return []
    if t == 'map':
        return {}
    if t in ('integer', 'long'):
        return 0
    if t in ('double', 'float'):
        return 0.0
    if t == 'boolean':
        return False
    if t == 'timestamp':
        return '2026-10-01T00:00:00Z'
    if t == 'blob':
        return ''
    enum = getattr(shape, 'enum', None)
    return enum[0] if enum else f'<{shape.name}>'


console = None


def console_call(name, args_json='{}'):
    """The function every console page calls (with callPromising, so Node.js Lambda functions can run in the twin)."""
    return console.call(name, args_json)
