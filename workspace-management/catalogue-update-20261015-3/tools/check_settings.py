"""Audit declared command ownership and conflicting repeated execution settings."""
import json
from pathlib import Path
from datetime import datetime, timezone

from registry import load, relative_path, registered_files, selected_module_inputs, write_report

ROOT = Path(__file__).resolve().parents[1]


def command_entry(command, cwd):
    """Parse a documented subset of interpreter options without running commands."""
    python_flags = set('bBdEiIOPqRsSuvx')
    python_information = {'--help', '--help-env', '--help-xoptions', '--help-all', '--version'}
    node_flags = {'--trace-warnings', '--no-warnings', '--use-strict', '--check', '-c',
                  '--enable-source-maps', '--experimental-strip-types', '--experimental-transform-types',
                  '--inspect', '--inspect-brk'}
    node_values = {'--input-type', '--max-old-space-size'}
    index = 1
    local_path_disabled = False
    while index < len(command):
        token = command[index]
        if token == '--':
            index += 1
            break
        if token == '-':
            return {'mode': 'stdin', 'path': None}
        if not token.startswith('-'):
            break
        if command[0] == '{python}':
            if token in python_information:
                return {'mode': 'information', 'path': None}
            if token == '--check-hash-based-pycs':
                if index + 1 >= len(command):
                    raise ValueError('Python option requires a value')
                index += 2
                continue
            if token.startswith('--check-hash-based-pycs='):
                if not token.partition('=')[2]:
                    raise ValueError('Python option requires a value')
                index += 1
                continue
            if token.startswith('--'):
                raise ValueError('unsupported Python option')
            chars = token[1:]
            for position, character in enumerate(chars):
                if character in 'h?V':
                    return {'mode': 'information', 'path': None}
                if character in 'IP':
                    local_path_disabled = True
                if character in 'cmWX':
                    attached = chars[position + 1:]
                    if not attached:
                        if index + 1 >= len(command):
                            raise ValueError('Python option requires a value')
                        index += 1
                    if character == 'c':
                        return {'mode': 'inline', 'path': None}
                    if character == 'm':
                        name = attached or command[index]
                        import re
                        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*', name):
                            raise ValueError('invalid Python module name')
                        return {'mode': 'module', 'path': None, 'module': name, 'local_path_disabled': local_path_disabled}
                    break
                if character not in python_flags:
                    raise ValueError('unsupported Python option')
            index += 1
        else:
            if token in {'-h', '--help', '-v', '--version'}:
                return {'mode': 'information', 'path': None}
            if token in {'-e', '--eval', '-p', '--print'}:
                if index + 1 >= len(command):
                    raise ValueError('Node option requires a value')
                return {'mode': 'inline', 'path': None}
            if token.startswith(('--eval=', '--print=')):
                if not token.partition('=')[2]:
                    raise ValueError('Node option requires a value')
                return {'mode': 'inline', 'path': None}
            if token in node_flags or token.startswith(('--inspect=', '--inspect-brk=')):
                index += 1
            elif token in node_values:
                if index + 1 >= len(command):
                    raise ValueError('Node option requires a value')
                index += 2
            elif token.partition('=')[0] in node_values and token.partition('=')[1]:
                if not token.partition('=')[2]:
                    raise ValueError('Node option requires a value')
                index += 1
            else:
                raise ValueError('unsupported Node option')
    if index >= len(command):
        return {'mode': 'no-script', 'path': None}
    name = command[index]
    if name == '-':
        return {'mode': 'stdin', 'path': None}
    if command[0] == 'node' and name == 'inspect':
        return {'mode': 'inspection', 'path': None}
    anchored = name.startswith('{root}/')
    if anchored:
        name = name[len('{root}/'):]
    if any(character in name for character in ':{}'):
        raise ValueError('nonportable or placeholder script path')
    relative_path(name)
    return {'mode': 'script', 'path': relative_path(name if anchored or cwd == '.' else cwd + '/' + name)}


def script_path(command, cwd):
    return command_entry(command, cwd)['path']


