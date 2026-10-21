"""aws_twin: the AWS twin, in Python.

A wire-level twin of AWS services: it answers the HTTP requests boto3, OSBot-AWS or the
AWS CLI send, signed exactly as they would be for AWS, from a virtual file system instead
of an account. The same code runs in CPython (tests, CI, a local endpoint) and in the
browser under Pyodide (the S3 browser on aws.twin.sgit.ai).

    from aws_twin import Twin
    with Twin() as twin:                        # every botocore request now goes to the twin
        boto3.client('s3').create_bucket(Bucket='my-bucket')
        twin.traffic.records                    # what was sent, what came back

Pure Python, no dependency beyond the standard library; boto3 is only needed by the code
that calls the twin, never by the twin.
"""
from aws_twin.core.Twin import Twin
from aws_twin.vfs.Vfs__Provider__Memory import Vfs__Provider__Memory

__version__ = 'v0.3.0'
__all__     = ['Twin', 'Vfs__Provider__Memory', '__version__']
