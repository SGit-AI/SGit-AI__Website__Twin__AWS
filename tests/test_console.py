"""The console's Python side (aws_twin/web/Console.py), as its pages call it: Lambda browsing, Cloud
Control resources, the twin's data, the request log, and the live rules (Cloud Control for buckets,
read-only). The twin answers; live mode is exercised by routing nothing live, which checks the calls
the console makes, not AWS."""
import base64
import json

from aws_twin.web.Console import Console
from tests.helpers        import needs_node_runtime, skip_if_twin_unavailable


def console():
    c = Console()
    c.start('[]')
    return c


def call(c, op, **args):
    out = json.loads(c.call(op, json.dumps(args)))
    return out['result'], out['call']


def test_lambda_browser_in_the_twin():
    c = console()
    try:
        result, entry = call(c, 'lambda_list', region='eu-west-2')
        assert result['functions'] == [] and entry['error'] is None
        result, entry = call(c, 'lambda_seed', region='eu-west-2')
        assert result['created'] == ['example-hello-python', 'example-site-check']
        assert {t['operation'] for t in entry['traffic']} >= {'CreateRole', 'CreateFunction', 'CreateFunctionUrlConfig', 'PutRule', 'AddPermission', 'PutTargets'}
        rows = call(c, 'lambda_list', region='eu-west-2')[0]['functions']
        assert [(r['name'], r['runtime']) for r in rows] == [('example-hello-python', 'python3.13'), ('example-site-check', 'nodejs22.x')]
        assert call(c, 'lambda_list', region='us-east-1')[0]['functions'] == []
        got = call(c, 'lambda_get', region='eu-west-2', name='example-site-check')[0]
        assert got['configuration']['Environment']['Variables'] == {'TARGET': 'https://sgit.ai/'}
        assert got['url']['AuthType'] == 'AWS_IAM' and got['policy']['Statement'][0]['Principal'] == {'Service': 'events.amazonaws.com'}
        assert [r['ScheduleExpression'] for r in got['rules']] == ['rate(15 minutes)']
        code = call(c, 'lambda_code', region='eu-west-2', name='example-hello-python')[0]
        assert code['files'][0]['name'] == 'app.py' and 'def handler' in code['files'][0]['text'] and base64.b64decode(code['zip_b64'])[:2] == b'PK'
        inv = call(c, 'lambda_invoke', region='eu-west-2', name='example-hello-python', payload='{"name": "Dinis"}')[0]
        assert json.loads(inv['payload'])['hello'] == 'Dinis' and inv['function_error'] is None and 'START RequestId' in inv['log']
        logs = call(c, 'lambda_logs', region='eu-west-2', name='example-hello-python')[0]
        assert logs['source'] == 'twin' and len(logs['invocations']) == 1
        counts = [call(c, 'lambda_count', region=r)[0] for r in ('eu-west-2', 'us-east-1')]
        assert [x['count'] for x in counts] == [2, 0]
    finally:
        c.use_twin(); c.twin.deactivate()


def test_node_function_runs_from_the_console():
    needs_node_runtime()
    c = console()
    try:
        call(c, 'lambda_seed', region='eu-west-2')
        inv = call(c, 'lambda_invoke', region='eu-west-2', name='example-site-check', payload='{}')[0]
        skip_if_twin_unavailable(json.loads(inv['payload']))
        assert json.loads(inv['payload'])['status'] == 200                    # the twin's internet answers sgit.ai
    finally:
        c.use_twin(); c.twin.deactivate()


def test_resources_through_cloud_control():
    c = console()
    try:
        call(c, 'create_bucket', name='a-bucket-in-london', region='eu-west-2')
        call(c, 'create_bucket', name='a-bucket-in-virginia', region='us-east-1')
        call(c, 'lambda_seed', region='eu-west-2')
        buckets = call(c, 'resources', type_name='AWS::S3::Bucket')[0]
        assert [r['identifier'] for r in buckets['resources']] == ['a-bucket-in-london', 'a-bucket-in-virginia']   # every region's
        one = call(c, 'resource', type_name='AWS::S3::Bucket', identifier='a-bucket-in-virginia')[0]
        assert one['properties']['RegionalDomainName'] == 'a-bucket-in-virginia.s3.us-east-1.amazonaws.com'
        assert [r['identifier'] for r in call(c, 'resources', type_name='AWS::Lambda::Function')[0]['resources']] == ['example-hello-python', 'example-site-check']
        role = call(c, 'resource', type_name='AWS::IAM::Role', identifier='example-lambda-role')[0]['properties']
        assert role['ManagedPolicyArns'] == ['arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole']
        rule = call(c, 'resources', type_name='AWS::Events::Rule')[0]['resources'][0]
        assert call(c, 'resource', type_name='AWS::Events::Rule', identifier=rule['identifier'])[0]['properties']['ScheduleExpression'] == 'rate(15 minutes)'
        _, entry = call(c, 'resources', type_name='AWS::DynamoDB::Table')
        assert entry['error']['code'] == 'NotImplemented' and 'AWS::DynamoDB::Table' in entry['error']['message']   # a gap, by name
        overview = call(c, 'overview')[0]
        assert overview['buckets'] == 2 and overview['functions'] == 2 and overview['rules'] == 1 and overview['roles'] == 1
    finally:
        c.use_twin(); c.twin.deactivate()


