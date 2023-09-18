from github import Github
from .. import config
from uuid import uuid1

g = Github(config['github']['token'])

def build(pkgbase, group):
    if group == 'GitHubActions':
        g.get_repo(config['github']['cactus']).get_workflow("builder_github_actions.yml").create_dispatch('main', {'pkgbase': pkgbase})
    elif group == 'GitHubActionsUnsafe':
        g.get_repo(config['github']['cactus']).get_workflow("builder_github_actions_unsafe.yml").create_dispatch('main', {'pkgbase': pkgbase})
    elif group == 'x86_64':
        g.get_repo(config['github']['cactus']).get_workflow("builder_self_hosted_x86_64.yml").create_dispatch('main', {'pkgbase': pkgbase})
    elif group == 'aarch64':
        g.get_repo(config['github']['cactus']).get_workflow("builder_self_hosted_aarch64.yml").create_dispatch('main', {'pkgbase': pkgbase})
