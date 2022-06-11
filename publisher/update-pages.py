#!/bin/python

if __name__ == '__main__':
    import sys
    import json
    import logging
    import shutil
    from pathlib import Path
    from tornado.log import enable_pretty_logging
    from tornado.options import options
    from .. import config
    from ..models import Status, Version

    options.logging = 'debug'
    logger = logging.getLogger()
    enable_pretty_logging(options=options, logger=logger)

    lines = []
    lines.append('Build status')
    lines.append('')
    lines.append('|Package|Status|Detail|Workflow|Timestamp|')
    lines.append('|:------|:-----|:-----|:-------|:--------|')
    url_prefix = 'https://github.com/arch4edu/cactus/actions/runs/'
    for record in Status.objects.all():
        lines.append(f'|{record.key}|{record.status}|{record.detail}|[{record.workflow}]({url_prefix}{record.workflow})|{record.timestamp}|')
    lines.append('')
    lines.append('<script src="https://unpkg.com/tablefilter@latest/dist/tablefilter/tablefilter.js"></script>')
    lines.append('<script src="./table.js"></script>')

    with open('pages/index.md', 'w') as f:
        f.write('\n'.join(lines))
