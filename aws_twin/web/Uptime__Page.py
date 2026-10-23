"""The uptime page's Python side: every button on uptime/index.html calls one method here, through
call(name, args_json), and every method is Uptime__Deploy's boto3, which the twin answers, or the
account does in live mode. The page itself never talks to AWS.

The page enters Python with callPromising, so the Lambda twin can run the Node.js function through
the browser's JSPI. Reading a real append lane, and decrypting reports, is the page's JavaScript:
the key that decrypts them never reaches Python."""
import json
import os
import time

from aws_twin.apps.uptime.Uptime__Deploy import Uptime__Deploy
from aws_twin.core.Twin                  import Twin
from aws_twin.core.Twin__Browser_Http    import Twin__Browser_Blocked
from aws_twin.vfs.Vfs__Provider__Memory  import Vfs__Provider__Memory

SESSION_ENV = ('AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN', 'AWS_DEFAULT_REGION')
LIVE_ROUTES = {s: 'live' for s in ('sts', 'iam', 'lambda', 'events', 'cloudfront')}
TWIN_ONLY   = {'twin_lane', 'internet', 'fire', 'lane', 'mark'}


class Uptime__Page:
    def __init__(self):
        self.twin, self.live, self.deploy, self.vfs = None, False, None, None

    # ── lifecycle ───────────────────────────────────────────────────────
    def start(self):
        self.vfs = Vfs__Provider__Memory()
        return self.use_twin()

    def _swap(self, twin):
        if self.twin is not None:
            self.twin.deactivate()
        self.twin = twin.activate()

    def use_twin(self):
        for k in SESSION_ENV:
            os.environ.pop(k, None)
        self.live = False
        self._swap(Twin(vfs=self.vfs, keep_bodies=False))
        return {'mode': 'twin', 'account': self.twin.account_id}

    def use_live(self, session_json):
        s = json.loads(session_json)
        if not s.get('sessionToken'):
            raise ValueError('a live session needs a session token: paste one from the AWS access portal on /sessions/')
        os.environ.update({'AWS_ACCESS_KEY_ID': s['accessKeyId'], 'AWS_SECRET_ACCESS_KEY': s['secretAccessKey'],
                           'AWS_SESSION_TOKEN': s['sessionToken'], 'AWS_DEFAULT_REGION': s.get('region') or 'eu-west-2'})
        self.live = True
        self._swap(Twin(vfs=self.vfs, set_credentials=False, routes=LIVE_ROUTES))
        import boto3
        who = boto3.client('sts', region_name=os.environ['AWS_DEFAULT_REGION']).get_caller_identity()
        return {'mode': 'live', 'account': who['Account'], 'arn': who['Arn']}

    def call(self, name, args_json='{}'):
        """Run one method; return its result or error, and the AWS operations it caused."""
        args, before, started = json.loads(args_json), len(self.twin.traffic.records), time.time()
        try:
            if name == 'use_live':
                result = self.use_live(**args)
            elif name == 'use_twin':
                result = self.use_twin()
            else:
                if self.live and name in TWIN_ONLY:
                    raise ValueError(f'{name} is the twin\'s: in live mode the lane is read by the page, and the schedule is AWS\'s')
                result = getattr(self, 'op_' + name)(**args)
            error = None
        except Exception as e:
            result = None
            code   = getattr(e, 'response', {}).get('Error', {}).get('Code') if hasattr(e, 'response') else None
            if isinstance(e, Twin__Browser_Blocked):
                code = 'BrowserBlocked'
            error  = {'type': type(e).__name__, 'code': code or type(e).__name__, 'message': str(e)}
        traffic = [{k: r[k] for k in ('service', 'operation', 'method', 'url', 'status', 'ms', 'target')} for r in self.twin.traffic.records[before:]]
        return json.dumps({'result': result, 'error': error, 'traffic': traffic, 'ms': round((time.time() - started) * 1000),
                           'mode': 'live' if self.live else 'twin'}, default=str)

    # ── configuration ───────────────────────────────────────────────────
    def op_configure(self, regions, targets, recipient_key='', append_url='', append_token='', controller_key='',
                     schedule='rate(15 minutes)', function_url=False, cloudfront=False):
        self.deploy = Uptime__Deploy(regions=regions, targets=targets, recipient_key=recipient_key, append_url=append_url,
                                     append_token=append_token, controller_key=controller_key, schedule=schedule,
                                     function_url=function_url or cloudfront, cloudfront=cloudfront)
        env = self.deploy.environment()
        return {'regions': regions, 'targets': len(targets), 'environment_bytes': sum(len(k) + len(v) for k, v in env.items()),
                'package_bytes': len(self.deploy.package())}

    def op_handler_source(self):
        return Uptime__Deploy.handler_source()

    # ── the twin's side: a lane, and an internet ────────────────────────
    def op_twin_lane(self):
        lanes = self.twin.append_lanes
        known = getattr(self, '_lane', None)
        if known and lanes.store.exists(known['vault_id'], 'lane.json'):
            return known
        self._lane = lanes.create_lane()
        return self._lane

    def op_internet(self, answers):
        self.twin.internet.forget()
        for a in answers:
            self.twin.internet.answer(a['target'], status=a.get('status') or 200, ms=a.get('ms', 40), error=a.get('error') or None)
        return {'answers': len(answers)}

    # ── deploy, step by step (the page waits between them) ──────────────
    def op_role(self):
        return self.deploy.ensure_role()

    def op_function(self, region, role_arn):
        return self.deploy.put_function(region, role_arn)

    def op_state(self, region):
        return self.deploy.function_state(region)

    def op_config(self, region, role_arn):
        return self.deploy.put_config(region, role_arn)

    def op_schedule(self, region, function_arn):
        return self.deploy.put_schedule(region, function_arn)

    def op_url(self, region):
        return self.deploy.put_url(region)

    def op_cloudfront(self, urls):
        return self.deploy.put_cloudfront(urls)

    # ── use ─────────────────────────────────────────────────────────────
    def op_invoke(self, region, targets=None):
        return self.deploy.invoke(region, targets)

    def op_fire(self, region):
        fired = self.twin.services['events'].fire(region, f'{self.deploy.name}-schedule')
        for i in fired['invocations']:
            if 'result' in i:
                i['result'] = {k: i['result'][k] for k in ('result', 'error', 'logs', 'ms')}
        return fired

    def op_functions(self):
        out = []
        for region in self.deploy.regions:
            try:
                state = self.deploy.function_state(region)
            except Exception as e:
                state = {'state': 'not deployed' if 'ResourceNotFound' in type(e).__name__ or 'Function not found' in str(e) else str(e)}
            row = {'region': region, **state}
            if not self.live:
                row['invocations'] = len(self.twin.services['lambda'].invocations(region, self.deploy.name))
            out.append(row)
        return out

    def op_lane(self, vault_id, enum_key):
        return self.twin.append_lanes.fetch(vault_id, enum_key)

    def op_mark(self, vault_id, enum_key, file_ids):
        return self.twin.append_lanes.mark_processed(vault_id, enum_key, file_ids)

    # ── teardown ────────────────────────────────────────────────────────
    def op_teardown_region(self, region):
        return self.deploy.teardown_region(region)

    def op_teardown_cloudfront(self):
        return self.deploy.teardown_cloudfront()

    def op_teardown_role(self):
        return self.deploy.teardown_role()


page = None


def uptime_call(name, args_json='{}'):
    """The function the page calls (with callPromising)."""
    global page
    if page is None:
        page = Uptime__Page()
        page.start()
    return page.call(name, args_json)
