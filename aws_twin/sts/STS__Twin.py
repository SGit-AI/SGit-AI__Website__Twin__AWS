"""The STS twin: the query protocol's GetCallerIdentity, so code that asks "who am I"
before doing anything (OSBot-AWS does, for the account id) gets an answer."""
from urllib.parse import parse_qsl

from aws_twin.core.Twin__Http import Twin__Response
from aws_twin.s3.S3__Xml      import x

STS_NS = 'https://sts.amazonaws.com/doc/2011-06-15/'


class STS__Twin:
    service = 'sts'

    def __init__(self, twin):
        self.twin = twin

    def handle(self, request):
        params = dict(request.query)
        if request.body:
            params.update(parse_qsl(request.body.decode('utf-8', 'replace'), keep_blank_values=True))
        action = params.get('Action', 'Unknown')
        if action == 'GetCallerIdentity':
            t     = self.twin
            inner = x('Arn', f'arn:aws:sts::{t.account_id}:assumed-role/{t.role_name}/{t.session_name}') + x('UserId', f'AROATWIN0000000000000:{t.session_name}') + x('Account', t.account_id)
            body  = (f'<GetCallerIdentityResponse xmlns="{STS_NS}"><GetCallerIdentityResult>{inner}</GetCallerIdentityResult>'
                     f'<ResponseMetadata>{x("RequestId", request.request_id)}</ResponseMetadata></GetCallerIdentityResponse>')
            return action, Twin__Response(200, {'content-type': 'text/xml'}, body)
        body = (f'<ErrorResponse xmlns="{STS_NS}"><Error><Type>Sender</Type>{x("Code", "NotImplemented")}'
                f'{x("Message", f"the twin does not implement sts {action}")}</Error>{x("RequestId", request.request_id)}</ErrorResponse>')
        return action, Twin__Response(501, {'content-type': 'text/xml'}, body)
