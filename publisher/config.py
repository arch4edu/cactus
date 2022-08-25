#!/bin/python
from .. import config
from ..common.util import run

with open('/root/.ssh/known_hosts', 'w') as f:
    f.write(run(['ssh-keyscan', '-p', str(config['publisher']['port']), config['publisher']['host']], capture_output=True).stdout.decode('utf-8'))

with open('/root/.ssh/config', 'w') as f:
    f.write('Host repository\n')
    f.write(f"\tHostname {config['publisher']['host']}\n")
    f.write(f"\tPort {config['publisher']['port']}\n")
    f.write(f"\tUser {config['publisher']['user']}\n")
    f.write("\tIdentityFile /root/.ssh/ssh_key\n")
