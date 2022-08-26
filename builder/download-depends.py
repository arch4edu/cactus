#!/bin/python

def load_depends(repository, pkgbase, key='depends'):
    with open(repository / pkgbase / 'cactus.yaml') as f:
        cactus = yaml.safe_load(f)
    if not key in cactus:
        return []
    else:
        return cactus[key]

def resolve_depends(repository, pkgbase, result, key='depends'):
    for i in load_depends(repository, pkgbase, key=key):
        if type(i) is dict:
            pkgbase, pkgname = list(i.keys())[0], list(i.values())[0]
            if not (pkgbase, pkgname) in result:
                result.append((pkgbase, pkgname))
                if not 'recursive' in i or i['recursive']:
                    result = resolve_depends(repository, pkgbase, result) 
        else:
            pkgbase, pkgname = i, i.split('/')[-1]
            if not (pkgbase, pkgname) in result:
                result.append((pkgbase, pkgname))
                result = resolve_depends(repository, pkgbase, result) 
    return result

if __name__ == '__main__':
    import sys
    import json
    import logging
    import yaml
    from datetime import datetime, timedelta
    from django.db import connection
    from pathlib import Path
    from tornado.log import enable_pretty_logging
    from tornado.options import options
    from .. import config
    from ..models import Status
    from ..common.util import run, move, remove, rmtree

    options.logging = 'debug'
    logger = logging.getLogger()
    enable_pretty_logging(options=options, logger=logger)

    repository = Path(sys.argv[1])
    pkgbase = sys.argv[2]

    all_depends = []
    all_depends = resolve_depends(repository, pkgbase, all_depends)
    all_depends = resolve_depends(repository, pkgbase, all_depends, 'makedepends')

    depends = repository / pkgbase / 'depends'
    if depends.exists():
        rmtree(depends)
    depends.mkdir()

    for pkgbase, pkgname in all_depends:
        connection.connect()
        try:
            status = Status.objects.get(key=pkgbase)
        except:
            logger.warning('Cannot find {pkgbase} in the database.')
            status = None

        downloaded = False
        if status is None or datetime.now() - status.timestamp > timedelta(days=1):
            logger.info(f'Downloading {pkgname} with pacman ...')
            try:
                run(['pacman', '--config', 'pacman/pacman.conf', '--dbpath', 'pacman/db', '--gpgdir', 'pacman/gnupg', '--cachedir', depends, '--noconfirm', '-Swdd', pkgname])
                downloaded = True
            except:
                if status:
                    logger.warning(f'Failed to download pkgname with pacman.')
                else:
                    raise(f'Failed to download pkgname with pacman.')

        if not downloaded:
            logger.info(f'Downloading {pkgname} from {pkgbase} in {status.workflow} ...')
            basename = status.key.split('/')[-1]
            try:
                run(['gh', 'run', 'watch', status.workflow, '-R', config['github']['cactus']])
                run(['gh', 'run', 'download', status.workflow, '-n', f'{basename}.package', '-R', config['github']['cactus']])
            except:
                raise Exception(f'Failed to download {pkgname}.')

            packages = [i for i in Path('.').glob('*.pkg.tar.zst')]

            matched = False
            for package in packages:
                if 'COLON' in package.name:
                    package = package.rename(package.name.replace('COLON', ':'))

                _pkgname = '-'.join(package.name.split('-')[:-3])
                if _pkgname == pkgname:
                    move(package, depends / package.name)
                    matched = True
                else:
                    remove(package)

            if not matched:
                raise Exception(f'No package named {pkgname} in {pkgbase}.')
