"""Check the hashed verification lock and optionally the active interpreter."""
import argparse
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
import re
import sys

from registry import load_json

ROOT = Path(__file__).resolve().parents[1]


def validate(data):
    if not isinstance(data, dict) or data.get('schema') != 'python-verification-lock/v1' or data.get('python') != '>=3.11':
        raise ValueError('invalid Python verification lock')
    packages = data.get('packages')
    if not isinstance(packages, list) or not packages:
        raise ValueError('empty dependency inventory')
    names = set()
    for package in packages:
        if not isinstance(package, dict):
            raise ValueError('package must be an object')
        name = package.get('name', '')
        if not isinstance(name, str) or not re.fullmatch('[A-Za-z0-9_.-]+', name):
            raise ValueError('invalid package name')
        normalized = re.sub('[-_.]+', '-', name).lower()
        if normalized in names:
            raise ValueError('duplicate package name')
        names.add(normalized)
        pinned = package.get('version')
        if not isinstance(pinned, str) or not re.fullmatch(r'\d+(?:\.\d+){1,3}(?:(?:\.post|\.dev)\d+)?', pinned):
            raise ValueError('invalid pinned version')
        if not isinstance(package.get('marker'), str) or package['marker'] not in {'', 'sys_platform == "win32"'}:
            raise ValueError('unsupported platform marker')
        if not isinstance(package.get('role'), str) or package['role'] not in {'direct', 'transitive'} or not isinstance(package.get('files'), list) or not package['files']:
            raise ValueError('missing package metadata')
        filenames = set()
        for distribution in package['files']:
            if not isinstance(distribution, dict):
                raise ValueError('distribution must be an object')
            digest, url = distribution.get('sha256'), distribution.get('url')
            if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest) or not isinstance(url, str) or not url.startswith('https://files.pythonhosted.org/'):
                raise ValueError('invalid distribution identity')
            filename = distribution.get('filename', '')
            if not isinstance(filename, str) or not filename or filename in filenames or '/' in filename or '\\' in filename:
                raise ValueError('invalid or duplicate distribution filename')
            filenames.add(filename)
    return data


def render(data):
    validate(data)
    lines = ['# Optional verification environment; Python >=3.11.', '--require-hashes']
    for package in data['packages']:
        marker = ' ; ' + package['marker'] if package['marker'] else ''
        lines.append(package['name'] + '==' + package['version'] + marker + ' \\')
        hashes = sorted({distribution['sha256'] for distribution in package['files']})
        for index, digest in enumerate(hashes):
            lines.append('    --hash=sha256:' + digest + (' \\' if index < len(hashes)-1 else ''))
    return '\n'.join(lines) + '\n'


def installed(data, lookup=version, platform=sys.platform):
    records = []
    for package in validate(data)['packages']:
        if package['marker'] and platform != 'win32':
            records.append({'name': package['name'], 'status': 'not-applicable', 'reason': package['marker']})
            continue
        try:
            actual = lookup(package['name'])
        except PackageNotFoundError:
            actual = None
        records.append({'name': package['name'], 'expected': package['version'], 'installed': actual,
                        'status': 'match' if actual == package['version'] else 'mismatch'})
    return records


def verify_files(root):
    root = Path(root)
    data = load_json(root / 'tools/python-lock.json')
    if render(data) != (root / 'tools/requirements-verification.lock.txt').read_text(encoding='utf-8'):
        raise ValueError('requirements hash lock drift')
    for name, requirements in [('selenium-lock.json', 'requirements-extension.lock.txt'),
                               ('python-build-lock.json', 'requirements-build.lock.txt')]:
        lock = root / 'tools' / name
        if lock.is_file():
            extra = load_json(lock)
            if render(extra) != (root / 'tools' / requirements).read_text(encoding='utf-8'):
                raise ValueError(name + ' hash lock drift')
            if name == 'python-build-lock.json':
                versions = {re.sub('[-_.]+', '-', p['name']).lower(): p['version'] for p in data['packages']}
                for package in extra['packages']:
                    key = re.sub('[-_.]+', '-', package['name']).lower()
                    if key in versions and versions[key] != package['version']:
                        raise ValueError('runtime/build dependency version conflict: ' + key)
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--installed', action='store_true')
    args = parser.parse_args()
    data = verify_files(ROOT)
    records = installed(data) if args.installed else []
    build_lock = ROOT / 'tools/python-build-lock.json'
    if args.installed and sys.version_info >= (3, 15) and build_lock.is_file():
        merged = {re.sub('[-_.]+', '-', item['name']).lower(): item for item in records}
        for item in installed(load_json(build_lock)):
            merged[re.sub('[-_.]+', '-', item['name']).lower()] = item
        records = list(merged.values())
    passed = all(item['status'] != 'mismatch' for item in records)
    report = {'passed': passed, 'packages': len(data['packages']), 'installed_checked': args.installed,
              'build_dependencies_checked': bool(args.installed and sys.version_info >= (3, 15) and build_lock.is_file()),
              'checked_records': len(records),
              'scope': 'Verification Python dependencies and explicitly enabled YAML build dependencies only. No Windows acceptance or vulnerability scan.', 'records': records}
    if args.installed:
        (ROOT / 'catalog/results/python-environment.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as error:
        raise SystemExit('ERROR: ' + str(error))
