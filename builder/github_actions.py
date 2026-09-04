from github import Github
from .. import config
from uuid import uuid1

g = Github(config['github']['token'])

WORKFLOWS = {
    'GitHubActions': 'builder_github_actions.yml',
    'GitHubActionsUnsafe': 'builder_github_actions_unsafe.yml',
    'x86_64': 'builder_self_hosted_x86_64.yml',
    'aarch64': 'builder_github_actions_aarch64.yml',
}

def build(pkgbase, group, cache_workflow_id=''):
    inputs = {'pkgbase': pkgbase}
    if group == 'GitHubActionsUnsafe' and cache_workflow_id:
        inputs['cache_workflow_id'] = cache_workflow_id
    g.get_repo(config['github']['cactus']).get_workflow(WORKFLOWS[group]).create_dispatch('main', inputs, throw=True)
