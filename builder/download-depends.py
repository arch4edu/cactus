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

    logger.info('Resolving dependencies ...')
    pacman_packages = []
    artifact_packages = []
    for pkgbase, pkgname in all_depends:
        if pkgbase == 'pacman':
            pacman_packages.append(pkgname)
            continue

        try:
            status = Status.objects.get(key=pkgbase)
        except:
            raise Exception(f'Cannot find {pkgbase} in the database.')
        
        # status.timestamp = status.timestamp.replace(tzinfo=None)

        if datetime.now() - status.timestamp > timedelta(days=1):
            pacman_packages.append(f'{config["pacman"]["repository"]}/{pkgname}')
        else:
            _pkgbase = status.key.split('/')[-1]
            artifact_packages.append((status.workflow, _pkgbase, pkgname))

    if len(pacman_packages) > 0:
        logger.info(f'Downloading {pacman_packages} with pacman ...')
        run(['pacman', '--cachedir', depends, '--noconfirm', '-Swdd'] + pacman_packages)

    for workflow, pkgbase, pkgname in artifact_packages:
        download_artifact_package(workflow, pkgbase, pkgname)
        package = [i for i in Path('.').glob('*.pkg.tar.zst')][-1]
        move(package, depends / package.name)
