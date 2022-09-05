#!/bin/python
import time
from django.db import connection
from .. import config, logger
from ..common.util import run, parse_package

def remove_package(package, repository=None):
    pkgname, _, _, _, arch, _ = parse_package(package)
    oldfiles = []
    oldfiles.append(f'{config["publisher"]["path"]}/{arch}/{package}')
    oldfiles.append(oldfiles[-1] + '.sig')

    if repository:
        db = repository / arch / f"{config['pacman']['repository']}.db.tar.gz"
        run(['repo-remove', db, pkgname])
        time.sleep(1)

    if arch == 'any':
        for arch in config['pacman']['archs'].split(' '):
            oldfiles.append(f'{config["publisher"]["path"]}/{arch}/{package}')
            oldfiles.append(oldfiles[-1] + '.sig')
            if repository:
                db = repository / arch / f"{config['pacman']['repository']}.db.tar.gz"
                run(['repo-remove', db, pkgname])
                time.sleep(1)

    run(['ssh', 'repository', 'rm'] + oldfiles)
    logger.debug('Deleted %s.', oldfiles)

if __name__ == '__main__':
    from pathlib import Path
    from ..models import Status, Package

    repository = Path('repository')

    logger.info('Removing old packages ...')
    for package in Package.objects.filter(age__gt=config['publisher']['max-age']):
        remove_package(package.package)
        package.delete()

    logger.info('Removing dropped packages ...')
    status = Status.objects.all()
    for package in Package.objects.exclude(key__in=status):

        if not repository.exists():
            run(['rsync', '-avP', '--exclude', '*.pkg*', f'repository:{config["publisher"]["path"]}/*', repository])

        remove_package(package.package, repository)
        run(['sh', '-c', f'rsync -avP repository/* repository:{config["publisher"]["path"]}'])
        package.delete()
        logger.info('Removed %s', package.name)
