"""Install the hashed verification environment, including Python 3.15's YAML build."""
from pathlib import Path
import sys
from datetime import datetime, timezone
from registry import child_environment, run_process, write_report
from check_python_lock import verify_files

ROOT = Path(__file__).resolve().parents[1]


def main():
    destination = ROOT / 'catalog/results/python-setup.json'
    report = {'schema': 'verification-environment-setup/v1', 'python': sys.version.split()[0],
              'started_at_utc': datetime.now(timezone.utc).isoformat(), 'status': 'running', 'passed': False,
              'pyyaml_profile': 'hashed-source/pure-python' if sys.version_info >= (3, 15) else 'hashed-binary', 'checks': []}
    write_report(destination, report)
    if sys.prefix == sys.base_prefix:
        report.update(status='blocked', finished_at_utc=datetime.now(timezone.utc).isoformat())
        write_report(destination, report)
        print('BLOCKED: Run this installer with a virtual-environment Python.')
        return 2
    try:
        verify_files(ROOT)
    except (OSError, ValueError) as error:
        report.update(status='failed', error=str(error), finished_at_utc=datetime.now(timezone.utc).isoformat())
        write_report(destination, report)
        print('FAILED: ' + str(error))
        return 1
    cache = ROOT / 'work/python-package-cache'
    environment = child_environment()
    environment['PIP_DISABLE_PIP_VERSION_CHECK'] = '1'
    environment['PIP_CACHE_DIR'] = str(cache)
    environment['PIP_REQUIRE_VIRTUALENV'] = '1'
    commands = []
    base = [sys.executable, '-m', 'pip', 'install', '--cache-dir', str(cache), '--require-hashes', '--only-binary=:all:']
    if sys.version_info >= (3, 15):
        commands.append([*base, '-r', 'tools/requirements-build.lock.txt'])
        environment['PYYAML_FORCE_LIBYAML'] = '0'
        environment['PYYAML_FORCE_CYTHON'] = '0'
        commands.append([*base, '--no-build-isolation', '--no-binary=PyYAML', '-r', 'tools/requirements-verification.lock.txt'])
    else:
        commands.append([*base, '-r', 'tools/requirements-verification.lock.txt'])
    if sys.version_info >= (3, 15):
        commands.append([sys.executable, '-c',
                         'import yaml; assert not yaml.__with_libyaml__, "Use a fresh virtual environment for the pure-Python YAML profile"; '
                         'assert yaml.safe_load("ready: true") == {"ready": True}; print("Pure-Python PyYAML import and parse passed")'])
    commands.extend([[sys.executable, '-m', 'pip', 'check'],
                     [sys.executable, 'tools/check_python_lock.py', '--installed']])
    for command in commands:
        check = {'argv': command[1:], 'status': 'running', 'exit_code': None,
                 'started_at_utc': datetime.now(timezone.utc).isoformat(), 'output': ''}
        report['checks'].append(check)
        write_report(destination, report)
        try:
            result = run_process(command, ROOT, timeout=300, environment=environment)
        except KeyboardInterrupt:
            result = {'exit_code': 130, 'output': 'interrupted by user', 'error': 'KeyboardInterrupt', 'interrupted': True}
        code = result['exit_code']
        check.update(result, status='interrupted' if result.get('interrupted') else 'passed' if code == 0 else 'failed',
                     finished_at_utc=datetime.now(timezone.utc).isoformat())
        output = result['output']
        print(output, end='' if output.endswith('\n') else '\n', flush=True)
        write_report(destination, report)
        if code:
            report.update(status=check['status'], finished_at_utc=datetime.now(timezone.utc).isoformat())
            if 'error' in result:
                report['error'] = result['error']
            write_report(destination, report)
            return code
    report.update(status='passed', passed=True, finished_at_utc=datetime.now(timezone.utc).isoformat())
    write_report(destination, report)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