def audit(data):
    # Callers obtain structurally validated registry data; this adds semantic checks.
    errors, warnings, entries, owners, excluded, mapped = [], [], {}, {}, [], []
    interrupt_graces = {}
    for tool in data['tools']:
        key = tool['id']
        for field in ('files', 'binaries', 'modules'):
            if len(tool[field]) != len(set(tool[field])):
                errors.append(f'{key}: duplicate {field}')
        seen = set()
        declared = set(registered_files(tool, data))
        mappings = {entry['module']: entry['files'] for entry in selected_module_inputs(tool, data)}
        used_mappings = set()
        for command in tool['commands']:
            signature = (tool['cwd'], tuple(command))
            if signature in seen:
                errors.append(f'{key}: duplicate command')
            seen.add(signature)
            try:
                entry = command_entry(command, tool['cwd'])
                path = entry['path']
                if entry['mode'] == 'module' and entry['module'] in mappings:
                    name = entry['module']
                    used_mappings.add(name)
                    prefix = '' if tool['cwd'] == '.' else tool['cwd'] + '/'
                    source = prefix + name.replace('.', '/')
                    if entry['local_path_disabled']:
                        errors.append(f'{key}: local module mapping is incompatible with Python -I/-P')
                    elif not ({source + '.py', source + '/__main__.py'} & set(mappings[name])):
                        errors.append(f'{key}: module mapping has no entry source under its cwd')
                    else:
                        mapped.append({'owner': key, 'module': name, 'files': mappings[name]})
                elif entry['mode'] != 'script':
                    excluded.append({'owner': key, 'mode': entry['mode']})
            except ValueError as error:
                errors.append(f'{key}: command entry cannot be checked: {error}')
                path = None
            if path is not None and path not in declared:
                errors.append(f'{key}: command script is not a registered input: {path}')
            interrupt_graces.setdefault(signature, set()).add(tool.get('interrupt_grace_seconds', 0))
            entries.setdefault(signature, []).append((key, tool['timeout_seconds']))
            owners.setdefault(signature, set()).add(key)
        if set(mappings) != used_mappings:
            errors.append(f'{key}: unused module input mapping')
    seen_checks = set()
    for check in data['checks']:
        if check.get('interrupt_grace_seconds', 0):
            errors.append('interrupt grace is supported on registered tools only')
        signature = (check['cwd'], tuple(check['argv']))
        if signature in seen_checks:
            errors.append('duplicate standard check command: ' + check['name'])
        seen_checks.add(signature)
        try:
            entry = command_entry(check['argv'], check['cwd'])
            if entry['mode'] != 'script':
                excluded.append({'owner': 'check: ' + check['name'], 'mode': entry['mode']})
        except ValueError as error:
            errors.append('check: ' + check['name'] + ': command entry cannot be checked: ' + str(error))
        interrupt_graces.setdefault(signature, set()).add(check.get('interrupt_grace_seconds', 0))
        entries.setdefault(signature, []).append(('check: ' + check['name'], check['timeout_seconds']))
    for signature, definitions in entries.items():
        if len(interrupt_graces.get(signature, set())) > 1:
            errors.append('conflicting interrupt grace for same cwd/argv: ' + ', '.join(name for name, _ in definitions))
        if len({timeout for _, timeout in definitions}) > 1:
            errors.append('conflicting timeout for same cwd/argv: ' + ', '.join(name for name, _ in definitions))
        if len(owners.get(signature, set())) > 1:
            warnings.append('shared invocation across tools: ' + ', '.join(sorted(owners[signature])))
    return {'schema': 'workspace-settings-audit/v1', 'passed': not errors,
            'errors': sorted(set(errors)), 'warnings': sorted(set(warnings)),
            'tools': len(data['tools']), 'standard_checks': len(data['checks']),
            'unique_invocations': len(entries), 'excluded_entries': excluded, 'module_input_entries': mapped,
            'scope': 'Declared inputs, Python/Node script ownership after supported interpreter flags, exact cwd/argv duplicate and timeout consistency only. Local module inputs are explicit source declarations, not proof of runtime import resolution; unregistered modules and all transitive dependencies are not inferred.'}


def main():
    destination = ROOT / 'catalog/results/settings-audit.json'
    running = {'schema': 'workspace-settings-audit/v1', 'status': 'running', 'passed': False,
               'started_at_utc': datetime.now(timezone.utc).isoformat()}
    write_report(destination, running)
    try:
        report = audit(load(check_consistency=False))
        report.update(status='passed' if report['passed'] else 'failed',
                      started_at_utc=running['started_at_utc'], finished_at_utc=datetime.now(timezone.utc).isoformat())
    except (OSError, ValueError, TypeError, KeyError) as error:
        report = dict(running, status='failed', errors=[type(error).__name__ + ': ' + str(error)],
                      finished_at_utc=datetime.now(timezone.utc).isoformat())
    write_report(destination, report)
    for error in report.get('errors', []):
        print('ERROR:', error)
    for warning in report.get('warnings', []):
        print('NOTICE:', warning)
    print('SETTINGS CHECK', 'PASSED' if report['passed'] else 'FAILED')
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
