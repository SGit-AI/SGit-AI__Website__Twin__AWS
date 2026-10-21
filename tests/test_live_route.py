"""The live route against real AWS, with invented credentials: STS must answer
InvalidClientTokenId, which proves the request left, was signed, reached AWS and came back
through the twin's hook. Opt-in (it needs the network): AWS_TWIN_LIVE_TESTS=1."""
import os

import boto3

from aws_twin      import Twin
from tests.helpers import raises, skip


def test_live_sts_with_invented_keys():
    if os.environ.get('AWS_TWIN_LIVE_TESTS') != '1':
        skip('opt-in: set AWS_TWIN_LIVE_TESTS=1 (calls AWS STS with invented keys)')
    with Twin(routes={'sts': 'live'}, set_credentials=False) as twin:
        sts = boto3.client('sts', region_name='eu-west-2', aws_access_key_id='INVENTED-KEY-FOR-A-TEST',
                           aws_secret_access_key='invented', aws_session_token='invented')
        raises('InvalidClientTokenId', sts.get_caller_identity)
        rec = twin.traffic.records[-1]
        assert rec['target'] == 'live' and rec['status'] == 403 and rec['signed']
