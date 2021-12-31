#!/bin/python
from .. import config

print(f'::set-output name=pacman_repository::%s' % config['pacman']['repository'])
print(f'::set-output name=pacman_keyring_repository::%s' % config['pacman']['keyring_repository'])
print(f'::set-output name=pacman_mirrorlist_repository::%s' % config['pacman']['mirrorlist_repository'])
print(f'::set-output name=github_repository::%s' % config['github']['repository'])
print(f'::set-output name=email_name::%s' % config['email']['name'])
print(f'::set-output name=email_address::%s' % config['email']['address'])
