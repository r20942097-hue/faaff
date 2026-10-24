"""Prepare a new workspace from the trusted base ZIP and checked catalogue update."""
import argparse
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

from extract_snapshot import extract
from registry import safe_path
from verify_catalogue_update import apply_update, BASE_SHA256


def prepare(root, base, update, update_sha256, destination):
    root = Path(root)
    if not isinstance(destination, str) or not destination.startswith('work/'):
        raise ValueError('output must be a new directory under work/')
    target = safe_path(root, destination)
    if target.exists() or target.is_symlink():
        raise ValueError('output directory already exists')
    scratch = safe_path(root, 'work/catalogue-update-staging')
    scratch.mkdir(parents=True, exist_ok=True)
    owned = False
    try:
        with TemporaryDirectory(dir=scratch) as directory:
            candidate = Path(directory) / 'candidate'
            extract(update, update_sha256, candidate)
            extract(base, BASE_SHA256, target)
            owned = True
            count = apply_update(candidate, target, BASE_SHA256)
        return count
    except BaseException:
        if owned:
            shutil.rmtree(target)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--update', type=Path, required=True)
    parser.add_argument('--update-sha256', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        count = prepare(Path.cwd(), args.base, args.update, args.update_sha256, args.output)
    except (OSError, ValueError) as error:
        parser.exit(1, 'UPDATE PREPARATION FAILED: ' + str(error) + '\n')
    print('UPDATE PREPARATION PASSED:', count, 'checked candidate files')
    print('Create a fresh virtual environment in the new workspace, then run tools/manage.py setup and all.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
