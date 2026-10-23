"""The CloudFront twin, the minimum a deployment needs: web distributions, kept as configured.

    /cloudfront/distributions/<id>.json     id, ETag, status, domain, the DistributionConfig XML as sent

Covered (rest-xml, /2020-05-31/): CreateDistribution, GetDistribution, GetDistributionConfig,
ListDistributions, UpdateDistribution, DeleteDistribution. The rules that bite in real use hold:
every change needs the current ETag in If-Match (412 PreconditionFailed when stale), and a
distribution must be disabled before it can be deleted (409 DistributionNotDisabled).
A distribution is Deployed at once; AWS takes minutes. Requests to its domain are not served yet.
Not covered, and answered 501 NotImplemented by name: invalidations, policies, functions, OAC, and the rest."""
import re
import time
from xml.etree import ElementTree

from aws_twin.core.Twin__Http    import Twin__Response
from aws_twin.core.Twin__Service import Twin__Error, Twin__Store, iso_now, random_id
from aws_twin.s3.S3__Xml         import x, parse

CF_NS   = 'http://cloudfront.amazonaws.com/doc/2020-05-31/'
SUMMARY = ('Aliases', 'Origins', 'OriginGroups', 'DefaultCacheBehavior', 'CacheBehaviors', 'CustomErrorResponses', 'Comment',
           'PriceClass', 'Enabled', 'ViewerCertificate', 'Restrictions', 'WebACLId', 'HttpVersion', 'IsIPV6Enabled')


