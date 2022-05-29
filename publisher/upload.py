#!/bin/python

if __name__ == '__main__':
    import os
    import sys
    import json
    import logging
    import subprocess
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
        workflow = json.loads(record.detail)['workflow']
        logger.info(f'Downloading {record.key} from {workflow}')
        subprocess.run(f"gh run download {workflow} -n {workflow}.package -D ..".split(' '), cwd='cactus')
        packages = [i for i in Path('.').glob('*.pkg.tar.zst')]

        for package in packages:
            subprocess.run(['gpg', '--pinentry-mode', 'loopback', '--passphrase', '', '--detach-sign', '--', package])
            logger.info('Signed %s', package.name)
            arch = package.name[:-12].split('-')[-1]
            if not arch in config['pacman']['archs'].split(' '):
                continue
            shutil.copy(package, repository / 'any')
            shutil.copy(package.parent / f'{package.name}.sig' , repository / 'any')
            subprocess.run(['repo-add', repository / arch / f"{config['pacman']['repository']}.db.tar.gz", package])
            if arch == 'any':
                for arch in config['pacman']['archs'].split(' '):
                    os.symlink(repository / 'any' / package.name, repository / arch / package.name)
                    os.symlink(repository / 'any' / f'{package.name}.sig', repository / arch / f'{package.name}.sig')
                    subprocess.run(['repo-add', repository / arch / f"{config['pacman']['repository']}.db.tar.gz", package])
            os.remove(package)
            os.remove(package.parent / f'{package.name}.sig')
            logger.info('Uploaded %s', package.name)

        record.status = 'PUBLISHED'
        record.save()
