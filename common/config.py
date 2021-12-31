#!/bin/python
from .. import config

print(f'::set-output name=pacman_repository::%s' % config['pacman_repository'])
print(f'::set-output name=github_repository::%s' % config['github_repository'])
