#!/bin/python
import os
from django.db import connection

if __name__ == '__main__':
    import time
    import sys
    import json
    import logging
    import shutil
    from pathlib import Path
    from .. import config, logger
    from ..common.util import run, symlink
    from ..models import Status, Version

    repository = Path('repository')

    for record in Status.objects.filter(status='BUILT'):
        if not repository.exists():
            run(['rsync', '-avP', '--exclude', '*.pkg*', f'repository:{os.environ["REMOTE_PATH"]}/*', repository])

        workflow = record.workflow
        logger.info(f'Downloading {record.key} from {workflow}')
        try:
            run(f"gh run download {workflow} -n {workflow}.package -D ..".split(' '), cwd='cactus')
        except:
            logger.error('Failed to download %s', record.key)
            continue

        packages = [i for i in Path('.').glob('*.pkg.tar.zst')]

        for package in packages:
            if 'COLON' in package.name:
                package = package.rename(package.name.replace('COLON', ':'))

            run(['gpg', '--pinentry-mode', 'loopback', '--passphrase', '', '--detach-sign', '--', package])

            logger.info('Signed %s', package.name)
            arch = package.name[:-12].split('-')[-1]
            if arch != 'any' and not arch in config['pacman']['archs'].split(' '):
                continue
            shutil.move(package, repository / arch / package.name)
            shutil.move(package.parent / f'{package.name}.sig' , repository / arch / f'{package.name}.sig')

            db = repository / arch / f"{config['pacman']['repository']}.db.tar.gz"
            run(['repo-add', db, repository / arch / package.name])
            time.sleep(1)

            if arch == 'any':
                for arch in config['pacman']['archs'].split(' '):
                    symlink(Path('..') / 'any' / package.name, repository / arch / package.name)
                    symlink(Path('..') / 'any' / f'{package.name}.sig', repository / arch / f'{package.name}.sig')

                    db = repository / arch / f"{config['pacman']['repository']}.db.tar.gz"
                    run(['repo-add', db, repository / arch / package.name])
                    time.sleep(1)

            run(['sh', '-c', f'rsync -avP repository/* repository:{os.environ["REMOTE_PATH"]}'])
            logger.info('Published %s', package.name)

        connection.connect()
        record.status = 'PUBLISHED'
        record.save()
