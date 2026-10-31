#!/usr/bin/env python3
"""Firefox MV3 temporary-add-on fixture. NOT a product Firefox E2E."""
import argparse
import json
import sys
import tempfile
import threading
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path

from ai.extension_fixture_e2e import Handler

MANIFEST = {
    "manifest_version": 3,
    "name": "Isolated Firefox MV3 fixture",
    "version": "0.0.1",
    "browser_specific_settings": {"gecko": {"id": "test-fixture@invalid.example"}},
    "background": {"scripts": ["background.js"]},
    "host_permissions": ["http://127.0.0.1/*"],
    "content_scripts": [{"matches": ["http://127.0.0.1/*"],
                         "js": ["content.js"], "run_at": "document_idle"}],
}
CONTENT = """'use strict';
document.documentElement.dataset.firefoxFixtureInjected = 'yes';
browser.runtime.sendMessage({kind: 'firefox-fixture-probe'}).then(
  r => { document.documentElement.dataset.firefoxFixtureAcknowledged =
           r && r.ok && r.senderIsLocal ? 'yes' : 'no'; },
  () => { document.documentElement.dataset.firefoxFixtureAcknowledged = 'no'; }
);
"""
BACKGROUND = """'use strict';
browser.runtime.onMessage.addListener((message, sender) => {
  if (message && message.kind === 'firefox-fixture-probe') {
    return Promise.resolve({
      ok: true, senderIsLocal: (sender.url || '').startsWith('http://127.0.0.1:')
    });
  }
});
"""

def write_fixture(folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "manifest.json").write_text(json.dumps(MANIFEST), encoding="utf-8")
    (folder / "content.js").write_text(CONTENT, encoding="utf-8")
    (folder / "background.js").write_text(BACKGROUND, encoding="utf-8")
    return folder

def probe(executable=None):
    from selenium import webdriver
    from selenium.webdriver.firefox.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    with tempfile.TemporaryDirectory(prefix="firefox-fixture-") as temp:
        source = write_fixture(Path(temp) / "extension")
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        task = threading.Thread(target=server.serve_forever, daemon=True)
        task.start()
        try:
            options = Options()
            options.add_argument("-headless")
            if executable:
                options.binary_location = executable
            driver = webdriver.Firefox(options=options)
            try:
                addon_id = driver.install_addon(str(source), temporary=True)
                if not addon_id:
                    raise RuntimeError("Temporary Firefox add-on ID missing")
                driver.get(f"http://127.0.0.1:{server.server_port}/fixture")
                WebDriverWait(driver, 20).until(
                    lambda d: d.execute_script(
                        "return document.documentElement.dataset.firefoxFixtureAcknowledged") == "yes")
                injected = driver.execute_script(
                    "return document.documentElement.dataset.firefoxFixtureInjected")
                assert injected == "yes"
                assert driver.find_element(By.ID, "fixture").text == "Extension injection test"
                return {"status": "PASS", "scope": "disposable_firefox_mv3_addon",
                        "version": driver.capabilities.get("browserVersion", "unknown"),
                        "content_script": "PASS", "background_messaging": "PASS"}
            finally:
                driver.quit()
        finally:
            server.shutdown()
            server.server_close()
            task.join(timeout=5)

def run(executable=None):
    result = {"schema": "firefox-mv3-fixture/v1",
              "generated_at_utc": datetime.now(timezone.utc).isoformat(),
              "product_e2e": "NOT_RUN", "media_e2e": "NOT_RUN",
              "release_readiness": "NO_GO"}
    try:
        result["fixture_e2e"] = probe(executable)
    except Exception as exc:
        # Do not leak web-driver commands, environment paths or private URLs.
        result["fixture_e2e"] = {"status": "FAIL", "error_type": type(exc).__name__}
    return result

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable")
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    report = run(args.executable)
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(payload, encoding="utf-8")
    print(payload)
    return 0 if report["fixture_e2e"]["status"] == "PASS" else 1

if __name__ == "__main__":
    sys.exit(main())
