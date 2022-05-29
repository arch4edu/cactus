#!/bin/python
def get_pkgbase(entry):
    if type(entry) == dict:
        return list(entry.keys())[0]
    elif type(entry) == str:
        return entry
    else:
        raise ValueError

def add_edge(graph, source, target):
    source = get_pkgbase(source)
    target = get_pkgbase(target)
    if not source in graph:
        graph[source] = set()
    graph[source].add(target)

def recursively_fail(dependency_graph, reversed_dependency_graph, pkgbase, caller=None):
    if pkgbase in dependency_graph:
        del dependency_graph[pkgbase]
        status = Status.objects.get(key=pkgbase)
        if status.status == 'STALED':
            status.status = 'ERROR'
            status.detail = f'Dependency issue: {caller} .'
            status.save()
        if pkgbase in reversed_dependency_graph:
            for i in reversed_dependency_graph[pkgbase]:
                recursively_fail(dependency_graph, reversed_dependency_graph, i, caller=pkgbase)

def recursively_skip(dependency_graph, reversed_dependency_graph, pkgbase, caller=None):
    if pkgbase in dependency_graph:
        if caller:
            del dependency_graph[pkgbase]
            status = Status.objects.get(key=pkgbase)
            if status.status == 'STALED':
                status.detail = f'Waiting for dependency: {caller} .'
                status.save()
        else:
            caller = pkgbase
        if pkgbase in reversed_dependency_graph:
            for i in reversed_dependency_graph[pkgbase]:
                recursively_skip(dependency_graph, reversed_dependency_graph, i, caller=caller)

if __name__ == '__main__':
    import logging
    import json
    import os
    import sys
    import traceback
    import yaml
    from graphlib import TopologicalSorter
    from pathlib import Path
    from datetime import datetime, timedelta
    from tornado.log import enable_pretty_logging
    from tornado.options import options
    from ..models import Status
    from .. import config
    from ..builder import github_actions

    options.logging = 'debug'
    logger = logging.getLogger()
    enable_pretty_logging(options=options, logger=logger)

    repository = Path(sys.argv[1])
    dependency_graph = {}
    reversed_dependency_graph = {}

    for i in repository.rglob('cactus.yaml'):
        try:
            pkgbase = str(i.parent)[len(str(repository))+1:]
            with open(i) as f:
                cactus = yaml.safe_load(f)
            if not 'repo_depends' in cactus:
                add_edge(dependency_graph, pkgbase, 'dummy')
                add_edge(reversed_dependency_graph, 'dummy', pkgbase)
            else:
                for j in cactus['repo_depends']:
                    add_edge(dependency_graph, pkgbase, j)
                    add_edge(reversed_dependency_graph, j, pkgbase)
            logger.debug(f'Loaded %s', pkgbase)
        except:
            logger.error(f'Failed to load %s', pkgbase)
            traceback.print_exc()

    failed = [i.key for i in Status.objects.filter(status='ERROR')]
    for i in failed:
        recursively_fail(dependency_graph, reversed_dependency_graph, i)

    staled = [i.key for i in Status.objects.filter(status='STALED')]
    for i in staled:
        recursively_skip(dependency_graph, reversed_dependency_graph, i)

    building = [i.key for i in Status.objects.filter(status='BUILDING')]
    for i in building:
        recursively_skip(dependency_graph, reversed_dependency_graph, i)

    sorter = TopologicalSorter(dependency_graph)
    order = list(sorter.static_order())
    order = [i for i in order if i in staled]

    resources = config['scheduler']

    for group in resources.keys():
        if group == 'default':
            continue
        resources[group]['used'] = Status.objects.filter(detail=group).count()
        logger.info('%s: %d / %d', group, resources[group]['used'], resources[group]['total'])

    for i in order:
        if i == 'dummy':
            continue
        with open(repository / i / 'cactus.yaml') as f:
            cactus = yaml.safe_load(f)
        if not 'group' in cactus:
            if 'armv6h' in i or 'armv7h' in i or 'aarch64' in i:
                cactus['group'] = 'arm'
            else:
                cactus['group'] = resources['default']
        if resources[cactus['group']]['used'] < resources[cactus['group']]['total']:
            status = Status.objects.get(key=i)
            logger.info('Building %s', i)
            github_actions.build(i)
            status.status = 'BUILDING'
            status.detail = cactus['group']
            status.save()
