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
        try:
            status = Status.objects.get(key=pkgbase)
            if caller and status.status == 'STALE':
                status.status = 'FAILED'
                status.detail = f'Dependency issue: {caller}.'
                status.save()
        except:
            pass
        if pkgbase in reversed_dependency_graph:
            for i in reversed_dependency_graph[pkgbase]:
                recursively_fail(dependency_graph, reversed_dependency_graph, i, caller=pkgbase)

def recursively_skip(dependency_graph, reversed_dependency_graph, pkgbase, caller=None):
    if pkgbase in dependency_graph:
        if caller:
            del dependency_graph[pkgbase]
            try:
                status = Status.objects.get(key=pkgbase)
                if status.status == 'STALE':
                    status.detail = f'Waiting for dependency: {caller}.'
                    status.save()
            except:
                pass
        else:
            caller = pkgbase
        if pkgbase in reversed_dependency_graph:
            for i in reversed_dependency_graph[pkgbase]:
                recursively_skip(dependency_graph, reversed_dependency_graph, i, caller=caller)

if __name__ == '__main__':
    import os
    import sys
    import json
    import logging
    import traceback
    import yaml
    from graphlib import TopologicalSorter
    from pathlib import Path
    from datetime import datetime, timedelta
    from .. import config, logger
    from ..models import Status
    from ..builder import github_actions

    logger.setLevel(logging.INFO)

    repository = Path(sys.argv[1])
    dependency_graph = {}
    reversed_dependency_graph = {}

    logger.info('Loading cactus.yaml')
    for i in repository.rglob('cactus.yaml'):
        try:
            pkgbase = str(i.parent)[len(str(repository))+1:]
            with open(i) as f:
                cactus = yaml.safe_load(f)
            depends = cactus['depends'] if 'depends' in cactus else []
            depends += cactus['makedepends'] if 'makedepends' in cactus else []
            if len(depends) == 0:
                add_edge(dependency_graph, pkgbase, 'dummy')
                add_edge(reversed_dependency_graph, 'dummy', pkgbase)
            else:
                for j in depends:
                    add_edge(dependency_graph, pkgbase, j)
                    add_edge(reversed_dependency_graph, j, pkgbase)
            logger.debug(f'Loaded %s', pkgbase)
        except:
            logger.error(f'Failed to load %s', pkgbase)
            traceback.print_exc()

    logger.info('Recursively skip packages')
    failed = [i.key for i in Status.objects.filter(status='FAILED')]
    staled = [i.key for i in Status.objects.filter(status='STALE')]
    scheduled = [i.key for i in Status.objects.filter(status='SCHEDULED')]
    building = [i.key for i in Status.objects.filter(status='BUILDING')]
    for i in failed + staled + scheduled + building:
        recursively_skip(dependency_graph, reversed_dependency_graph, i)

    logger.info('Start scheduling')
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
            if 'aarch64' in i:
                cactus['group'] = 'aarch64'
            else:
                cactus['group'] = resources['default']
        if resources[cactus['group']]['used'] < resources[cactus['group']]['total']:
            try:
                status = Status.objects.get(key=i)
            except:
                logger.warn('Cannot find %s in database. Skipping', i)
            logger.info('Schedule to build %s', i)
            github_actions.build(i, cactus['group'])
            status.status = 'SCHEDULED'
            status.detail = cactus['group']
            status.save()
            resources[cactus['group']]['used'] += 1
            logger.info('%s: %d / %d', cactus['group'], resources[cactus['group']]['used'], resources[cactus['group']]['total'])
