#!/bin/python
import os
import shutil
import subprocess

def run(command, **kwargs):
    return subprocess.run(command, check=True, **kwargs)

remove = os.remove
move = shutil.move
rmtree = shutil.rmtree

def symlink(source, target):
    try:
        os.symlink(source, target)
    except FileExistsError:
        os.remove(target)
        os.symlink(source, target)
