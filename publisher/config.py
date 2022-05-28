#!/bin/python
from .. import config

print(f'::set-output name=publisher_host::%s' % config['publisher']['host'])
print(f'::set-output name=publisher_port::%s' % config['publisher']['port'])
print(f'::set-output name=publisher_username::%s' % config['publisher']['username'])
print(f'::set-output name=publisher_path::%s' % config['publisher']['path'])

with open('archrepo2.ini', 'w') as f:
    f.write('[repository]\n')
    f.write(f"name: {config['pacman']['repository']}\n")
    f.write('path: repository\n')
    f.write(f"supported-archs: {config['pacman']['archs']}\n")
    f.write('notification-type: simple-udp\n')
    f.write('notification-addresses: 127.0.0.1:9900\n')
    f.write('notification-secret: secret\n')
