"""Strict shared command registry; no shell execution or credential inspection."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from tempfile import NamedTemporaryFile
import uuid

REGISTRY = Path(__file__).with_name('registry.json')


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def load_json(path):
    def invalid_number(value):
        raise ValueError('invalid JSON number: ' + value)
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique_object, parse_constant=invalid_number)


def relative_path(value, allow_dot=False):
    if not isinstance(value, str) or not value or '\\' in value or '\x00' in value:
        raise ValueError('invalid relative path')
    path = PurePosixPath(value)
    if value == '.' and allow_dot:
        return value
    if path.is_absolute() or any(p in {'', '.', '..', '.git', '.aws', '.codex', '.agents'} for p in value.split('/')):
        raise ValueError('unsafe relative path: ' + value)
    return value


def safe_path(root, value, allow_dot=False):
    relative_path(value, allow_dot)
    root = Path(root).resolve()
    path = root / value
    if not path.resolve().is_relative_to(root):
        raise ValueError('path escapes workspace: ' + value)
    current = path
    while current != root:
        if current.is_symlink():
            raise ValueError('symlink is not a source: ' + value)
        current = current.parent
    return path


def argv(value):
    if not isinstance(value, list) or not value or not all(isinstance(v, str) and v and '\x00' not in v for v in value):
        raise ValueError('argv must be a nonempty string array')
    if value[0] not in {'{python}', 'node'}:
        raise ValueError('unsupported command executable')
    for argument in value:
        if re.search(r'\{[^{}]+\}', argument.replace('{root}', '').replace('{python}', '')):
            raise ValueError('unknown command placeholder')
    return value


def validate_command(item):
    if not isinstance(item, dict) or not {'cwd', 'timeout_seconds'}.issubset(item):
        raise ValueError('command requires cwd and timeout_seconds')
    relative_path(item['cwd'], allow_dot=True)
    seconds = item['timeout_seconds']
    if type(seconds) is not int or not 1 <= seconds <= 600:
        raise ValueError('timeout_seconds must be an integer from 1 to 600')


def load(path=REGISTRY):
    data = load_json(path)
    if not isinstance(data, dict) or data.get('schema') != 'workspace-tools/v1' or not isinstance(data.get('tools'), list) or not isinstance(data.get('checks'), list):
        raise ValueError('invalid tools registry schema')
    seen = set()
    for item in data['tools']:
        if not isinstance(item, dict) or not isinstance(item.get('id'), str) or not re.fullmatch('[a-z][a-z0-9-]*', item['id']) or item['id'] in seen:
            raise ValueError('invalid or duplicate tool id')
        seen.add(item['id'])
        if not isinstance(item.get('name'), str) or not item['name']:
            raise ValueError('missing tool name')
        validate_command(item)
        for key in ['files', 'binaries', 'modules', 'commands']:
            if not isinstance(item.get(key), list):
                raise ValueError('missing tool list: ' + key)
        for name in item['files']:
            relative_path(name)
        for name in item['binaries'] + item['modules']:
            if not isinstance(name, str) or not re.fullmatch('[a-zA-Z0-9_.-]+', name):
                raise ValueError('invalid dependency name')
        for command in item['commands']:
            argv(command)
    names = set()
    for item in data['checks']:
        if not isinstance(item, dict) or not isinstance(item.get('name'), str) or item['name'] in names:
            raise ValueError('invalid or duplicate check name')
        names.add(item['name'])
        validate_command(item)
        argv(item['argv'])
    return data


def expand(command, root):
    argv(command)
    return [part.replace('{root}', str(Path(root).resolve())).replace('{python}', sys.executable) for part in command]


def execute(command, root, cwd='.', timeout=120):
    directory = safe_path(root, cwd, allow_dot=True)
    try:
        result = subprocess.run(expand(command, root), cwd=directory, capture_output=True, text=True,
                                encoding='utf-8', env=child_environment(), timeout=timeout, check=False, shell=False)
        return {'exit_code': result.returncode, 'output': result.stdout + result.stderr}
    except subprocess.TimeoutExpired:
        return {'exit_code': 124, 'output': f'timeout after {timeout} seconds'}
    except OSError as error:
        return {'exit_code': 127, 'output': str(error)}


def child_environment():
    environment = os.environ.copy()
    environment['PYTHONUTF8'] = '1'
    environment['PYTHONIOENCODING'] = 'utf-8'
    return environment


def write_report(destination, report):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(mode='w', encoding='utf-8', newline='', dir=destination.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def run_tool(root, key):
    from doctor import inspect
    data = load()
    tool = next((item for item in data['tools'] if item['id'] == key), None)
    if tool is None:
        raise ValueError('unknown tool: ' + key)
    destination = safe_path(root, 'catalog/results/tool-' + key + '.json')
    report = {'schema': 'workspace-tool-run/v1', 'run_id': uuid.uuid4().hex, 'tool': key,
              'started_at_utc': datetime.now(timezone.utc).isoformat(), 'status': 'running', 'passed': False,
              'python': {'executable': sys.executable, 'version': sys.version.split()[0]}, 'checks': []}
    write_report(destination, report)
    ready = next(item for item in inspect(root, registry=data)['tools'] if item['id'] == key)
    if ready['status'] != 'ready' or not tool['commands']:
        report.update(status='blocked', missing=ready['missing'], finished_at_utc=datetime.now(timezone.utc).isoformat())
        write_report(destination, report)
        print('BLOCKED: ' + tool['name'] + '; ' + ', '.join(ready['missing']))
        return 2
    results = []
    for command in tool['commands']:
        result = execute(command, root, tool['cwd'], tool['timeout_seconds'])
        results.append(result)
        print(result['output'], end='' if result['output'].endswith('\n') else '\n')
        if result['exit_code']:
            break
    passed = all(result['exit_code'] == 0 for result in results)
    report.update(checks=results, passed=passed, status='passed' if passed else 'failed',
                  finished_at_utc=datetime.now(timezone.utc).isoformat())
    write_report(destination, report)
    return results[-1]['exit_code']
