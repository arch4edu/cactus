#!/bin/python

if __name__ == '__main__':
    import os
    import sys
    import json
    from datetime import datetime, timedelta
    from django.db.models import F
    from pathlib import Path
    from .. import logger
    from ..models import Status, Version

    lines = open('nvchecker.log').readlines()

    logger.info('Updating newver')
    for line in lines:
        line = json.loads(line)
        try:
            record = Version.objects.get(key=line['name'])
        except Version.DoesNotExist:
            record = Version(key=line['name'])
        if line['event'] != 'updated':
            line['version'] = 'FAILED'
        if record.newver != line['version']:
            record.newver = line['version']
        record.save()

    logger.info('Marking staled and error')

    repository = Path(sys.argv[1])
    for record in Version.objects.exclude(newver__exact=F('oldver')):
        key = record.key[:record.key.find(':')]
        if not (repository / key).exists():
            record.delete()
            logger.warn('Removed %s', key)
        try:
            status = Status.objects.get(key=key)
        except Status.DoesNotExist:
            if not (repository / key).exists():
                continue
            status = Status(key=key)

        if record.newver == 'FAILED':
            status.status = 'FAILED'
            status.detail = 'nvchecker failed'
            status.save()
            continue
        if status.status in ['', 'PUBLISHED']:
            status.status = 'STALED'
            status.save()
        elif status.status == 'FAILED' and datetime.now() - status.timestamp > timedelta(days=1):
            status.status = 'STALED'
            status.save()

        if status.status == 'STALED':
            logger.debug(f'{key}: {record.oldver} -> {record.newver}')
        else:
            logger.debug(f'{key}: {status.status} on {status.timestamp}')
