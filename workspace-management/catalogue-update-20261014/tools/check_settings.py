"""Audit declared command ownership and conflicting repeated execution settings."""
import json
from pathlib import Path
from datetime import datetime, timezone

from registry import load, relative_path, registered_files, write_report

ROOT = Path(__file__).resolve().parents[1]


def script_path(command, cwd):
    """Resolve direct Python/Node scripts lexically; modules/inline code are separate."""
    if len(command) < 2 or command[1].startswith('-'):
        return None
    name = command[1]
    if command[0] == 'node' and name in {'inspect', 'repl'}:
        return None
    if name.startswith('{root}/'):
        name = name[len('{root}/'):]
        relative_path(name)
        if any(character in name for character in ':{}'):
            raise ValueError('nonportable or placeholder script path')
        return name
    if any(character in name for character in ':{}'):
        raise ValueError('nonportable or placeholder script path')
    relative_path(name)
    return relative_path(name if cwd == '.' else cwd + '/' + name)


def audit(data):
    # Callers obtain structurally validated registry data; this adds semantic checks.
    errors, warnings, entries, owners = [], [], {}, {}
    for tool in data['tools']:
        key = tool['id']
        for field in ('files', 'binaries', 'modules'):
            if len(tool[field]) != len(set(tool[field])):
                errors.append(f'{key}: duplicate {field}')
        seen = set()
        declared = set(registered_files(tool, data))
        for command in tool['commands']:
            signature = (tool['cwd'], tuple(command))
            if signature in seen:
                errors.append(f'{key}: duplicate command')
            seen.add(signature)
            try:
                path = script_path(command, tool['cwd'])
            except ValueError:
                errors.append(f'{key}: unsafe direct script path')
                path = None
            if path is not None and path not in declared:
                errors.append(f'{key}: command script is not a registered input: {path}')
            entries.setdefault(signature, []).append((key, tool['timeout_seconds']))
            owners.setdefault(signature, set()).add(key)
    seen_checks = set()
    for check in data['checks']:
        signature = (check['cwd'], tuple(check['argv']))
        if signature in seen_checks:
            errors.append('duplicate standard check command: ' + check['name'])
        seen_checks.add(signature)
        entries.setdefault(signature, []).append(('check: ' + check['name'], check['timeout_seconds']))
    for signature, definitions in entries.items():
        if len({timeout for _, timeout in definitions}) > 1:
            errors.append('conflicting timeout for same cwd/argv: ' + ', '.join(name for name, _ in definitions))
        if len(owners.get(signature, set())) > 1:
            warnings.append('shared invocation across tools: ' + ', '.join(sorted(owners[signature])))
    return {'schema': 'workspace-settings-audit/v1', 'passed': not errors,
            'errors': sorted(set(errors)), 'warnings': sorted(set(warnings)),
            'tools': len(data['tools']), 'standard_checks': len(data['checks']),
            'unique_invocations': len(entries),
            'scope': 'Declared inputs, direct Python/Node script ownership, exact cwd/argv duplicate and timeout consistency only. Module resolution, test-directory contents and all transitive dependencies are not inferred.'}


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
