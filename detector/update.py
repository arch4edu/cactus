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
    nvchecker_failed = []
    for line in lines:
        line = json.loads(line)
        if line['logger_name'] == 'nvchecker.util':
            continue
        if line['event'] == 'up-to-date':
            continue
        try:
            record = Version.objects.get(key=line['name'])
        except Version.DoesNotExist:
            record = Version(key=line['name'])
        if line['event'] != 'updated':
            nvchecker_failed.append(line['name'])
        elif record.newver != line['version']:
            record.newver = line['version']
        record.save()

    nvchecker_failed = set([key[:key.find(':')] for key in nvchecker_failed])

    logger.info('Marking failed')
    for key in nvchecker_failed:
        logger.debug(f'{key}: nvchecker failed')
        try:
            status = Status.objects.get(key=key)
        except Status.DoesNotExist:
            status = Status(key=key)
        if not status.detail.startswith('nvchecker failed'):
            if status.status == '':
                status.detail = 'nvchecker failed'
            else:
                status.detail = f'nvchecker failed, previously {status.status}'
            status.status = 'FAILED'
            status.save()

    logger.info('Checking previous failed')
    for status in Status.objects.filter(detail__startswith='nvchecker failed'):
        if status.key in nvchecker_failed:
            continue
        up_to_date = True
        for version in Version.objects.filter(key__startswith=f'{status.key}:'):
            if version.oldver != version.newver:
                up_to_date = False
                break
        if up_to_date:
            if ',' in status.detail:
                status.status = status.detail.split('previously ', 1)[1]
            else:
                status.status = 'STALE'
            logger.debug(f'{status.key}: recover from nvchecker failed to {status.status}')
            status.detail = ''
            status.save()

    logger.info('Marking stale')

    repository = Path(sys.argv[1])
    for record in Version.objects.exclude(newver__exact=F('oldver')):
        key = record.key[:record.key.find(':')]
        try:
            status = Status.objects.get(key=key)
        except Status.DoesNotExist:
            status = Status(key=key)

        if not (repository / key).exists():
            logger.warning('Removed %s', key)
            record.delete()
            status.delete()
            continue

        status.timestamp = status.timestamp.replace(tzinfo=None)
        print(datetime.now().tzinfo, status.timestamp.tzinfo) # Debug

        if status.status in ['', 'BUILT', 'PUBLISHED']:
            status.status = 'STALE'
            status.save()
            logger.debug(f'{key}: {record.oldver} -> {record.newver}')
        elif status.status == 'FAILED' and datetime.now() - status.timestamp > timedelta(days=1):
            status.status = 'STALE'
            status.save()
            logger.debug(f'{key}: try to rebuild {record.newver}')

    if datetime.today().weekday() > 0:
        sys.exit(0)

    logger.info('Removing dropped packages')

    for record in Version.objects.filter(newver__exact=F('oldver')):
        key = record.key[:record.key.find(':')]
        if not (repository / key).exists():
            try:
                status = Status.objects.get(key=key)
                status.delete()
            except Status.DoesNotExist:
                pass
            record.delete()
            logger.warning('Removed %s', key)
