"""The twins a deployment needs, through plain boto3: IAM roles, Lambda (running Python and Node.js
handlers), EventBridge rules, CloudFront distributions. Each test also checks a rule AWS enforces, so
the twin catches the mistake before the account does."""
import base64
import io
import json
import zipfile

import boto3

from aws_twin      import Twin
from tests.helpers import raises, needs_node_runtime, skip_if_twin_unavailable

TRUST = json.dumps({'Version': '2012-10-17', 'Statement': [{'Effect': 'Allow', 'Principal': {'Service': 'lambda.amazonaws.com'}, 'Action': 'sts:AssumeRole'}]})


def zipped(name, code):
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w') as z:
        z.writestr(name, code)
    return out.getvalue()


def test_iam_roles():
    with Twin():
        iam  = boto3.client('iam')
        role = iam.create_role(RoleName='lambda-role', AssumeRolePolicyDocument=TRUST, Description='d')['Role']
        assert role['Arn'] == 'arn:aws:iam::111111111111:role/lambda-role' and role['AssumeRolePolicyDocument']['Statement'][0]['Action'] == 'sts:AssumeRole'
        raises('EntityAlreadyExists', lambda: iam.create_role(RoleName='lambda-role', AssumeRolePolicyDocument=TRUST))
        raises('MalformedPolicyDocument', lambda: iam.create_role(RoleName='bad', AssumeRolePolicyDocument='{not json'))
        iam.attach_role_policy(RoleName='lambda-role', PolicyArn='arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole')
        iam.put_role_policy(RoleName='lambda-role', PolicyName='inline', PolicyDocument=json.dumps({'Version': '2012-10-17', 'Statement': []}))
        assert [p['PolicyName'] for p in iam.list_attached_role_policies(RoleName='lambda-role')['AttachedPolicies']] == ['AWSLambdaBasicExecutionRole']
        assert iam.list_role_policies(RoleName='lambda-role')['PolicyNames'] == ['inline']
        raises('DeleteConflict', lambda: iam.delete_role(RoleName='lambda-role'))
        iam.detach_role_policy(RoleName='lambda-role', PolicyArn='arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole')
        iam.delete_role_policy(RoleName='lambda-role', PolicyName='inline')
        iam.delete_role(RoleName='lambda-role')
        raises('NoSuchEntity', lambda: iam.get_role(RoleName='lambda-role'))


def test_lambda_python_function():
    with Twin() as twin:
        lam  = boto3.client('lambda', region_name='eu-west-2')
        code = zipped('app.py', 'import os\ndef handler(event, context):\n    print("seen", event["x"])\n'
                                '    return {"region": os.environ["AWS_REGION"], "x": event["x"], "name": context.function_name, "flag": os.environ.get("FLAG")}\n')
        raises('InvalidParameterValueException', lambda: lam.create_function(FunctionName='f', Runtime='python3.13', Handler='app.handler',
                                                                             Role='arn:aws:iam::111111111111:role/missing', Code={'ZipFile': code}))
        role = boto3.client('iam').create_role(RoleName='r', AssumeRolePolicyDocument=TRUST)['Role']['Arn']
        conf = lam.create_function(FunctionName='f', Runtime='python3.13', Handler='app.handler', Role=role, Code={'ZipFile': code},
                                   Environment={'Variables': {'FLAG': 'on'}})
        assert conf['State'] == 'Active' and conf['CodeSha256'] and conf['FunctionArn'].endswith(':function:f')
        lam.get_waiter('function_active_v2').wait(FunctionName='f')
        raises('ResourceConflictException', lambda: lam.create_function(FunctionName='f', Runtime='python3.13', Handler='app.handler', Role=role, Code={'ZipFile': code}))
        r = lam.invoke(FunctionName='f', Payload=json.dumps({'x': 7}), LogType='Tail')
        assert json.loads(r['Payload'].read()) == {'region': 'eu-west-2', 'x': 7, 'name': 'f', 'flag': 'on'} and 'FunctionError' not in r
        assert 'seen 7' in base64.b64decode(r['LogResult']).decode()
        r = lam.invoke(FunctionName='f', Payload=b'{}')                                    # KeyError in the handler
        assert r['FunctionError'] == 'Unhandled' and json.loads(r['Payload'].read())['errorType'] == 'KeyError'
        assert lam.invoke(FunctionName='f', InvocationType='Event', Payload=b'{"x": 1}')['StatusCode'] == 202
        lam.update_function_configuration(FunctionName='f', Environment={'Variables': {'FLAG': 'off'}}, Timeout=9)
        assert json.loads(lam.invoke(FunctionName='f', Payload=b'{"x": 1}')['Payload'].read())['flag'] == 'off'
        assert [f['FunctionName'] for f in lam.list_functions()['Functions']] == ['f']
        assert boto3.client('lambda', region_name='us-east-1').list_functions()['Functions'] == []          # per region
        assert len(twin.services['lambda'].invocations('eu-west-2', 'f')) == 4
        lam.delete_function(FunctionName='f')
        raises('ResourceNotFoundException', lambda: lam.get_function(FunctionName='f'))


