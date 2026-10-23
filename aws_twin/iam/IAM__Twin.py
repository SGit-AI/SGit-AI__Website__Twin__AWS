"""The IAM twin, roles only: what a deployment needs to give a Lambda function an execution role.

    /iam/roles/<name>.json      the role, its trust policy, attached policy ARNs, inline policies

Covered: CreateRole, GetRole, DeleteRole, ListRoles, AttachRolePolicy, DetachRolePolicy,
ListAttachedRolePolicies, PutRolePolicy, GetRolePolicy, DeleteRolePolicy, ListRolePolicies.
Errors as IAM sends them: EntityAlreadyExists, NoSuchEntity, DeleteConflict, MalformedPolicyDocument.
Not covered, and answered 501 NotImplemented by name: everything else (users, groups, managed
policies as objects, the policy simulator). The twin does not evaluate policies."""
import json
import re
from urllib.parse import parse_qsl, quote

from aws_twin.core.Twin__Http    import Twin__Response
from aws_twin.core.Twin__Service import Twin__Error, Twin__Store, iso_now, random_id
from aws_twin.s3.S3__Xml         import x

IAM_NS    = 'https://iam.amazonaws.com/doc/2010-05-08/'
ROLE_NAME = re.compile(r'^[\w+=,.@-]{1,64}$')


