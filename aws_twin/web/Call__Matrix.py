"""The calls the twin's pages make, and which ways of making them work.

The same AWS operation, sent five ways: the AWS CLI; boto3 in a normal Python (code outside a
browser); boto3 in the browser under Pyodide; the official AWS SDK for JavaScript in the browser;
and the twin. Outside a browser nothing stops a request but AWS itself; inside one, the browser
lets a page read an answer only when AWS sends CORS headers for the page's origin, and that differs
by service and, for S3, by bucket.

Measured with invented keys, so no account and no permission is involved: an answer from AWS (an
error such as InvalidClientTokenId) means the request reached AWS and the caller could read the
answer; a blocked request means the browser refused it before or after it was sent. The twin column
says whether the twin implements the operation (any answer but NotImplemented).
admin/build/call_matrix.py measures the CLI, code and twin columns; the calls page measures the two
browser columns in whatever browser opens it, and admin/build/call_matrix_browser.js records them."""

PROBE_KEYS = {'aws_access_key_id': 'INVENTED-KEY-FOR-PROBE', 'aws_secret_access_key': 'invented-for-the-call-matrix',
              'aws_session_token': 'invented-session-token'}
NO_CORS_BUCKET = 'aws-twin-probe-bucket-without-a-cors-rule'

OPS = [
    # group,        service,          operation,            params,                                                     region,       js package,             cli,                                                                   note
    ('identity',    'sts',            'GetCallerIdentity',  {},                                                         'eu-west-2',  'client-sts',            ['sts', 'get-caller-identity'],                                         'the session check'),
    ('S3',          's3',             'ListBuckets',        {},                                                         'eu-west-2',  'client-s3',             ['s3api', 'list-buckets'],                                              'S3 sends no CORS headers for the service endpoint: a page can never list buckets this way'),
    ('S3',          's3',             'ListObjectsV2',      {'Bucket': NO_CORS_BUCKET},                                 'eu-west-2',  'client-s3',             ['s3api', 'list-objects-v2', '--bucket', NO_CORS_BUCKET],               'a bucket without a CORS rule for the page; with one, it works'),
    ('S3',          's3',             'GetBucketLocation',  {'Bucket': NO_CORS_BUCKET},                                 'eu-west-2',  'client-s3',             ['s3api', 'get-bucket-location', '--bucket', NO_CORS_BUCKET],           'the same: per bucket'),
    ('resources',   'cloudcontrol',   'ListResources',      {'TypeName': 'AWS::S3::Bucket'},                            'eu-west-2',  'client-cloudcontrol',   ['cloudcontrol', 'list-resources', '--type-name', 'AWS::S3::Bucket'],   'lists every bucket, any region: how the console lists buckets'),
    ('resources',   'cloudcontrol',   'GetResource',        {'TypeName': 'AWS::Lambda::Function', 'Identifier': 'example'}, 'eu-west-2', 'client-cloudcontrol', ['cloudcontrol', 'get-resource', '--type-name', 'AWS::Lambda::Function', '--identifier', 'example'], ''),
    ('Lambda',      'lambda',         'ListFunctions',      {},                                                         'eu-west-2',  'client-lambda',         ['lambda', 'list-functions'],                                           ''),
    ('Lambda',      'lambda',         'GetFunction',        {'FunctionName': 'example'},                                'eu-west-2',  'client-lambda',         ['lambda', 'get-function', '--function-name', 'example'],               'needs a function'),
    ('Lambda',      'lambda',         'Invoke',             {'FunctionName': 'example', 'Payload': '{}'},               'eu-west-2',  'client-lambda',         ['lambda', 'invoke', '--function-name', 'example', '/dev/null'],        'needs a function; runs code'),
    ('Lambda',      'lambda',         'GetFunctionUrlConfig', {'FunctionName': 'example'},                              'eu-west-2',  'client-lambda',         ['lambda', 'get-function-url-config', '--function-name', 'example'],    'needs a function'),
    ('IAM',         'iam',            'ListRoles',          {},                                                         'us-east-1',  'client-iam',            ['iam', 'list-roles'],                                                  'global'),
    ('IAM',         'iam',            'GetRole',            {'RoleName': 'example'},                                    'us-east-1',  'client-iam',            ['iam', 'get-role', '--role-name', 'example'],                          'needs a role'),
    ('EventBridge', 'events',         'ListRules',          {},                                                         'eu-west-2',  'client-eventbridge',    ['events', 'list-rules'],                                               ''),
    ('Logs',        'logs',           'DescribeLogGroups',  {},                                                         'eu-west-2',  'client-cloudwatch-logs', ['logs', 'describe-log-groups'],                                       ''),
    ('Logs',        'logs',           'FilterLogEvents',    {'logGroupName': '/aws/lambda/example'},                    'eu-west-2',  'client-cloudwatch-logs', ['logs', 'filter-log-events', '--log-group-name', '/aws/lambda/example'], 'needs a log group'),
    ('CloudFront',  'cloudfront',     'ListDistributions',  {},                                                         'us-east-1',  'client-cloudfront',     ['cloudfront', 'list-distributions'],                                   'global'),
    ('EC2',         'ec2',            'DescribeInstances',  {},                                                         'eu-west-2',  'client-ec2',            ['ec2', 'describe-instances'],                                          ''),
    ('EC2',         'ec2',            'DescribeRegions',    {},                                                         'eu-west-2',  'client-ec2',            ['ec2', 'describe-regions'],                                            ''),
    ('billing',     'ce',             'GetCostAndUsage',    {'TimePeriod': {'Start': '2026-10-01', 'End': '2026-10-02'}, 'Granularity': 'DAILY', 'Metrics': ['UnblendedCost']},
                                                                                                                        'us-east-1',  'client-cost-explorer',  ['ce', 'get-cost-and-usage', '--time-period', 'Start=2026-10-01,End=2026-10-02', '--granularity', 'DAILY', '--metrics', 'UnblendedCost'], ''),
    ('CloudFormation', 'cloudformation', 'DescribeStacks',  {},                                                         'eu-west-2',  'client-cloudformation', ['cloudformation', 'describe-stacks'],                                   ''),
    ('data',        'dynamodb',       'ListTables',         {},                                                         'eu-west-2',  'client-dynamodb',       ['dynamodb', 'list-tables'],                                            ''),
    ('data',        'sqs',            'ListQueues',         {},                                                         'eu-west-2',  'client-sqs',            ['sqs', 'list-queues'],                                                 ''),
    ('data',        'sns',            'ListTopics',         {},                                                         'eu-west-2',  'client-sns',            ['sns', 'list-topics'],                                                 ''),
    ('secrets',     'kms',            'ListKeys',           {},                                                         'eu-west-2',  'client-kms',            ['kms', 'list-keys'],                                                   ''),
    ('secrets',     'secretsmanager', 'ListSecrets',        {},                                                         'eu-west-2',  'client-secrets-manager', ['secretsmanager', 'list-secrets'],                                    ''),
    ('secrets',     'ssm',            'DescribeParameters', {},                                                         'eu-west-2',  'client-ssm',            ['ssm', 'describe-parameters'],                                         ''),
    ('containers',  'ecr',            'DescribeRepositories', {},                                                       'eu-west-2',  'client-ecr',            ['ecr', 'describe-repositories'],                                       ''),
    ('containers',  'ecs',            'ListClusters',       {},                                                         'eu-west-2',  'client-ecs',            ['ecs', 'list-clusters'],                                               ''),
    ('network',     'route53',        'ListHostedZones',    {},                                                         'us-east-1',  'client-route-53',       ['route53', 'list-hosted-zones'],                                       'global'),
    ('network',     'apigateway',     'GetRestApis',        {},                                                         'eu-west-2',  'client-api-gateway',    ['apigateway', 'get-rest-apis'],                                        ''),
    ('monitoring',  'cloudwatch',     'ListMetrics',        {},                                                         'eu-west-2',  'client-cloudwatch',     ['cloudwatch', 'list-metrics'],                                         ''),
    ('accounts',    'sso-admin',      'ListInstances',      {},                                                         'eu-west-2',  'client-sso-admin',      ['sso-admin', 'list-instances'],                                        'IAM Identity Center'),
    ('accounts',    'identitystore',  'ListUsers',          {'IdentityStoreId': 'd-0000000000'},                        'eu-west-2',  'client-identitystore',  ['identitystore', 'list-users', '--identity-store-id', 'd-0000000000'], 'IAM Identity Center'),
    ('accounts',    'organizations',  'ListAccounts',       {},                                                         'us-east-1',  'client-organizations',  ['organizations', 'list-accounts'],                                     'global'),
]


def rows():
    return [{'id': f'{svc}.{op}', 'group': g, 'service': svc, 'operation': op, 'params': params, 'region': region,
             'js_package': js, 'cli': cli, 'note': note} for g, svc, op, params, region, js, cli, note in OPS]


def classify(error=None, blocked=False):
    """One word for a probe's outcome: reached (AWS answered, the caller could read it), blocked, or error."""
    if blocked:
        return {'status': 'blocked'}
    if error is None:
        return {'status': 'ok'}
    code = getattr(error, 'response', {}).get('Error', {}).get('Code')
    if code:
        return {'status': 'reached', 'code': code}
    return {'status': 'error', 'code': type(error).__name__, 'message': str(error)[:200]}
