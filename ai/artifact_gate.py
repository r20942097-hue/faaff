"""Offline, read-only ZIP artifact security/integrity preflight.

PASS here means archive structure + bounded CRC verification only. It never means
application correctness, genuine provenance or approval for publication.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import stat
import sys
import unicodedata
import zipfile
from pathlib import Path

MAX_MEMBERS = 15000
MAX_TOTAL_MEMBERS = 50000
MAX_ARCHIVES = 100
MAX_ARCHIVE_BYTES = 1024 * 1024 * 1024
MAX_ENTRY_SIZE = 128 * 1024 * 1024
MAX_TOTAL_SIZE = 768 * 1024 * 1024
MAX_RATIO = 900
MAX_NESTED_BYTES = 24 * 1024 * 1024
MAX_DEPTH = 2
CHUNK = 256 * 1024
INVALID_CHARS = set('<>:"|?*')
DEVICE = re.compile(r'^(?:con|prn|aux|nul|com[1-9¹²³]|lpt[1-9¹²³])(?:\..*)?$', re.I)
SHA256 = re.compile(r'[0-9a-f]{64}\Z')


def name_error(name: str) -> str | None:
    """Validate paths safely on Windows, Linux, and macOS (no extraction)."""
    if not name or name[0] == '/' or '\\' in name or '\0' in name:
        return 'empty/absolute/backslash/NUL path'
    pieces = name.rstrip('/').split('/')
    if any(not part or part in ('.', '..') for part in pieces):
        return 'empty/dot/traversal component'
    for component in pieces:
        if component.endswith((' ', '.')) or DEVICE.fullmatch(component):
            return 'Windows path collision or reserved device'
        if any(ord(c) < 32 or c in INVALID_CHARS for c in component):
            return 'invalid/control filename character'
    return None


def _scan(zf: zipfile.ZipFile, label: str, depth: int, budget: list[int], findings: list[str], summary: dict) -> None:
    entries = zf.infolist()
    summary['archives_checked'] += 1
    summary['entries_seen'] += len(entries)
    if summary['archives_checked'] > MAX_ARCHIVES or summary['entries_seen'] > MAX_TOTAL_MEMBERS:
        findings.append(f'{label}: global archive/entry budget exceeded')
        return
    if not entries:
        findings.append(f'{label}: empty archive')
        return
    if len(entries) > MAX_MEMBERS:
        findings.append(f'{label}: too many entries ({len(entries)})')
        return
    seen: dict[str, str] = {}
    file_keys: set[str] = set()
    checked: list[tuple[zipfile.ZipInfo, str, bool]] = []
    for info in entries:
        path = info.filename
        err = name_error(path)
        if err:
            findings.append(f'{label}/{path!r}: {err}')
            continue
        canonical = unicodedata.normalize('NFC', path.rstrip('/')).casefold()
        if canonical in seen:
            findings.append(f'{label}/{path}: name collision with {seen[canonical]}')
            continue
        seen[canonical] = path
        directory = info.is_dir()
        if not directory:
            file_keys.add(canonical)
        mode = (info.external_attr >> 16) & 0xFFFF
        if stat.S_ISLNK(mode):
            findings.append(f'{label}/{path}: symlink entry rejected')
            continue
        if info.flag_bits & 1:
            findings.append(f'{label}/{path}: encrypted entry rejected')
            continue
        if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            findings.append(f'{label}/{path}: unsupported compression method')
            continue
        if info.file_size > MAX_ENTRY_SIZE:
            findings.append(f'{label}/{path}: entry too large')
            continue
        if not directory and info.file_size > 0 and (info.compress_size == 0 or info.file_size / info.compress_size > MAX_RATIO):
            findings.append(f'{label}/{path}: excessive compression ratio')
            continue
        checked.append((info, path, directory))
    # Explicit file and implicit parent directory must never share the same name.
    for key in file_keys:
        if any(other.startswith(key + '/') for other in seen):
            findings.append(f'{label}/{seen[key]}: file/directory conflict')
    for info, path, directory in checked:
        if directory:
            continue
        if budget[0] + info.file_size > MAX_TOTAL_SIZE:
            findings.append(f'{label}/{path}: cumulative declared size exceeded')
            continue
        budget[0] += info.file_size
        summary['members_checked'] += 1
        nested = path.lower().endswith('.zip')
        collect = nested and depth < MAX_DEPTH and info.file_size <= MAX_NESTED_BYTES
        if nested and depth >= MAX_DEPTH:
            findings.append(f'{label}/{path}: nested ZIP depth limit exceeded')
        elif nested and not collect:
            findings.append(f'{label}/{path}: nested ZIP too large to inspect')
        buf = io.BytesIO() if collect else None
        amount = 0
        try:
            with zf.open(info) as inp:
                while True:
                    data = inp.read(CHUNK)
                    if not data:
                        break
                    amount += len(data)
                    if amount > info.file_size or amount > MAX_ENTRY_SIZE:
                        raise ValueError('inflated data exceeds declared size')
                    if buf is not None:
                        buf.write(data)
            if amount != info.file_size:
                raise ValueError('uncompressed bytes differ from metadata')
        except (OSError, RuntimeError, EOFError, zipfile.BadZipFile, ValueError, NotImplementedError) as exc:
            findings.append(f'{label}/{path}: failed bounded CRC read ({type(exc).__name__})')
            continue
        if buf is not None:
            try:
                with zipfile.ZipFile(io.BytesIO(buf.getvalue())) as nested_archive:
                    _scan(nested_archive, label + '/' + path, depth + 1, budget, findings, summary)
            except (zipfile.BadZipFile, OSError, ValueError, RuntimeError, EOFError) as exc:
                findings.append(f'{label}/{path}: invalid nested ZIP ({type(exc).__name__})')


def inspect(path: Path, expected_sha256: str | None = None) -> dict:
    path = Path(path)
    issues: list[str] = []
    digest = None
    summary = {'archives_checked': 0, 'members_checked': 0, 'entries_seen': 0}
    if expected_sha256 is not None and (not isinstance(expected_sha256, str) or SHA256.fullmatch(expected_sha256) is None):
        issues.append('invalid supplied SHA-256 (lowercase 64 hex required)')
    if path.is_symlink() or not path.is_file():
        issues.append('file missing, wrong type or symbolic link')
    else:
        try:
            if path.stat().st_size > MAX_ARCHIVE_BYTES:
                raise ValueError('archive file exceeds 1 GiB limit')
            hash_state = hashlib.sha256()
            with path.open('rb') as f:
                for data in iter(lambda: f.read(1024 * 1024), b''):
                    hash_state.update(data)
            digest = hash_state.hexdigest()
            if expected_sha256 is not None and expected_sha256 != digest:
                issues.append('SHA-256 mismatch')
            with zipfile.ZipFile(path) as zf:
                _scan(zf, path.name, 0, [0], issues, summary)
        except (OSError, zipfile.BadZipFile, ValueError, RuntimeError, EOFError) as exc:
            issues.append(f'archive unreadable ({type(exc).__name__})')
    return {'schema': 'gpt1-artifact-security-gate/v1', 'scope': 'bounded ZIP structure/CRC/SHA only',
            'status': 'FAIL' if issues else 'PASS', 'file': path.name, 'sha256': digest,
            'summary': summary, 'issues': issues,
            'product_e2e': 'NOT_RUN', 'provenance_signature': 'NOT_RUN', 'release_approval': 'NOT_RUN'}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('zip_path', type=Path)
    parser.add_argument('--sha256', help='expected lowercase SHA-256 digest')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    result = inspect(args.zip_path, expected_sha256=args.sha256)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"{result['status']}: {result['file']}; archives {result['summary']['archives_checked']}; entries {result['summary']['members_checked']}")
        for issue in result['issues']:
            print('ERROR:', issue)
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
