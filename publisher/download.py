#!/bin/python

if __name__ == '__main__':
    import os
    import sys
    import json
    import logging
    import subprocess
    from tornado.log import enable_pretty_logging
    from tornado.options import options
    from ..models import Status, Version

    options.logging = 'debug'
    logger = logging.getLogger()
    enable_pretty_logging(options=options, logger=logger)

    for record in Status.objects.filter(status='BUILT'):
        logger.info(f'Downloading {record.key}')
        workflow = json.loads(record.detail)['workflow']
        subprocess.run(f"gh run download {workflow} -n {workflow}.package -D ..".split(' '), cwd='cactus')
