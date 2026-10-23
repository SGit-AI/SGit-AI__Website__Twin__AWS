"""The Cloud Control API twin: one way to list and read any resource, which a browser can reach.

S3's ListBuckets never answers a page; Cloud Control answers any origin, and its ListResources for
AWS::S3::Bucket returns every bucket in the account whatever region it is called in (measured with a
real account on 23 October 2026). So the console lists buckets, and browses every other resource
type, through it.

Covered (JSON 1.0, X-Amz-Target CloudApiService.*): ListResources and GetResource, for the types
the twin holds, read from the other twins' stores:
    AWS::S3::Bucket                 every bucket, from any region           identifier: the name
    AWS::Lambda::Function           per region                              identifier: the name
    AWS::IAM::Role                  global                                  identifier: the name
    AWS::Events::Rule               per region                              identifier: the ARN
    AWS::CloudFront::Distribution   global                                  identifier: the id
A list carries only the identifying property, as AWS's does; GetResource carries the properties in
the resource type's CloudFormation shape. Other types answer 501 NotImplemented, by name. The
create, update and delete operations are not twinned."""
import json
from urllib.parse import unquote

from aws_twin.core.Twin__Service import Twin__Error, json_error, json_response, region_of

CT = 'application/x-amz-json-1.0'


class CloudControl__Twin:
    service = 'cloudcontrolapi'

    def __init__(self, twin):
        self.twin = twin

    def handle(self, request):
        action = (request.header('x-amz-target') or '.Unknown').split('.')[-1]
        region = region_of(request, self.twin.region)
        try:
            params = json.loads(request.body or b'{}')
            if action not in ('ListResources', 'GetResource'):
                raise Twin__Error(501, 'NotImplemented', f'the twin does not implement cloudcontrol {action}')
            type_name = params.get('TypeName', '')
            kind = TYPES.get(type_name)
            if kind is None:
                raise Twin__Error(501, 'NotImplemented', f'the twin holds no {type_name or "(no TypeName)"} resources; it holds {", ".join(TYPES)}')
            if action == 'ListResources':
                items = [{'Identifier': i, 'Properties': json.dumps(p)} for i, p in getattr(self, 'list_' + kind)(region)]
                return action, json_response(200, {'TypeName': type_name, 'ResourceDescriptions': items}, CT)
            ident = params.get('Identifier', '')
            props = getattr(self, 'get_' + kind)(region, ident)
            if props is None:
                raise Twin__Error(404, 'ResourceNotFoundException',
                                  f'{type_name} Handler returned status FAILED: {ident} not found (HandlerErrorCode: NotFound)')
            return action, json_response(200, {'TypeName': type_name, 'ResourceDescription': {'Identifier': ident, 'Properties': json.dumps(props, default=str)}}, CT)
        except Twin__Error as e:
            return action, json_error(e, request, CT)
        except ValueError:
            return action, json_error(Twin__Error(400, 'SerializationException', 'the body is not JSON'), request, CT)

    # ── S3 ──────────────────────────────────────────────────────────────
    def buckets(self):
        vfs = self.twin.vfs
        if not vfs.exists('/s3'):
            return []
        return sorted(e['name'] for e in vfs.list_folder('/s3') if e['type'] == 'folder' and vfs.exists(f'/s3/{e["name"]}/bucket.json'))

    def list_bucket(self, region):
        return [(b, {'BucketName': b}) for b in self.buckets()]                # every region's, as AWS answers

    def get_bucket(self, region, name):
        if name not in self.buckets():
            return None
        info = json.loads(self.twin.vfs.read_file(f'/s3/{name}/bucket.json'))
        where = info.get('Region') or self.twin.region
        out = {'BucketName': name, 'Arn': f'arn:aws:s3:::{name}', 'DomainName': f'{name}.s3.amazonaws.com',
               'RegionalDomainName': f'{name}.s3.{where}.amazonaws.com', 'DualStackDomainName': f'{name}.s3.dualstack.{where}.amazonaws.com',
               'WebsiteURL': f'http://{name}.s3-website.{where}.amazonaws.com'}
        if info.get('Versioning') in ('Enabled', 'Suspended'):
            out['VersioningConfiguration'] = {'Status': info['Versioning']}
        return out

    # ── Lambda ──────────────────────────────────────────────────────────
    def list_function(self, region):
        return [(c['FunctionName'], {'FunctionName': c['FunctionName']}) for c in self.twin.services['lambda'].functions(region)]

    def get_function(self, region, name):
        try:
            c = self.twin.services['lambda'].config(region, unquote(name))
        except Twin__Error:
            return None
        keep = ('FunctionName', 'Runtime', 'Handler', 'Role', 'MemorySize', 'Timeout', 'Description', 'Architectures', 'PackageType',
                'EphemeralStorage', 'LoggingConfig', 'TracingConfig', 'Environment')
        return dict({k: c[k] for k in keep if k in c}, Arn=c['FunctionArn'])

    # ── IAM ─────────────────────────────────────────────────────────────
    def list_role(self, region):
        iam = self.twin.services['iam']
        return [(f[:-5], {'RoleName': f[:-5]}) for f in sorted(iam.store.files('roles'))]

    def get_role(self, region, name):
        r = self.twin.services['iam'].store.read_json('roles', f'{name}.json')
        if r is None:
            return None
        return {'RoleName': r['RoleName'], 'Arn': r['Arn'], 'RoleId': r['RoleId'], 'Path': r['Path'], 'Description': r.get('Description', ''),
                'MaxSessionDuration': r['MaxSessionDuration'], 'AssumeRolePolicyDocument': json.loads(r['AssumeRolePolicyDocument']),
                'ManagedPolicyArns': r['AttachedPolicies'],
                'Policies': [{'PolicyName': k, 'PolicyDocument': json.loads(v)} for k, v in r['InlinePolicies'].items()]}

    # ── EventBridge ─────────────────────────────────────────────────────
    def list_rule(self, region):
        ev = self.twin.services['events']
        rules = [ev.store.read_json(region, 'rules', f) for f in sorted(ev.store.files(region, 'rules'))]
        return [(r['Arn'], {'Arn': r['Arn']}) for r in rules]

    def get_rule(self, region, ident):
        name = ident.split('/')[-1]
        r = self.twin.services['events'].store.read_json(region, 'rules', f'{name}.json')
        if r is None:
            return None
        return {k: r[k] for k in ('Name', 'Arn', 'ScheduleExpression', 'EventPattern', 'State', 'Description', 'EventBusName', 'Targets') if r.get(k) not in (None, '')}

    # ── CloudFront ──────────────────────────────────────────────────────
    def list_distribution(self, region):
        cf = self.twin.services['cloudfront']
        return [(f[:-5], {'Id': f[:-5]}) for f in sorted(cf.store.files('distributions'))]

    def get_distribution(self, region, ident):
        d = self.twin.services['cloudfront'].store.read_json('distributions', f'{ident}.json')
        if d is None:
            return None
        return {'Id': d['Id'], 'DomainName': d['DomainName'], 'DistributionConfig': {'Enabled': d['Enabled'], 'CallerReference': d['CallerReference']}}


TYPES = {'AWS::S3::Bucket': 'bucket', 'AWS::Lambda::Function': 'function', 'AWS::IAM::Role': 'role',
         'AWS::Events::Rule': 'rule', 'AWS::CloudFront::Distribution': 'distribution'}
