"""Check a pasted session against the real account, from the browser.

The one call is STS GetCallerIdentity, which needs no permission and which STS answers a
browser (measured: Access-Control-Allow-Origin: *). It goes through the twin with the sts
route set to 'live': botocore signs it with the pasted credentials, the twin's hook sends
it on to AWS (in Pyodide, urllib3 uses the browser's fetch), and the request and answer are
recorded like any other. Nothing else is sent anywhere."""
import json

from aws_twin.core.Twin import Twin


def check_session(session_json):
    s    = json.loads(session_json)
    twin = Twin(routes={'sts': 'live'}, set_credentials=False)
    with twin:
        import boto3
        sts = boto3.client('sts', region_name=s.get('region') or 'eu-west-2',
                           aws_access_key_id=s['accessKeyId'], aws_secret_access_key=s['secretAccessKey'],
                           aws_session_token=s.get('sessionToken'))
        try:
            who = sts.get_caller_identity()
            out = {'ok': True, 'account': who['Account'], 'arn': who['Arn'], 'user_id': who['UserId']}
        except Exception as e:
            err = getattr(e, 'response', {}).get('Error', {}) if hasattr(e, 'response') else {}
            out = {'ok': False, 'code': err.get('Code') or type(e).__name__, 'message': err.get('Message') or str(e)}
    out['traffic'] = [{k: r[k] for k in ('target', 'service', 'operation', 'method', 'url', 'status', 'signed', 'ms')} for r in twin.traffic.records]
    return json.dumps(out)
