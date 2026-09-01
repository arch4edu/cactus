#!/bin/python
import os
import shutil
import subprocess
import time
from pathlib import Path
from .. import config, logger

def run(command, **kwargs):
    if not 'check' in kwargs:
        kwargs['check'] = True
    return subprocess.run(command, **kwargs)

def rsync(arguments, **kwargs):
    for retry in range(5):
        if retry:
            time.sleep(retry * 30)
        output = run(['rsync', '-av', '--progress', '--timeout', '600'] + arguments, check=False, **kwargs)
        if output.returncode == 0:
            return
        logger.warning('rsync exited with %d', output.returncode)
    raise Exception(f'rsync failed after 5 attempts: {arguments}')

remove = os.remove
copy = shutil.copy2
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

def readable(archive):
    for command in (['gzip', '-t', archive], ['bsdtar', '-tf', archive]):
        output = run(command, check=False, capture_output=True)
        if output.returncode != 0:
            logger.warning('%s failed on %s: %s', command[0], archive, output.stderr.decode().strip())
            return False
    return True

def repair_databases(repository):
    pattern = f'{config["pacman"]["repository"]}.*.tar.gz'
    databases = set(repository.glob(f'*/{pattern}'))
    for backup in repository.glob(f'*/{pattern}.old'):
        databases.add(backup.with_name(backup.name.removesuffix('.old')))
    for database in sorted(databases):
        if database.exists() and readable(database):
            continue
        backup = database.with_name(f'{database.name}.old')
        if not backup.exists() or not readable(backup):
            raise Exception(f'{database} is unusable and {backup} cannot restore it.')
        logger.warning('%s is unusable. Restoring it from %s', database, backup)
        copy(backup, database)

def sync_repository(repository):
    if repository.exists():
        return
    rsync(['--exclude', '*.pkg*', '--exclude', '*.lck', f'repository:{config["publisher"]["path"]}/*', repository])
    repair_databases(repository)

def upload_packages(repository):
    pattern = f'{config["pacman"]["repository"]}.*'
    destination = f'repository:{config["publisher"]["path"]}'
    rsync(['--exclude', pattern, '--exclude', '.tmp.*', '--exclude', 'lastupdate', f'{repository}/', destination])

def upload_databases(repository):
    pattern = f'{config["pacman"]["repository"]}.*'
    destination = f'repository:{config["publisher"]["path"]}'
    databases = sorted(repository.glob(pattern)) + sorted(repository.glob(f'*/{pattern}'))
    paths = [str(database.relative_to(repository)) for database in databases if database.suffix != '.lck']
    rsync(['--relative'] + paths + [destination], cwd=repository)
    # rsync sorts its file list, so lastupdate needs its own transfer to land after the databases.
    rsync(['lastupdate', destination], cwd=repository)

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