class CloudFront__Twin:
    service = 'cloudfront'

    def __init__(self, twin):
        self.twin  = twin
        self.store = Twin__Store(twin.vfs, 'cloudfront')

    def handle(self, request):
        path, m = request.path.rstrip('/'), request.method
        routes = [('GET',    r'^/2020-05-31/distribution$',             'ListDistributions'),
                  ('POST',   r'^/2020-05-31/distribution$',             'CreateDistribution'),
                  ('GET',    r'^/2020-05-31/distribution/([A-Z0-9]+)$', 'GetDistribution'),
                  ('DELETE', r'^/2020-05-31/distribution/([A-Z0-9]+)$', 'DeleteDistribution'),
                  ('GET',    r'^/2020-05-31/distribution/([A-Z0-9]+)/config$', 'GetDistributionConfig'),
                  ('PUT',    r'^/2020-05-31/distribution/([A-Z0-9]+)/config$', 'UpdateDistribution')]
        for method, pattern, action in routes:
            hit = re.match(pattern, path)
            if hit and method == m:
                try:
                    return action, getattr(self, 'op_' + action)(request, *hit.groups())
                except Twin__Error as e:
                    return action, self.error(e, request)
        action = 'Unknown'
        return action, self.error(Twin__Error(501, 'NotImplemented', f'the twin does not implement cloudfront {m} {request.path}'), request)

    def error(self, e, request):
        body = (f'<?xml version="1.0"?>\n<ErrorResponse xmlns="{CF_NS}"><Error><Type>Sender</Type>{x("Code", e.code)}{x("Message", e.message)}</Error>'
                f'{x("RequestId", request.request_id)}</ErrorResponse>')
        return Twin__Response(e.status, {'content-type': 'text/xml'}, body)

    # ── the store ───────────────────────────────────────────────────────
    def get(self, dist_id):
        d = self.store.read_json('distributions', f'{dist_id}.json')
        if d is None:
            raise Twin__Error(404, 'NoSuchDistribution', 'The specified distribution does not exist.')
        return d

    def save(self, d):
        self.store.write_json(d, 'distributions', f'{d["Id"]}.json')

    @staticmethod
    def config_of(body):
        try:
            root = parse(body)
        except ElementTree.ParseError:
            raise Twin__Error(400, 'MalformedXML', 'The XML document you provided was not well-formed.')
        if root.tag != 'DistributionConfig':
            raise Twin__Error(400, 'MalformedXML', 'Expected a DistributionConfig.')
        for need in ('CallerReference', 'Origins', 'DefaultCacheBehavior', 'Comment', 'Enabled'):
            if root.find(need) is None:
                raise Twin__Error(400, 'MalformedInput', f'DistributionConfig is missing {need}.')
        return root

    @staticmethod
    def inner_xml(root):
        """The config without its namespace, as CloudFront returns it."""
        return ''.join(ElementTree.tostring(child, encoding='unicode') for child in root)

    def require_etag(self, request, d):
        etag = request.header('if-match')
        if not etag:
            raise Twin__Error(400, 'InvalidIfMatchVersion', 'The If-Match version is missing or not valid for the resource.')
        if etag != d['ETag']:
            raise Twin__Error(412, 'PreconditionFailed', 'The precondition given in one or more of the request-header fields evaluated to false.')

    def distribution_xml(self, d):
        signers = '<ActiveTrustedSigners><Enabled>false</Enabled><Quantity>0</Quantity></ActiveTrustedSigners>'
        groups  = '<ActiveTrustedKeyGroups><Enabled>false</Enabled><Quantity>0</Quantity></ActiveTrustedKeyGroups>'
        return (x('Id', d['Id']) + x('ARN', d['ARN']) + x('Status', d['Status']) + x('LastModifiedTime', d['LastModifiedTime']) +
                x('InProgressInvalidationBatches', 0) + x('DomainName', d['DomainName']) + signers + groups +
                f'<DistributionConfig>{d["Config"]}</DistributionConfig>')

    def respond(self, status, root, inner, d, extra=None):
        body = f'<?xml version="1.0" encoding="UTF-8"?>\n<{root} xmlns="{CF_NS}">{inner}</{root}>'
        return Twin__Response(status, dict({'content-type': 'text/xml', 'etag': d['ETag']}, **(extra or {})), body)

    # ── operations ──────────────────────────────────────────────────────
    def op_CreateDistribution(self, request):
        root = self.config_of(request.body)
        ref  = root.findtext('CallerReference')
        for f in self.store.files('distributions'):
            old = self.store.read_json('distributions', f)
            if old.get('CallerReference') == ref:
                raise Twin__Error(409, 'DistributionAlreadyExists', f'A distribution with caller reference {ref} already exists: {old["Id"]}.')
        dist_id = 'E' + random_id(13)
        d = {'Id': dist_id, 'ARN': f'arn:aws:cloudfront::{self.twin.account_id}:distribution/{dist_id}', 'Status': 'Deployed',
             'LastModifiedTime': iso_now(), 'DomainName': 'd' + random_id(13, 'abcdefghijklmnopqrstuvwxyz0123456789') + '.cloudfront.net',
             'ETag': 'E' + random_id(13), 'CallerReference': ref, 'Enabled': root.findtext('Enabled') == 'true',
             'Config': self.inner_xml(root)}
        self.save(d)
        return self.respond(201, 'Distribution', self.distribution_xml(d), d,
                            {'location': f'https://cloudfront.amazonaws.com/2020-05-31/distribution/{dist_id}'})

    def op_GetDistribution(self, request, dist_id):
        d = self.get(dist_id)
        return self.respond(200, 'Distribution', self.distribution_xml(d), d)

    def op_GetDistributionConfig(self, request, dist_id):
        d = self.get(dist_id)
        return self.respond(200, 'DistributionConfig', d['Config'], d)

    def op_UpdateDistribution(self, request, dist_id):
        d = self.get(dist_id)
        self.require_etag(request, d)
        root = self.config_of(request.body)
        if root.findtext('CallerReference') != d['CallerReference']:
            raise Twin__Error(400, 'IllegalUpdate', 'The CallerReference of a distribution cannot be changed.')
        d.update(Config=self.inner_xml(root), Enabled=root.findtext('Enabled') == 'true', ETag='E' + random_id(13), LastModifiedTime=iso_now())
        self.save(d)
        return self.respond(200, 'Distribution', self.distribution_xml(d), d)

    def op_DeleteDistribution(self, request, dist_id):
        d = self.get(dist_id)
        self.require_etag(request, d)
        if d['Enabled']:
            raise Twin__Error(409, 'DistributionNotDisabled', 'The distribution you are trying to delete has not been disabled.')
        self.store.delete('distributions', f'{dist_id}.json')
        return Twin__Response(204, {}, b'')

    def op_ListDistributions(self, request):
        items = []
        for f in sorted(self.store.files('distributions')):
            d    = self.store.read_json('distributions', f)
            conf = ElementTree.fromstring(f'<c>{d["Config"]}</c>')
            keep = ''.join(ElementTree.tostring(conf.find(t), encoding='unicode') for t in SUMMARY if conf.find(t) is not None)
            items.append('<DistributionSummary>' + x('Id', d['Id']) + x('ARN', d['ARN']) + x('Status', d['Status']) +
                         x('LastModifiedTime', d['LastModifiedTime']) + x('DomainName', d['DomainName']) + keep + x('Staging', 'false') +
                         '</DistributionSummary>')
        inner = (x('Marker', '') + x('MaxItems', 100) + x('IsTruncated', 'false') + x('Quantity', len(items)) +
                 (f'<Items>{"".join(items)}</Items>' if items else ''))
        body  = f'<?xml version="1.0" encoding="UTF-8"?>\n<DistributionList xmlns="{CF_NS}">{inner}</DistributionList>'
        return Twin__Response(200, {'content-type': 'text/xml'}, body)