def test_lambda_nodejs_function_and_the_twins_internet():
    needs_node_runtime()
    with Twin() as twin:
        lam  = boto3.client('lambda', region_name='us-east-1')
        role = boto3.client('iam').create_role(RoleName='r', AssumeRolePolicyDocument=TRUST)['Role']['Arn']
        code = zipped('index.mjs', 'export const handler = async (event, context) => {\n'
                                   '  console.log("checking", event.url);\n'
                                   '  try { const r = await fetch(event.url); return { status: r.status, region: process.env.AWS_REGION, fn: context.functionName }; }\n'
                                   '  catch (e) { return { error: e.cause && e.cause.code } }\n};\n')
        lam.create_function(FunctionName='js', Runtime='nodejs22.x', Handler='index.handler', Role=role, Code={'ZipFile': code})
        call = lambda url: json.loads(lam.invoke(FunctionName='js', Payload=json.dumps({'url': url}))['Payload'].read())
        first = call('https://example.com/')
        skip_if_twin_unavailable(first)
        assert first == {'error': 'ENOTFOUND'}                                             # no answer configured: unreachable
        twin.internet.answer('https://example.com/', status=503)
        twin.internet.answer('down.example', error='ECONNREFUSED')
        assert call('https://example.com/') == {'status': 503, 'region': 'us-east-1', 'fn': 'js'}
        assert call('https://down.example/x') == {'error': 'ECONNREFUSED'}
        lam.update_function_configuration(FunctionName='js', Handler='index.missing')
        r = lam.invoke(FunctionName='js', Payload=b'{}')
        assert r['FunctionError'] == 'Unhandled' and json.loads(r['Payload'].read())['errorType'] == 'Runtime.HandlerNotFound'


def test_eventbridge_schedule_needs_the_permission():
    needs_node_runtime()
    with Twin() as twin:
        lam, ev = boto3.client('lambda', region_name='eu-west-2'), boto3.client('events', region_name='eu-west-2')
        role = boto3.client('iam').create_role(RoleName='r', AssumeRolePolicyDocument=TRUST)['Role']['Arn']
        arn  = lam.create_function(FunctionName='tick', Runtime='nodejs22.x', Handler='index.handler', Role=role,
                                   Code={'ZipFile': zipped('index.mjs', 'export const handler = async (e) => ({ source: e.source, kind: e["detail-type"] });')})['FunctionArn']
        raises('ValidationException', lambda: ev.put_rule(Name='bad', ScheduleExpression='every 5 minutes'))
        rule = ev.put_rule(Name='tick', ScheduleExpression='rate(15 minutes)')['RuleArn']
        ev.put_targets(Rule='tick', Targets=[{'Id': 't', 'Arn': arn}])
        fired = twin.services['events'].fire('eu-west-2', 'tick')['invocations'][0]
        assert not fired['ok'] and 'resource policy' in fired['reason']                    # as AWS: no permission, no invocation
        lam.add_permission(FunctionName='tick', StatementId='s', Action='lambda:InvokeFunction', Principal='events.amazonaws.com', SourceArn=rule)
        raises('ResourceConflictException', lambda: lam.add_permission(FunctionName='tick', StatementId='s', Action='lambda:InvokeFunction', Principal='events.amazonaws.com'))
        fired = twin.services['events'].fire('eu-west-2', 'tick')['invocations'][0]
        skip_if_twin_unavailable(fired['result']['error'])
        assert fired['ok'] and fired['result']['result'] == {'source': 'aws.events', 'kind': 'Scheduled Event'}
        assert json.loads(lam.get_policy(FunctionName='tick')['Policy'])['Statement'][0]['Condition']['ArnLike']['AWS:SourceArn'] == rule
        raises('ValidationException', lambda: ev.delete_rule(Name='tick'))                # targets first
        ev.remove_targets(Rule='tick', Ids=['t'])
        ev.delete_rule(Name='tick')
        assert ev.list_rules()['Rules'] == []


def test_cloudfront_distribution_lifecycle():
    with Twin():
        cf  = boto3.client('cloudfront')
        cfg = {'CallerReference': 'ref-1', 'Comment': 'c', 'Enabled': True,
               'Origins': {'Quantity': 1, 'Items': [{'Id': 'o', 'DomainName': 'abc.lambda-url.eu-west-2.on.aws',
                                                      'CustomOriginConfig': {'HTTPPort': 80, 'HTTPSPort': 443, 'OriginProtocolPolicy': 'https-only'}}]},
               'DefaultCacheBehavior': {'TargetOriginId': 'o', 'ViewerProtocolPolicy': 'https-only', 'CachePolicyId': '4135ea2d-6df8-44a3-9df3-4b5a84be39ad'}}
        d = cf.create_distribution(DistributionConfig=cfg)
        dist_id = d['Distribution']['Id']
        assert d['Distribution']['DomainName'].endswith('.cloudfront.net') and d['ETag']
        raises('DistributionAlreadyExists', lambda: cf.create_distribution(DistributionConfig=cfg))
        got = cf.get_distribution_config(Id=dist_id)
        assert got['DistributionConfig']['Origins']['Items'][0]['DomainName'] == 'abc.lambda-url.eu-west-2.on.aws'
        assert cf.list_distributions()['DistributionList']['Items'][0]['Origins']['Quantity'] == 1
        raises('DistributionNotDisabled', lambda: cf.delete_distribution(Id=dist_id, IfMatch=got['ETag']))
        got['DistributionConfig']['Enabled'] = False
        raises('InvalidIfMatchVersion', lambda: cf.update_distribution(Id=dist_id, IfMatch='', DistributionConfig=got['DistributionConfig']))
        new = cf.update_distribution(Id=dist_id, IfMatch=got['ETag'], DistributionConfig=got['DistributionConfig'])
        raises('PreconditionFailed', lambda: cf.delete_distribution(Id=dist_id, IfMatch=got['ETag']))             # stale ETag
        cf.delete_distribution(Id=dist_id, IfMatch=new['ETag'])
        raises('NoSuchDistribution', lambda: cf.get_distribution(Id=dist_id))
