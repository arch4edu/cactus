#!/bin/python

# Final detector stage: flag packages whose binaries need a shared library that
# no longer exists in any repo (an soname bump left them dangling). The producing
# side lives in the publisher -- repo-add records each package's DT_NEEDED sonames
# into the `links` database via bin/scan-links -- and this consumes it.
#
# Warn-only: it writes a `Broken links: ...` note into Status.detail for a package
# whose check is enabled, and never changes status. It only touches PUBLISHED rows
# -- exactly the set the links database describes -- whose detail is always empty or
# a prior note, so it cannot collide with the scheduler's detail=group slot tag or
# update.py's `nvchecker failed` / `Retry` details.
#
# Per-package opt via `check-links` in cactus.yaml: default true, but false for
# `-bin` packages, whose dangling links are usually bundled/foreign libraries a
# rebuild cannot fix.

import io
import re
import subprocess
import tarfile
import traceback
import urllib.request
from pathlib import Path

# Each arch runs the check in its own container: the available-.so set comes from
# this container's own `pacman -Fyy`, which can only see its own architecture's
# repos, so aarch64 needs a second run on an ARM host.
PREFIX = 'Broken links: '
# The dynamic loader and libc are never "missing"; musl and other foreign libcs
# ride along in bundled binaries and cannot be resolved from Arch repos.
IGNORE = re.compile(r'^(ld-linux.*|ld\.so.*|libc\.so.*|libc\.musl.*)$')


def read_db(blob):
    # A pacman db/links tarball is entries of <name-ver-rel>/<file>. Return
    # {entry: {field: [values]}} for the desc/links files inside.
    out = {}
    with tarfile.open(fileobj=io.BytesIO(blob)) as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            entry = member.name.split('/')[0]
            text = tar.extractfile(member).read().decode('utf-8', 'replace')
            fields = out.setdefault(entry, {})
            key = None
            for line in text.splitlines():
                if line.startswith('%') and line.endswith('%'):
                    key = line
                    fields[key] = []
                elif line and key:
                    fields[key].append(line)
    return out


def fetch(mirror, arch, name):
    url = f'{mirror}/{arch}/{name}'
    with urllib.request.urlopen(url, timeout=120) as response:
        return response.read()


def available_sonames(arch):
    # Every .so provided by an installed sync database, basename only, matching how
    # DT_NEEDED records a soname. On x86_64 multilib is enabled so a native package
    # linking a 32-bit-only library is not falsely flagged; aarch64 has no multilib.
    if arch == 'x86_64':
        subprocess.run(
            ['bash', '-c',
             'grep -q "^\\[multilib\\]" /etc/pacman.conf || '
             'printf "[multilib]\\nInclude = /etc/pacman.d/mirrorlist\\n" >> /etc/pacman.conf'],
            check=True)
    subprocess.run(['pacman', '-Fyy'], check=True)
    sonames = set()
    for db in Path('/var/lib/pacman/sync').glob('*.files'):
        listing = subprocess.run(
            ['bsdtar', '-xOf', db, '--include', '*/files'],
            capture_output=True, check=True).stdout.decode('utf-8', 'replace')
        for line in listing.splitlines():
            if '.so' in line and '/' in line:
                sonames.add(line.rsplit('/', 1)[1])
    return sonames


