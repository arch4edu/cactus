#!/bin/python

if __name__ == '__main__':
    import logging
    import sys
    import traceback
    from pathlib import Path
    import yaml
    import toml
    from tornado.log import enable_pretty_logging
    from tornado.options import options
    from ..common.options import Options
    from ..models import Status

    options.logging = 'debug'
    logger = logging.getLogger()
    enable_pretty_logging(options=options, logger=logger)

    repository = Path(sys.argv[1])
    arch = sys.argv[2] if len(sys.argv) > 2 else 'x86_64'

    with open(Path(__file__).parent / 'aliases.yaml') as f:
        aliases = yaml.safe_load(f)

    config = Options()
    config.__config__.oldver = 'nvchecker/oldver.json'
    config.__config__.newver = 'nvchecker/newver.json'

    # An nvchecker entry runs in the stage matching its resolution-arch: the entry's
    # cactus-only `arch:` key if set, else the package's directory arch (x86_64/ and
    # any/ resolve to x86_64, aarch64/ to aarch64). The `arch:` key lets an aarch64
    # package track the x86_64 official version (e.g. gradle) by resolving in the
    # x86_64 stage against its native DB; it is stripped before dump.
    def dir_arch(pkgbase):
        return 'aarch64' if pkgbase.split('/', 1)[0] == 'aarch64' else 'x86_64'

    for i in repository.rglob('cactus.yaml'):
        try:
            pkgbase = str(i.parent)[len(str(repository))+1:]
            with open(i) as f:
                cactus = yaml.safe_load(f)
            entry_archs = set()
            emitted = False
            for j, nvchecker in enumerate(cactus['nvchecker']):
                resolution_arch = nvchecker.get('arch') or dir_arch(pkgbase)
                entry_archs.add(resolution_arch)
                if resolution_arch != arch:
                    continue
                if 'alias' in nvchecker.keys():
                    config[f'{pkgbase}:{j}'] = dict(aliases[nvchecker['alias']])
                else:
                    entry = {k: v for k, v in nvchecker.items() if k != 'arch'}
                    for key, value in entry.items():
                        if value is None:
                            entry[key] = i.parent.name
                    config[f'{pkgbase}:{j}'] = entry
                config[f'{pkgbase}:{j}']['user_agent'] = 'nvchecker'
                emitted = True
            if len(entry_archs) > 1:
                logger.warning(
                    '%s mixes nvchecker arches %s; failed/recovery bookkeeping '
                    'assumes one stage per package', pkgbase, sorted(entry_archs))
            if emitted:
                logger.debug('Loaded %s', pkgbase)
        except:
            logger.error(f'Failed to load %s', pkgbase)
            try:
                status = Status.objects.get(key=pkgbase)
            except:
                status = Status(key=pkgbase)
            status.status = 'FAILED'
            status.detail = 'Failed to load cactus.yaml.'
            traceback.print_exc()

    with open('nvchecker.toml', 'w') as f:
        toml.dump(config, f)
