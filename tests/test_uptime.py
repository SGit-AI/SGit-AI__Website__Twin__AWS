"""The uptime check, end to end in the twin: deployed with Uptime__Deploy's boto3 to three regions,
invoked and fired on its schedule, against the twin's internet; its reports land in an sgit append
lane twin and are decrypted here exactly as sgit's PKI__Crypto.hybrid_decrypt does (RSA-OAEP
SHA-256 unwrapping an AES-256-GCM key). The decryption needs the cryptography package (a test
dependency only; the function has none), and is skipped without it."""
import base64
import json
import time

import boto3

from aws_twin                              import Twin
from aws_twin.apps.uptime.Uptime__Deploy   import Uptime__Deploy
from tests.helpers                         import has_module, needs_node_runtime, raises, skip, skip_if_twin_unavailable

REGIONS = ['eu-west-2', 'us-east-1', 'ap-southeast-2']
_keys   = {}


def keys():
    """An sgit-shaped identity: RSA-4096 for encryption, P-256 for signing, made once per run."""
    if not has_module('cryptography'):
        skip('needs the cryptography package to make and use keys (a test dependency, not the function\'s)')
    if not _keys:
        from cryptography.hazmat.primitives.asymmetric import rsa, ec
        from cryptography.hazmat.primitives            import serialization
        enc  = rsa.generate_private_key(public_exponent=65537, key_size=4096)
        sign = ec.generate_private_key(ec.SECP256R1())
        pem  = lambda k: k.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
        _keys.update(enc=enc, sign=sign, bundle=json.dumps({'v': 1, 'encrypt': pem(enc), 'sign': pem(sign), 'label': 'uptime test'}), sign_pem=pem(sign))
    return _keys


