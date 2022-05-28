from github import Github
from .. import config
from uuid import uuid1

g = Github(config['github']['token'])

def build(pkgbase):
    g.get_repo(config['github']['cactus']).get_workflow("builder_github_actions.yml").create_dispatch('main', {'pkgbase': pkgbase})
