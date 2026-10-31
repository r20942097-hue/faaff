#!/usr/bin/env python3
"""Read-only toolchain inventory; no installs, executable paths or secrets."""
import argparse
import importlib.metadata
import json
import platform
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

TOOLS = {
    'git': ('git', '--version'),
    'node': ('node', '--version'),
    'npm': ('npm', '--version'),
    'ffmpeg': ('ffmpeg', '-version'),
    'ffprobe': ('ffprobe', '-version'),
    'firefox': ('firefox', '--version'),
    'chromium': ('chromium', '--version'),
}
VERSION_RE = re.compile(r'(?<!\d)(\d+(?:\.\d+){1,3})(?!\d)')

def parse_version(message):
    match = VERSION_RE.search(message)
    return match.group(1) if match else None

def probe(name, executable, args, which=shutil.which, runner=subprocess.run):
    resolved = which(executable)
    if not resolved:
        return {'status': 'MISSING', 'version': None}
    try:
        result = runner([resolved, *args], capture_output=True, text=True,
                        timeout=10, check=False)
        output = (result.stdout or '') + '\n' + (result.stderr or '')
        version = parse_version(output[:400])
        if result.returncode == 0 and version:
            return {'status': 'AVAILABLE', 'version': version}
        return {'status': 'NOT_VERIFIED', 'version': version}
    except (OSError, subprocess.TimeoutExpired):
        return {'status': 'NOT_VERIFIED', 'version': None}

def collect():
    try:
        playwright_version = importlib.metadata.version('playwright')
        playwright = {'status': 'AVAILABLE', 'version': playwright_version}
    except importlib.metadata.PackageNotFoundError:
        playwright = {'status': 'MISSING', 'version': None}
    tools = {key: probe(key, name, args) for key, (name, *args) in TOOLS.items()}
    tools['playwright_python'] = playwright
    return {
        'schema': 'dev-toolchain-inventory/v1',
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'os': platform.system(),
        'python': platform.python_version(),
        'tools': tools,
        'browser_product_e2e': 'NOT_RUN',
        'release_readiness': 'NO_GO',
    }

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output')
    a = p.parse_args(argv)
    report = collect()
    payload = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    if a.output:
        dest = Path(a.output)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(payload, encoding='utf-8')
    print(payload)
    return 0

if __name__ == '__main__':
    sys.exit(main())
