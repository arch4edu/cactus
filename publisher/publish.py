#!/bin/python
import time
from .. import config, logger
from ..common.util import run, move, symlink, parse_package, sync_repository, upload_repository, download_artifact_package

def repo_add(repository, arch, package):
    db = repository / arch / f"{config['pacman']['repository']}.db.tar.gz"
    run(['repo-add', db, package])
    time.sleep(1)

if __name__ == '__main__':
    from pathlib import Path
    from django.db import connection
    from django.db.models import F
    from ..models import Status, Version, Package

    repository = Path('pacman-repository')

    for record in Status.objects.filter(status='BUILT'):
        sync_repository(repository)

        workflow = record.workflow
        pkgbase = record.key.split('/')[-1]

        try:
            download_artifact_package(workflow, pkgbase)
        except Exception as e:
            logger.error(f'Failed to download artifact for {pkgbase} (workflow {workflow}): {e}')
            record.detail = 'Download artifact failed'
            record.save()
            continue

        published = []

        for package in Path('.').glob('*.pkg.tar.zst'):
            run(['gpg', '--pinentry-mode', 'loopback', '--passphrase', '', '--detach-sign', '--', package])
            signature = package.parent / f'{package.name}.sig'
            logger.info('Signed %s', package.name)

            _, _, _, _, arch, _ = parse_package(package.name)
            if arch != 'any' and not arch in config['pacman']['archs'].split(' '):
                logger.info('Ignored %s', package.name)
                continue

            move(package, repository / arch / package.name)
            move(signature, repository / arch / signature.name)
            repo_add(repository, arch, repository / arch / package.name)

            if arch == 'any':
                for arch in config['pacman']['archs'].split(' '):
                    symlink(Path('..') / 'any' / package.name, repository / arch / package.name)
                    symlink(Path('..') / 'any' / f'{package.name}.sig', repository / arch / f'{package.name}.sig')
                    repo_add(repository, arch, repository / arch / package.name)

            with open(repository / 'lastupdate', 'w') as f:
                f.write(str(int(time.time())))

            upload_repository(repository)

            connection.connect()
            package_record = Package(key=record.key, package=package.name)
            package_record.save()

            logger.info('Published %s', package.name)
            published.append(package.name)

        connection.connect()
        if published:
            Package.objects.filter(key=record.key).exclude(package__in=published).update(age=F('age') + 1)
        record.status = 'PUBLISHED'
        record.save()
