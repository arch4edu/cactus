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
        try:
            connection.connect()
            workflow = Status.objects.get(key=pkgbase).workflow

            logger.info(f'Downloading {pkgbase} from {workflow} ...')
            run(['gh', 'run', 'watch', workflow, '-R', config['github']['cactus']])
            run(['gh', 'run', 'download', workflow, '-n', f'{workflow}.package', '-R', config['github']['cactus']])
        except:
            logger.warning(f'Failed to download {pkgbase} from workflow. Downloading {pkgname} with pacman ...')
            try:
                run(['pacman', '--config', 'pacman/pacman.conf', '--dbpath', 'pacman/db', '--gpgdir', 'pacman/gnupg', '--cachedir', depends, '--noconfirm', '-Swdd', pkgname])
                continue
            except:
                raise Exception(f'Failed to download {pkgbase}/{pkgname}.')

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
