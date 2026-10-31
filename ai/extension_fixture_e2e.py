#!/usr/bin/env python3
"""Prove a disposable MV3 extension loads in Chromium; NEVER claim product E2E."""
import argparse
import json
import sys
import tempfile
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

MANIFEST = {
    "manifest_version": 3,
    "name": "Isolated Extension Test Fixture",
    "version": "0.0.1",
    "host_permissions": ["http://127.0.0.1/*"],
    "background": {"service_worker": "background.js"},
    "content_scripts": [{
        "matches": ["http://127.0.0.1/*"],
        "js": ["content.js"],
        "run_at": "document_idle",
    }],
}
CONTENT = """'use strict';
document.documentElement.dataset.fixtureInjected = 'yes';
chrome.runtime.sendMessage({ kind: 'fixture-probe' }, (response) => {
  const passed = !chrome.runtime.lastError && response && response.ok === true;
  document.documentElement.dataset.fixtureAcknowledged = passed ? 'yes' : 'no';
});
"""
BACKGROUND = """'use strict';
chrome.runtime.onMessage.addListener((message, sender, respond) => {
  if (message && message.kind === 'fixture-probe') {
    respond({ok: true, senderUrlIsLocal: (sender.url || '').startsWith('http://127.0.0.1:')});
  }
});
"""

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != '/fixture':
            self.send_error(404)
            return
        body = b'<!doctype html><html><head><title>Local fixture</title></head><body><h1 id="fixture">Extension injection test</h1></body></html>'
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass

def write_fixture(folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'manifest.json').write_text(json.dumps(MANIFEST), encoding='utf-8')
    (folder / 'content.js').write_text(CONTENT, encoding='utf-8')
    (folder / 'background.js').write_text(BACKGROUND, encoding='utf-8')
    return folder

def probe(executable=None):
    from playwright.sync_api import sync_playwright
    with tempfile.TemporaryDirectory(prefix='isolated-ext-') as temporary:
        root = Path(temporary)
        ext = write_fixture(root / 'extension')
        profile = root / 'profile'
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as playwright:
                opts = dict(
                    user_data_dir=str(profile), channel='chromium', headless=True,
                    args=[f'--disable-extensions-except={ext}', f'--load-extension={ext}'],
                    timeout=45000,
                )
                if executable:
                    opts['executable_path'] = executable
                context = playwright.chromium.launch_persistent_context(**opts)
                try:
                    page = context.new_page()
                    page.goto(f'http://127.0.0.1:{server.server_port}/fixture', wait_until='load')
                    page.wait_for_function('document.documentElement.dataset.fixtureAcknowledged === "yes"', timeout=15000)
                    assert page.locator('#fixture').inner_text() == 'Extension injection test'
                    assert page.evaluate('document.documentElement.dataset.fixtureInjected') == 'yes'
                    return {'status': 'PASS', 'scope': 'disposable_mv3_fixture_only',
                            'version': context.browser.version if context.browser else 'unknown',
                            'content_script': 'PASS', 'message_roundtrip': 'PASS'}
                finally:
                    context.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

def run(executable=None):
    out = {'schema': 'chromium-extension-fixture/v1',
           'generated_at_utc': datetime.now(timezone.utc).isoformat(),
           'real_product_e2e': 'NOT_RUN', 'firefox_extension_e2e': 'NOT_RUN',
           'media_e2e': 'NOT_RUN', 'release_readiness': 'NO_GO'}
    try:
        out['fixture_e2e'] = probe(executable)
    except Exception as exc:
        # Avoid printing browser-command diagnostics or local paths into CI artifacts.
        out['fixture_e2e'] = {'status': 'FAIL', 'error_type': type(exc).__name__}
    return out

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable', help='Local Chromium executable (optional)')
    parser.add_argument('--output')
    args = parser.parse_args(argv)
    result = run(args.executable)
    payload = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        p = Path(args.output)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(payload, encoding='utf-8')
    print(payload)
    return 0 if result['fixture_e2e']['status'] == 'PASS' else 1

if __name__ == '__main__':
    sys.exit(main())
