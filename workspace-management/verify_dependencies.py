"""Compare review-visible requirement mirrors with the verified source snapshot."""
import argparse
import hashlib
import json
from pathlib import Path
from registry import safe_path

# Keep review manifests outside ZIP; installation still uses the snapshot's locks.
MIRRORS = (
    ('runtime', 'tools/requirements-verification.lock.txt'),
    ('build', 'tools/requirements-build.lock.txt'),
    ('extension', 'tools/requirements-extension.lock.txt'),
)


def audit(root, snapshot):
    """Return evidence only after all profiles match their snapshot originals."""
    rows = []
    for profile, source in MIRRORS:
        relative = 'dependencies/' + profile + '/requirements.txt'
        mirror = safe_path(root, relative)
        original = safe_path(snapshot, source)
        for path in (mirror, original):
            if not path.is_file():
                raise OSError('dependency manifest is missing or not a regular file: ' + str(path))
        copy = mirror.read_bytes()
        expected = original.read_bytes()
        if copy != expected:
            raise ValueError('dependency mirror differs from snapshot: ' + profile
                             + '; mirror SHA256=' + hashlib.sha256(copy).hexdigest()
                             + '; snapshot SHA256=' + hashlib.sha256(expected).hexdigest())
        rows.append({'profile': profile, 'mirror': relative, 'snapshot_source': source,
                     'bytes': len(expected), 'sha256': hashlib.sha256(expected).hexdigest()})
    return {'schema': 'dependency-mirror-check/v1', 'passed': True, 'profiles': rows}


def verify(root, snapshot):
    return len(audit(root, snapshot)['profiles'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', required=True, type=Path)
    parser.add_argument('--json', action='store_true', help='Print validated per-file evidence as JSON.')
    args = parser.parse_args()
    try:
        evidence = audit(Path(__file__).resolve().parent, args.snapshot)
    except (OSError, ValueError) as error:
        parser.exit(1, 'DEPENDENCY MIRROR CHECK FAILED: ' + str(error) + '\n')
    if args.json:
        print(json.dumps(evidence, ensure_ascii=False, indent=2))
    else:
        print('DEPENDENCY MIRROR CHECK PASSED:', len(evidence['profiles']), 'profiles')
        for row in evidence['profiles']:
            print(row['profile'], str(row['bytes']) + ' bytes', 'SHA256=' + row['sha256'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