class IAM__Twin:
    service = 'iam'

    def __init__(self, twin):
        self.twin  = twin
        self.store = Twin__Store(twin.vfs, 'iam')

    # ── dispatch ────────────────────────────────────────────────────────
    def handle(self, request):
        params = dict(request.query)
        if request.body:
            params.update(parse_qsl(request.body.decode('utf-8', 'replace'), keep_blank_values=True))
        action = params.get('Action', 'Unknown')
        op     = getattr(self, 'op_' + action, None)
        try:
            if op is None:
                raise Twin__Error(501, 'NotImplemented', f'the twin does not implement iam {action}')
            inner = op(params)
            body  = (f'<{action}Response xmlns="{IAM_NS}">' + (f'<{action}Result>{inner}</{action}Result>' if inner is not None else '') +
                     f'<ResponseMetadata>{x("RequestId", request.request_id)}</ResponseMetadata></{action}Response>')
            return action, Twin__Response(200, {'content-type': 'text/xml'}, body)
        except Twin__Error as e:
            body = (f'<ErrorResponse xmlns="{IAM_NS}"><Error><Type>Sender</Type>{x("Code", e.code)}{x("Message", e.message)}</Error>'
                    f'{x("RequestId", request.request_id)}</ErrorResponse>')
            return action, Twin__Response(e.status, {'content-type': 'text/xml'}, body)

    # ── the store ───────────────────────────────────────────────────────
    def role(self, name):
        role = self.store.read_json('roles', f'{name}.json')
        if role is None:
            raise Twin__Error(404, 'NoSuchEntity', f'The role with name {name} cannot be found.')
        return role

    def role_by_arn(self, arn):
        """For other twins: the role an ARN names, or None."""
        m = re.match(r'^arn:aws:iam::(\d{12}):role/(?:.*/)?([\w+=,.@-]+)$', arn or '')
        return self.store.read_json('roles', f'{m.group(2)}.json') if m and m.group(1) == self.twin.account_id else None

    def save(self, role):
        self.store.write_json(role, 'roles', f'{role["RoleName"]}.json')

    def role_xml(self, role):
        return x('Path', role['Path']) + x('RoleName', role['RoleName']) + x('RoleId', role['RoleId']) + x('Arn', role['Arn']) + \
               x('CreateDate', role['CreateDate']) + x('AssumeRolePolicyDocument', quote(role['AssumeRolePolicyDocument'])) + \
               (x('Description', role['Description']) if role.get('Description') else '') + x('MaxSessionDuration', role['MaxSessionDuration'])

    @staticmethod
    def policy_document(text, what):
        try:
            doc = json.loads(text)
        except (TypeError, ValueError):
            raise Twin__Error(400, 'MalformedPolicyDocument', f'{what} is not valid JSON.')
        if not isinstance(doc, dict) or 'Statement' not in doc:
            raise Twin__Error(400, 'MalformedPolicyDocument', f'{what} has no Statement.')
        return text

    # ── operations ──────────────────────────────────────────────────────
    def op_CreateRole(self, p):
        name = p.get('RoleName', '')
        if not ROLE_NAME.match(name):
            raise Twin__Error(400, 'ValidationError', f'Invalid role name: {name!r}')
        if self.store.exists('roles', f'{name}.json'):
            raise Twin__Error(409, 'EntityAlreadyExists', f'Role with name {name} already exists.')
        path = p.get('Path', '/')
        role = {'RoleName': name, 'Path': path, 'RoleId': 'AROA' + random_id(17), 'Arn': f'arn:aws:iam::{self.twin.account_id}:role{path}{name}',
                'CreateDate': iso_now(millis=False), 'Description': p.get('Description', ''), 'MaxSessionDuration': int(p.get('MaxSessionDuration', 3600)),
                'AssumeRolePolicyDocument': self.policy_document(p.get('AssumeRolePolicyDocument'), 'The trust policy'),
                'AttachedPolicies': [], 'InlinePolicies': {}}
        self.save(role)
        return f'<Role>{self.role_xml(role)}</Role>'

    def op_GetRole(self, p):
        return f'<Role>{self.role_xml(self.role(p.get("RoleName", "")))}</Role>'

    def op_ListRoles(self, p):
        roles = [self.store.read_json('roles', f) for f in sorted(self.store.files('roles'))]
        return x('IsTruncated', 'false') + '<Roles>' + ''.join(f'<member>{self.role_xml(r)}</member>' for r in roles) + '</Roles>'

    def op_DeleteRole(self, p):
        role = self.role(p.get('RoleName', ''))
        if role['AttachedPolicies'] or role['InlinePolicies']:
            raise Twin__Error(409, 'DeleteConflict', 'Cannot delete entity, must detach all policies first.')
        self.store.delete('roles', f'{role["RoleName"]}.json')

    def op_AttachRolePolicy(self, p):
        role, arn = self.role(p.get('RoleName', '')), p.get('PolicyArn', '')
        if not re.match(r'^arn:aws:iam::(aws|\d{12}):policy/', arn):
            raise Twin__Error(400, 'InvalidInput', f'ARN {arn} is not valid.')
        if arn not in role['AttachedPolicies']:
            role['AttachedPolicies'].append(arn)
            self.save(role)

    def op_DetachRolePolicy(self, p):
        role, arn = self.role(p.get('RoleName', '')), p.get('PolicyArn', '')
        if arn not in role['AttachedPolicies']:
            raise Twin__Error(404, 'NoSuchEntity', f'Policy {arn} was not found.')
        role['AttachedPolicies'].remove(arn)
        self.save(role)

    def op_ListAttachedRolePolicies(self, p):
        role = self.role(p.get('RoleName', ''))
        items = ''.join(f'<member>{x("PolicyName", a.split("/")[-1])}{x("PolicyArn", a)}</member>' for a in role['AttachedPolicies'])
        return f'<AttachedPolicies>{items}</AttachedPolicies>' + x('IsTruncated', 'false')

    def op_PutRolePolicy(self, p):
        role = self.role(p.get('RoleName', ''))
        role['InlinePolicies'][p.get('PolicyName', '')] = self.policy_document(p.get('PolicyDocument'), 'The policy document')
        self.save(role)

    def op_GetRolePolicy(self, p):
        role, name = self.role(p.get('RoleName', '')), p.get('PolicyName', '')
        if name not in role['InlinePolicies']:
            raise Twin__Error(404, 'NoSuchEntity', f'The role policy with name {name} cannot be found.')
        return x('RoleName', role['RoleName']) + x('PolicyName', name) + x('PolicyDocument', quote(role['InlinePolicies'][name]))

    def op_DeleteRolePolicy(self, p):
        role, name = self.role(p.get('RoleName', '')), p.get('PolicyName', '')
        if role['InlinePolicies'].pop(name, None) is None:
            raise Twin__Error(404, 'NoSuchEntity', f'The role policy with name {name} cannot be found.')
        self.save(role)

    def op_ListRolePolicies(self, p):
        role = self.role(p.get('RoleName', ''))
        return '<PolicyNames>' + ''.join(x('member', n) for n in sorted(role['InlinePolicies'])) + '</PolicyNames>' + x('IsTruncated', 'false')
