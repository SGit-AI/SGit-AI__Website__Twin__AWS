"""The Lambda twin: functions per region, kept as deployed, and run when invoked.

    /lambda/<region>/functions/<name>/config.json        the FunctionConfiguration
    /lambda/<region>/functions/<name>/code.zip           the deployment package, as uploaded
    /lambda/<region>/functions/<name>/policy.json        the resource policy (AddPermission)
    /lambda/<region>/functions/<name>/url.json           the function URL configuration
    /lambda/<region>/functions/<name>/invocations.json   the last 25 invocations: event, result, logs

Covered (rest-json): CreateFunction (ZipFile, or S3Bucket/S3Key from the S3 twin), GetFunction,
GetFunctionConfiguration, ListFunctions, UpdateFunctionCode, UpdateFunctionConfiguration,
DeleteFunction, Invoke (RequestResponse, Event, DryRun; LogType Tail), AddPermission, GetPolicy,
RemovePermission, CreateFunctionUrlConfig, GetFunctionUrlConfig, DeleteFunctionUrlConfig.

Invoke runs the deployed code (Lambda__Runtime): nodejs* through node_harness.mjs, with node in
CPython and through the browser's JSPI in Pyodide; python* in process. The function's outbound
HTTP goes to the twin's internet and the sgit append lane twin, never out.
Faithful where it catches mistakes: an execution role must exist in the IAM twin and trust
lambda.amazonaws.com; names conflict; a missing handler fails at invoke, not at create.
Not faithful: no cold-start delay, no concurrency, no versions or aliases, no layers; the function
is Active and its updates Successful at once."""
import base64
import fnmatch
import hashlib
import io
import json
import re
import uuid
import zipfile

from aws_twin.core.Twin__Http    import Twin__Response
from aws_twin.core.Twin__Service import Twin__Error, Twin__Store, iso_now, json_error, json_response, random_id, region_of

FUNCTION_NAME = re.compile(r'^[a-zA-Z0-9-_]{1,64}$')
RUNTIMES      = re.compile(r'^(nodejs\d+\.x|python3\.\d+|java\d+|dotnet\d+|ruby\d\.\d+|provided(\.al2023|\.al2)?)$')
ROLE_ARN      = re.compile(r'^arn:aws:iam::\d{12}:role/.+$')


def code_sha256(zip_bytes):
    return base64.b64encode(hashlib.sha256(zip_bytes).digest()).decode()