def sgit_decrypt(private_key, enc_text):
    """sgit's hybrid_decrypt, as shipped in sgit-ai 0.24.0 (sgit_ai/crypto/PKI__Crypto.py)."""
    from cryptography.hazmat.primitives.asymmetric   import padding
    from cryptography.hazmat.primitives               import hashes
    from cryptography.hazmat.primitives.ciphers.aead  import AESGCM
    env = json.loads(base64.b64decode(enc_text))
    assert env['v'] == 2 and set(env) == {'v', 'w', 'i', 'c'}
    aes = private_key.decrypt(base64.b64decode(env['w']), padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
    return json.loads(AESGCM(aes).decrypt(base64.b64decode(env['i']), base64.b64decode(env['c']), None))


def reports(twin, lane):
    """The lane, read as its owner would: list and fetch with the enum key; each payload is base64 of the .enc text."""
    out = []
    for entry in twin.append_lanes.fetch(lane['vault_id'], lane['enum_key']):
        out.append(sgit_decrypt(keys()['enc'], base64.b64decode(entry['content']).decode()))
    return out


def deployed(twin, **kw):
    lane = twin.append_lanes.create_lane()
    twin.internet.answer('https://sgit.ai/', status=200, ms=5)
    twin.internet.answer('https://down.example/', status=503, ms=5)
    twin.internet.answer('unreachable.example', error='ECONNREFUSED')
    d = Uptime__Deploy(regions=REGIONS, targets=['https://sgit.ai/', 'https://down.example/'], recipient_key=keys()['bundle'],
                       append_url=lane['write_url'], append_token=lane['append_token'], **kw)
    return d, lane, d.deploy(wait=0)


def test_deploy_invoke_and_read_the_reports():
    needs_node_runtime()
    with Twin() as twin:
        d, lane, steps = deployed(twin)
        assert [s['step'] for s in steps] == ['role'] + ['function', 'schedule'] * 3
        for region in REGIONS:
            conf = boto3.client('lambda', region_name=region).get_function_configuration(FunctionName='aws-twin-uptime')
            assert conf['Runtime'] == 'nodejs22.x' and conf['Handler'] == 'index.handler' and 'UPTIME_APPEND_TOKEN' in conf['Environment']['Variables']
        out = d.invoke('eu-west-2')
        skip_if_twin_unavailable(out['payload'])
        assert out['function_error'] is None, out
        p = out['payload']
        assert p['region'] == 'eu-west-2' and p['trigger'] == 'invoke' and (p['up'], p['down']) == (1, 1)
        assert p['submitted'] == {'ok': True, 'status': 200, 'bytes': p['submitted']['bytes']}
        assert {r['url']: r['status'] for r in p['results']} == {'https://sgit.ai/': 200, 'https://down.example/': 503}
        out = d.invoke('us-east-1', targets=['https://unreachable.example/', 'http://169.254.169.254/latest/meta-data', 'file:///etc/passwd'])
        errors = [r['error'] for r in out['payload']['results']]
        assert 'ECONNREFUSED' in errors[0] and errors[1] == 'refused: a private address' and errors[2] == 'refused: only http and https'
        for region in REGIONS:
            fired = twin.services['events'].fire(region, 'aws-twin-uptime-schedule')
            assert fired['invocations'][0]['ok'], fired
        got = reports(twin, lane)
        assert len(got) == 5 and sorted(r['trigger'] for r in got) == ['invoke', 'invoke', 'schedule', 'schedule', 'schedule']
        assert {r['region'] for r in got if r['trigger'] == 'schedule'} == set(REGIONS)
        first = next(r for r in got if r['region'] == 'eu-west-2' and r['trigger'] == 'invoke')
        assert first['kind'] == 'aws.twin-uptime/1' and first['function'] == 'aws-twin-uptime' and len(first['results']) == 2
        ids = [e['file_id'] for e in twin.append_lanes.list(lane['vault_id'], lane['enum_key'])]
        assert twin.append_lanes.mark_processed(lane['vault_id'], lane['enum_key'], ids)['missing'] == []
        assert twin.append_lanes.list(lane['vault_id'], lane['enum_key']) == []


def test_a_wrong_token_is_refused_by_the_lane():
    needs_node_runtime()
    with Twin() as twin:
        d, lane, _ = deployed(twin)
        d.append_token = 'ab' * 32                                                          # not an anchor of the lane
        d.put_config('eu-west-2')
        out = d.invoke('eu-west-2')
        skip_if_twin_unavailable(out['payload'])
        assert out['payload']['submitted'] == {'ok': False, 'status': 404, 'bytes': out['payload']['submitted']['bytes']}
        assert twin.append_lanes.list(lane['vault_id'], lane['enum_key']) == []


def test_function_url_requests_must_be_signed_by_the_controller():
    needs_node_runtime()
    k = keys()                                                                             # skips without cryptography
    from cryptography.hazmat.primitives.asymmetric import ec, utils
    from cryptography.hazmat.primitives            import hashes
    with Twin() as twin:
        d, lane, _ = deployed(twin, controller_key=k['sign_pem'], function_url=True)
        lam = boto3.client('lambda', region_name='eu-west-2')

        def url_event(body, ts=None, key=k['sign']):
            ts  = int(time.time()) if ts is None else ts
            r, s = utils.decode_dss_signature(key.sign(f'{ts}\n{body}'.encode(), ec.ECDSA(hashes.SHA256())))
            sig = base64.b64encode(r.to_bytes(32, 'big') + s.to_bytes(32, 'big')).decode()          # raw r||s, as sgit and WebCrypto sign
            return {'version': '2.0', 'rawPath': '/', 'headers': {'x-uptime-ts': str(ts), 'x-uptime-sig': sig, 'content-type': 'application/json'},
                    'requestContext': {'http': {'method': 'POST', 'path': '/'}}, 'body': body, 'isBase64Encoded': False}

        def call(event):
            return json.loads(lam.invoke(FunctionName='aws-twin-uptime', Payload=json.dumps(event))['Payload'].read())

        body = json.dumps({'targets': ['https://sgit.ai/']})
        ok = call(url_event(body))
        skip_if_twin_unavailable(ok)
        assert ok['statusCode'] == 200 and json.loads(ok['body'])['up'] == 1 and json.loads(ok['body'])['trigger'] == 'url'
        tampered = url_event(body); tampered['body'] = json.dumps({'targets': ['https://down.example/']})
        assert call(tampered)['statusCode'] == 403
        assert call(url_event(body, ts=int(time.time()) - 3600))['statusCode'] == 403             # outside five minutes
        assert call(url_event(body, key=ec.generate_private_key(ec.SECP256R1())))['statusCode'] == 403
        url = lam.get_function_url_config(FunctionName='aws-twin-uptime')
        assert url['AuthType'] == 'NONE' and url['Cors']['AllowOrigins'] == ['https://aws.twin.sgit.ai']


def test_cloudfront_in_front_of_every_region_and_teardown():
    with Twin() as twin:
        lane = twin.append_lanes.create_lane()
        d = Uptime__Deploy(regions=REGIONS, targets=['https://sgit.ai/'], append_url=lane['write_url'], append_token=lane['append_token'],
                           recipient_key='-----BEGIN PUBLIC KEY-----\nMIIB\n-----END PUBLIC KEY-----', cloudfront=True)
        steps = d.deploy(wait=0)
        cf = next(s for s in steps if s['step'] == 'cloudfront')
        conf = boto3.client('cloudfront').get_distribution_config(Id=cf['id'])['DistributionConfig']
        assert [o['Id'] for o in conf['Origins']['Items']] == REGIONS
        assert [b['PathPattern'] for b in conf['CacheBehaviors']['Items']] == [f'/{r}/*' for r in REGIONS]
        assert all(o['DomainName'].endswith('.on.aws') for o in conf['Origins']['Items'])
        again = d.deploy(wait=0)                                                            # idempotent: updates, creates nothing new
        assert next(s for s in again if s['step'] == 'cloudfront')['action'] == 'updated'
        assert [f['FunctionName'] for f in boto3.client('lambda', region_name='us-east-1').list_functions()['Functions']] == ['aws-twin-uptime']
        assert d.teardown_cloudfront()['state'] == 'disabling' and d.teardown_cloudfront()['state'] == 'deleted'
        for step in d.teardown():
            assert step['state'] if 'state' in step else step['removed']
        for region in REGIONS:
            assert boto3.client('lambda', region_name=region).list_functions()['Functions'] == []
            assert boto3.client('events', region_name=region).list_rules()['Rules'] == []
        raises('NoSuchEntity', lambda: boto3.client('iam').get_role(RoleName='aws-twin-uptime-lambda'))


def test_environment_stays_inside_lambdas_4kb():
    d = Uptime__Deploy(targets=[f'https://site-{i}.example/with/a/long/path/to/check' for i in range(120)], recipient_key='x' * 800,
                       append_url='https://dev.send.sgraph.ai/api/vault/append/write/v', append_token='ab' * 32)
    raises_value = False
    try:
        d.environment()
    except ValueError as e:
        raises_value = '4 KB' in str(e)
    assert raises_value
