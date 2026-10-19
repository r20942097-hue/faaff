"""Run the signed Firefox extension with locked dependencies in isolated Docker."""
import hashlib
import io
import json
import os
import re
from pathlib import Path
import subprocess
import tarfile
import urllib.request

from registry import load_json, safe_path, write_report

ROOT = Path(__file__).resolve().parents[1]


def record_result(lock, source, target, exit_code, error=None):
    report = load_json(source) if source.is_file() and error is None else {'checks': [], 'passed': False}
    if not isinstance(report, dict) or not isinstance(report.get('checks'), list):
        raise ValueError('invalid extension fixture report')
    report['passed'] = exit_code == 0 and report.get('passed') is True and bool(report['checks'])
    report['status'] = 'running' if exit_code is None else 'passed' if report['passed'] else 'failed'
    report['exit_code'] = exit_code
    if error:
        report['error'] = error
    elif not source.is_file():
        report['error'] = 'fixture report was not produced'
    report['image'] = lock['image']
    report['addon_identity'] = lock['addon']
    report['driver_identity'] = lock['driver']
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='')
    return report['passed']


def verified_download(url, digest, destination):
    if destination.is_file() and hashlib.sha256(destination.read_bytes()).hexdigest() == digest:
        return destination.read_bytes()
    with urllib.request.urlopen(url, timeout=60) as response:
        body = response.read(32*1024*1024+1)
    if len(body) > 32*1024*1024 or hashlib.sha256(body).hexdigest() != digest:
        raise ValueError('download size or SHA256 mismatch')
    destination.write_bytes(body)
    return body


def verify():
    lock = load_json(ROOT / 'tools/extension-lock.json')
    if lock['schema'] != 'firefox-extension-verification/v1':
        raise ValueError('invalid extension lock')
    if not re.fullmatch(r'mcr\.microsoft\.com/playwright/python@sha256:[0-9a-f]{64}', lock['image']):
        raise ValueError('invalid pinned container image')
    cache = safe_path(ROOT, 'work/firefox-extension')
    cache.mkdir(parents=True, exist_ok=True)
    archive_path = safe_path(ROOT, 'work/firefox-extension/driver.tar.gz')
    addon_path = safe_path(ROOT, 'work/firefox-extension/ublock.xpi')
    driver_path = safe_path(ROOT, 'work/firefox-extension/geckodriver')
    verified_download(lock['addon']['url'], lock['addon']['sha256'], addon_path)
    body = verified_download(lock['driver']['url'], lock['driver']['sha256'], archive_path)
    with tarfile.open(fileobj=io.BytesIO(body), mode='r:gz') as archive:
        members = archive.getmembers()
        if len(members) != 1 or members[0].name != 'geckodriver' or not members[0].isfile() or members[0].size > 32*1024*1024:
            raise ValueError('unexpected driver archive')
        driver_path.write_bytes(archive.extractfile(members[0]).read())
    driver_path.chmod(0o755)
    files = ['ad-ubo.txt', 'ad.txt', 'tracking.txt', 'japanese-text-softener.txt', 'japanese-text-softener-deep.txt']
    fixtures = {name: safe_path(ROOT, 's/' + name).read_text(encoding='utf-8') for name in files}
    safe_path(ROOT, 'work/firefox-extension/filters.json').write_text(json.dumps(fixtures, ensure_ascii=False) + '\n', encoding='utf-8', newline='')
    environment = os.environ.copy()
    for name in ['DOCKER_HOST', 'DOCKER_CONTEXT', 'DOCKER_TLS', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH']:
        environment.pop(name, None)
    process = "import subprocess,sys; log=open('/results/install.log','w'); subprocess.run([sys.executable,'-m','pip','install','--require-hashes','-r','/inputs/requirements.txt'],stdout=log,stderr=subprocess.STDOUT,check=True); subprocess.run([sys.executable,'/inputs/probe.py','--root','/results','--addon','/results/ublock.xpi'],check=True)"
    command = ['docker', '--host=unix:///var/run/docker.sock', 'run', '--rm', '--ipc=private', '--shm-size=512m',
               '-v', str(cache) + ':/results',
               '-v', str(ROOT / 'tools/firefox_extension_probe.py') + ':/inputs/probe.py:ro',
               '-v', str(ROOT / 'tools/requirements-extension.lock.txt') + ':/inputs/requirements.txt:ro',
               '-v', '/etc/ssl/certs/ca-certificates.crt:/inputs/ca-certificates.crt:ro',
               '-e', 'PIP_CERT=/inputs/ca-certificates.crt', '-e', 'SSL_CERT_FILE=/inputs/ca-certificates.crt',
               lock['image'], 'python', '-c', process]
    source = safe_path(ROOT, 'work/firefox-extension/fixtures-report.json')
    target = safe_path(ROOT, 'catalog/results/filter-extension-current.json')
    if source.exists():
        source.unlink()
    # Invalidate the prior successful result before starting a new attempt.
    record_result(lock, source, target, None, 'verification is running')
    print('Starting locked Firefox extension fixture verification', flush=True)
    try:
        completed = subprocess.run(command, cwd=ROOT, env=environment, check=False, timeout=600)
    except (OSError, subprocess.TimeoutExpired) as error:
        record_result(lock, source, target, 124 if isinstance(error, subprocess.TimeoutExpired) else 127, str(error))
        raise
    passed = record_result(lock, source, target, completed.returncode)
    return completed.returncode or (0 if passed else 1)


def main():
    target = safe_path(ROOT, 'catalog/results/filter-extension-current.json')
    write_report(target, {'passed': False, 'status': 'running', 'checks': [],
                          'scope': 'Signed Firefox extension fixture verification is starting.'})
    try:
        return verify()
    except KeyboardInterrupt:
        write_report(target, {'passed': False, 'status': 'interrupted', 'exit_code': 130, 'checks': []})
        return 130
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
        # Preserve a detailed subprocess report if verify() already wrote one.
        report = load_json(target)
        if report.get('status') != 'failed':
            report = {'passed': False, 'status': 'failed', 'checks': [], 'error': type(error).__name__}
        report['passed'] = False
        report['status'] = 'failed'
        write_report(target, report)
        print('EXTENSION CHECK FAILED:', type(error).__name__, flush=True)
        return report.get('exit_code') or 1


if __name__ == '__main__':
    raise SystemExit(main())
