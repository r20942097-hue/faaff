"""Strict shared command registry; no shell execution or credential inspection."""
import json
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
import re
import subprocess
import signal
import time
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
    grace = item.get('interrupt_grace_seconds', 0)
    if type(grace) is not int or not 0 <= grace <= 10 or grace >= seconds:
        raise ValueError('interrupt_grace_seconds must be 0 to 10 and below the timeout')


def validate_directories(directories):
    if not isinstance(directories, list) or not all(isinstance(name, str) for name in directories):
        raise ValueError('directories must be a path array')
    if len(directories) > 32 or len(set(directories)) != len(directories):
        raise ValueError('too many or duplicate input directories')
    for name in directories:
        relative_path(name)
        if ':' in name or any(part.startswith('.') or part == '__pycache__' for part in name.split('/')):
            raise ValueError('invalid input directory path')


def validate_module_inputs(entries):
    if not isinstance(entries, list) or len(entries) > 32:
        raise ValueError('module_inputs must be an array of at most 32 mappings')
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {'module', 'files'}:
            raise ValueError('module input requires module and files only')
        name, files = entry['module'], entry['files']
        if (not isinstance(name, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*', name)
                or name in seen):
            raise ValueError('invalid or duplicate module input name')
        seen.add(name)
        if (not isinstance(files, list) or not 1 <= len(files) <= 128
                or not all(isinstance(name, str) for name in files) or len(set(files)) != len(files)):
            raise ValueError('module input requires unique Python source files')
        for name in files:
            relative_path(name)
            if not name.endswith('.py') or ':' in name or any(part.startswith('.') for part in name.split('/')):
                raise ValueError('module input must be a portable Python source path')


def selected_module_inputs(tool, registry=None):
    entries = {}
    for owner in [tool, *selected_groups(tool, registry)]:
        for entry in owner.get('module_inputs', []):
            name, files = entry['module'], sorted(entry['files'])
            if name in entries and entries[name] != files:
                raise ValueError('conflicting module input mappings')
            entries[name] = files
    if len(entries) > 32:
        raise ValueError('too many combined module input mappings')
    return [{'module': name, 'files': files} for name, files in sorted(entries.items())]


def load(path=REGISTRY, check_consistency=True):
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
        validate_directories(item.get('directories', []))
        validate_module_inputs(item.get('module_inputs', []))
        for name in item['files']:
            relative_path(name)
        for name in item['binaries'] + item['modules']:
            if not isinstance(name, str) or not re.fullmatch('[a-zA-Z0-9_.-]+', name):
                raise ValueError('invalid dependency name')
        for command in item['commands']:
            argv(command)
    groups = data.get('input_groups', [])
    if not isinstance(groups, list):
        raise ValueError('input_groups must be an array')
    group_ids = set()
    for group in groups:
        if (not isinstance(group, dict) or not isinstance(group.get('id'), str)
                or not re.fullmatch('[a-z][a-z0-9-]*', group['id']) or group['id'] in group_ids
                or not isinstance(group.get('name'), str) or not group['name']):
            raise ValueError('invalid or duplicate input group')
        group_ids.add(group['id'])
        members, files = group.get('tools'), group.get('files')
        directories = group.get('directories', [])
        validate_directories(directories)
        validate_module_inputs(group.get('module_inputs', []))
        if (not isinstance(members, list) or not members or not all(isinstance(m, str) and m in seen for m in members)
                or len(set(members)) != len(members) or not isinstance(files, list) or not (files or directories or group.get('module_inputs'))):
            raise ValueError('invalid input group members or files')
        for name in files:
            relative_path(name)
        if len(set(files)) != len(files):
            raise ValueError('duplicate input group file')
    for tool in data['tools']:
        selected_module_inputs(tool, data)
        if len(selected_directories(tool, data)) > 32:
            raise ValueError('too many combined input directories')
    names = set()
    for item in data['checks']:
        if not isinstance(item, dict) or not isinstance(item.get('name'), str) or item['name'] in names:
            raise ValueError('invalid or duplicate check name')
        names.add(item['name'])
        validate_command(item)
        argv(item['argv'])
        if item.get('interrupt_grace_seconds', 0):
            raise ValueError('interrupt grace is supported on registered tools only')
    if check_consistency:
        from check_settings import audit
        report = audit(data)
        if not report['passed']:
            raise ValueError('inconsistent tool registry: ' + '; '.join(report['errors']))
    return data


def expand(command, root):
    argv(command)
    return [part.replace('{root}', str(Path(root).resolve())).replace('{python}', sys.executable) for part in command]


def execute(command, root, cwd='.', timeout=120, interrupt_grace=0):
    directory = safe_path(root, cwd, allow_dot=True)
    return run_process(expand(command, root), directory, timeout, interrupt_grace=interrupt_grace)


def run_process(command, directory, timeout=120, environment=None, interrupt_grace=0):
    """Capture a trusted argv without a shell; retain partial timeout diagnostics."""
    if interrupt_grace:
        return run_captured_process(command, directory, timeout, environment, interrupt_grace)
    try:
        result = subprocess.run(command, cwd=directory, capture_output=True, text=True,
                                encoding='utf-8', errors='backslashreplace',
                                env=child_environment() if environment is None else environment,
                                timeout=timeout, check=False, shell=False)
        report = {'exit_code': result.returncode, 'output': result.stdout + result.stderr}
        if result.returncode == 130:report['interrupted'] = True
        return report
    except subprocess.TimeoutExpired as error:
        def decoded(value):
            return value.decode('utf-8', errors='backslashreplace') if isinstance(value, bytes) else value or ''
        partial = decoded(error.stdout) + decoded(error.stderr)
        return {'exit_code': 124, 'error': 'TimeoutExpired',
                'output': partial + ('\n' if partial and not partial.endswith('\n') else '') + f'timeout after {timeout} seconds'}
    except OSError as error:
        return {'exit_code': 127, 'error': type(error).__name__, 'output': str(error)}


def communicate_process(process,timeout):
    deadline=time.monotonic()+timeout
    partial=None
    while True:
        remaining=deadline-time.monotonic()
        if remaining<=0:
            raise subprocess.TimeoutExpired(process.args,timeout,
                output=getattr(partial,'stdout',None),stderr=getattr(partial,'stderr',None))
        try:return process.communicate(timeout=min(0.1,remaining))
        except subprocess.TimeoutExpired as error:partial=error


def run_captured_process(command,directory,timeout,environment,interrupt_grace):
    """Let a supervising child finish its cleanup before forcing its termination."""
    options={'cwd':directory,'stdout':subprocess.PIPE,'stderr':subprocess.PIPE,'text':True,
             'encoding':'utf-8','errors':'backslashreplace',
             'env':child_environment() if environment is None else environment}
    if os.name=='nt':options['creationflags']=subprocess.CREATE_NEW_PROCESS_GROUP
    try:process=subprocess.Popen(command,**options)
    except OSError as error:return {'exit_code':127,'error':type(error).__name__,'output':str(error)}
    interrupted,timed_out,forced=False,False,False
    handlers={}
    try:
        stdout,stderr=communicate_process(process,timeout)
    except (KeyboardInterrupt,subprocess.TimeoutExpired) as error:
        interrupted=isinstance(error,KeyboardInterrupt);timed_out=not interrupted
        for name in ['SIGINT','SIGBREAK']:
            value=getattr(signal,name,None)
            if value is not None:
                try:handlers[value]=signal.signal(value,signal.SIG_IGN)
                except ValueError:pass
        try:
            try:process.send_signal(signal.CTRL_BREAK_EVENT if os.name=='nt' else signal.SIGINT)
            except OSError:
                forced=True
                try:process.terminate()
                except OSError:pass
            try:stdout,stderr=communicate_process(process,interrupt_grace)
            except subprocess.TimeoutExpired:
                forced=True;process.kill()
                try:stdout,stderr=communicate_process(process,5)
                except subprocess.TimeoutExpired as remaining:
                    def decoded(value):return value.decode('utf-8','backslashreplace') if isinstance(value,bytes) else value or ''
                    stdout,stderr=decoded(remaining.stdout),decoded(remaining.stderr)
        finally:
            for value,handler in handlers.items():signal.signal(value,handler)
    report={'exit_code':130 if interrupted else 124 if timed_out else process.returncode,
            'output':stdout+stderr,'controller_forced':forced}
    if interrupted or report['exit_code']==130:report['interrupted']=True
    if timed_out:
        report['error']='TimeoutExpired'
        report['output']+='\n'+f'timeout after {timeout} seconds'
    return report


def child_environment():
    environment = os.environ.copy()
    environment['PYTHONUTF8'] = '1'
    environment['PYTHONIOENCODING'] = 'utf-8'
    return environment


def selected_groups(tool, registry=None):
    return [group for group in (registry or {}).get('input_groups', []) if tool.get('id') in group['tools']]


def directory_files(root, name):
    """Enumerate explicitly declared Python sources; no symlink traversal or imports."""
    root = Path(root).resolve()
    directory = safe_path(root, name)
    if not directory.is_dir():
        raise ValueError('input directory missing or not a directory')
    pending, files, entries = [(directory, 0)], [], 0
    while pending:
        current, depth = pending.pop()
        if depth > 32:
            raise ValueError('input directory exceeds depth limit 32')
        safe_path(root, current.relative_to(root).as_posix())
        with os.scandir(current) as stream:
            for entry in stream:
                entries += 1
                if entries > 4096:
                    raise ValueError('input directory exceeds entry limit 4096')
                if entry.is_symlink():
                    raise ValueError('symlink in input directory')
                if entry.is_dir(follow_symlinks=False):
                    if entry.name == '__pycache__':
                        continue
                    if entry.name.startswith('.'):
                        raise ValueError('hidden directory in input directory')
                    pending.append((Path(entry.path), depth + 1))
                elif entry.is_file(follow_symlinks=False):
                    if entry.name.endswith('.py'):
                        relative = Path(entry.path).relative_to(Path(root)).as_posix()
                        safe_path(root, relative)
                        files.append(relative)
                else:
                    raise ValueError('nonregular entry in input directory')
    if not files:
        raise ValueError('input directory has no Python sources')
    return sorted(files)


def selected_directories(tool, registry=None):
    return sorted(set(tool.get('directories', [])) | {name for group in selected_groups(tool, registry) for name in group.get('directories', [])})


def directory_inventory(root, tool, registry=None):
    inventory, errors = {}, {}
    for name in selected_directories(tool, registry):
        try:
            inventory[name] = directory_files(root, name)
        except (OSError, ValueError) as error:
            inventory[name] = []
            errors[name] = str(error) if isinstance(error, ValueError) else type(error).__name__
    return inventory, errors


def registered_files(tool, registry=None, root=None):
    declared = set(tool['files']) | {name for group in selected_groups(tool, registry) for name in group['files']}
    declared.update(name for entry in selected_module_inputs(tool, registry) for name in entry['files'])
    if root is not None:
        inventory, errors = directory_inventory(root, tool, registry)
        if errors:
            raise ValueError('invalid registered directories: ' + ', '.join(sorted(errors)))
        declared.update(name for members in inventory.values() for name in members)
    return sorted(declared)


def input_identity(root, tool, registry=None):
    """Identify declared files, Python directory membership and configuration."""
    root = Path(root).resolve()
    files = {}
    groups = selected_groups(tool, registry)
    inventory, errors = directory_inventory(root, tool, registry)
    names = set(registered_files(tool, registry)) | {name for members in inventory.values() for name in members}
    for name in sorted(names):
        try:
            path = safe_path(root, name)
            with path.open('rb') as stream:
                files[name] = hashlib.file_digest(stream, 'sha256').hexdigest()
        except (ValueError, OSError):
            files[name] = None
    definition_value = {'tool': tool, 'input_groups': groups} if groups else tool
    definition = json.dumps(definition_value, sort_keys=True, ensure_ascii=True, separators=(',', ':')).encode('utf-8')
    identity = {'schema': 'registered-tool-inputs/v1', 'tool_definition_sha256': hashlib.sha256(definition).hexdigest(),
                'files': files, 'scope': 'Declared files, Python sources in explicit directories and tool definition only; external services, binaries and all transitive inputs are not fingerprinted.'}
    if selected_module_inputs(tool, registry):
        identity['module_inputs'] = selected_module_inputs(tool, registry)
    if selected_directories(tool, registry):
        identity.update(directories=inventory, directory_errors=errors)
    return identity


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
    report['inputs_before'] = input_identity(root, tool, data)
    write_report(destination, report)
    ready = next(item for item in inspect(root, registry=data)['tools'] if item['id'] == key)
    if ready['status'] != 'ready' or not tool['commands']:
        report.update(status='blocked', missing=ready['missing'], finished_at_utc=datetime.now(timezone.utc).isoformat())
        write_report(destination, report)
        print('BLOCKED: ' + tool['name'] + '; ' + ', '.join(ready['missing']))
        return 2
    results = []
    guarded_inputs = bool(selected_directories(tool, data) or selected_module_inputs(tool, data))
    for command in tool['commands']:
        if guarded_inputs and report['inputs_before'] != input_identity(root, tool, data):
            print('INPUT CHANGED: stopping before the next command')
            results.append({'exit_code': 3, 'output': 'registered directory or module inputs changed before execution'})
            break
        try:
            if tool.get('interrupt_grace_seconds', 0):
                result = execute(command, root, tool['cwd'], tool['timeout_seconds'], interrupt_grace=tool['interrupt_grace_seconds'])
            else:
                result = execute(command, root, tool['cwd'], tool['timeout_seconds'])
        except KeyboardInterrupt:
            result = {'exit_code': 130, 'output': 'interrupted by user', 'interrupted': True}
        results.append(result)
        report['checks'] = results
        write_report(destination, report)
        print(result['output'], end='' if result['output'].endswith('\n') else '\n')
        if result['exit_code']:
            break
        if guarded_inputs and report['inputs_before'] != input_identity(root, tool, data):
            print('INPUT CHANGED: stopping remaining commands')
            results.append({'exit_code': 3, 'output': 'registered directory or module inputs changed during execution'})
            break
    passed = all(result['exit_code'] == 0 for result in results)
    report.update(checks=results, passed=passed, status='interrupted' if results[-1].get('interrupted') else 'passed' if passed else 'failed',
                  finished_at_utc=datetime.now(timezone.utc).isoformat())
    report['inputs_after'] = input_identity(root, tool, data)
    report['inputs_unchanged_during_run'] = report['inputs_before'] == report['inputs_after']
    if guarded_inputs and not report['inputs_unchanged_during_run'] and report['passed']:
        print('INPUT CHANGED: final input check failed')
        report.update(passed=False, status='failed')
        report['checks'].append({'exit_code': 3, 'output': 'registered directory or module inputs changed during execution'})
    write_report(destination, report)
    return report['checks'][-1]['exit_code']
