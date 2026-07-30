#!/bin/python

if __name__ == '__main__':
    import sys
    import json
    from datetime import datetime, timedelta
    from django.db.models import F
    from django.db.models.functions import Now
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
            Status.objects.create(key=key, status='FAILED', detail='nvchecker failed')
            continue
        if not status.detail.startswith('nvchecker failed'):
            if status.status == '':
                detail = 'nvchecker failed'
            else:
                detail = f'nvchecker failed, previously {status.status}'
            Status.objects.filter(key=key).update(status='FAILED', detail=detail)

    logger.info('Checking previous failed')
    for status in Status.objects.filter(detail__startswith='nvchecker failed'):
        if status.key in nvchecker_failed:
            continue
        if ',' in status.detail:
            new_status = status.detail.split('previously ', 1)[1]
        else:
            new_status = 'STALE'
        logger.debug(f'{status.key}: recover from nvchecker failed to {new_status}')
        Status.objects.filter(key=status.key).update(status=new_status, detail='')

    logger.info('Marking stale')

    repository = Path(sys.argv[1])
    for record in Version.objects.exclude(newver__exact=F('oldver')):
        key = record.key[:record.key.find(':')]
        try:
            status = Status.objects.get(key=key)
        except Status.DoesNotExist:
            status = Status(key=key)

        if not (repository / key).exists():
            continue

        if status.status in ['', 'BUILT', 'PUBLISHED']:
            status.status = 'STALE'
            status.save()
            logger.debug(f'{key}: {record.oldver} -> {record.newver}')

    logger.info('Retrying failed packages')
    retryable = Status.objects.filter(
        status='FAILED',
        timestamp__lt=Now() - timedelta(days=1)
    ).exclude(detail__startswith='nvchecker failed')
    for status in retryable:
        if not (repository / status.key).exists():
            continue
        status.status = 'STALE'
        status.detail = 'Retry'
        status.save()
        logger.debug(f'{status.key}: try to rebuild')
