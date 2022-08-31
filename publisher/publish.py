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
    from ..models import Status, Version, Package

    repository = Path('repository')

    for record in Status.objects.filter(status='BUILT'):
        if not repository.exists():
            run(['rsync', '-avP', '--exclude', '*.pkg*', f'repository:{config["publisher"]["path"]}/*', repository])

        workflow = record.workflow
        basename = record.key.split('/')[-1]
        logger.info(f'Downloading {record.key} from {workflow}')
        try:
            run(['gh', 'run', 'download', workflow, '-n', f'{basename}.package', '-R', config['github']['cactus']])
        except:
            try:
                run(['gh', 'run', 'watch', workflow, '-R', config['github']['cactus']])
                run(['gh', 'run', 'download', workflow, '-n', f'{basename}.package', '-R', config['github']['cactus']])
            except:
                logger.error('Failed to download %s', record.key)
                continue

        packages = [i for i in Path('.').glob('*.pkg.tar.zst')]

        if len(packages) > 0:
            for package_record in Package.objects.filter(key=record.key):
                package_record.age += 1
                if package_record.age > config["publisher"]["max-age"]:
                    arch = package_record.name[:-12].split('-')[-1]
                    oldfiles = []
                    oldfiles.append(f'{config["publisher"]["path"]}/{arch}/{package_record.package}')
                    oldfiles.append(oldfiles[-1] + '.sig')
                    if arch == 'any':
                        for arch in config['pacman']['archs'].split(' '):
                            oldfiles.append(f'{config["publisher"]["path"]}/{arch}/{package_record.package}')
                            oldfiles.append(oldfiles[-1] + '.sig')
                    run(['ssh', 'repository', 'rm'] + oldfiles)
                    package_record.delete()
                else:
                    package_record.save()

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

            run(['sh', '-c', f'rsync -avP repository/* repository:{config["publisher"]["path"]}'])

            package_record = Package(key=record.key, package=package.name)
            package_record.save()

            logger.info('Published %s', package.name)

        connection.connect()
        record.status = 'PUBLISHED'
        record.save()
