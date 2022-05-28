#!/bin/python
import base64
from .. import config

with open('gpg.key', 'wb') as f:
    key = config['pacman']['gpg_key']
    key = base64.b64decode(key)
    f.write(key)

with open('ssh.key', 'w') as f:
    f.write(config['publisher']['key'])
