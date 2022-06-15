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

    with open(Path(__file__).parent / 'aliases.yaml') as f:
        aliases = yaml.safe_load(f)

    config = Options()
    config.__config__.oldver = '/dev/null'
    config.__config__.newver = 'newver.json'

    for i in repository.rglob('cactus.yaml'):
        try:
            pkgbase = str(i.parent)[len(str(repository))+1:]
            with open(i) as f:
                cactus = yaml.safe_load(f)
            for j, nvchecker in enumerate(cactus['nvchecker']):
                if 'alias' in nvchecker.keys():
                    config[f'{pkgbase}:{j}'] = aliases[nvchecker['alias']]
                else:
                    for key, value in nvchecker.items():
                        if value is None:
                            nvchecker[key] = i.parent.name
                    config[f'{pkgbase}:{j}'] = nvchecker
            logger.debug('Loaded %s', pkgbase)
        except:
            logger.error(f'Failed to load %s', pkgbase)
            try:
                status = Status.objects.get(key=pkgbase)
            except:
                status = Status(key=key)
            status.status = 'FAILED'
            status.detail = 'Failed to load cactus.yaml.'
            traceback.print_exc()

    with open('nvchecker.toml', 'w') as f:
        toml.dump(config, f)
