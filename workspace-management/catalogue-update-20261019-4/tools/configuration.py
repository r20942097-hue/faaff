"""Validate catalogue configuration before creating generated files or links."""
import re
from registry import load_json, relative_path, safe_path


def validate(root, config):
    if not isinstance(config, dict) or config.get('schema', 'workspace-catalog/v1') != 'workspace-catalog/v1':
        raise ValueError('invalid catalogue schema')
    if 'layout' in config:
        raise ValueError('layout is not a catalogue setting; use link_mode')
    if not isinstance(config.get('link_mode', 'symlink'), str) or config.get('link_mode', 'symlink') not in {'symlink', 'direct'}:
        raise ValueError('link_mode must be symlink or direct')
    if not isinstance(config.get('sources'), list):
        raise ValueError('sources must be an array')
    names, locations = set(), set()
    for source in config['sources']:
        if not isinstance(source, dict) or not isinstance(source.get('name'), str) or not re.fullmatch('[a-zA-Z0-9_-]+', source['name']):
            raise ValueError('invalid source name')
        relative_path(source.get('path'), allow_dot=True)
        if source['name'] in names or source.get('path') in locations:
            raise ValueError('duplicate source name or path')
        names.add(source['name'])
        locations.add(source.get('path'))
        safe_path(root, source['path'], allow_dot=True)
        if not isinstance(source.get('kind'), str) or source['kind'] not in {'repository', 'library', 'management'}:
            raise ValueError('invalid source kind')
        repository = source.get('repository')
        if repository is not None and (not isinstance(repository, str) or not re.fullmatch(r'https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository)):
            raise ValueError('invalid repository URL')
        reference = source.get('repository_ref')
        if reference is not None and (repository is None or not isinstance(reference, str) or not re.fullmatch('[0-9a-f]{40}', reference)):
            raise ValueError('repository_ref requires a repository and a full commit SHA')
        if 'include' in source:
            if not isinstance(source['include'], list):
                raise ValueError('include must contain unique paths')
            for name in source['include']:
                relative_path(name)
            if len(set(source['include'])) != len(source['include']):
                raise ValueError('include must contain unique paths')
        if source['path'] == '.' and 'include' not in source:
            raise ValueError('workspace root requires an explicit include list')
    relationships = config.get('filter_relationships', [])
    if not isinstance(relationships, list):
        raise ValueError('filter_relationships must be an array')
    for relation in relationships:
        if not isinstance(relation, dict):
            raise ValueError('filter relationship must be an object')
        safe_path(root, relation.get('base'))
        safe_path(root, relation.get('target'))
        if not isinstance(relation.get('extra_rules'), list) or not all(isinstance(rule, str) for rule in relation['extra_rules']):
            raise ValueError('extra_rules must be a string array')
    # Generated output paths must also remain inside the workspace.
    for path in ['catalog', 'catalog/generated', 'catalog/results']:
        safe_path(root, path)
    return config


def load(root):
    return validate(root, load_json(safe_path(root, 'catalog/config.json')))
