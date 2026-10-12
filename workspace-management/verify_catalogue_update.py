"""Apply checked catalogue candidate files to a freshly verified snapshot in CI."""
import hashlib
from pathlib import Path
import re
from registry import load_json, safe_path

BASE_SHA256 = 'e2ab70a46e41a2f193f8738b0917a9966c3850056f68d79e0f7b48b3e59208d9'
FILES = frozenset({
    'README.md', 'catalog/ARTIFACTS.md', 'catalog/INTEGRATION.md', 'catalog/README.md',
    'catalog/REPORT.md', 'catalog/artifacts.json', 'catalog/config.json', 'catalog/projects.json',
    'tools/artifacts.py', 'tools/browser_smoke.py', 'tools/manage.py', 'tools/registry.json',
    'tools/tests/test_artifacts.py', 'tools/tests/test_manage.py', 'tools/tests/test_registry.py',
    'tools/check_artifact_publication.py', 'tools/tests/test_artifact_publication.py',
})


def apply_update(source, target, snapshot_sha256):
    source, target = Path(source), Path(target)
    if source.is_symlink() or target.is_symlink() or not source.is_dir() or not target.is_dir():
        raise ValueError('candidate and snapshot must be regular directories')
    if not safe_path(target, 'SNAPSHOT.json').is_file():
        raise ValueError('candidate target must be an extracted snapshot')
    if safe_path(target, 'catalog/results/catalogue-development-update.json').exists():
        raise ValueError('candidate update already applied')
    manifest = load_json(safe_path(source, 'manifest.json'))
    if (not isinstance(manifest, dict) or manifest.get('schema') != 'catalogue-development-update/v1'
            or snapshot_sha256 != BASE_SHA256 or manifest.get('base_snapshot_sha256') != BASE_SHA256
            or not isinstance(manifest.get('files'), dict) or set(manifest['files']) != FILES):
        raise ValueError('candidate manifest or base snapshot mismatch')
    prepared = []
    for name, expected in sorted(manifest['files'].items()):
        if not isinstance(expected, str) or not re.fullmatch('[0-9a-f]{64}', expected):
            raise ValueError('invalid candidate SHA256')
        origin, destination = safe_path(source, name), safe_path(target, name)
        if not origin.is_file() or origin.stat().st_size > 2 * 1024 * 1024:
            raise ValueError('candidate must be a bounded regular file: ' + name)
        if destination.exists() and not destination.is_file():
            raise ValueError('candidate destination is not a regular file: ' + name)
        body = origin.read_bytes()
        if hashlib.sha256(body).hexdigest() != expected:
            raise ValueError('candidate file SHA256 mismatch: ' + name)
        body.decode('utf-8')
        prepared.append((destination, body))
    # Validate every file before changing any member of the isolated target.
    for destination, body in prepared:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(body)
    from registry import write_report
    write_report(safe_path(target, 'catalog/results/catalogue-development-update.json'), {
        'schema': 'catalogue-development-update/v1', 'base_snapshot_sha256': BASE_SHA256,
        'files': manifest['files'], 'scope': 'Development catalogue candidate applied after base ZIP verification; base ZIP bytes are unchanged.',
    })
    return len(prepared)
