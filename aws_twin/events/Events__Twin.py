"""The EventBridge twin: scheduled rules on the default bus, and their targets, per region.

    /events/<region>/rules/<name>.json      the rule, its schedule or pattern, state, targets

Covered (JSON 1.1, X-Amz-Target AWSEvents.*): PutRule, DescribeRule, ListRules, EnableRule,
DisableRule, DeleteRule, PutTargets, ListTargetsByRule, RemoveTargets.
Twin-only: fire(region, rule) does what the schedule does when it comes round: it invokes each
Lambda target with a scheduled event, and, as EventBridge does, only when the function's resource
policy lets events.amazonaws.com invoke it for this rule. A refused or failed invocation is
returned, where AWS would only count it in a metric.
Not covered: custom buses, event patterns matched against put_events, other target types."""
import json
import re
import uuid

from aws_twin.core.Twin__Service import Twin__Error, Twin__Store, iso_now, json_error, json_response, region_of

CT        = 'application/x-amz-json-1.1'
RULE_NAME = re.compile(r'^[\.\-_A-Za-z0-9]{1,64}$')
SCHEDULE  = re.compile(r'^(rate\(\d+ (minute|minutes|hour|hours|day|days)\)|cron\(.+\))$')


class Events__Twin:
    service = 'events'

    def __init__(self, twin):
        self.twin  = twin
        self.store = Twin__Store(twin.vfs, 'events')

    def handle(self, request):
        action = (request.header('x-amz-target') or '.Unknown').split('.')[-1]
        region = region_of(request, self.twin.region)
        op     = getattr(self, 'op_' + action, None)
        try:
            if op is None:
                raise Twin__Error(501, 'NotImplemented', f'the twin does not implement events {action}')
            params = json.loads(request.body or b'{}')
            return action, json_response(200, op(region, params) or {}, CT)
        except Twin__Error as e:
            return action, json_error(e, request, CT)
        except ValueError:
            return action, json_error(Twin__Error(400, 'SerializationException', 'the body is not JSON'), request, CT)

    # ── the store ───────────────────────────────────────────────────────
    def rule(self, region, name, bus='default'):
        rule = self.store.read_json(region, 'rules', f'{name}.json')
        if rule is None:
            raise Twin__Error(400, 'ResourceNotFoundException', f'Rule {name} does not exist on EventBus {bus}.')
        return rule

    def save(self, region, rule):
        self.store.write_json(rule, region, 'rules', f'{rule["Name"]}.json')

    @staticmethod
    def public(rule):
        return {k: v for k, v in rule.items() if k != 'Targets'}

    # ── operations ──────────────────────────────────────────────────────
    def op_PutRule(self, region, p):
        name = p.get('Name', '')
        if not RULE_NAME.match(name):
            raise Twin__Error(400, 'ValidationException', f'Rule name {name!r} is not valid.')
        if not p.get('ScheduleExpression') and not p.get('EventPattern'):
            raise Twin__Error(400, 'ValidationException', 'Parameter(s) ScheduleExpression or EventPattern must be specified.')
        if p.get('ScheduleExpression') and not SCHEDULE.match(p['ScheduleExpression']):
            raise Twin__Error(400, 'ValidationException', 'Parameter ScheduleExpression is not valid.')
        old  = self.store.read_json(region, 'rules', f'{name}.json') or {}
        arn  = f'arn:aws:events:{region}:{self.twin.account_id}:rule/{name}'
        rule = {'Name': name, 'Arn': arn, 'EventBusName': 'default', 'State': p.get('State', 'ENABLED'),
                'Description': p.get('Description', ''), 'ScheduleExpression': p.get('ScheduleExpression'),
                'EventPattern': p.get('EventPattern'), 'Targets': old.get('Targets', [])}
        self.save(region, {k: v for k, v in rule.items() if v is not None})
        return {'RuleArn': arn}

    def op_DescribeRule(self, region, p):
        return dict(self.public(self.rule(region, p.get('Name', ''))), CreatedBy=self.twin.account_id)

    def op_ListRules(self, region, p):
        rules = [self.store.read_json(region, 'rules', f) for f in sorted(self.store.files(region, 'rules'))]
        prefix = p.get('NamePrefix', '')
        return {'Rules': [self.public(r) for r in rules if r['Name'].startswith(prefix)]}

    def op_EnableRule(self, region, p):
        rule = self.rule(region, p.get('Name', '')); rule['State'] = 'ENABLED'; self.save(region, rule)

    def op_DisableRule(self, region, p):
        rule = self.rule(region, p.get('Name', '')); rule['State'] = 'DISABLED'; self.save(region, rule)

    def op_DeleteRule(self, region, p):
        rule = self.rule(region, p.get('Name', ''))
        if rule['Targets']:
            raise Twin__Error(400, 'ValidationException', "Rule can't be deleted since it has targets.")
        self.store.delete(region, 'rules', f'{rule["Name"]}.json')

    def op_PutTargets(self, region, p):
        rule = self.rule(region, p.get('Rule', ''))
        for t in p.get('Targets', []):
            if not t.get('Id') or not t.get('Arn'):
                raise Twin__Error(400, 'ValidationException', 'A target needs an Id and an Arn.')
            rule['Targets'] = [old for old in rule['Targets'] if old['Id'] != t['Id']] + [t]
        self.save(region, rule)
        return {'FailedEntryCount': 0, 'FailedEntries': []}

    def op_ListTargetsByRule(self, region, p):
        return {'Targets': self.rule(region, p.get('Rule', ''))['Targets']}

    def op_RemoveTargets(self, region, p):
        rule = self.rule(region, p.get('Rule', ''))
        ids  = set(p.get('Ids', []))
        rule['Targets'] = [t for t in rule['Targets'] if t['Id'] not in ids]
        self.save(region, rule)
        return {'FailedEntryCount': 0, 'FailedEntries': []}

    # ── twin-only: the schedule comes round ─────────────────────────────
    def fire(self, region, name):
        rule = self.rule(region, name)
        if rule['State'] != 'ENABLED':
            return {'rule': name, 'fired': False, 'reason': 'the rule is disabled', 'invocations': []}
        event = {'version': '0', 'id': str(uuid.uuid4()), 'detail-type': 'Scheduled Event', 'source': 'aws.events',
                 'account': self.twin.account_id, 'time': iso_now(millis=False), 'region': region,
                 'resources': [rule['Arn']], 'detail': {}}
        lam, out = self.twin.services['lambda'], []
        for t in rule['Targets']:
            m = re.match(r'^arn:aws:lambda:([a-z0-9-]+):(\d{12}):function:([^:]+)', t['Arn'])
            if not m:
                out.append({'target': t['Id'], 'ok': False, 'reason': 'only Lambda targets are twinned'}); continue
            fn_region, _, fn = m.groups()
            if not lam.allows(fn_region, fn, 'events.amazonaws.com', rule['Arn']):
                out.append({'target': t['Id'], 'function': fn, 'ok': False,
                            'reason': "the function's resource policy does not let events.amazonaws.com invoke it for this rule (lambda add-permission)"})
                continue
            payload = t['Input'].encode() if t.get('Input') else json.dumps(event).encode()
            result  = lam.invoke_internal(fn_region, fn, payload)
            out.append({'target': t['Id'], 'function': fn, 'ok': result['error'] is None, 'result': result})
        return {'rule': name, 'fired': True, 'event': event, 'invocations': out}
