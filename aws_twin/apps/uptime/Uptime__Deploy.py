"""Deploy the uptime check with boto3: the same calls against the twin and against an account.

    deploy = Uptime__Deploy(regions=['eu-west-2', 'us-east-1'], targets=['https://sgit.ai/'],
                            recipient_key=bundle_or_pem, append_url=..., append_token=...)
    deploy.deploy()                      # role, then each region: function, schedule (and URL, CloudFront)
    deploy.invoke('eu-west-2')           # run it now, with the caller's IAM authority
    deploy.teardown()                    # everything it made, backwards

Each step is also a method of its own, so a page can call them one by one and wait between them in
JavaScript instead of blocking the browser: ensure_role, put_function, function_state, put_config,
put_schedule, put_url, put_cloudfront, and their teardown counterparts.
The function is aws_twin/apps/uptime/handler/index.mjs, zipped here, unchanged."""
import base64
import hashlib
import io
import json
import os
import time
import zipfile

HANDLER       = os.path.join(os.path.dirname(__file__), 'handler', 'index.mjs')
TRUST         = {'Version': '2012-10-17', 'Statement': [{'Effect': 'Allow', 'Principal': {'Service': 'lambda.amazonaws.com'}, 'Action': 'sts:AssumeRole'}]}
BASIC_LOGS    = 'arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'
CACHING_OFF   = '4135ea2d-6df8-44a3-9df3-4b5a84be39ad'      # AWS managed cache policy CachingDisabled
ALL_VIEWER    = 'b689b0a8-53d0-40ab-baf2-68738e2966ac'      # AWS managed origin request policy AllViewerExceptHostHeader
SITE_ORIGIN   = 'https://aws.twin.sgit.ai'


def client_error_code(e):
    return getattr(e, 'response', {}).get('Error', {}).get('Code')


