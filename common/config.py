#!/bin/python
import os
from .. import config

with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
    f.write(f"github_repository={config['github']['repository']}\n")
    f.write(f"github_token={config['github']['token']}\n")
    f.write(f"pacman_repository={config['pacman']['repository']}\n")
    f.write(f"pacman_keyring_repository={config['pacman']['keyring_repository']}\n")
    f.write(f"pacman_mirrorlist_repository={config['pacman']['mirrorlist_repository']}\n")
    f.write(f"pacman_archs={config['pacman']['archs']}\n")
