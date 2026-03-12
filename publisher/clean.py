#!/bin/python
import sys
import time
from pathlib import Path

from django.db.models import F
from .. import config, logger
from ..common.util import run, parse_package
from ..models import Status, Version, Package

def repo_remove(db, pkgname):
    output = run(['repo-remove', db, pkgname], capture_output=True, check=False)
    stderr = output.stderr.decode('utf-8')
    if output.returncode != 0 and not f"Package matching '{pkgname}' not found." in stderr:
        raise Exception(f'Failed to remove {pkgname} from {db}.')
    time.sleep(1)

def remove_package(package, repository=None):
    pkgname, _, _, _, arch, _ = parse_package(package)
    oldfiles = []
    oldfiles.append(f'{config["publisher"]["path"]}/{arch}/{package}')
    oldfiles.append(oldfiles[-1] + '.sig')

    if repository:
        db = repository / arch / f"{config['pacman']['repository']}.db.tar.gz"
        repo_remove(db, pkgname)

    if arch == 'any':
        for arch in config['pacman']['archs'].split(' '):
            oldfiles.append(f'{config["publisher"]["path"]}/{arch}/{package}')
            oldfiles.append(oldfiles[-1] + '.sig')
            if repository:
                db = repository / arch / f"{config['pacman']['repository']}.db.tar.gz"
                repo_remove(db, pkgname)

    run(['ssh', 'repository', 'rm', '-f'] + oldfiles)
    logger.debug('Deleted %s.', oldfiles)

def clean_old():
    """Remove packages exceeding max-age."""
    repository = Path('pacman-repository')
    logger.info('Removing old packages ...')

    for package in Package.objects.filter(age__gt=config['publisher']['max-age']):
        remove_package(package.package)
        package.delete()

        if not repository.exists():
            run(['rsync', '-avP', '--exclude', '*.pkg*', f'repository:{config["publisher"]["path"]}/*', repository])

        with open(repository / 'lastupdate', 'w') as f:
            f.write(str(int(time.time())))

        run(['sh', '-c', f'rsync -avP repository/* repository:{config["publisher"]["path"]}'])

def clean_unmaintained():
    """Remove packages with no version updates and missing from repository."""
    # Step 1: Clean up database records - combines detector's two cleanup cases
    repository = Path('repository')
    logger.info('Cleaning database records for dropped packages')

    for record in Version.objects.all():
        key = record.key[:record.key.find(':')]
        if not (repository / key).exists():
            try:
                status = Status.objects.get(key=key)
                status.delete()
            except Status.DoesNotExist:
                pass
            record.delete()
            logger.warning('Removed %s', key)

    # Step 2: Remove unmaintained packages using 'pacman-repository' path
    repository = Path('pacman-repository')
    logger.info('Removing package files for dropped packages ...')

    status = Status.objects.all()
    for package in Package.objects.exclude(key__in=status):
        if not repository.exists():
            run(['rsync', '-avP', '--exclude', '*.pkg*', f'repository:{config["publisher"]["path"]}/*', repository])

        remove_package(package.package, repository)

        with open(repository / 'lastupdate', 'w') as f:
            f.write(str(int(time.time())))

        run(['sh', '-c', f'rsync -avP repository/* repository:{config["publisher"]["path"]}'])
        package.delete()
        logger.info('Removed %s', package.key)


if __name__ == '__main__':
    # Determine which phase to run based on first argument
    phase = sys.argv[1] if len(sys.argv) > 1 else 'all'

    if phase == 'old':
        clean_old()
    elif phase == 'unmaintained':
        clean_unmaintained()
    else:
        # Default: run both
        clean_old()
        clean_unmaintained()
