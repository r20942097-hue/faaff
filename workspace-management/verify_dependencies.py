"""Compare review-visible requirement mirrors with the verified source snapshot."""
import argparse
from pathlib import Path
from registry import safe_path

# Keep review manifests outside ZIP; installation still uses the snapshot's locks.
MIRRORS = (
    ('runtime', 'tools/requirements-verification.lock.txt'),
    ('build', 'tools/requirements-build.lock.txt'),
    ('extension', 'tools/requirements-extension.lock.txt'),
)


def verify(root, snapshot):
    for profile, source in MIRRORS:
        mirror = safe_path(root, 'dependencies/' + profile + '/requirements.txt')
        original = safe_path(snapshot, source)
        if mirror.read_bytes() != original.read_bytes():
            raise ValueError('dependency mirror differs from snapshot: ' + profile)
    return len(MIRRORS)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', required=True, type=Path)
    args = parser.parse_args()
    try:
        count = verify(Path(__file__).resolve().parent, args.snapshot)
    except (OSError, ValueError) as error:
        parser.exit(1, 'DEPENDENCY MIRROR CHECK FAILED: ' + str(error) + '\n')
    print('DEPENDENCY MIRROR CHECK PASSED:', count, 'profiles')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
