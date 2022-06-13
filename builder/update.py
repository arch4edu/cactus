#!/bin/python

if __name__ == '__main__':
    import os
    import sys
    import logging
    from tornado.log import enable_pretty_logging
    from tornado.options import options
    from ..models import Status, Version

    options.logging = 'debug'
    logger = logging.getLogger()
    enable_pretty_logging(options=options, logger=logger)

    _, key, build_status, run_id = sys.argv

    status = Status.objects.get(key=key)
    status.workflow = run_id
    if build_status == 'built':
        status.status = 'BUILT'
        status.detail = ''
        for record in Version.objects.filter(key__startswith=key):
            record.oldver = record.newver
            record.save()
    else:
        status.status = 'FAILED'
        status.detail = 'Build failed.'
    status.save()

