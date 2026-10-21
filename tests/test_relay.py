"""The local relay: it forwards signed requests unchanged, adds CORS for the page's origin only, refuses
anything that is not AWS, and holds no credentials. In CI the "AWS" behind it is the twin's own endpoint,
allowed for the test; AWS_TWIN_LIVE_TESTS=1 adds a call to real STS with invented keys."""
import http.client
import os

import boto3

from aws_twin                    import Twin
from aws_twin.core.Twin__Relay   import Twin__Relay
from tests.helpers               import IN_BROWSER, raises, skip

ORIGIN = 'https://aws.twin.sgit.ai'


def _raw(relay, method, headers, body=None):
    c = http.client.HTTPConnection('127.0.0.1', relay.port, timeout=10)
    c.request(method, '/relay', body=body, headers=headers)
    r = c.getresponse()
    out = (r.status, {k.lower(): v for k, v in r.getheaders()}, r.read())
    c.close()
    return out


def test_relay_policy():
    if IN_BROWSER:
        skip('the relay runs on the user\'s machine, not in the page')
    with Twin__Relay(port=0, quiet=True).start() as relay:
        status, h, _ = _raw(relay, 'OPTIONS', {'origin': ORIGIN, 'access-control-request-method': 'GET',
                                               'access-control-request-headers': 'authorization,x-amz-date,x-twin-target',
                                               'access-control-request-private-network': 'true'})
        assert status == 204 and h['access-control-allow-origin'] == ORIGIN and h['access-control-allow-private-network'] == 'true'
        c = http.client.HTTPConnection('127.0.0.1', relay.port, timeout=10); c.request('GET', '/health', headers={'origin': ORIGIN}); r = c.getresponse()
        assert r.status == 200 and b'"holds_credentials": false' in r.read() and r.getheader('access-control-allow-origin') == ORIGIN; c.close()
        status, h, _ = _raw(relay, 'OPTIONS', {'origin': 'https://evil.example', 'access-control-request-method': 'GET'})
        assert status == 403 and 'access-control-allow-origin' not in h
        status, _, body = _raw(relay, 'GET', {'origin': ORIGIN, 'x-twin-target': 'https://example.com/'})
        assert status == 400 and b'amazonaws.com' in body                      # not an open proxy
        status, _, body = _raw(relay, 'GET', {'origin': ORIGIN, 'x-twin-target': 'http://s3.amazonaws.com/'})
        assert status == 400                                                   # https only
        status, _, body = _raw(relay, 'GET', {'origin': 'https://evil.example', 'x-twin-target': 'https://sts.amazonaws.com/'})
        assert status == 403


def test_live_route_through_the_relay():
    """boto3 → the twin's live route → the relay → an endpoint (here the twin's own, standing in for AWS)."""
    if IN_BROWSER:
        skip('needs sockets: the relay and the stand-in endpoint')
    upstream = Twin(set_credentials=False)
    with upstream.serve(port=0) as server:
        with Twin__Relay(port=0, quiet=True, allow_hosts={f'127.0.0.1:{server.port}'}).start() as relay:
            with Twin(routes={'s3': 'live'}, live_relay=relay.url, set_credentials=False) as client_side:
                s3 = boto3.client('s3', region_name='eu-west-2', endpoint_url=server.url,
                                  aws_access_key_id='k', aws_secret_access_key='s', aws_session_token='t')
                s3.create_bucket(Bucket='via-the-relay', CreateBucketConfiguration={'LocationConstraint': 'eu-west-2'})
                s3.put_object(Bucket='via-the-relay', Key='a b/c.txt', Body=b'relayed', ContentType='text/plain', Metadata={'m': '1'})
                got = s3.get_object(Bucket='via-the-relay', Key='a b/c.txt')
                assert got['Body'].read() == b'relayed' and got['ContentType'] == 'text/plain' and got['Metadata'] == {'m': '1'}
                assert [o['Key'] for o in s3.list_objects_v2(Bucket='via-the-relay')['Contents']] == ['a b/c.txt']
                raises('NoSuchKey', lambda: s3.get_object(Bucket='via-the-relay', Key='nope'))
                s3.put_object(Bucket='via-the-relay', Key='untyped', Body=b'x')       # no Content-Type: none must be invented
                assert s3.head_object(Bucket='via-the-relay', Key='untyped')['ContentType'] == 'binary/octet-stream'
            assert {r['target'] for r in client_side.traffic.records} == {'live'}
            assert [r['operation'] for r in client_side.traffic.records][:3] == ['CreateBucket', 'PutObject', 'GetObject']   # named, though the twin did not answer
    ops = upstream.traffic.summary()['operations']
    assert ops['s3.PutObject'] == 2 and ops['s3.CreateBucket'] == 1                  # the requests arrived, signed, unchanged


def test_live_sts_through_the_relay_with_invented_keys():
    if IN_BROWSER:
        skip('needs sockets')
    if os.environ.get('AWS_TWIN_LIVE_TESTS') != '1':
        skip('opt-in: set AWS_TWIN_LIVE_TESTS=1 (calls AWS STS with invented keys, through the relay)')
    with Twin__Relay(port=0, quiet=True).start() as relay:
        with Twin(routes={'sts': 'live', 's3': 'live'}, live_relay=relay.url, set_credentials=False) as twin:
            kw = dict(region_name='eu-west-2', aws_access_key_id='INVENTED-KEY-FOR-A-TEST', aws_secret_access_key='invented', aws_session_token='invented')
            raises('InvalidClientTokenId', boto3.client('sts', **kw).get_caller_identity)
            raises('InvalidAccessKeyId', boto3.client('s3', **kw).list_buckets)            # ListBuckets: what a browser cannot do directly
            assert [r['status'] for r in twin.traffic.records] == [403, 403]


def test_s3_browser_live_mode_is_read_only_by_default():
    from aws_twin.web.S3__Browser import S3__Browser
    import json
    b = S3__Browser()
    b.start('[]')
    try:
        b.live = True                                                         # as use_live would leave it, without AWS
        out = json.loads(b.call('delete_bucket', json.dumps({'name': 'anything'})))
        assert out['call']['error']['code'] == 'ReadOnly' and out['call']['traffic'] == []   # refused before any request
        b.allow_writes = True
        out = json.loads(b.call('delete_bucket', json.dumps({'name': 'not-there-bucket'})))
        assert out['call']['error']['code'] == 'NoSuchBucket'                 # allowed through (here, to the twin)
    finally:
        b.use_twin()
        b.twin.deactivate()