def test_twin_data_and_the_request_log():
    c = console()
    try:
        call(c, 'lambda_seed', region='eu-west-2')
        tree = call(c, 'twin_tree')[0]
        assert {'lambda', 'iam', 'events', 'internet'} <= set(tree['groups'])
        conf = call(c, 'twin_file', path='/lambda/eu-west-2/functions/example-hello-python/config.json')[0]
        assert conf['json']['Runtime'] == 'python3.13'
        assert call(c, 'twin_file', path='/lambda/eu-west-2/functions/example-hello-python/code.zip')[0]['zip'][0]['name'] == 'app.py'
        rows = call(c, 'requests', after=0)[0]
        assert rows and all(r['target'] == 'twin' for r in rows)
        detail = call(c, 'request', seq=rows[0]['seq'])[0]
        assert detail['request']['headers'] and 'authorization' not in detail['request']['headers']
        assert detail['response']['body']['text'] is not None
        assert call(c, 'requests', after=rows[-1]['seq'])[0] == []
        assert call(c, 'twin_reset', prefix='/lambda')[0]['deleted'] > 0
        assert call(c, 'lambda_list', region='eu-west-2')[0]['functions'] == []
    finally:
        c.use_twin(); c.twin.deactivate()


def test_live_rules():
    from aws_twin.web.Console import masked
    c = console()
    try:
        call(c, 'create_bucket', name='listed-through-cloud-control', region='eu-west-2')
        c.live = True                                                   # as use_live leaves it; the twin still answers here
        result, entry = call(c, 'buckets')
        assert [b['name'] for b in result] == ['listed-through-cloud-control'] and 'cloudcontrol' in entry['python']
        assert [t['operation'] for t in entry['traffic']] == ['ListResources']   # not S3's ListBuckets, which a browser cannot make
        _, entry = call(c, 'lambda_invoke', region='eu-west-2', name='x', payload='{}')
        assert entry['error']['code'] == 'ReadOnly'                     # invoking runs code: a write, refused until allowed
        token = 'IQoJb3JpZ2luX2VjEXAMPLE' * 10
        assert masked({'x-amz-security-token': token})['x-amz-security-token'].startswith('IQoJb3…') and token not in json.dumps(masked({'x-amz-security-token': token}))
    finally:
        c.live = False
        c.use_twin(); c.twin.deactivate()


def test_call_editor_and_the_matrix():
    c = console()
    try:
        rows = call(c, 'matrix')[0]
        assert len(rows) == 34 and {r['id'] for r in rows} >= {'s3.ListBuckets', 'cloudcontrol.ListResources', 'lambda.ListFunctions'}
        assert 'lambda' in call(c, 'services')[0]
        ops = call(c, 'operations', service='lambda')[0]
        assert 'ListFunctions' in ops['operations'] and ops['protocol'] == 'rest-json' and ops['signing_name'] == 'lambda'
        sk = call(c, 'skeleton', service='lambda', operation='Invoke')[0]
        assert sk['params'] == {'FunctionName': '<NamespacedFunctionName>'} and sk['required'] == ['FunctionName'] and sk['write'] is True
        assert call(c, 'skeleton', service='s3', operation='ListBuckets')[0]['write'] is False
        call(c, 'lambda_seed', region='eu-west-2')
        out = call(c, 'send', service='lambda', operation='ListFunctions', params={}, region='eu-west-2')[0]
        assert out['status'] == 200 and [f['FunctionName'] for f in out['result']['Functions']] == ['example-hello-python', 'example-site-check']
        _, entry = call(c, 'send', service='lambda', operation='GetFunction', params={'FunctionName': 'missing'}, region='eu-west-2')
        assert entry['error']['code'] == 'ResourceNotFoundException'                # a call that needs state, named
        _, entry = call(c, 'send', service='dynamodb', operation='ListTables', params={})
        assert entry['error']['code'] == 'NotImplemented'
        c.live = True                                                         # read-only live: a write is refused before it is sent
        _, entry = call(c, 'send', service='lambda', operation='DeleteFunction', params={'FunctionName': 'example-hello-python'}, region='eu-west-2')
        assert entry['error']['code'] == 'ReadOnly' and entry['traffic'] == []
        c.live = False
    finally:
        c.live = False
        c.use_twin(); c.twin.deactivate()


def test_requests_carry_the_call_for_replay_and_compare():
    c = console()
    try:
        call(c, 'lambda_seed', region='eu-west-2')
        _, entry = call(c, 'lambda_get', region='eu-west-2', name='example-hello-python')
        seq = entry['traffic'][0]['seq']
        detail = call(c, 'request', seq=seq)[0]
        assert detail['api'] == {'service': 'lambda', 'operation': 'GetFunction', 'region': 'eu-west-2', 'params': {'FunctionName': 'example-hello-python'}}
        rec = next(r for r in c.twin.traffic.records if r['seq'] == seq)
        rec['target'] = 'live'                                               # as if it had gone to AWS: compare it with the twin
        cmp = call(c, 'request_twin', seq=seq)[0]
        assert cmp['status'] == 200 and cmp['same_status'] and 'example-hello-python' in cmp['body']
        create = next(r for r in c.twin.traffic.records if r.get('api', {}).get('operation') == 'CreateFunction')
        _, entry = call(c, 'request_twin', seq=create['seq'])
        assert entry['error'] and 'only reads' in entry['error']['message']     # a write is never re-sent to the twin
    finally:
        c.use_twin(); c.twin.deactivate()