if __name__ == '__main__':
    import sys
    import yaml
    from .. import config, logger
    from ..models import Status

    repository = Path(sys.argv[1])
    arch = sys.argv[2] if len(sys.argv) > 2 else 'x86_64'
    repo = config['pacman']['repository']
    mirror = config['pacman'].get('mirror') or 'https://repo.arch4edu.org'

    # Best-effort: this is a warn-only pass that runs after the database update, so a
    # transient mirror or pacman failure should be logged and skipped, not turn the
    # whole detector run red. It runs again in 12 hours.
    try:
        available = available_sonames(arch)
        # arch4edu's own libraries satisfy each other's links.
        repo_files = read_db(fetch(mirror, arch, f'{repo}.files.tar.gz'))
        # The links database copies each package's db `desc` alongside its `links`
        # file, so %BASE% is read from the links entry itself -- no version-skewed
        # join with the files database.
        links = read_db(fetch(mirror, arch, f'{repo}.links.tar.gz'))
    except Exception:
        logger.error('Could not gather link data; skipping the check this run')
        traceback.print_exc()
        sys.exit(0)

    for fields in repo_files.values():
        for path in fields.get('%FILES%', []):
            if '.so' in path and '/' in path:
                available.add(path.rsplit('/', 1)[1])

    # Map a pkgbase to its Status key -- the cactus.yaml path relative to the
    # checkout, which nests under category dirs (x86_64/r/r-ade4) and does not track
    # %ARCH% (octave-io is x86_64 but lives under any/). Rebuilding it from
    # %ARCH%/%BASE% would miss over half the repository.
    paths = {}
    for cactus_yaml in repository.rglob('cactus.yaml'):
        paths.setdefault(cactus_yaml.parent.name, []).append(
            cactus_yaml.parent.relative_to(repository).as_posix())

    logger.info('Checking links against %d available sonames', len(available))
    broken = {}       # repo_path -> {soname}
    checked = set()   # repo_paths actually evaluated this run
    # The per-arch links database describes this arch's packages plus `any` packages;
    # `any` is architecture-independent and shares one Status row, so only the primary
    # x86_64 run owns it -- aarch64 considers only aarch64/ dirs.
    accept = (arch, 'any') if arch == 'x86_64' else (arch,)
    for fields in links.values():
        base = (fields.get('%BASE%') or [None])[0]
        if not base:
            continue
        repo_path = next(
            (p for p in paths.get(base, []) if p.split('/', 1)[0] in accept), None)
        if not repo_path:
            continue

        try:
            with open(repository / repo_path / 'cactus.yaml') as f:
                cactus = yaml.safe_load(f)
        except Exception:
            continue
        # Reached once the package is resolved and its config read: a real verdict for
        # it, so a stale note may be cleared below even when it now needs no libraries.
        # A package skipped above (unmapped, unreadable) keeps its note, no flapping.
        checked.add(repo_path)
        enabled = not base.endswith('-bin')
        if isinstance(cactus, dict) and 'check-links' in cactus:
            enabled = cactus['check-links']
        if not enabled:
            continue

        # DT_NEEDED is usually a bare soname, occasionally an rpath-style path;
        # compare basenames against the basename-keyed available set.
        missing = {
            so for so in {n.rsplit('/', 1)[-1] for n in fields.get('%LINKS%', [])}
            if so not in available and not IGNORE.match(so)
        }
        if missing:
            # Split packages share one repo_path; union their missing sonames.
            broken.setdefault(repo_path, set()).update(missing)

    logger.info('%d packages have broken links', len(broken))
    # Only PUBLISHED rows: they are exactly the packages the links database
    # describes, and their detail is always '' (set by the publisher) or a previous
    # broken-links note -- so this cannot collide with the scheduler's detail=group
    # slot tag, a FAILED reason, or the publisher's BUILT 'Download artifact failed'.
    for repo_path, missing in broken.items():
        detail = (PREFIX + ', '.join(sorted(missing)))[:200]
        if Status.objects.filter(key=repo_path, status='PUBLISHED').update(detail=detail):
            logger.warning('%s: %s', repo_path, detail)

    # Clear the note once a package resolves clean or turns the check off -- but only
    # for packages actually evaluated this run, so a transient skip does not wipe a
    # still-valid note. Same shape as update.py's nvchecker-failed recovery; keyed on
    # the prefix, which only this stage ever writes.
    for status in Status.objects.filter(detail__startswith=PREFIX):
        if status.key in checked and status.key not in broken:
            Status.objects.filter(key=status.key, detail__startswith=PREFIX).update(detail='')
            logger.debug('%s: links resolved', status.key)
