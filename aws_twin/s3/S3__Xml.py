"""Small XML helpers for S3's rest-xml protocol, standard library only."""
from xml.sax.saxutils import escape
from xml.etree         import ElementTree

S3_NS = 'http://s3.amazonaws.com/doc/2006-03-01/'


def x(tag, value):
    return f'<{tag}>{escape(str(value))}</{tag}>'


def doc(root, inner):
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<{root} xmlns="{S3_NS}">{inner}</{root}>'


def parse(body: bytes):
    """Parse a request body, dropping namespaces so callers can find('Key')."""
    root = ElementTree.fromstring(body)
    for el in root.iter():
        if '}' in el.tag:
            el.tag = el.tag.split('}', 1)[1]
    return root


def error_xml(code, message, request_id, **extra):
    inner = x('Code', code) + x('Message', message) + ''.join(x(k, v) for k, v in extra.items() if v is not None) + x('RequestId', request_id)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<Error>{inner}</Error>'
