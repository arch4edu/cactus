if __name__ == '__main__':
    from github import Github
    from .. import config

    g = Github(config['github']['token'])
    g.get_repo(config['github']['cactus']).get_workflow("scheduler.yml").create_dispatch('main')
