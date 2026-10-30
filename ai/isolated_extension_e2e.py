"""Fail-closed offline real-extension smoke gate, never a product release gate.

Requires an *already isolated* process: non-root, a distinct network namespace
from a parent supplied by a privileged wrapper, and no external default routes.
First prove the harness with a synthetic MV3 extension; only then exercise the
SHA256-pinned product ZIP. Never disables the Chromium sandbox or visits sites.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import importlib.metadata
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import unicodedata
import zipfile

SHA256 = re.compile(r"[0-9a-f]{64}\Z")
MAX_CANDIDATE_BYTES = 128 * 1024 * 1024
MAX_UNPACKED_BYTES = 40 * 1024 * 1024
MAX_MEMBERS = 10000
MAX_MEMBER = 8 * 1024 * 1024
CONTROL_MARKER = 'GPT1_CONTROL_WORKER_POPUP_MESSAGE_OK'


def supports_namespace() -> bool:
    return os.name == 'posix' and Path('/proc/self/ns/net').exists()


def isolation_check(parent_netns: str | None) -> list[str]:
    errors = []
    if not supports_namespace():
        return ['LINUX_NETNS_REQUIRED']
    if os.geteuid() == 0:
        errors.append('ROOT_RUNTIME_FORBIDDEN')
    try:
        current = os.readlink('/proc/self/ns/net')
    except OSError:
        errors.append('CURRENT_NETNS_UNREADABLE')
        current = None
    if not parent_netns or not re.fullmatch(r'net:\[\d+\]', parent_netns):
        errors.append('PARENT_NETNS_RECEIPT_MISSING')
    elif current == parent_netns:
        errors.append('PARENT_NETNS_NOT_ISOLATED')
    try:
        ipv4 = [line.split() for line in Path('/proc/net/route').read_text().splitlines()[1:]]
        if any(len(parts) < 2 for parts in ipv4):
            errors.append('IPV4_ROUTE_PARSE_ERROR')
        if any(len(parts) >= 2 and parts[1] == '00000000' for parts in ipv4):
            errors.append('DEFAULT_IPV4_ROUTE_PRESENT')
        if any(parts and parts[0] != 'lo' for parts in ipv4):
            errors.append('NON_LOOPBACK_IPV4_ROUTE_PRESENT')
        ipv6 = [line.split() for line in Path('/proc/net/ipv6_route').read_text().splitlines()]
        if any(len(parts) < 10 for parts in ipv6):
            errors.append('IPV6_ROUTE_PARSE_ERROR')
        if any(len(parts) >= 2 and parts[0] == '0' * 32 and parts[1] == '00000000'
               for parts in ipv6):
            errors.append('DEFAULT_IPV6_ROUTE_PRESENT')
        if any(parts and parts[-1] != 'lo' for parts in ipv6):
            errors.append('NON_LOOPBACK_IPV6_ROUTE_PRESENT')

    except (OSError, UnicodeError):
        errors.append('ROUTE_TABLE_UNREADABLE')
    return errors


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def source_preflight(path: Path, expected: str) -> dict:
    if not isinstance(expected, str) or not SHA256.fullmatch(expected):
        return {'status': 'FAIL', 'reason': 'INVALID_EXPECTED_DIGEST'}
    if path.is_symlink() or not path.is_file() or path.suffix.lower() != '.zip':
        return {'status': 'FAIL', 'reason': 'EXPECTED_REGULAR_ZIP'}
    if path.stat().st_size > MAX_CANDIDATE_BYTES:
        return {'status': 'FAIL', 'reason': 'ARCHIVE_TOO_LARGE'}
    if sha256_of(path) != expected:
        return {'status': 'FAIL', 'reason': 'ARCHIVE_DIGEST_MISMATCH'}
    # Existing tested v2.8 verifier invokes artifact_gate (bounded ZIP CRC,
    # traversal, collisions and nested archive checks) before manifest checks.
    from extension_source_preflight import inspect
    r = inspect(path, expected)
    return {'status': r.get('status', 'FAIL'),
            'reason': r.get('reason'),
            'manifest_roots': [x.get('root') for x in r.get('extensions', [])
                               if x.get('status') == 'PASS' and x.get('manifest_version') == 3
                               and x.get('root') != '.'],
            'manifest_count': len(r.get('extensions', []))}


def extract_verified_root(path: Path, root: str, dst: Path) -> dict:
    """Extract only an exact validated extension root after source preflight.

    Rechecks each path independently rather than trusting a previous status,
    rejects symlinks, and bounds every read; executable bits are not restored.
    """
    if not root or root.startswith('/') or '\\' in root or not root.endswith('/'):
        raise ValueError('BAD_SELECTED_EXTENSION_ROOT')
    if any(x in ('', '.', '..') for x in root.rstrip('/').split('/')):
        raise ValueError('BAD_SELECTED_EXTENSION_ROOT')
    seen = set()
    selected = []
    total = 0
    with zipfile.ZipFile(path) as z:
        for item in z.infolist():
            if not item.filename.startswith(root):
                continue
            rel = item.filename[len(root):]
            if not rel:
                continue
            parts = rel.rstrip('/').split('/')
            if any(x in ('', '.', '..') for x in parts) or '\\' in rel or ':' in rel or any(ord(c)<32 for c in rel):
                raise ValueError('UNSAFE_EXTENSION_MEMBER')
            key = unicodedata.normalize('NFC', rel.rstrip('/')).casefold()
            if key in seen:
                raise ValueError('DUPLICATE_EXTENSION_MEMBER')
            seen.add(key)
            if stat.S_ISLNK(item.external_attr >> 16):
                raise ValueError('SYMLINK_EXTENSION_MEMBER')
            total += item.file_size
            if item.file_size > MAX_MEMBER or total > MAX_UNPACKED_BYTES or len(seen) > MAX_MEMBERS:
                raise ValueError('EXTRACTION_LIMIT_EXCEEDED')
            selected.append((item, rel))
        if not any(rel == 'manifest.json' for _, rel in selected):
            raise ValueError('NO_SELECTED_ROOT_MANIFEST')
        dst.mkdir(parents=True, exist_ok=True)
        for item, rel in selected:
            target = dst / rel
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with z.open(item) as src, target.open('xb') as out:
                    count = 0
                    while True:
                        chunk = src.read(256 * 1024)
                        if not chunk: break
                        count += len(chunk)
                        if count > item.file_size or count > MAX_MEMBER:
                            raise ValueError('MEMBER_OVERRUN')
                        out.write(chunk)
                    if count != item.file_size:
                        raise ValueError('MEMBER_SIZE_MISMATCH')
    return {'files': len(selected), 'extracted_bytes': total}


def make_control_fixture(dirpath: Path) -> None:
    dirpath.mkdir()
    (dirpath / 'manifest.json').write_text(json.dumps({
        'manifest_version': 3, 'name': 'Synthetic isolated positive control',
        'version': '1.0.0', 'background': {'service_worker': 'worker.js'},
        'action': {'default_popup': 'popup.html'},
        'permissions': ['storage']}), encoding='utf-8')
    (dirpath / 'worker.js').write_text(
        "chrome.runtime.onMessage.addListener((m,s,r)=>{if(m==='gpt1-ping')"
        "{chrome.storage.local.set({gpt1Control: true}).then(()=>r('gpt1-pong'));return true;}});",
        encoding='utf-8')
    (dirpath / 'popup.html').write_text(
        '<!doctype html><meta charset="utf-8"><body>'
        '<div id="gpt1-positive-control">PENDING</div>'
        '<script src="popup.js"></script></body>',
        encoding='utf-8')
    (dirpath / 'popup.js').write_text(
        "chrome.runtime.sendMessage('gpt1-ping', async reply => {"
        "if (chrome.runtime.lastError || reply !== 'gpt1-pong') return;"
        "const state = await chrome.storage.local.get('gpt1Control');"
        "if(state.gpt1Control === true)"
        "document.querySelector('#gpt1-positive-control').textContent='" + CONTROL_MARKER + "';"
        "});", encoding='utf-8')


def verify_positive_control(page) -> bool:
    """Fail closed until popup JavaScript, worker message and storage all succeed."""
    page.locator('#gpt1-positive-control').wait_for(state='visible', timeout=5000)
    return bool(page.wait_for_function(
        "marker => document.querySelector('#gpt1-positive-control')?.textContent === marker",
        arg=CONTROL_MARKER, timeout=7000))


def browser_probe(extension_dir: Path, profile: Path, *, browser_executable: str | None = None,
                  control: bool = False) -> dict:
    result = {'status': 'BLOCKED', 'browser_process': 'NOT_RUN',
              'worker': 'NOT_RUN', 'popup': 'NOT_RUN'}
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        result['reason'] = 'PLAYWRIGHT_NOT_INSTALLED'
        return result
    try:
        result['playwright_version'] = importlib.metadata.version('playwright')
    except importlib.metadata.PackageNotFoundError:
        result['playwright_version'] = 'UNKNOWN'
    result['browser_source'] = 'SYSTEM_OVERRIDE' if browser_executable else 'PLAYWRIGHT_CHROMIUM'
    manifest = json.loads((extension_dir / 'manifest.json').read_text(encoding='utf-8'))
    popup = manifest.get('action', {}).get('default_popup')
    with sync_playwright() as p:
        opts = {'headless': True, 'channel': 'chromium', 'chromium_sandbox': True,
                'timeout': 20000, 'args': [
                    '--disable-extensions-except=' + str(extension_dir),
                    '--load-extension=' + str(extension_dir),
                    '--disable-background-networking', '--disable-sync',
                    '--no-first-run', '--disable-component-update']}
        if browser_executable is not None:
            opts['executable_path'] = browser_executable
        try:
            ctx = p.chromium.launch_persistent_context(str(profile), **opts)
        except Exception:
            result['reason'] = 'BROWSER_LAUNCH_FAILED'
            return result
        try:
            result['browser_process'] = 'STARTED'
            result['browser_version'] = ctx.browser.version if ctx.browser else None
            worker = next((w for w in ctx.service_workers
                           if w.url.startswith('chrome-extension://')), None)
            if worker is None:
                try:
                    worker = ctx.wait_for_event(
                        'serviceworker', predicate=lambda w: w.url.startswith('chrome-extension://'),
                        timeout=12000)
                except Exception:
                    result.update(reason='WORKER_NOT_OBSERVED', worker='NOT_OBSERVED')
                    return result
            result['worker'] = 'OBSERVED'
            try:
                info = worker.evaluate('() => ({name:chrome.runtime.getManifest().name, version:chrome.runtime.getManifest().version})')
                if info.get('name') != manifest.get('name') or info.get('version') != manifest.get('version'):
                    result['reason'] = 'WORKER_MANIFEST_MISMATCH'
                    return result
            except Exception:
                result['reason'] = 'WORKER_API_ERROR'
                return result
            result['worker'] = 'PASS'
            if popup:
                extid = worker.url.split('/')[2]
                try:
                    page = ctx.new_page()
                    page.goto('chrome-extension://' + extid + '/' + popup,
                              wait_until='domcontentloaded', timeout=10000)
                    if not page.locator('html').count():
                        result['reason'] = 'POPUP_EMPTY'
                        return result
                    if control:
                        try:
                            if not verify_positive_control(page):
                                result['reason'] = 'CONTROL_POPUP_WORKER_ROUNDTRIP_FAILED'
                                return result
                        except Exception:
                            result['reason'] = 'CONTROL_POPUP_WORKER_ROUNDTRIP_FAILED'
                            return result
                    result['popup'] = 'PASS'
                except Exception:
                    result['reason'] = 'POPUP_NAVIGATION_FAILED'
                    return result
            else:
                result['popup'] = 'NOT_DECLARED'
                if control:
                    result['reason'] = 'CONTROL_POPUP_NOT_DECLARED'
                    return result
            result['status'] = 'PASS'
            return result
        finally:
            try:
                ctx.close()
            except Exception:
                pass


def inspect(archive: Path, expected_sha256: str, selected_root: str,
            parent_netns: str | None, executable: str | None = None,
            preflight=source_preflight, runner=browser_probe) -> dict:
    report = {'schema': 'gpt1-isolated-real-extension-e2e/v1',
              'candidate': archive.name, 'scope': 'offline browser load / MV3 worker / popup',
              'status': 'BLOCKED', 'product_browser': 'NOT_RUN',
              'synthetic_control': 'NOT_RUN', 'real_site': 'NOT_RUN',
              'recording': 'NOT_RUN', 'windows_device': 'NOT_RUN',
              'release_decision': 'CANDIDATE_NO_GO'}
    failures = isolation_check(parent_netns)
    if failures:
        report['reason'] = 'ISOLATION_PRECONDITION_FAILED'
        report['isolation_errors'] = failures
        return report
    try:
        checked = preflight(archive, expected_sha256)
    except (OSError, RuntimeError, ImportError, ValueError, zipfile.BadZipFile):
        report['reason'] = 'SOURCE_PREFLIGHT_UNAVAILABLE_OR_INVALID'
        return report
    report['source_preflight'] = checked
    if checked['status'] != 'PASS' or selected_root not in checked.get('manifest_roots', []):
        report['status'] = 'FAIL' if checked['status'] == 'FAIL' else 'BLOCKED'
        report['reason'] = 'SOURCE_PREFLIGHT_NOT_PASS_OR_ROOT_NOT_FOUND'
        return report
    with tempfile.TemporaryDirectory(prefix='gpt1-offline-browser-') as temp:
        work = Path(temp)
        fixture = work/'fixture'; make_control_fixture(fixture)
        control = runner(fixture, work/'control-profile', browser_executable=executable, control=True)
        report['synthetic_control'] = control
        if control.get('status') != 'PASS':
            report['reason'] = 'BROWSER_HARNESS_CONTROL_FAILED'
            return report
        source = work/'source'
        try:
            report['extraction'] = extract_verified_root(archive, selected_root, source)
        except (OSError, RuntimeError, ValueError, zipfile.BadZipFile):
            report.update(status='FAIL', reason='VERIFIED_ROOT_EXTRACTION_FAILED')
            return report
        product = runner(source, work/'product-profile', browser_executable=executable, control=False)
        report['product_browser'] = product
        if product.get('status') != 'PASS':
            report['reason'] = 'PRODUCT_OFFLINE_BROWSER_CHECK_INCOMPLETE'
            return report
    report['status'] = 'PASS_OFFLINE_ONLY'
    report['reason'] = 'OFFLINE_BROWSER_ONLY_NO_RELEASE_APPROVAL'
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--root', required=True, help='Root inside ZIP including trailing slash')
    parser.add_argument('--browser-executable', help='Nonbundled Chromium; compatibility not guaranteed')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    r = inspect(args.archive, args.sha256, args.root,
                os.getenv('GPT1_PARENT_NETNS'), args.browser_executable)
    print(json.dumps(r, ensure_ascii=False, indent=2) if args.json else
          f"{r['status']}: {r.get('reason', '')}; release: {r['release_decision']}")
    return 0 if r['status'] == 'PASS_OFFLINE_ONLY' else (1 if r['status'] == 'FAIL' else 2)

if __name__ == '__main__':
    sys.exit(main())