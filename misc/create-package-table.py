#!/bin/python
from ..common.util import run
from .. import logger
import yaml

# This script read the PKGBUILDs in the repository and generate the package table.
# It should be only used when the package table is totally broken.

pkgext = '.pkg.tar.zst'

class INFO:

    def __init__(self, srcinfo):
        self.pkgbase = None
        self.pkgname = None
        self.epoch = None
        self.pkgver = None
        self.pkgrel = None
        self.arch = []

        if srcinfo[0].startswith('pkgbase = '):
            self.pkgbase = srcinfo[0].replace('pkgbase = ', '')
        else:
            self.pkgname = srcinfo[0].replace('pkgbase = ', '')

        for line in srcinfo[1:]:
            if line.startswith('\tepoch = '):
                self.epoch = line.replace('\tepoch = ', '')
            elif line.startswith('\tpkgver = '):
                self.pkgver = line.replace('\tpkgver = ', '')
            elif line.startswith('\tpkgrel = '):
                self.pkgrel = line.replace('\tpkgrel = ', '')
            elif line.startswith('\tarch = '):
                self.arch.append(line.replace('\tarch = ', ''))

def predict_packages(pkgbuild):
    packages = []

    srcinfo = run(['makepkg', '--printsrcinfo'], cwd=pkgbuild.parent, capture_output=True).stdout.decode('utf-8')
    srcinfo = srcinfo.split('\npkgname = ')
    srcinfo = [INFO(info.split('\n')) for info in srcinfo]

    cactus = pkgbuild.parent / 'cactus.yaml'
    if not cactus.exists():
        logger.warning('%s does not exist.', cactus)
        return packages
    with open(cactus) as f:
        cactus = yaml.safe_load(f)

    aarch64 = False
    if 'group' in cactus and 'aarch64' in cactus['group'] or 'aarch64' in str(pkgbuild):
        aarch64 = True

    for pkginfo in srcinfo[1:]:
        pkgname = pkginfo.pkgname
        epoch = pkginfo.epoch if pkginfo.epoch else srcinfo[0].epoch
        pkgver = pkginfo.pkgver if pkginfo.pkgver else srcinfo[0].pkgver
        pkgrel = pkginfo.pkgrel if pkginfo.pkgrel else srcinfo[0].pkgrel
        arch = pkginfo.arch if pkginfo.arch else srcinfo[0].arch

        if len(arch) == 0:
            logger.warning('No arch in %s.', cactus)
            return []
        if 'any' in arch:
            if len(arch) > 1:
                logger.warning('No arch in %s.', cactus)
            arch='any'
        else:
            arch = 'aarch64' if aarch64 else 'x86_64'

        if epoch:
            packages.append(f'{pkgname}-{epoch}:{pkgver}-{pkgrel}-{arch}{pkgext}')
        else:
            packages.append(f'{pkgname}-{pkgver}-{pkgrel}-{arch}{pkgext}')

    logger.debug('Predicted packages: %s from %s', packages, pkgbuild)
    return packages

if __name__ == '__main__':

    import os
    import sys
    from pathlib import Path
    from multiprocessing import Pool
    from ..models import Package, Status

    repository = Path(sys.argv[1])
    pkgbuilds = [i for i in repository.rglob('PKGBUILD')]

    package_list = open(sys.argv[2]).readlines()
    package_list = [os.path.basename(i.strip('\n')) for i in package_list]

    with Pool(16) as pool:
        predicted = pool.map(predict_packages, pkgbuilds)

    for pkgbuild, packages in zip(pkgbuilds, predicted):
        key = str(pkgbuild.parent.relative_to(repository))
        try:
            status = Status.objects.get(key=key)
        except:
            logger.warning('%s is not in the database', key)

        for package in packages:
            if not package in package_list:
                logger.warning('Cannot find %s in repository.', package)
            try:
                record = Package.objects.get(key=key, package=package)
            except:
                record = Package(key=key, package=package)
                record.save()
