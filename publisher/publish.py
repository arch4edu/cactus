#!/bin/python
import time
from .. import config, logger
from ..common.util import run, move, symlink, parse_package, download_artifact_package

def repo_add(repository, arch, package):
    db = repository / arch / f"{config['pacman']['repository']}.db.tar.gz"
    run(['repo-add', db, package])
    time.sleep(1)

if __name__ == '__main__':
    from pathlib import Path
    from django.db import connection
    from ..models import Status, Version, Package

    repository = Path('repository')

    for record in Status.objects.filter(status='BUILT'):
        if not repository.exists():
            run(['rsync', '-avP', '--exclude', '*.pkg*', f'repository:{config["publisher"]["path"]}/*', repository])

        workflow = record.workflow
        pkgbase = record.key.split('/')[-1]

        download_artifact_package(workflow, pkgbase)

        connection.connect()
        for package_record in Package.objects.filter(key=record.key):
            package_record.age += 1
            package_record.save()

        for package in Path('.').glob('*.pkg.tar.zst'):
            run(['gpg', '--pinentry-mode', 'loopback', '--passphrase', '', '--detach-sign', '--', package])
            signature = package.parent / f'{package.name}.sig'
            logger.info('Signed %s', package.name)

            _, _, _, _, arch, _ = parse_package(package.name)
            if arch != 'any' and not arch in config['pacman']['archs'].split(' '):
                logger.info('Ignored %s', package.name)
                continue

            move(package, repository / arch)
            move(signature, repository / arch)
            repo_add(repository, arch, repository / arch / package.name)

            if arch == 'any':
                for arch in config['pacman']['archs'].split(' '):
                    symlink(Path('..') / 'any' / package.name, repository / arch / package.name)
                    symlink(Path('..') / 'any' / f'{package.name}.sig', repository / arch / f'{package.name}.sig')
                    repo_add(repository, arch, repository / arch / package.name)

            with open(repository / 'lastupdate', 'w') as f:
                f.write(str(int(time.time())))

            run(['sh', '-c', f'rsync -avP repository/* repository:{config["publisher"]["path"]}'])

            connection.connect()
            package_record = Package(key=record.key, package=package.name)
            package_record.save()

            logger.info('Published %s', package.name)

        record.status = 'PUBLISHED'
        record.save()
