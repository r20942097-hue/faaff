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


V2_FILES = FILES | {'tools/registry.py', 'tools/doctor.py', 'tools/tests/test_doctor.py'}

V3_FILES = V2_FILES | {'tools/check_settings.py', 'tools/tests/test_settings.py', 'tools/configuration.py', 'tools/tests/test_configuration.py'}

V4_FILES = V3_FILES | {'tools/check_suite_audit.py', 'tools/tests/test_suite_adapter.py'}

V5_FILES = V4_FILES | {
    'tools/portfolio_status.py', 'tools/tests/test_portfolio_status.py',
    'tools/check_extension.py', 'tools/tests/test_extension_startup.py',
    's/scripts/generate_lists.py', 's/tests/test_generation.py', 's/CHANGELOG.md', 's/README.md',
    'faaff/browser_filter_lists/scripts/validate_filters.py',
    'faaff/browser_filter_lists/scripts/test_validator.py',
    'faaff/browser_filter_lists/CHANGELOG.md',
}

V6_FILES = V5_FILES | {
    'tools/bounded_process.py', 'tools/tests/test_bounded_process.py',
    'tools/inspect_module_search.py', 'tools/tests/test_module_search.py',
    'tools/tests/test_setup_verification.py',
}

V7_FILES = V6_FILES | {'tools/tests/test_browser_startup.py'}

def apply_update(source, target, snapshot_sha256):
    source, target = Path(source), Path(target)
    if source.is_symlink() or target.is_symlink() or not source.is_dir() or not target.is_dir():
        raise ValueError('candidate and snapshot must be regular directories')
    if not safe_path(target, 'SNAPSHOT.json').is_file():
        raise ValueError('candidate target must be an extracted snapshot')
    if safe_path(target, 'catalog/results/catalogue-development-update.json').exists():
        raise ValueError('candidate update already applied')
    manifest = load_json(safe_path(source, 'manifest.json'))
    schemas = {'catalogue-development-update/v1': FILES, 'catalogue-development-update/v2': V2_FILES, 'catalogue-development-update/v3': V3_FILES, 'catalogue-development-update/v4': V4_FILES, 'catalogue-development-update/v5': V5_FILES, 'catalogue-development-update/v6': V6_FILES, 'catalogue-development-update/v7': V7_FILES}
    allowed = schemas.get(manifest.get('schema')) if isinstance(manifest, dict) and isinstance(manifest.get('schema'), str) else None
    if (not isinstance(manifest, dict) or allowed is None
            or snapshot_sha256 != BASE_SHA256 or manifest.get('base_snapshot_sha256') != BASE_SHA256
            or not isinstance(manifest.get('files'), dict) or set(manifest['files']) != allowed):
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
        'schema': manifest['schema'], 'base_snapshot_sha256': BASE_SHA256,
        'files': manifest['files'], 'scope': 'Development catalogue candidate applied after base ZIP verification; base ZIP bytes are unchanged.',
    })
    return len(prepared)
