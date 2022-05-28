#!/bin/python

if __name__ == '__main__':
    import os
    import sys
    import logging
    from tornado.log import enable_pretty_logging
    from tornado.options import options
    from ..models import Status

    options.logging = 'debug'
    logger = logging.getLogger()
    enable_pretty_logging(options=options, logger=logger)

    _, key, build_status, run_id = sys.argv

    status = Status.objects.get(key=key)

    if build_status == 'built':
        status.status = 'BUILT'
        status.detail = f'workflow: {run_id}'
    else:
        status.status = 'ERROR'
        status.detail = f'build failed. workflow: {run_id}'
    status.save()
