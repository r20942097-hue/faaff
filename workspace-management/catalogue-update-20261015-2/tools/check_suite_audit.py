"""Run immutable Suite tests with ZIP fixtures retaining their requested paths.

On Windows zipfile normalizes backslashes supplied as a string before writing.
The unsafe-path fixture must contain a literal backslash to test rejection.
This plugin only replaces fixture construction; auditor and assertions stay intact.
"""
import argparse
import subprocess
import hashlib
import json
import os
from pathlib import Path
import sys
from zipfile import ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'library-files/tool-sources/security'


def make_zip(path, entries):
    with ZipFile(path, 'w') as archive:
        for name, body in entries:
            info = ZipInfo(name)
            info.filename = name
            info.orig_filename = name
            archive.writestr(info, body)


class LiteralZipFixture:
    def pytest_collection_modifyitems(self, items):
        for item in items:
            if item.module.__file__ == str(SOURCE / 'tests/test_audit_suite_release.py'):
                item.module.make_zip = make_zip


def install_raw_path_check(module):
    inspect_bundle = module._inspect_bundle
    def inspect_raw(bundle, result, candidate, *limits):
        # ZipInfo.filename can be normalized by Windows. Inspect the original
        # archive spelling before the pinned validator performs other checks.
        for info in bundle.infolist():
            reason = module._unsafe_name(info.orig_filename, directory=info.is_dir())
            if reason and info.orig_filename != info.filename:
                result.findings.append(repr(info.orig_filename) + ': ' + reason)
        return inspect_bundle(bundle, result, candidate, *limits)
    module._inspect_bundle = inspect_raw


def run_suite():
    manifest = json.loads((SOURCE / 'SOURCE-ORIGIN.json').read_text(encoding='utf-8'))
    for name in ['tools/audit_suite_release.py', 'tests/test_audit_suite_release.py']:
        expected = next(item['sha256'] for item in manifest['files'] if item['path'] == name)
        if hashlib.sha256((SOURCE / name).read_bytes()).hexdigest() != expected:
            raise ValueError('pinned Suite source changed: ' + name)
    import pytest
    os.chdir(SOURCE)
    sys.path.insert(0, str(SOURCE))
    from tools import audit_suite_release
    install_raw_path_check(audit_suite_release)
    return pytest.main(['tests/test_audit_suite_release.py', '-q'], plugins=[LiteralZipFixture()])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite-worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    # Direct script execution starts without a previously loaded parent `tools`
    # package. Keep pytest's cwd/sys.path/module mutations in that child only.
    if args.suite_worker and __spec__ is None:
        return run_suite()
    try:
        return subprocess.run([sys.executable, str(Path(__file__).resolve()), '--suite-worker'],
                              cwd=ROOT, check=False).returncode
    except KeyboardInterrupt:
        return 130


if __name__ == '__main__':
    raise SystemExit(main())
