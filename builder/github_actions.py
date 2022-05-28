from github import Github
from .. import config
from uuid import uuid1

g = Github(config['github']['token'])

def build(pkgbase, uuid):
    inputs = {'pkgbase': pkgbase, 'uuid': uuid}
    g.get_repo('petronny/cactus').get_workflow("builder_github_actions.yml").create_dispatch('main', inputs)
