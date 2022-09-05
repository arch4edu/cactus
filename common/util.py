#!/bin/python
import os
import shutil
import subprocess
from pathlib import Path
from .. import config, logger

def run(command, **kwargs):
    return subprocess.run(command, check=True, **kwargs)

remove = os.remove
move = shutil.move
rmtree = shutil.rmtree

def symlink(source, target):
    try:
        os.symlink(source, target)
    except FileExistsError:
        os.remove(target)
        os.symlink(source, target)

def parse_package(package):
    position = package.find('.pkg.tar')
    pkgext = package[position:]
    package = package[:position].split('-')
    arch = package[-1]
    pkgrel = package[-2]
    pkgver = package[-3]
    epoch = None
    if ':' in pkgver:
        epoch, pkgver = pkgver.split(':')
    pkgname = '-'.join(package[:-3])
    return pkgname, epoch, pkgver, pkgrel, arch, pkgext

def download_artifact_package(workflow, pkgbase, pkgname=None):
    if pkgname:
        logger.info(f'Downloading {pkgname} in {pkgbase} from {workflow} ...')
    else:
        logger.info(f'Downloading all packages in {pkgbase} from {workflow} ...')

    try:
        run(['gh', 'run', 'download', workflow, '-n', f'{pkgbase}.package', '-R', config['github']['cactus']])
    except:
        try:
            run(['gh', 'run', 'watch', workflow, '-R', config['github']['cactus']])
            run(['gh', 'run', 'download', workflow, '-n', f'{pkgbase}.package', '-R', config['github']['cactus']])
        except:
            raise Exception(f'Failed to download {pkgbase} from {workflow}.')

    for package in Path('.').glob('*.pkg.tar.zst'):
        if 'COLON' in package.name:
            package.rename(package.name.replace('COLON', ':'))

    if pkgname:
        matched = False
        for package in Path('.').glob('*.pkg.tar.zst'):
            _pkgname, _, _, _, _, _ = parse_package(package.name)
            if _pkgname == pkgname:
                matched = True
            else:
                remove(package)

        if not matched:
            raise Exception(f'No package named {pkgname} in {pkgbase}.')
