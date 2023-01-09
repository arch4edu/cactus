#!/bin/python

if __name__ == '__main__':
    import sys
    from ..models import Status, Version
    from .. import logger

    for pkgbase in sys.argv[1:]:
        status = Status.objects.get(key=pkgbase)
        if status.status != 'STALE':
            status.status = 'STALE'
            status.save()
        logger.info(f'Marked {pkgbase} as staled.')

        for record in Version.objects.filter(key__startswith=pkgbase):
            record.oldver = ''
            record.save()
            logger.info(f'Removed oldver from {record.key}')
