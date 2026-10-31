"""Read-only RPLAY ZIP source lineage / known P0 guard; never extract or execute."""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

SCHEMA = 'rplay-source-intake/v1'
CANONICAL = (
    'segment_store.js',
    'src/segment_store.js',
    'rplay-stable-player-extension/segment_store.js',
    'rplay-stable-player-extension-firefox/segment_store.js',
)
KNOWN_BAD_P0 = '3f1a00b89207f8cb783f59152db6ff230c300569f79b1e1eb691353b70218b9e'
ISSUE_URL = 'https://github.com/r20942097-hue/faaff/issues/31'
MAX_SOURCE = 1024 * 1024
MAX_ENTRIES = 25000

def hash_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()

def inspect(path, expected_sha256=None):
    path = Path(path)
    report = {
        'schema': SCHEMA, 'archive_name': path.name, 'archive_sha256': None,
        'archive_hash_match': None, 'status': 'BLOCKED_INTAKE',
        'release_decision': 'NO_GO', 'product_browser_e2e': 'NOT_RUN',
        'production_recording_e2e': 'NOT_RUN', 'known_p0': False,
        'source_files': [], 'issues': [],
    }
    if expected_sha256 is not None and (len(expected_sha256) != 64 or
            any(ch not in '0123456789abcdef' for ch in expected_sha256)):
        report['issues'].append('INVALID_EXPECTED_SHA256')
        return report
    try:
        report['archive_sha256'] = hash_file(path)
        report['archive_hash_match'] = report['archive_sha256'] == expected_sha256 if expected_sha256 else None
        if expected_sha256 and not report['archive_hash_match']:
            report['issues'].append('ARCHIVE_SHA256_MISMATCH')
            return report
        with zipfile.ZipFile(path) as z:
            members = z.infolist()
            if len(members) > MAX_ENTRIES:
                report['issues'].append('TOO_MANY_ENTRIES')
                return report
            by_name = {}
            for entry in members:
                if entry.filename in CANONICAL:
                    by_name.setdefault(entry.filename, []).append(entry)
            for name in CANONICAL:
                records = by_name.get(name, [])
                if len(records) > 1:
                    report['issues'].append('DUPLICATE_CANONICAL_SOURCE')
                for record in records:
                    if record.file_size > MAX_SOURCE or record.file_size < 1 or record.flag_bits & 1:
                        report['issues'].append('INVALID_SOURCE_MEMBER')
                        continue
                    try:
                        with z.open(record) as stream:
                            content = stream.read(MAX_SOURCE + 1)
                        if len(content) != record.file_size or len(content) > MAX_SOURCE:
                            report['issues'].append('SOURCE_LENGTH_MISMATCH')
                            continue
                    except (RuntimeError, OSError, zipfile.BadZipFile, EOFError):
                        report['issues'].append('SOURCE_CRC_OR_READ_FAILURE')
                        continue
                    digest = hashlib.sha256(content).hexdigest()
                    report['source_files'].append({
                        'path': name, 'sha256': digest, 'size': len(content),
                        'known_p0': digest == KNOWN_BAD_P0,
                    })
    except (OSError, ValueError, zipfile.BadZipFile, zipfile.LargeZipFile):
        report['issues'].append('INVALID_OR_UNREADABLE_ZIP')
        return report
    if any(s['known_p0'] for s in report['source_files']):
        report['known_p0'] = True
        report['issues'].append('KNOWN_P0_PRECOMMIT_EVICTION')
        report['issue_url'] = ISSUE_URL
        report['status'] = 'BLOCKED_KNOWN_P0'
    elif not report['source_files']:
        report['issues'].append('CANONICAL_SOURCE_NOT_FOUND')
    else:
        report['issues'].append('UNREVIEWED_SOURCE_HASH')
        report['status'] = 'NEEDS_REVIEW'
    report['issues'] = sorted(set(report['issues']))
    if any(x in report['issues'] for x in
           ('DUPLICATE_CANONICAL_SOURCE', 'INVALID_SOURCE_MEMBER', 'SOURCE_CRC_OR_READ_FAILURE', 'SOURCE_LENGTH_MISMATCH')):
        report['status'] = 'BLOCKED_KNOWN_P0' if report['known_p0'] else 'BLOCKED_INTAKE'
    if len({s['sha256'] for s in report['source_files']}) > 1:
        report['issues'].append('DIVERGENT_SOURCE_COPIES')
        report['status'] = 'BLOCKED_KNOWN_P0' if report['known_p0'] else 'BLOCKED_INTAKE'
    return report

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive')
    parser.add_argument('--expected-sha256')
    parser.add_argument('--output')
    args = parser.parse_args(argv)
    report = inspect(args.archive, args.expected_sha256)
    payload = json.dumps(report, indent=2, ensure_ascii=False) + '\n'
    if args.output:
        destination = Path(args.output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(payload, encoding='utf-8')
    print(payload)
    return 3 if report['known_p0'] else 2

if __name__ == '__main__':
    sys.exit(main())
