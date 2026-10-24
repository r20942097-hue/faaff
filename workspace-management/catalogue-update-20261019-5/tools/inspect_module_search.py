"""Observe standard Python path lookup without importing the declared packages."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone

from check_settings import command_entry
from registry import load, run_process, safe_path, selected_module_inputs, input_identity, write_report

ROOT = Path(__file__).resolve().parents[1]
MARKER = 'WORKSPACE_MODULE_SEARCH_RESULT:'
PROBE = r'''
import importlib.machinery
import json
import os
import sys

name = sys.argv[1]
paths = [os.path.abspath(value or os.getcwd()) for value in sys.path]
search = paths
chain = []
outcome = 'missing'
parts = name.split('.')
for index in range(len(parts)):
    fullname = '.'.join(parts[:index+1])
    spec = importlib.machinery.PathFinder.find_spec(fullname, search)
    if spec is None:
        break
    locations = list(spec.submodule_search_locations or [])
    chain.append({'module': fullname, 'origin': spec.origin,
                  'package': spec.submodule_search_locations is not None,
                  'locations': locations})
    if index < len(parts)-1:
        if spec.submodule_search_locations is None:
            outcome = 'parent_not_package'
            break
        search = locations
        continue
    if spec.submodule_search_locations is not None:
        main = importlib.machinery.PathFinder.find_spec(fullname+'.__main__', locations)
        if main is None:
            outcome = 'missing_main'
            break
        if main.submodule_search_locations is not None:
            outcome = 'main_is_package'
            break
        chain.append({'module': fullname+'.__main__', 'origin': main.origin,
                      'package': main.submodule_search_locations is not None,
                      'locations': list(main.submodule_search_locations or [])})
    outcome = 'found'
payload = {'outcome': outcome, 'chain': chain, 'search_path': paths,
           'flags': {name: getattr(sys.flags, name, None) for name in
                     ['isolated','safe_path','ignore_environment','no_site','no_user_site']},
           'python_version': sys.version.split()[0],
           'custom_meta_finders': sum(getattr(finder,'__module__','') not in
                                     ['_frozen_importlib','_frozen_importlib_external']
                                     for finder in sys.meta_path)}
print('WORKSPACE_MODULE_SEARCH_RESULT:'+json.dumps(payload, ensure_ascii=True), flush=True)
'''


def path_identity(root, value):
    """Keep workspace paths useful and avoid exposing external search-path values."""
    if value is None:
        return None
    path = Path(value)
    resolved = path.resolve()
    try:
        return {'kind': 'workspace', 'path': resolved.relative_to(root.resolve()).as_posix() or '.'}
    except ValueError:
        identity = os.path.normcase(str(resolved)).encode('utf-8', errors='backslashreplace')
        return {'kind': 'external', 'identity_sha256': hashlib.sha256(identity).hexdigest()}


def validate_payload(payload, module):
    """Accept only the bounded protocol emitted by our standard-path probe."""
    if not isinstance(payload, dict):
        raise ValueError('invalid probe response')
    chain = payload.get('chain')
    outcomes = {'found', 'missing', 'missing_main', 'parent_not_package', 'main_is_package'}
    outcome = payload.get('outcome')
    flags = payload.get('flags')
    names = ['isolated', 'safe_path', 'ignore_environment', 'no_site', 'no_user_site']
    if (not isinstance(outcome, str) or outcome not in outcomes
            or not isinstance(chain, list) or len(chain) > len(module.split('.')) + 1
            or not isinstance(flags, dict) or set(flags) != set(names)
            or any(value is not None and type(value) not in (int, bool) for value in flags.values())
            or not isinstance(payload.get('python_version'), str)
            or len(payload['python_version']) > 64
            or type(payload.get('custom_meta_finders')) is not int
            or payload['custom_meta_finders'] < 0
            or not isinstance(payload.get('search_path'), list)
            or any(not isinstance(value, str) or not os.path.isabs(value)
                   for value in payload['search_path'])):
        raise ValueError('invalid probe response')
    parts = module.split('.')
    allowed_names = ['.'.join(parts[:index+1]) for index in range(len(parts))] + [module+'.__main__']
    for index, item in enumerate(chain):
        if (not isinstance(item, dict) or item.get('module') != allowed_names[index]
                or type(item.get('package')) is not bool
                or (item.get('origin') is not None
                    and (not isinstance(item['origin'], str) or not os.path.isabs(item['origin'])))):
            raise ValueError('invalid probe response')
    if outcome == 'found' and (not chain or not isinstance(chain[-1].get('origin'), str)):
        raise ValueError('invalid probe response')
    return payload


def observe(root, tool, registry=None, runner=run_process, environment=None):
    root = Path(root).resolve()
    mappings = {entry['module']: entry['files'] for entry in selected_module_inputs(tool, registry)}
    results = []
    for command in tool['commands']:
        entry = command_entry(command, tool['cwd'])
        if entry['mode'] != 'module' or entry['module'] not in mappings:
            continue
        name = entry['module']
        result = {'tool': tool['id'], 'module': name, 'registered_files': mappings[name],
                  'status': 'unverified', 'runtime_import_verified': False}
        prefix = '' if tool['cwd'] == '.' else tool['cwd'] + '/'
        stem = prefix + name.replace('.', '/')
        entry_files = {stem + '.py', stem + '/__main__.py'} & set(mappings[name])
        try:
            expected = {os.path.normcase(str(safe_path(root, value).resolve())) for value in entry_files}
            if not expected or any(not safe_path(root, value).is_file() for value in entry_files):
                raise ValueError('registered entry source unavailable')
        except (OSError, ValueError, RuntimeError):
            result['status'] = 'registered_source_unavailable'
            results.append(result)
            continue
        options = entry.get('python_options', [])
        probe_command = [sys.executable, *options, '-c', PROBE, name]
        raw = runner(probe_command, safe_path(root, tool['cwd'], allow_dot=True),
                     timeout=5, environment=environment)
        result['probe_exit_code'] = raw['exit_code']
        if raw['exit_code']:
            result['status'] = 'probe_failed'
            results.append(result)
            continue
        try:
            messages = [line[len(MARKER):] for line in raw['output'].splitlines() if line.startswith(MARKER)]
            if len(messages) != 1:
                raise ValueError('invalid probe response')
            payload = validate_payload(json.loads(messages[0]), name)
            result.update(flags=payload['flags'], python_version=payload['python_version'],
                          custom_meta_finders=payload['custom_meta_finders'],
                          search_path=[path_identity(root, value) for value in payload['search_path']],
                          chain=[{'module': item['module'], 'origin': path_identity(root, item['origin']),
                                  'package': item['package']} for item in payload['chain']])
            if payload['outcome'] != 'found':
                result['status'] = payload['outcome']
            else:
                origin = payload['chain'][-1]['origin']
                actual = os.path.normcase(str(Path(origin).resolve())) if isinstance(origin, str) else None
                result['status'] = 'matches_registered_path' if actual in expected else 'different_source'
        except (OSError, ValueError, KeyError, TypeError, AttributeError, RuntimeError):
            result.update(status='invalid_probe_response')
        results.append(result)
    return results


def collect(root, registry=None, runner=run_process, environment=None):
    registry = load() if registry is None else registry
    started = datetime.now(timezone.utc).isoformat()
    owners = [tool for tool in registry['tools'] if selected_module_inputs(tool, registry)]
    before = {tool['id']: input_identity(root, tool, registry) for tool in owners}
    entries = [entry for tool in registry['tools']
               for entry in observe(root, tool, registry, runner=runner, environment=environment)]
    after = {tool['id']: input_identity(root, tool, registry) for tool in owners}
    return {'schema': 'workspace-module-search/v1',
            'started_at_utc': started, 'finished_at_utc': datetime.now(timezone.utc).isoformat(),
            'status': 'inputs_changed' if before != after else 'completed' if entries else 'not_applicable',
            'passed': (before == after and all(row['status'] == 'matches_registered_path' for row in entries)) if entries else None,
            'registered_inputs_before': before, 'registered_inputs_after': after,
            'registered_inputs_unchanged': before == after,
            'runtime_import_verified': False, 'entries': entries,
            'scope': 'PathFinder lookup in the registered cwd with the same Python startup options. '
                     'Declared package initializers and entry modules are not imported. '
                     'Startup hooks, parent __path__ changes, custom meta finders, concurrent edits '
                     'and transitive runtime imports are not verified. External paths are hashed.'}


def main(root=ROOT):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(root))
    args = parser.parse_args()
    target = safe_path(args.root, 'catalog/results/module-search.json')
    write_report(target, {'schema': 'workspace-module-search/v1', 'status': 'running', 'passed': False})
    try:
        report = collect(args.root)
    except (OSError, ValueError, TypeError) as error:
        write_report(target, {'schema': 'workspace-module-search/v1', 'status': 'failed',
                              'passed': False, 'error': type(error).__name__})
        parser.exit(1, 'MODULE SEARCH FAILED: ' + type(error).__name__ + '\n')
    write_report(target, report)
    print('MODULE SEARCH:', len(report['entries']), 'entries;', report['status'])
    return 0 if report['passed'] is not False else 1


if __name__ == '__main__':
    raise SystemExit(main())
