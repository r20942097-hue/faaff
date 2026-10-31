#!/usr/bin/env python3
"""Playwright browser toolchain fixture smoke; NOT a product/extension E2E."""
import argparse
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

def check_browser(browser_name, executable=None):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        browser_type = getattr(playwright, browser_name)
        options = {"headless": True, "timeout": 30000}
        if executable:
            options["executable_path"] = executable
        browser = browser_type.launch(**options)
        try:
            page = browser.new_page()
            try:
                page.set_content('<!doctype html><html><body><h1 id="probe">Toolchain ready</h1></body></html>')
                assert page.locator("#probe").inner_text() == "Toolchain ready"
                assert page.evaluate("2+2") == 4
                return {"status": "PASS", "version": browser.version, "scope": "in_memory_fixture_only"}
            finally:
                page.close()
        finally:
            browser.close()

def run(browser_name, executable=None):
    report = {"schema": "browser-toolchain-preflight/v1",
              "generated_at_utc": datetime.now(timezone.utc).isoformat(),
              "platform": platform.system(), "browser": browser_name,
              "extension_e2e": "NOT_RUN", "media_recording_e2e": "NOT_RUN",
              "site_e2e": "NOT_RUN"}
    try:
        report["toolchain_smoke"] = check_browser(browser_name, executable)
    except Exception as error:
        report["toolchain_smoke"] = {"status": "FAIL", "error_type": type(error).__name__,
            "hint": "Check the Playwright package, browser download and system dependencies"}
    return report

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", choices=("chromium", "firefox"), required=True)
    parser.add_argument("--executable", help="Optional local executable, no browser installation")
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    report = run(args.browser, args.executable)
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        dest = Path(args.output)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(payload, encoding="utf-8")
    print(payload)
    return 0 if report["toolchain_smoke"]["status"] == "PASS" else 1

if __name__ == "__main__":
    sys.exit(main())
