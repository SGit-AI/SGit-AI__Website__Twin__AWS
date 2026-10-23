"""The IAM page's policies and calls: each policy file is a well-formed policy with its placeholders, the
bucket CORS rule is one S3 accepts (here, the twin's S3, through botocore's own validation), and the Identity
Center calls the page makes pass botocore's parameter validation: the twin answers them NotImplemented, by
name, which it can only do once botocore has built and sent them. admin/build/check_cli.py does the same for
the page's text through the AWS CLI."""
import json
import os

import boto3

from aws_twin      import Twin
from tests.helpers import IN_BROWSER, raises, skip

POLICIES = os.path.join(os.path.dirname(__file__), '..', 'iam', 'policies')
INSTANCE = 'arn:aws:sso:::instance/ssoins-0000000000000000'
PS_ARN   = 'arn:aws:sso:::permissionSet/ssoins-0000000000000000/ps-0000000000000000'


def _policy(name, bucket='my-bucket', folder='reports'):
    with open(os.path.join(POLICIES, name), encoding='utf-8') as f:
        text = f.read()
    return text, json.loads(text.replace('BUCKET_NAME', bucket).replace('FOLDER', folder))


def test_policy_files_are_policies():
    if IN_BROWSER:
        skip('the policy files are site content, not in the browser bundle')
    names = sorted(f for f in os.listdir(POLICIES) if f.endswith('.json') and f.startswith(('s3-', 'twin-')))
    assert names == ['s3-list-bucket-names.json', 's3-read-one-bucket.json', 's3-read-one-folder.json',
                     's3-read-write-one-bucket.json', 'twin-reader.json']
    for name in names:
        text, doc = _policy(name)
        assert doc['Version'] == '2012-10-17' and doc['Statement'], name
        for st in doc['Statement']:
            assert st['Effect'] == 'Allow' and st['Action'] and st['Resource'], (name, st)
            actions = st['Action'] if isinstance(st['Action'], list) else [st['Action']]
            assert not any(a in ('*', 's3:*') for a in actions), (name, 'no wildcard grants')
        if name.startswith('s3-') and name != 's3-list-bucket-names.json':
            assert 'BUCKET_NAME' in text, name
    _, listing = _policy('s3-list-bucket-names.json')
    assert [a for st in listing['Statement'] for a in st['Action']] == ['s3:ListAllMyBuckets', 's3:GetBucketLocation', 'cloudformation:ListResources']   # names only: Cloud Control lists, S3's permission decides what
    _, read = _policy('s3-read-one-bucket.json')
    writes = {'s3:PutObject', 's3:DeleteObject', 's3:DeleteBucket', 's3:PutBucketPolicy', 's3:PutBucketCORS'}
    assert not writes & {a for st in read['Statement'] for a in (st['Action'] if isinstance(st['Action'], list) else [st['Action']])}


def test_bucket_cors_rule_is_one_s3_accepts():
    if IN_BROWSER:
        skip('the policy files are site content, not in the browser bundle')
    _, rule = _policy('bucket-cors-for-aws-twin.json')
    assert [r['AllowedOrigins'] for r in rule['CORSRules']] == [['https://aws.twin.sgit.ai']]   # this site only
    with Twin():
        s3 = boto3.client('s3', region_name='eu-west-2')
        s3.create_bucket(Bucket='cors-rule-bucket', CreateBucketConfiguration={'LocationConstraint': 'eu-west-2'})
        s3.put_bucket_cors(Bucket='cors-rule-bucket', CORSConfiguration=rule)                  # botocore validates the shape
        got = s3.get_bucket_cors(Bucket='cors-rule-bucket')['CORSRules'][0]
        assert got['AllowedOrigins'] == ['https://aws.twin.sgit.ai'] and 'ETag' in got['ExposeHeaders'] and got['MaxAgeSeconds'] == 3000


def test_identity_center_calls_pass_botocore_validation():
    policy = json.dumps({'Version': '2012-10-17', 'Statement': [{'Effect': 'Allow', 'Action': ['s3:ListAllMyBuckets'], 'Resource': '*'}]})
    with Twin():
        sso = boto3.client('sso-admin', region_name='eu-west-2')
        ids = boto3.client('identitystore', region_name='eu-west-2')
        calls = [
            lambda: sso.create_permission_set(InstanceArn=INSTANCE, Name='S3-List-Bucket-Names', Description='See bucket names, not contents', SessionDuration='PT1H'),
            lambda: sso.put_inline_policy_to_permission_set(InstanceArn=INSTANCE, PermissionSetArn=PS_ARN, InlinePolicy=policy),
            lambda: sso.create_account_assignment(InstanceArn=INSTANCE, TargetId='111122223333', TargetType='AWS_ACCOUNT', PermissionSetArn=PS_ARN,
                                                  PrincipalType='GROUP', PrincipalId='11111111-1111-1111-1111-111111111111'),
            lambda: sso.provision_permission_set(InstanceArn=INSTANCE, PermissionSetArn=PS_ARN, TargetType='ALL_PROVISIONED_ACCOUNTS'),
            lambda: ids.create_user(IdentityStoreId='d-0000000000', UserName='daily-user', DisplayName='Daily User',
                                    Name={'GivenName': 'Daily', 'FamilyName': 'User'}, Emails=[{'Value': 'daily.user@example.com', 'Type': 'work', 'Primary': True}]),
            lambda: ids.create_group(IdentityStoreId='d-0000000000', DisplayName='s3-list-only'),
            lambda: ids.get_user_id(IdentityStoreId='d-0000000000', AlternateIdentifier={'UniqueAttribute': {'AttributePath': 'userName', 'AttributeValue': 'daily-user'}}),
        ]
        for call in calls:
            raises('NotImplemented', call)                                                 # built, signed, sent, and named by the twin
        raises('NotImplemented', lambda: boto3.client('iam').simulate_custom_policy(
            PolicyInputList=[policy], ActionNames=['s3:ListBucket'], ResourceArns=['arn:aws:s3:::my-bucket']))
