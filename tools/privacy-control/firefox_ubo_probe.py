"""Real Firefox + official signed uBO XPI, isolated loopback HTTP probe.

No real websites. Firefox profile is temporary. The CI-only /etc/hosts
entries point test hostnames at 127.0.0.1. Fails closed if any step cannot be
observed, e.g., a default list has not loaded. Does not import user profiles.
"""
import argparse
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import shutil
import socket
import sys
import threading
import time
from urllib.parse import parse_qs, urlsplit

from fetch_firefox_xpi import LOCKFILE, verify_bytes

REPOSITORY = Path(__file__).resolve().parents[2]
TRACKING_HOST = "probe.scorecardresearch.com"
CONTROL_HOST = "upc-control.test"
EXPECTED_HOSTS = {TRACKING_HOST, CONTROL_HOST}


class LabServer(ThreadingHTTPServer):
    def __init__(self):
        self.requests_seen = set()
        self.counter_lock = threading.Lock()
        super().__init__(("127.0.0.1", 0), LabHandler)

    def observed(self, token):
        with self.counter_lock:
            return token in self.requests_seen


class LabHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlsplit(self.path)
        token = parse_qs(parsed.query).get("token", [""])[0]
        if parsed.path == "/index":
            host = parse_qs(parsed.query).get("host", [""])[0]
            if host not in EXPECTED_HOSTS or len(token) > 80:
                self.send_error(400)
                return
            target = "http://" + host + ":" + str(self.server.server_port)
            content = ('<!doctype html><html><body><img id="probe" src="'
                       + target + '/probe.gif?token=' + token
                       + '" alt=""></body></html>').encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        elif parsed.path == "/probe.gif":
            with self.server.counter_lock:
                self.server.requests_seen.add(token)
            # Valid minimal GIF, only request arrival is inspected.
            gif = bytes.fromhex(
                "47494638396101000100800000000000ffffff21f90401000000002c00000000010001000002024401003b")
            self.send_response(200)
            self.send_header("Content-Type", "image/gif")
            self.send_header("Content-Length", str(len(gif)))
            self.end_headers()
            self.wfile.write(gif)
        else:
            self.send_error(404)

    def log_message(self, fmt, *args):
        pass


def assert_loopback_mapping():
    for host in EXPECTED_HOSTS:
        if socket.gethostbyname(host) != "127.0.0.1":
            raise ValueError("CI host mapping missing (refusing network request): " + host)


def observe(driver, server, host):
    token = secrets.token_hex(16)
    url = "http://127.0.0.1:" + str(server.server_port)
    driver.get(url + "/index?host=" + host + "&token=" + token)
    end = time.monotonic() + 1.5
    while time.monotonic() < end:
        if server.observed(token):
            return True
        time.sleep(0.08)
    return server.observed(token)


def probe(xpi, report_path):
    # Selenium is a CI-only test dependency, never a runtime UPC requirement.
    from selenium import webdriver
    from selenium.webdriver.firefox.options import Options
    from selenium.webdriver.firefox.service import Service

    assert_loopback_mapping()
    lock = json.loads(LOCKFILE.read_text(encoding="utf-8"))
    verify_bytes(xpi.read_bytes(), lock)
    options = Options()
    options.add_argument("-headless")
    for key, value in {
        "network.proxy.type": 0,
        "network.trr.mode": 5,
        "privacy.trackingprotection.enabled": False,
        "privacy.trackingprotection.pbmode.enabled": False,
        "dom.security.https_only_mode": False,
        "dom.security.https_first": False,
        "network.stricttransportsecurity.preloadlist": False,
        "browser.startup.homepage": "about:blank",
        "browser.shell.checkDefaultBrowser": False,
        "extensions.update.enabled": False,
    }.items():
        options.set_preference(key, value)

    geckodriver = shutil.which("geckodriver")
    driver = None
    server = LabServer()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        driver = webdriver.Firefox(
            options=options,
            service=Service(executable_path=geckodriver) if geckodriver else Service())
        driver.set_page_load_timeout(20)
        before = observe(driver, server, TRACKING_HOST)
        control_before = observe(driver, server, CONTROL_HOST)
        if not before or not control_before:
            raise ValueError("baseline HTTP did not arrive locally; cannot infer browser blocking")
        addon_id = driver.install_addon(str(xpi), temporary=True)
        if not addon_id:
            raise ValueError("Firefox did not return installed extension ID")
        blocked = False
        for _ in range(30):
            if not observe(driver, server, TRACKING_HOST):
                blocked = True
                break
            time.sleep(1)
        control_on = observe(driver, server, CONTROL_HOST)
        if not blocked:
            raise ValueError("uBO did not demonstrate default tracking block in isolated Firefox")
        if not control_on:
            raise ValueError("normal third-party control unexpectedly blocked")
        driver.uninstall_addon(addon_id)
        restored = False
        for _ in range(12):
            if observe(driver, server, TRACKING_HOST):
                restored = True
                break
            time.sleep(0.3)
        if not restored:
            raise ValueError("post-uninstall tracking request not restored")
        result = {
            "schema": "upc-firefox-ubo-loopback/v1",
            "status": "PASS",
            "firefox_version": driver.capabilities.get("browserVersion"),
            "official_ubo_version": lock["tag"],
            "xpi_sha256": sha256(xpi.read_bytes()).hexdigest(),
            "target": TRACKING_HOST,
            "baseline": "RECEIVED",
            "control_before": "RECEIVED",
            "extension_on": "BLOCKED",
            "control_while_installed": "RECEIVED",
            "after_uninstall": "RECEIVED",
            "network_scope": "LOCAL_LOOPBACK_ONLY_WITH_TEMPORARY_HOSTS_FILE",
            "actual_live_websites": "NOT_RUN",
            "actual_user_configuration": "NOT_VERIFIED",
            "real_signed_url_safety": "NOT_RUN",
            "published_rules": 0,
            "release": "NO_GO",
        }
        report_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print("UPC FIREFOX OFFICIAL uBO LOOPBACK PASS: before received,"
              " installed blocked, control preserved, uninstall restored")
    finally:
        if driver is not None:
            driver.quit()
        server.shutdown()
        server.server_close()
        thread.join(timeout=4)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--xpi", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    args = p.parse_args()
    try:
        xpi, report = args.xpi.resolve(), args.report.resolve()
        if xpi.is_relative_to(REPOSITORY) or report.is_relative_to(REPOSITORY):
            raise ValueError("all browser inputs and results must be outside checkout")
        if report.exists():
            raise ValueError("refuse to overwrite an existing report")
        probe(xpi, report)
        return 0
    except (ValueError, OSError, RuntimeError) as error:
        print("UPC FIREFOX LOOPBACK FAIL:", error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