class Lambda__Twin:
    service = 'lambda'

    def __init__(self, twin):
        self.twin  = twin
        self.store = Twin__Store(twin.vfs, 'lambda')
        from aws_twin.awslambda.Lambda__Runtime import Lambda__Runtime
        self.runtime = Lambda__Runtime(twin)

    # ── dispatch ────────────────────────────────────────────────────────
    ROUTES = [('GET',    r'^/2015-03-31/functions/?$',                       'ListFunctions'),
              ('POST',   r'^/2015-03-31/functions/?$',                       'CreateFunction'),
              ('GET',    r'^/2015-03-31/functions/([^/]+)/?$',               'GetFunction'),
              ('DELETE', r'^/2015-03-31/functions/([^/]+)/?$',               'DeleteFunction'),
              ('GET',    r'^/2015-03-31/functions/([^/]+)/configuration$',   'GetFunctionConfiguration'),
              ('PUT',    r'^/2015-03-31/functions/([^/]+)/configuration$',   'UpdateFunctionConfiguration'),
              ('PUT',    r'^/2015-03-31/functions/([^/]+)/code$',            'UpdateFunctionCode'),
              ('POST',   r'^/2015-03-31/functions/([^/]+)/invocations$',     'Invoke'),
              ('POST',   r'^/2015-03-31/functions/([^/]+)/policy$',          'AddPermission'),
              ('GET',    r'^/2015-03-31/functions/([^/]+)/policy$',          'GetPolicy'),
              ('DELETE', r'^/2015-03-31/functions/([^/]+)/policy/([^/]+)$',  'RemovePermission'),
              ('POST',   r'^/2021-10-31/functions/([^/]+)/url$',             'CreateFunctionUrlConfig'),
              ('GET',    r'^/2021-10-31/functions/([^/]+)/url$',             'GetFunctionUrlConfig'),
              ('DELETE', r'^/2021-10-31/functions/([^/]+)/url$',             'DeleteFunctionUrlConfig')]

    def handle(self, request):
        region = region_of(request, self.twin.region)
        for method, pattern, action in self.ROUTES:
            hit = re.match(pattern, request.path)
            if hit and method == request.method:
                try:
                    params = json.loads(request.body) if request.body and action not in ('Invoke',) else {}
                    return action, getattr(self, 'op_' + action)(request, region, params, *hit.groups())
                except Twin__Error as e:
                    return action, json_error(e, request)
                except ValueError:
                    return action, json_error(Twin__Error(400, 'InvalidRequestContentException', 'Could not parse request body into json.'), request)
        return 'Unknown', json_error(Twin__Error(501, 'NotImplemented', f'the twin does not implement lambda {request.method} {request.path}'), request)

    # ── the store ───────────────────────────────────────────────────────
    @staticmethod
    def name_of(ref):
        """A function name, ARN or partial ARN, without a qualifier."""
        m = re.match(r'^(?:arn:aws:lambda:[a-z0-9-]+:\d{12}:function:)?([^:]+)', ref)
        return m.group(1) if m else ref

    def config(self, region, ref):
        name = self.name_of(ref)
        conf = self.store.read_json(region, 'functions', name, 'config.json')
        if conf is None:
            raise Twin__Error(404, 'ResourceNotFoundException',
                              f'Function not found: arn:aws:lambda:{region}:{self.twin.account_id}:function:{name}')
        return conf

    def save(self, region, conf):
        self.store.write_json(conf, region, 'functions', conf['FunctionName'], 'config.json')

    def code(self, region, name):
        return self.store.read_bytes(region, 'functions', name, 'code.zip')

    def functions(self, region):
        return [self.store.read_json(region, 'functions', n, 'config.json') for n in self.store.folders(region, 'functions')
                if self.store.exists(region, 'functions', n, 'config.json')]

    def regions(self):
        return self.store.folders()

    # ── validation that mirrors AWS's ───────────────────────────────────
    def check_role(self, role_arn):
        if not ROLE_ARN.match(role_arn or ''):
            raise Twin__Error(400, 'ValidationException', f"1 validation error detected: Value '{role_arn}' at 'role' failed to satisfy constraint")
        role = self.twin.services['iam'].role_by_arn(role_arn)
        trusted = role is not None and 'lambda.amazonaws.com' in role.get('AssumeRolePolicyDocument', '')
        if not trusted:
            raise Twin__Error(400, 'InvalidParameterValueException', 'The role defined for the function cannot be assumed by Lambda.')

    def zip_of(self, code):
        if code.get('ZipFile'):
            data = base64.b64decode(code['ZipFile'])
        elif code.get('S3Bucket') and code.get('S3Key'):
            from aws_twin.s3.S3__Twin import key_file
            path = f'/s3/{code["S3Bucket"]}/data/{key_file(code["S3Key"])}'
            if not self.twin.vfs.exists(path):
                raise Twin__Error(400, 'InvalidParameterValueException', f'Error occurred while GetObject. S3 Error Code: NoSuchKey. S3 Error Message: The specified key does not exist.')
            data = self.twin.vfs.read_file(path)
        else:
            raise Twin__Error(400, 'InvalidParameterValueException', 'Please provide a source for function code.')
        try:
            zipfile.ZipFile(io.BytesIO(data)).namelist()
        except zipfile.BadZipFile:
            raise Twin__Error(400, 'InvalidParameterValueException', 'Could not unzip uploaded file. Please check your file, then try to upload again.')
        return data

    # ── functions ───────────────────────────────────────────────────────
    def op_CreateFunction(self, request, region, p):
        name = p.get('FunctionName', '')
        if not FUNCTION_NAME.match(name):
            raise Twin__Error(400, 'ValidationException', f"1 validation error detected: Value '{name}' at 'functionName' failed to satisfy constraint")
        if self.store.exists(region, 'functions', name, 'config.json'):
            raise Twin__Error(409, 'ResourceConflictException', f'Function already exist: {name}')
        if not RUNTIMES.match(p.get('Runtime', '')):
            raise Twin__Error(400, 'InvalidParameterValueException', f"The runtime parameter of {p.get('Runtime')} is not supported.")
        if not p.get('Handler'):
            raise Twin__Error(400, 'InvalidParameterValueException', 'The Handler parameter is required for a Zip package.')
        self.check_role(p.get('Role'))
        data = self.zip_of(p.get('Code') or {})
        conf = {'FunctionName': name, 'FunctionArn': f'arn:aws:lambda:{region}:{self.twin.account_id}:function:{name}',
                'Runtime': p['Runtime'], 'Role': p['Role'], 'Handler': p['Handler'], 'CodeSize': len(data),
                'Description': p.get('Description', ''), 'Timeout': int(p.get('Timeout', 3)), 'MemorySize': int(p.get('MemorySize', 128)),
                'LastModified': iso_now(offset='+0000'), 'CodeSha256': code_sha256(data), 'Version': '$LATEST',
                'Environment': {'Variables': (p.get('Environment') or {}).get('Variables', {})}, 'TracingConfig': {'Mode': 'PassThrough'},
                'RevisionId': str(uuid.uuid4()), 'State': 'Active', 'LastUpdateStatus': 'Successful', 'PackageType': 'Zip',
                'Architectures': p.get('Architectures') or ['x86_64'], 'EphemeralStorage': {'Size': 512},
                'LoggingConfig': {'LogFormat': 'Text', 'LogGroup': f'/aws/lambda/{name}'}}
        self.store.write_bytes(data, region, 'functions', name, 'code.zip')
        self.save(region, conf)
        if p.get('Tags'):
            self.store.write_json(p['Tags'], region, 'functions', name, 'tags.json')
        return json_response(201, conf)

    def op_GetFunction(self, request, region, p, ref):
        conf = self.config(region, ref)
        out  = {'Configuration': conf, 'Code': {'RepositoryType': 'S3',
                'Location': f'https://aws.twin.local/lambda/{region}/{conf["FunctionName"]}/code.zip'}}
        tags = self.store.read_json(region, 'functions', conf['FunctionName'], 'tags.json')
        if tags:
            out['Tags'] = tags
        return json_response(200, out)

    def op_GetFunctionConfiguration(self, request, region, p, ref):
        return json_response(200, self.config(region, ref))

    def op_ListFunctions(self, request, region, p):
        return json_response(200, {'Functions': sorted(self.functions(region), key=lambda c: c['FunctionName'])})

    def op_DeleteFunction(self, request, region, p, ref):
        name = self.config(region, ref)['FunctionName']
        for f in self.store.files(region, 'functions', name):
            self.store.delete(region, 'functions', name, f)
        return Twin__Response(204, {}, b'')

    def op_UpdateFunctionCode(self, request, region, p, ref):
        conf = self.config(region, ref)
        data = self.zip_of(p)
        self.store.write_bytes(data, region, 'functions', conf['FunctionName'], 'code.zip')
        conf.update(CodeSize=len(data), CodeSha256=code_sha256(data), LastModified=iso_now(offset='+0000'), RevisionId=str(uuid.uuid4()))
        self.save(region, conf)
        return json_response(200, conf)

    def op_UpdateFunctionConfiguration(self, request, region, p, ref):
        conf = self.config(region, ref)
        if 'Role' in p:
            self.check_role(p['Role'])
        if 'Runtime' in p and not RUNTIMES.match(p['Runtime']):
            raise Twin__Error(400, 'InvalidParameterValueException', f"The runtime parameter of {p['Runtime']} is not supported.")
        for k in ('Role', 'Handler', 'Description', 'Runtime'):
            if k in p:
                conf[k] = p[k]
        for k in ('Timeout', 'MemorySize'):
            if k in p:
                conf[k] = int(p[k])
        if 'Environment' in p:
            conf['Environment'] = {'Variables': (p['Environment'] or {}).get('Variables', {})}
        if len(json.dumps(conf['Environment']['Variables'])) > 4096:
            raise Twin__Error(400, 'InvalidParameterValueException', 'Lambda was unable to configure your environment variables because the environment variables you have provided exceeded the 4KB limit.')
        conf.update(LastModified=iso_now(offset='+0000'), RevisionId=str(uuid.uuid4()))
        self.save(region, conf)
        return json_response(200, conf)

    # ── invoke ──────────────────────────────────────────────────────────
    def op_Invoke(self, request, region, p, ref):
        conf  = self.config(region, ref)
        kind  = request.header('x-amz-invocation-type', 'RequestResponse')
        if kind == 'DryRun':
            return Twin__Response(204, {}, b'')
        if request.body:
            try:
                json.loads(request.body)
            except ValueError:
                raise Twin__Error(400, 'InvalidRequestContentException', 'Could not parse request body into json: the payload is not valid JSON.')
        result  = self.invoke_internal(region, conf['FunctionName'], request.body or b'{}')
        if kind == 'Event':
            return Twin__Response(202, {}, b'')
        headers = {'content-type': 'application/json', 'x-amz-executed-version': '$LATEST'}
        if result['error'] is not None:
            headers['x-amz-function-error'] = 'Unhandled'
        if request.header('x-amz-log-type') == 'Tail':
            headers['x-amz-log-result'] = base64.b64encode(result['log_text'].encode()[-4096:]).decode()
        return Twin__Response(200, headers, result['payload'])

    def invoke_internal(self, region, name, event_bytes):
        """Run a function, record the invocation; returns payload, error, logs, the requests it made."""
        conf   = self.config(region, name)
        result = self.runtime.invoke(region, conf, self.code(region, name), event_bytes)
        log    = self.store.read_json(region, 'functions', name, 'invocations.json', default=[])
        log    = (log + [{'at': iso_now(), 'request_id': result['request_id'], 'event': event_bytes.decode('utf-8', 'replace')[:4000],
                          'error': result['error'], 'payload': result['payload'].decode('utf-8', 'replace')[:8000],
                          'logs': result['logs'][-50:], 'requests': [{k: r.get(k) for k in ('method', 'url', 'status', 'error')} for r in result['requests']],
                          'ms': result['ms']}])[-25:]
        self.store.write_json(log, region, 'functions', name, 'invocations.json')
        return result

    def invocations(self, region, name):
        return self.store.read_json(region, 'functions', self.name_of(name), 'invocations.json', default=[])

    # ── the resource policy ─────────────────────────────────────────────
    def policy(self, region, name):
        return self.store.read_json(region, 'functions', name, 'policy.json', default={'Version': '2012-10-17', 'Id': 'default', 'Statement': []})

    def op_AddPermission(self, request, region, p, ref):
        conf, pol = self.config(region, ref), None
        pol = self.policy(region, conf['FunctionName'])
        sid = p.get('StatementId', '')
        if not sid or not p.get('Action') or not p.get('Principal'):
            raise Twin__Error(400, 'ValidationException', 'StatementId, Action and Principal are required.')
        if any(s['Sid'] == sid for s in pol['Statement']):
            raise Twin__Error(409, 'ResourceConflictException',
                              f'The statement id ({sid}) provided already exists. Please provide a new statement id, or remove the existing statement.')
        principal = p['Principal']
        st = {'Sid': sid, 'Effect': 'Allow', 'Principal': '*' if principal == '*' else ({'Service': principal} if principal.endswith('.amazonaws.com') else {'AWS': principal}),
              'Action': p['Action'], 'Resource': conf['FunctionArn']}
        cond = {}
        if p.get('SourceArn'):
            cond['ArnLike'] = {'AWS:SourceArn': p['SourceArn']}
        if p.get('SourceAccount'):
            cond['StringEquals'] = {'AWS:SourceAccount': p['SourceAccount']}
        if p.get('FunctionUrlAuthType'):
            cond.setdefault('StringEquals', {})['lambda:FunctionUrlAuthType'] = p['FunctionUrlAuthType']
        if cond:
            st['Condition'] = cond
        pol['Statement'].append(st)
        self.store.write_json(pol, region, 'functions', conf['FunctionName'], 'policy.json')
        return json_response(201, {'Statement': json.dumps(st)})

    def op_GetPolicy(self, request, region, p, ref):
        conf = self.config(region, ref)
        pol  = self.policy(region, conf['FunctionName'])
        if not pol['Statement']:
            raise Twin__Error(404, 'ResourceNotFoundException', 'The resource you requested does not exist.')
        return json_response(200, {'Policy': json.dumps(pol), 'RevisionId': conf['RevisionId']})

    def op_RemovePermission(self, request, region, p, ref, sid):
        conf = self.config(region, ref)
        pol  = self.policy(region, conf['FunctionName'])
        keep = [s for s in pol['Statement'] if s['Sid'] != sid]
        if len(keep) == len(pol['Statement']):
            raise Twin__Error(404, 'ResourceNotFoundException', f'Statement {sid} is not found in resource policy.')
        pol['Statement'] = keep
        self.store.write_json(pol, region, 'functions', conf['FunctionName'], 'policy.json')
        return Twin__Response(204, {}, b'')

    def allows(self, region, name, service, source_arn):
        """Would the function's resource policy let this AWS service invoke it, for this source?"""
        if not self.store.exists(region, 'functions', name, 'config.json'):
            return False
        for s in self.policy(region, name)['Statement']:
            principal = s.get('Principal')
            if not (principal == '*' or (isinstance(principal, dict) and principal.get('Service') == service)):
                continue
            if s.get('Action') not in ('lambda:InvokeFunction', 'lambda:*'):
                continue
            want = (s.get('Condition') or {}).get('ArnLike', {}).get('AWS:SourceArn')
            if want is None or fnmatch.fnmatchcase(source_arn, want):
                return True
        return False

    # ── function URLs ───────────────────────────────────────────────────
    def op_CreateFunctionUrlConfig(self, request, region, p, ref):
        conf = self.config(region, ref)
        if self.store.exists(region, 'functions', conf['FunctionName'], 'url.json'):
            raise Twin__Error(409, 'ResourceConflictException', f'Failed to create function url config for [functionArn = {conf["FunctionArn"]}]. Error message:  FunctionUrlConfig exists for this Lambda function')
        if p.get('AuthType') not in ('NONE', 'AWS_IAM'):
            raise Twin__Error(400, 'ValidationException', "1 validation error detected: Value at 'authType' failed to satisfy constraint")
        url = {'FunctionUrl': f'https://{random_id(32, "abcdefghijklmnopqrstuvwxyz0123456789")}.lambda-url.{region}.on.aws/',
               'FunctionArn': conf['FunctionArn'], 'AuthType': p['AuthType'], 'CreationTime': iso_now(), 'InvokeMode': p.get('InvokeMode', 'BUFFERED')}
        if p.get('Cors'):
            url['Cors'] = p['Cors']
        self.store.write_json(url, region, 'functions', conf['FunctionName'], 'url.json')
        return json_response(201, url)

    def op_GetFunctionUrlConfig(self, request, region, p, ref):
        conf = self.config(region, ref)
        url  = self.store.read_json(region, 'functions', conf['FunctionName'], 'url.json')
        if url is None:
            raise Twin__Error(404, 'ResourceNotFoundException', 'The resource you requested does not exist.')
        return json_response(200, dict(url, LastModifiedTime=url['CreationTime']))

    def op_DeleteFunctionUrlConfig(self, request, region, p, ref):
        conf = self.config(region, ref)
        if not self.store.exists(region, 'functions', conf['FunctionName'], 'url.json'):
            raise Twin__Error(404, 'ResourceNotFoundException', 'The resource you requested does not exist.')
        self.store.delete(region, 'functions', conf['FunctionName'], 'url.json')
        return Twin__Response(204, {}, b'')
