#!/bin/python
import os
import logging
import yaml
from pathlib import Path
from djangorm import DjangORM
from tornado.log import enable_pretty_logging
from tornado.options import options

options.logging = 'debug'
logger = logging.getLogger()
enable_pretty_logging(options=options, logger=logger)

file = Path(__file__).parent / 'config.local.yaml'
if not file.exists():
    file = Path(__file__).parent / 'config.yaml'

config = None
with open(file) as f:
    config = yaml.safe_load(f)

if 'CACTUS_CONFIG' in os.environ:
    config = yaml.safe_load(os.environ['CACTUS_CONFIG'])

db = DjangORM(module_name=Path(__file__).parent.name, database=config['database'], module_path=Path(__file__).parent.parent)
db.configure()
db.migrate()

if __name__ == '__main__':
    print(config)
