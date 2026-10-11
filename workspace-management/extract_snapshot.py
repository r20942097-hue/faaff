"""Check a portable snapshot's identity and payload before extracting any files."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import stat
import unicodedata
import zipfile

from registry import unique_object

MAX_BYTES = 128 * 1024 * 1024
RESERVED = {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}


def checked_archive(body, digest):
    if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest) or len(body) > MAX_BYTES or hashlib.sha256(body).hexdigest() != digest:
        raise ValueError('snapshot size or expected SHA256 mismatch')
    archive = zipfile.ZipFile(io.BytesIO(body))
    try:
        identities, content, total = set(), {}, 0
        members = archive.infolist()
        if not members or len(members) > 10000:
            raise ValueError('snapshot member count outside limits')
        for member in members:
            name = member.filename
            parts = name.split('/')
            if not name or member.is_dir() or '\\' in name or any(ord(c) < 32 for c in name):
                raise ValueError('invalid snapshot path')
            if any(not part or part.casefold() in {'.', '..', '.git', '.aws', '.codex', '.agents'} or any(c in part for c in ':<>"|?*') or part.endswith(('.', ' ')) or part.split('.')[0].upper() in RESERVED for part in parts):
                raise ValueError('unsafe or nonportable snapshot path: ' + name)
            identity = unicodedata.normalize('NFC', name).casefold()
            if identity in identities or member.flag_bits & 1 or stat.S_ISLNK(member.external_attr >> 16):
                raise ValueError('duplicate, encrypted or symlink snapshot entry')
            identities.add(identity)
            total += member.file_size
            if total > MAX_BYTES:
                raise ValueError('snapshot decompressed size exceeds limit')
            # ZIP reads also verify the CRC; no files have been written yet.
            content[name] = archive.read(member)
        # File/parent collisions must be caught before creating the output tree.
        for name in content:
            if any(unicodedata.normalize('NFC', '/'.join(name.split('/')[:index])).casefold() in identities for index in range(1, len(name.split('/')))):
                raise ValueError('snapshot file/directory collision')
        manifest_body = content.get('CONTENT_MANIFEST_SHA256.json')
        if manifest_body is None or len(manifest_body) > 4*1024*1024:
            raise ValueError('snapshot manifest missing or oversized')
        manifest = json.loads(manifest_body, object_pairs_hook=unique_object)
        if not isinstance(manifest, dict) or set(manifest) != set(content) - {'CONTENT_MANIFEST_SHA256.json'}:
            raise ValueError('snapshot content manifest inventory mismatch')
        for name, expected in manifest.items():
            if not isinstance(expected, str) or hashlib.sha256(content[name]).hexdigest() != expected:
                raise ValueError('snapshot payload SHA256 mismatch: ' + name)
        return content
    finally:
        archive.close()


def extract(archive, digest, destination):
    archive, destination = Path(archive), Path(destination)
    if archive.is_symlink() or not archive.is_file() or archive.stat().st_size > MAX_BYTES:
        raise ValueError('snapshot must be a regular bounded file')
    if destination.exists() or destination.is_symlink():
        raise ValueError('snapshot output must be a new directory')
    for parent in destination.absolute().parents:
        if parent.is_symlink():
            raise ValueError('snapshot output cannot traverse a symlink')
    content = checked_archive(archive.read_bytes(), digest)
    destination.mkdir(parents=True, exist_ok=False)
    try:
        for name, body in content.items():
            target = destination.joinpath(*name.split('/'))
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                stream.write(body)
    except BaseException:
        shutil.rmtree(destination)
        raise
    return len(content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', required=True, type=Path)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print('SNAPSHOT VERIFIED AND EXTRACTED:', extract(args.archive, args.sha256, args.output), 'files')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, zipfile.BadZipFile) as error:
        raise SystemExit('ERROR: ' + str(error))
