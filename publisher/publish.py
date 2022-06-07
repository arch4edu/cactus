#!/bin/python
import os
import subprocess
from django.db import connection

def run(command, **kwargs):
    subprocess.run(command, check=True, **kwargs)

def symlink(source, target):
    try:
        os.symlink(source, target)
    except FileExistsError:
        os.remove(target)
        os.symlink(source, target)

if __name__ == '__main__':
    import sys
    import json
    import logging
    import shutil
    from pathlib import Path
    from tornado.log import enable_pretty_logging
    from tornado.options import options
    from .. import config
    from ..models import Status, Version

    options.logging = 'debug'
    logger = logging.getLogger()
    enable_pretty_logging(options=options, logger=logger)

    repository = Path('repository')

    for record in Status.objects.filter(status='BUILT'):
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
                package.rename(package.name.replace('COLON', ':'))

            run(['gpg', '--pinentry-mode', 'loopback', '--passphrase', '', '--detach-sign', '--', package])

            logger.info('Signed %s', package.name)
            arch = package.name[:-12].split('-')[-1]
            if arch != 'any' and not arch in config['pacman']['archs'].split(' '):
                continue
            shutil.move(package, repository / arch / package.name)
            shutil.move(package.parent / f'{package.name}.sig' , repository / arch / f'{package.name}.sig')

            db = repository / arch / f"{config['pacman']['repository']}.db.tar.gz"
            subprocess.run(['repo-add', db, repository / arch / package.name])

            if arch == 'any':
                for arch in config['pacman']['archs'].split(' '):
                    symlink(Path('..') / 'any' / package.name, repository / arch / package.name)
                    symlink(Path('..') / 'any' / f'{package.name}.sig', repository / arch / f'{package.name}.sig')

                    db = repository / arch / f"{config['pacman']['repository']}.db.tar.gz"
                    subprocess.run(['repo-add', db, repository / arch / package.name])

            logger.info('Published %s', package.name)

        connection.connect()
        record.status = 'PUBLISHED'
        record.save()
