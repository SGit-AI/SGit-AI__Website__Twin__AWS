"""Send a botocore request to AWS from a browser (Pyodide).

botocore opens connections through its own urllib3 connection classes, which use
sockets; Pyodide's urllib3 only teaches urllib3's default classes to use the browser, so
botocore's own send makes no request at all there (it raises EndpointConnectionError).
This sends the already-signed request through urllib3's browser fetch instead, which is a
synchronous XMLHttpRequest on the page's main thread (or JSPI where the browser has it).
The browser sets Host and Content-Length itself, to the values botocore signed."""


def send_from_browser(prepared, timeout=0):
    from urllib3.contrib.emscripten.fetch   import send_request
    from urllib3.contrib.emscripten.request import EmscriptenRequest
    from botocore.awsrequest                import AWSResponse
    from aws_twin.core.Twin                 import _Raw

    body = prepared.body
    if hasattr(body, 'read'):
        body = body.read()
    if isinstance(body, str):
        body = body.encode('utf-8')
    headers = {k: (v.decode() if isinstance(v, bytes) else str(v)) for k, v in prepared.headers.items()}
    response = send_request(EmscriptenRequest(method=prepared.method, url=prepared.url, body=body or None,
                                              headers=headers, timeout=timeout))
    return AWSResponse(prepared.url, response.status_code, dict(response.headers), _Raw(response.body))
