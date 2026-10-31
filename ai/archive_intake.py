#!/usr/bin/env python3
"""Read-only ZIP intake with path, symlink, size, ratio and CRC checks. Never extracts."""
import argparse
import hashlib
import json
import posixpath
import re
import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath

ENTRY_LIMIT = 10000
TOTAL_LIMIT = 2 * 1024**3
FILE_LIMIT = 512 * 1024**2
RATIO_LIMIT = 1000
CHUNK = 1024 * 1024

def unsafe_name(name):
    if not name or '\\' in name or name.startswith('/') or name.startswith('//'):
        return True
    if re.match(r'^[a-zA-Z]:', name) or '\x00' in name:
        return True
    parts = PurePosixPath(name).parts
    if '..' in parts or '.' in parts or not parts:
        return True
    return any(part.endswith((' ', '.')) or ':' in part for part in parts)

def scan(path):
    path = Path(path)
    report = {'schema': 'zip-intake/v1', 'filename': path.name, 'status': 'BLOCKED',
              'product_e2e': 'NOT_RUN', 'release_readiness': 'NO_GO',
              'sha256': None, 'members': 0, 'issues': []}
    try:
        digest = hashlib.sha256()
        with path.open('rb') as src:
            for chunk in iter(lambda: src.read(CHUNK), b''):
                digest.update(chunk)
        report['sha256'] = digest.hexdigest()
        with zipfile.ZipFile(path, 'r') as archive:
            records = archive.infolist()
            report['members'] = len(records)
            if len(records) > ENTRY_LIMIT:
                report['issues'].append('TOO_MANY_ENTRIES')
            seen = set()
            logical_size = 0
            for record in records:
                name = record.filename
                normalized = posixpath.normpath(name).rstrip('/').casefold()
                if unsafe_name(name):
                    report['issues'].append('UNSAFE_PATH')
                if normalized in seen:
                    report['issues'].append('DUPLICATE_PATH')
                seen.add(normalized)
                if ((record.external_attr >> 16) & 0o170000) == stat.S_IFLNK:
                    report['issues'].append('SYMLINK')
                if record.flag_bits & 1:
                    report['issues'].append('ENCRYPTED_MEMBER')
                logical_size += record.file_size
                if record.file_size > FILE_LIMIT:
                    report['issues'].append('OVERSIZE_MEMBER')
                if logical_size > TOTAL_LIMIT:
                    report['issues'].append('OVERSIZE_ARCHIVE')
                if record.file_size and record.file_size / max(1, record.compress_size) > RATIO_LIMIT:
                    report['issues'].append('HIGH_COMPRESSION_RATIO')
            if not report['issues']:
                total_read = 0
                try:
                    for record in records:
                        if record.is_dir():
                            continue
                        counted = 0
                        with archive.open(record) as src:
                            while chunk := src.read(CHUNK):
                                counted += len(chunk)
                                total_read += len(chunk)
                                if counted > FILE_LIMIT or total_read > TOTAL_LIMIT or counted > record.file_size:
                                    raise ValueError('MEMBER_SIZE_MISMATCH')
                        if counted != record.file_size:
                            raise ValueError('MEMBER_SIZE_MISMATCH')
                except (zipfile.BadZipFile, RuntimeError, EOFError, ValueError, OSError):
                    report['issues'].append('BAD_CRC_OR_MEMBER')
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile, ValueError):
        report['issues'].append('INVALID_OR_UNREADABLE_ZIP')
    report['issues'] = sorted(set(report['issues']))
    report['status'] = 'PASSED_INTAKE_ONLY' if not report['issues'] else 'BLOCKED'
    return report

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archives', nargs='+')
    parser.add_argument('--output')
    args = parser.parse_args(argv)
    results = [scan(p) for p in args.archives]
    message = json.dumps({'archives': results}, indent=2, ensure_ascii=False) + '\n'
    if args.output:
        dest = Path(args.output)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(message, encoding='utf-8')
    print(message)
    return 0 if all(x['status'] == 'PASSED_INTAKE_ONLY' for x in results) else 2

if __name__ == '__main__':
    sys.exit(main())
