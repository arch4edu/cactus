#!/bin/python
import yaml

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
                if pkgbase != 'pacman' and (not 'recursive' in i or i['recursive']):
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
    from datetime import datetime, timedelta
    from django.db import connection
    from pathlib import Path
    from .. import config, logger
    from ..models import Status
    from ..common.util import run, move, rmtree, download_artifact_package

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
        if pkgbase == 'pacman':
            try:
                logger.info(f'Downloading {pkgname} with pacman ...')
                run(['pacman', '--cachedir', depends, '--noconfirm', '-Swdd', pkgname])
                continue
            except:
                raise Exception(f'Failed to download {pkgname} with pacman.')

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
                    logger.warning(f'Failed to download {pkgname} with pacman.')
                else:
                    raise(f'Failed to download {pkgname} with pacman.')

        if not downloaded:
            _pkgbase = status.key.split('/')[-1]
            download_artifact_package(status.workflow, _pkgbase, pkgname)
            package = [i for i in Path('.').glob('*.pkg.tar.zst')][0]
            move(package, depends)
