"""Offline Node syntax + static MV3 worker-import audit of a pinned ZIP.

Security boundary: artifact_gate and extension_source_preflight run before any read;
Node --check parses untrusted JavaScript from stdin without executing it.
This does NOT establish browser load, runtime APIs, recording or release approval.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
import os
import posixpath
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

MAX_ZIP = 128 * 1024 * 1024
MAX_JS = 8 * 1024 * 1024
MAX_TOTAL_JS = 40 * 1024 * 1024
SHA = re.compile(r'[0-9a-f]{64}\Z')
IMPORTS = re.compile(r'\bimportScripts\s*\(([^)]{0,1024})\)', re.MULTILINE)
DYNAMIC = re.compile(r'\bimport\s*\(')
STATIC_MODULE = re.compile(r'\b(?:import|export)\s+(?:[^;\n]*?\s+from\s+)?[\"\'](\.{1,2}/[^\"\']+)[\"\']')


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _parse_imports(source: str) -> tuple[list[str], list[str]]:
    """Conservative detection, NOT a JavaScript parser; unknown syntax is PARTIAL."""
    imports, warnings = [], []
    for match in IMPORTS.finditer(source):
        body = match.group(1)
        try:
            # static literal comma-separated importScripts('a.js', "b.js") only
            value = ast.literal_eval('[' + body + ']')
            if not isinstance(value, list) or not value or any(not isinstance(x, str) for x in value):
                raise ValueError('nonliteral')
            imports.extend(value)
        except (SyntaxError, ValueError, TypeError):
            warnings.append('NON_LITERAL_IMPORT_SCRIPTS_REQUIRES_RUNTIME_REVIEW')
    if len(re.findall(r'\bimportScripts\s*\(', source)) != len(list(IMPORTS.finditer(source))):
        warnings.append('UNPARSED_IMPORT_SCRIPTS_REQUIRES_RUNTIME_REVIEW')
    if DYNAMIC.search(source):
        warnings.append('POSSIBLE_UNSUPPORTED_DYNAMIC_IMPORT_REQUIRES_REVIEW')
    return imports, warnings


def _safe_local_ref(value: str) -> bool:
    if not value or value.startswith(('/', '.', '#')) or '\\' in value or ':' in value or '?' in value:
        return False
    return all(part not in ('', '.', '..') for part in value.split('/'))


def _node_syntax(source: bytes, is_module: bool, node: str, timeout: int = 7) -> str:
    """Check syntax; never evaluate JS. Strip potentially hostile inherited NODE_OPTIONS."""
    try:
        proc = subprocess.run([node, '--check', '--input-type=' + ('module' if is_module else 'commonjs')],
                              input=source, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=timeout, check=False, env={'PATH': os.environ.get('PATH', ''),
                                                                  'LANG': 'C', 'NODE_OPTIONS': ''})
    except (OSError, subprocess.TimeoutExpired):
        return 'UNAVAILABLE'
    return 'PASS' if proc.returncode == 0 else 'FAIL'


def inspect(path: Path, expected_sha256: str, root: str, *, node: str | None = None) -> dict:
    report = {'schema': 'gpt1-extension-js-preflight/v1', 'status': 'FAIL', 'scope': 'ZIP CRC + JS SYNTAX + LITERAL WORKER IMPORTS ONLY',
              'archive': Path(path).name, 'root': root, 'sha256': None,
              'scripts_checked': 0, 'syntax_failures': [], 'worker_imports': [],
              'issues': [], 'warnings': [], 'browser_e2e': 'NOT_RUN',
              'recording': 'NOT_RUN', 'windows_user_device': 'NOT_RUN', 'release_decision': 'CANDIDATE_NO_GO'}
    path = Path(path)
    if not isinstance(expected_sha256, str) or SHA.fullmatch(expected_sha256) is None:
        report['issues'].append('INVALID_TRUSTED_SHA256')
        return report
    if (path.is_symlink() or not path.is_file() or path.suffix.lower() != '.zip' or
            path.stat().st_size > MAX_ZIP):
        report['issues'].append('ZIP_INPUT_INVALID_OR_TOO_LARGE')
        return report
    digest = _sha256(path)
    report['sha256'] = digest
    if digest != expected_sha256:
        report['issues'].append('SHA256_MISMATCH')
        return report
    from extension_source_preflight import inspect as inspect_source
    baseline = inspect_source(path, expected_sha256)
    if baseline.get('status') != 'PASS':
        report['issues'].append('EXISTING_ARCHIVE_OR_MANIFEST_GATE_NOT_PASS')
        return report
    if not isinstance(root, str) or root not in [e['root'] for e in baseline['extensions'] if e['status'] == 'PASS']:
        report['issues'].append('ROOT_NOT_VERIFIED_EXTENSION')
        return report
    prefix = '' if root == '.' else root
    if prefix and not prefix.endswith('/'):
        report['issues'].append('ROOT_NOT_DIRECTORY')
        return report
    node_path = shutil.which('node') if node is None else node
    if not node_path:
        report['warnings'].append('NODE_NOT_AVAILABLE_SYNTAX_NOT_TESTED')
    with zipfile.ZipFile(path) as z:
        names = {i.filename for i in z.infolist() if not i.is_dir()}
        manifest = json.loads(z.read(prefix + 'manifest.json').decode('utf-8-sig'))
        bg = manifest.get('background') or {}
        worker = bg.get('service_worker') if manifest.get('manifest_version') == 3 else None
        worker_path = prefix + worker if isinstance(worker, str) and worker else None
        # Module children should be syntax-checked as modules as well.
        module_files = set()
        if worker_path and bg.get('type') == 'module':
            pending = [worker_path]
            while pending and len(module_files) < 1000:
                current = pending.pop()
                if current in module_files or current not in names:
                    continue
                module_files.add(current)
                if z.getinfo(current).file_size > MAX_JS:
                    report['issues'].append('JS_SOURCE_LIMIT_EXCEEDED')
                    break
                try:
                    code = z.read(current).decode('utf-8')
                except UnicodeError:
                    report['warnings'].append('MODULE_SOURCE_NOT_UTF8')
                    continue
                for relative in STATIC_MODULE.findall(code):
                    target = posixpath.normpath(posixpath.join(posixpath.dirname(current), relative))
                    if not target.startswith(prefix) or target not in names:
                        report['warnings'].append('MODULE_IMPORT_REQUIRES_REVIEW')
                    else:
                        pending.append(target)
            if pending:
                report['warnings'].append('MODULE_GRAPH_SCAN_INCOMPLETE')
        total = 0
        for name in sorted(names):
            if not name.startswith(prefix) or not name.lower().endswith(('.js', '.mjs')):
                continue
            rel = name[len(prefix):]
            if not rel or rel.startswith('../'):
                report['issues'].append('JS_MEMBER_INVALID')
                break
            info = z.getinfo(name)
            total += info.file_size
            if info.file_size > MAX_JS or total > MAX_TOTAL_JS:
                report['issues'].append('JS_SOURCE_LIMIT_EXCEEDED')
                break
            data = z.read(name)
            if node_path:
                kind = bool(name.endswith('.mjs') or name in module_files)
                result = _node_syntax(data, kind, node_path)
                report['scripts_checked'] += 1
                if result == 'FAIL':
                    report['syntax_failures'].append(rel)
                elif result == 'UNAVAILABLE':
                    report['warnings'].append('NODE_CHECK_FAILED_OR_TIMED_OUT')
        if worker_path is not None:
            if worker_path not in names:
                report['issues'].append('WORKER_SOURCE_MISSING')
            else:
                data = z.read(worker_path)
                try:
                    source = data.decode('utf-8')
                except UnicodeError:
                    report['issues'].append('WORKER_NOT_UTF8')
                    source = ''
                imports, warnings = _parse_imports(source)
                report['warnings'].extend(warnings)
                for ref in imports:
                    # importScripts resolves from the worker script URL.
                    base = worker.rsplit('/', 1)[0] + '/' if '/' in worker else ''
                    canonical = base + ref
                    report['worker_imports'].append(canonical)
                    if not _safe_local_ref(ref) or prefix + canonical not in names:
                        # Names are package-level; only the prefixed path is expected.
                        if not _safe_local_ref(ref):
                            report['issues'].append('UNSAFE_OR_REMOTE_WORKER_IMPORT')
                        else:
                            report['issues'].append('MISSING_WORKER_IMPORT')
        else:
            report['warnings'].append('NO_CHROMIUM_MV3_WORKER_DECLARED')
    report['syntax_failures'] = sorted(set(report['syntax_failures']))
    report['issues'] = sorted(set(report['issues']))
    report['warnings'] = sorted(set(report['warnings']))
    report['status'] = ('FAIL' if report['issues'] or report['syntax_failures'] else
                        'PARTIAL' if report['warnings'] else 'PASS_SYNTAX_REFS_ONLY')
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('zip_path', type=Path)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--root', required=True)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    output = inspect(args.zip_path, args.sha256, args.root)
    print(json.dumps(output, ensure_ascii=False, indent=2) if args.json else output['status'])
    return 0 if output['status'] == 'PASS_SYNTAX_REFS_ONLY' else (1 if output['status'] == 'FAIL' else 2)


if __name__ == '__main__':
    sys.exit(main())