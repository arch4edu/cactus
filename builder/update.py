#!/bin/python

if __name__ == '__main__':
    import os
    import sys
    import logging
    import json
    from tornado.log import enable_pretty_logging
    from tornado.options import options
    from ..models import Status

    options.logging = 'debug'
    logger = logging.getLogger()
    enable_pretty_logging(options=options, logger=logger)

    _, key, build_status, run_id = sys.argv

    status = Status.objects.get(key=key)

    detail = {}
    detail['workflow'] = run_id
    if build_status == 'built':
        status.status = 'BUILT'
    else:
        status.status = 'ERROR'
        detail['message'] = 'Build failed.'
    status.detail = json.dumps(detail)
    status.save()
