#!/bin/python

if __name__ == '__main__':
    import sys
    import json
    import logging
    import yaml
    from django.db import connection
    from pathlib import Path
    from tornado.log import enable_pretty_logging
    from tornado.options import options
    from .. import config
    from ..models import Status
    from ..common.util import run, move, remove

    options.logging = 'debug'
    logger = logging.getLogger()
    enable_pretty_logging(options=options, logger=logger)

    directory = Path(sys.argv[1])
    with open(directory / 'cactus.yaml') as f:
        cactus = yaml.safe_load(f)

    if not 'depends' in cactus:
        sys.exit()

    depends = directory / 'depends'
    depends.mkdir(exist_ok=True)

    for i in cactus['depends']:

        if type(i) is tuple:
            key, pkgname = i
        else:
            key, pkgname = i, i.split('/')[-1]

        try:
            connection.connect()
            workflow = Status.objects.get(key=key).workflow
            logger.info(f'Downloading {key} from {workflow} ...')
            run(f"gh run download {workflow} -n {workflow}.package -D ..".split(' '), cwd='cactus')
        except:
            logger.warning(f'Failed to download {key} from workflow. Downloading {pkgname} with pacman ...')
            try:
                run(['pacman', '--config', 'pacman/pacman.conf', '--dbpath', 'pacman/db', '--gpgdir', 'pacman/gnupg', '--cachedir', depends, '-Swdd', pkgname])
                continue
            except:
                raise Exception('Failed to download {key}/{pkgname}.')

        packages = [i for i in Path('.').glob('*.pkg.tar.zst')]

        matched = False
        for package in packages:
            if 'COLON' in package.name:
                package = package.rename(package.name.replace('COLON', ':'))

            _pkgname = '-'.join(package.name.split('-')[:-3])
            if _pkgname == pkgname:
                move(package, depends)
                matched = True
            else:
                remove(package)

        if not matched:
            raise Exception(f'No package named {pkgname} in {key}.')
