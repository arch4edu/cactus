#!/bin/python

if __name__ == '__main__':
    import os
    import sys
    import json
    import logging
    from tqdm import tqdm
    from datetime import datetime, timedelta
    from tornado.log import enable_pretty_logging
    from tornado.options import options
    from django.db.models import F
    from ..models import Status, Version

    options.logging = 'debug'
    logger = logging.getLogger()
    enable_pretty_logging(options=options, logger=logger)

    key = sys.argv[1]
    build_status = sys.argv[2]

    status = Status.objects.get(key=key)

    if build_status == 'built':
        status.status = 'BUILT'
        status.detail = f'{os.environ["GITHUB_WORKFLOW"]}'
    else:
        status.status = 'ERROR'
        status.detail = 'build failed. workflow: {os.environ["GITHUB_WORKFLOW"]}'
    status.save()