class Uptime__Deploy:
    def __init__(self, regions=('eu-west-2',), targets=(), recipient_key='', append_url='', append_token='', controller_key='',
                 name='aws-twin-uptime', role_name='aws-twin-uptime-lambda', schedule='rate(15 minutes)',
                 runtime='nodejs22.x', timeout=60, memory=256, function_url=False, cloudfront=False, session=None):
        self.regions, self.targets = list(regions), list(targets)
        self.recipient_key, self.append_url, self.append_token, self.controller_key = recipient_key, append_url, append_token, controller_key
        self.name, self.role_name, self.schedule = name, role_name, schedule
        self.runtime, self.timeout, self.memory = runtime, timeout, memory
        self.function_url, self.cloudfront = function_url, cloudfront
        self.session = session                                       # a boto3.Session, or None for the default

    # ── clients ─────────────────────────────────────────────────────────
    def client(self, service, region=None):
        import boto3
        factory = self.session.client if self.session else boto3.client
        return factory(service, region_name=region or 'us-east-1')

    # ── the package and its configuration ───────────────────────────────
    @staticmethod
    def handler_source():
        with open(HANDLER, encoding='utf-8') as f:
            return f.read()

    def package(self):
        """index.mjs in a zip, byte-identical for identical code (fixed timestamp), so CodeSha256 says when it changed."""
        out = io.BytesIO()
        with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
            info = zipfile.ZipInfo('index.mjs', date_time=(2026, 1, 1, 0, 0, 0))
            info.external_attr = 0o644 << 16
            z.writestr(info, self.handler_source())
        return out.getvalue()

    def environment(self):
        env = {'UPTIME_TARGETS': json.dumps(self.targets), 'UPTIME_RECIPIENT_KEY': self.recipient_pem(),
               'UPTIME_APPEND_URL': self.append_url, 'UPTIME_APPEND_TOKEN': self.append_token, 'UPTIME_CONTROLLER_KEY': self.controller_key}
        env = {k: v for k, v in env.items() if v}
        size = sum(len(k) + len(v) for k, v in env.items())
        if size > 4096:
            raise ValueError(f'the environment is {size} bytes; Lambda allows 4 KB: fewer targets, or a shorter key')
        return env

    def recipient_pem(self):
        """The public key the reports are encrypted to: an sgit bundle's encrypt PEM, or a PEM as given."""
        text = (self.recipient_key or '').strip()
        return json.loads(text)['encrypt'].strip() if text.startswith('{') else text

    # ── the execution role (global) ─────────────────────────────────────
    def ensure_role(self):
        iam = self.client('iam')
        try:
            role = iam.get_role(RoleName=self.role_name)['Role']
            created = False
        except Exception as e:
            if client_error_code(e) != 'NoSuchEntity':
                raise
            role = iam.create_role(RoleName=self.role_name, AssumeRolePolicyDocument=json.dumps(TRUST),
                                   Description='aws.twin uptime check: writes its own logs, nothing else')['Role']
            created = True
        attached = [p['PolicyArn'] for p in iam.list_attached_role_policies(RoleName=self.role_name)['AttachedPolicies']]
        if BASIC_LOGS not in attached:
            iam.attach_role_policy(RoleName=self.role_name, PolicyArn=BASIC_LOGS)
        return {'step': 'role', 'arn': role['Arn'], 'created': created}

    def role_arn(self):
        return self.client('iam').get_role(RoleName=self.role_name)['Role']['Arn']

    # ── one region ──────────────────────────────────────────────────────
    def put_function(self, region, role_arn=None):
        """Create the function, or update its code; a new role may not be usable for a few seconds
        (InvalidParameterValueException: 'cannot be assumed'), which a caller retries."""
        lam, data = self.client('lambda', region), self.package()
        try:
            conf = lam.get_function(FunctionName=self.name)['Configuration']
        except Exception as e:
            if client_error_code(e) != 'ResourceNotFoundException':
                raise
            conf = lam.create_function(FunctionName=self.name, Runtime=self.runtime, Role=role_arn or self.role_arn(), Handler='index.handler',
                                       Code={'ZipFile': data}, Timeout=self.timeout, MemorySize=self.memory,
                                       Description='aws.twin uptime check (https://aws.twin.sgit.ai/uptime/)',
                                       Environment={'Variables': self.environment()}, Architectures=['arm64'],
                                       Tags={'aws.twin': 'uptime'})
            return {'step': 'function', 'region': region, 'action': 'created', 'arn': conf['FunctionArn'], 'state': conf.get('State')}
        changed = conf['CodeSha256'] != base64.b64encode(hashlib.sha256(data).digest()).decode()
        if changed:
            conf = lam.update_function_code(FunctionName=self.name, ZipFile=data)
        return {'step': 'function', 'region': region, 'action': 'code updated' if changed else 'code unchanged', 'arn': conf['FunctionArn'],
                'state': conf.get('State'), 'needs_config': True}

    def function_state(self, region):
        conf = self.client('lambda', region).get_function_configuration(FunctionName=self.name)
        return {'state': conf.get('State'), 'update': conf.get('LastUpdateStatus'), 'ready': conf.get('State') == 'Active' and conf.get('LastUpdateStatus') != 'InProgress'}

    def put_config(self, region, role_arn=None):
        conf = self.client('lambda', region).update_function_configuration(
            FunctionName=self.name, Role=role_arn or self.role_arn(), Runtime=self.runtime, Handler='index.handler',
            Timeout=self.timeout, MemorySize=self.memory, Environment={'Variables': self.environment()})
        return {'step': 'configuration', 'region': region, 'arn': conf['FunctionArn']}

    def put_schedule(self, region, function_arn):
        events, lam = self.client('events', region), self.client('lambda', region)
        rule = events.put_rule(Name=f'{self.name}-schedule', ScheduleExpression=self.schedule, State='ENABLED',
                               Description='aws.twin uptime check')['RuleArn']
        try:
            lam.add_permission(FunctionName=self.name, StatementId='aws-twin-uptime-schedule', Action='lambda:InvokeFunction',
                               Principal='events.amazonaws.com', SourceArn=rule)
        except Exception as e:
            if client_error_code(e) != 'ResourceConflictException':
                raise
        events.put_targets(Rule=f'{self.name}-schedule', Targets=[{'Id': 'uptime', 'Arn': function_arn}])
        return {'step': 'schedule', 'region': region, 'rule': rule, 'expression': self.schedule}

    def put_url(self, region):
        lam = self.client('lambda', region)
        try:
            url = lam.get_function_url_config(FunctionName=self.name)['FunctionUrl']
        except Exception as e:
            if client_error_code(e) != 'ResourceNotFoundException':
                raise
            url = lam.create_function_url_config(FunctionName=self.name, AuthType='NONE',
                                                 Cors={'AllowOrigins': [SITE_ORIGIN], 'AllowMethods': ['POST'],
                                                       'AllowHeaders': ['content-type', 'x-uptime-ts', 'x-uptime-sig'], 'MaxAge': 600})['FunctionUrl']
        try:                                                       # the URL is public; the controller signature is its gate
            lam.add_permission(FunctionName=self.name, StatementId='aws-twin-uptime-url', Action='lambda:InvokeFunctionUrl',
                               Principal='*', FunctionUrlAuthType='NONE')
        except Exception as e:
            if client_error_code(e) != 'ResourceConflictException':
                raise
        return {'step': 'function url', 'region': region, 'url': url}

    # ── CloudFront: one hostname, a path per region ─────────────────────
    def distribution_config(self, urls, caller_reference=None):
        regions = list(urls)
        methods = {'Quantity': 7, 'Items': ['GET', 'HEAD', 'OPTIONS', 'PUT', 'POST', 'PATCH', 'DELETE'],
                   'CachedMethods': {'Quantity': 2, 'Items': ['GET', 'HEAD']}}
        def behaviour(region, path=None):
            b = {'TargetOriginId': region, 'ViewerProtocolPolicy': 'https-only', 'AllowedMethods': methods, 'Compress': False,
                 'CachePolicyId': CACHING_OFF, 'OriginRequestPolicyId': ALL_VIEWER}
            return dict(b, PathPattern=path) if path else b
        origins = [{'Id': r, 'DomainName': urls[r].split('://', 1)[-1].strip('/'),
                    'CustomOriginConfig': {'HTTPPort': 80, 'HTTPSPort': 443, 'OriginProtocolPolicy': 'https-only',
                                           'OriginSslProtocols': {'Quantity': 1, 'Items': ['TLSv1.2']}}} for r in regions]
        return {'CallerReference': caller_reference or f'{self.name}-{int(time.time())}', 'Comment': f'aws.twin uptime: {self.name}',
                'Enabled': True, 'PriceClass': 'PriceClass_100', 'HttpVersion': 'http2and3',
                'Origins': {'Quantity': len(origins), 'Items': origins},
                'DefaultCacheBehavior': behaviour(regions[0]),
                'CacheBehaviors': {'Quantity': len(regions), 'Items': [behaviour(r, f'/{r}/*') for r in regions]}}

    def find_distribution(self):
        items = self.client('cloudfront').list_distributions()['DistributionList'].get('Items', [])
        return next((d for d in items if d.get('Comment') == f'aws.twin uptime: {self.name}'), None)

    def put_cloudfront(self, urls):
        cf, found = self.client('cloudfront'), self.find_distribution()
        if found is None:
            d = cf.create_distribution(DistributionConfig=self.distribution_config(urls))['Distribution']
            return {'step': 'cloudfront', 'action': 'created', 'id': d['Id'], 'domain': d['DomainName'], 'status': d['Status']}
        current = cf.get_distribution_config(Id=found['Id'])
        conf = self.distribution_config(urls, current['DistributionConfig']['CallerReference'])
        d = cf.update_distribution(Id=found['Id'], IfMatch=current['ETag'], DistributionConfig=conf)['Distribution']
        return {'step': 'cloudfront', 'action': 'updated', 'id': d['Id'], 'domain': d['DomainName'], 'status': d['Status']}

    # ── all of it (CPython: waits with time.sleep) ──────────────────────
    def deploy(self, wait=0.5, tries=40):
        steps = [self.ensure_role()]
        role, urls = steps[0]['arn'], {}
        for region in self.regions:
            for attempt in range(tries):
                try:
                    step = self.put_function(region, role); break
                except Exception as e:
                    if client_error_code(e) != 'InvalidParameterValueException' or 'assumed' not in str(e) or attempt == tries - 1:
                        raise
                    time.sleep(wait)
            steps.append(step)
            self.wait_ready(region, wait, tries)
            if step.get('needs_config'):
                steps.append(self.put_config(region, role)); self.wait_ready(region, wait, tries)
            steps.append(self.put_schedule(region, step['arn']))
            if self.function_url or self.cloudfront:
                u = self.put_url(region); steps.append(u); urls[region] = u['url']
        if self.cloudfront and urls:
            steps.append(self.put_cloudfront(urls))
        return steps

    def wait_ready(self, region, wait=0.5, tries=40):
        for _ in range(tries):
            if self.function_state(region)['ready']:
                return True
            time.sleep(wait)
        raise TimeoutError(f'{self.name} in {region} did not become ready')

    # ── use ─────────────────────────────────────────────────────────────
    def invoke(self, region, targets=None):
        r = self.client('lambda', region).invoke(FunctionName=self.name, Payload=json.dumps({'targets': targets} if targets else {}).encode(), LogType='Tail')
        return {'region': region, 'status': r['StatusCode'], 'function_error': r.get('FunctionError'),
                'payload': json.loads(r['Payload'].read() or b'null'), 'log': base64.b64decode(r.get('LogResult', '')).decode('utf-8', 'replace')}

    # ── teardown ────────────────────────────────────────────────────────
    def teardown_region(self, region):
        events, lam, done = self.client('events', region), self.client('lambda', region), []
        rule = f'{self.name}-schedule'
        for call, kwargs, label in ((events.remove_targets, {'Rule': rule, 'Ids': ['uptime']}, 'schedule targets'),
                                    (events.delete_rule, {'Name': rule}, 'schedule'),
                                    (lam.delete_function_url_config, {'FunctionName': self.name}, 'function url'),
                                    (lam.delete_function, {'FunctionName': self.name}, 'function')):
            try:
                call(**kwargs); done.append(label)
            except Exception as e:
                if client_error_code(e) not in ('ResourceNotFoundException', 'NoSuchEntity'):
                    raise
        return {'step': 'teardown', 'region': region, 'removed': done}

    def teardown_cloudfront(self):
        """Disable, then delete once AWS has deployed the disable (the twin: at once; AWS: minutes, so call again)."""
        cf, found = self.client('cloudfront'), self.find_distribution()
        if found is None:
            return {'step': 'cloudfront teardown', 'state': 'none'}
        current = cf.get_distribution_config(Id=found['Id'])
        if current['DistributionConfig']['Enabled']:
            current['DistributionConfig']['Enabled'] = False
            cf.update_distribution(Id=found['Id'], IfMatch=current['ETag'], DistributionConfig=current['DistributionConfig'])
            return {'step': 'cloudfront teardown', 'state': 'disabling', 'id': found['Id']}
        d = cf.get_distribution(Id=found['Id'])
        if d['Distribution']['Status'] != 'Deployed':
            return {'step': 'cloudfront teardown', 'state': 'waiting for the disable to deploy', 'id': found['Id']}
        cf.delete_distribution(Id=found['Id'], IfMatch=d['ETag'])
        return {'step': 'cloudfront teardown', 'state': 'deleted', 'id': found['Id']}

    def teardown_role(self):
        iam = self.client('iam')
        try:
            for p in iam.list_attached_role_policies(RoleName=self.role_name)['AttachedPolicies']:
                iam.detach_role_policy(RoleName=self.role_name, PolicyArn=p['PolicyArn'])
            iam.delete_role(RoleName=self.role_name)
            return {'step': 'role teardown', 'state': 'deleted'}
        except Exception as e:
            if client_error_code(e) == 'NoSuchEntity':
                return {'step': 'role teardown', 'state': 'none'}
            raise

    def teardown(self):
        steps = [self.teardown_region(r) for r in self.regions]
        if self.cloudfront:
            steps.append(self.teardown_cloudfront())
        steps.append(self.teardown_role())
        return steps
