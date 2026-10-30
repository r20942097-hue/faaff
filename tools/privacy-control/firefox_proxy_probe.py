"""Isolated HTTP-proxy Firefox/uBO experiment; NO outbound proxy forwarding.

Unlike hosts-file loopback mapping, an explicit HTTP proxy keeps the requested
public hostname in the browser URL without resolving its destination as LAN IP.
HTTPS CONNECT and all unknown request targets are *refused*. An install should
never be marked effective if benign cross-host controls are blocked.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
import shutil
import socket
import sys
import threading
import time
from urllib.parse import parse_qs, urlsplit, urlencode

from fetch_firefox_xpi import LOCKFILE, verify_bytes

ROOT = Path(__file__).resolve().parents[2]
PAGE = "pages.example.com"
TRACKER = "probe.scorecardresearch.com"
SAME_SITE = "assets.example.com"
OTHER_SITE = "unrelated.example.org"
HOSTS = frozenset((PAGE, TRACKER, SAME_SITE, OTHER_SITE))
GIF = bytes.fromhex("47494638396101000100800000000000ffffff21f90401000000002c00000000010001000002024401003b")


class IsolatedProxy(ThreadingHTTPServer):
    def __init__(self, extra_hosts=()):
        self.extra_hosts = frozenset(extra_hosts)
        if any(not isinstance(host, str) or
               re.fullmatch(r"[a-z0-9-]+(?:\\.[a-z0-9-]+)+", host) is None
               for host in self.extra_hosts):
            raise ValueError("unsafe candidate test hostname")
        self.allowed_hosts = HOSTS | self.extra_hosts
        self.hits = set()
        self.denied = 0
        self.secret = secrets.token_bytes(32)
        self.flow_events = []
        self.guard = threading.Lock()
        super().__init__(("127.0.0.1", 0), ProxyHandler)

    def seen(self, host, token):
        with self.guard:
            return (host, token) in self.hits

    def signed_digest(self, token, tag):
        return hmac.new(self.secret, f"{token}|{tag}".encode(), "sha256").hexdigest()


class ProxyHandler(BaseHTTPRequestHandler):
    def do_CONNECT(self):
        self._deny()

    def do_POST(self):
        self._deny()

    def _deny(self):
        with self.server.guard:
            self.server.denied += 1
        self.send_error(403)

    def do_GET(self):
        parsed = urlsplit(self.path)
        try:
            valid_port = parsed.port == self.server.server_port
        except ValueError:
            valid_port = False
        if (parsed.scheme != "http" or parsed.hostname not in self.server.allowed_hosts
                or not valid_port or parsed.username or parsed.password):
            self._deny()
            return
        args = parse_qs(parsed.query, keep_blank_values=True)
        tokens = args.get("token", [])
        if (len(tokens) != 1 or re.fullmatch(r"[a-f0-9]{32}", tokens[0]) is None):
            self._deny()
            return
        token = tokens[0]
        if parsed.path == "/index" and parsed.hostname == PAGE:
            targets = args.get("host", [])
            if len(targets) != 1 or targets[0] not in HOSTS:
                self._deny()
                return
            dest = f"http://{targets[0]}:{self.server.server_port}/safe.png?token={token}"
            content = ('<!doctype html><html><body><img id="check" src="'
                       + dest + '"></body></html>').encode()
            mime = "text/html; charset=utf-8"
        elif parsed.path == "/batch" and parsed.hostname == PAGE:
            hosts = sorted(self.server.extra_hosts | (HOSTS - {PAGE}))
            targets = [
                f'<img src="http://{host}:{self.server.server_port}/safe.png?token={token}" alt="">'
                for host in hosts
            ]
            content = ('<!doctype html><html><body>' +
                       ''.join(targets) + '</body></html>').encode()
            mime = "text/html; charset=utf-8"
        elif parsed.path == "/safe.png":
            with self.server.guard:
                self.server.hits.add((parsed.hostname, token))
            content = GIF
            mime = "image/gif"
        elif parsed.hostname == PAGE and parsed.path == "/signed":
            tag = args.get("utm_source", [])
            digest = args.get("sig", [])
            if (len(tag) != 1 or tag[0] != "synthetic-campaign"
                    or len(digest) != 1
                    or not hmac.compare_digest(digest[0], self.server.signed_digest(token, tag[0]))):
                self._deny()
                return
            content = b"UPC_SIGNED_OK"
            mime = "text/plain; charset=utf-8"
            with self.server.guard:
                self.server.flow_events.append(("signed", token))
        elif parsed.hostname == PAGE and parsed.path == "/auth/login":
            content = b"UPC_AUTH_LOGIN_OK"
            mime = "text/plain; charset=utf-8"
            self.send_response(200)
            self.send_header("Set-Cookie", "upc_lab=synthetic; Path=/; SameSite=Lax; HttpOnly")
            self.send_header("Content-Type", mime)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return
        elif parsed.hostname == PAGE and parsed.path == "/auth/check":
            if "upc_lab=synthetic" not in self.headers.get("Cookie", "").split("; "):
                self._deny()
                return
            content = b"UPC_AUTH_COOKIE_OK"
            mime = "text/plain; charset=utf-8"
            with self.server.guard:
                self.server.flow_events.append(("auth", token))
        elif parsed.hostname == PAGE and parsed.path == "/media":
            if self.headers.get("Range", "") != "bytes=0-31":
                self._deny()
                return
            content = bytes(range(32))
            self.send_response(206)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Range", "bytes 0-31/256")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            with self.server.guard:
                self.server.flow_events.append(("range", token))
            return
        else:
            self._deny()
            return
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, fmt, *args):
        pass


def observe(driver, server, host, seconds=2.25):
    token = secrets.token_hex(16)
    page = f"http://{PAGE}:{server.server_port}/index?host={host}&token={token}"
    driver.get(page)
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if server.seen(host, token):
            return True
        time.sleep(0.09)
    return server.seen(host, token)


def synthetic_safety(driver, server):
    """Real browser checks for auth, signed query integrity, and byte ranges."""
    from selenium.webdriver.common.by import By

    token = secrets.token_hex(16)
    base = f"http://{PAGE}:{server.server_port}"
    tag = "synthetic-campaign"
    sig = server.signed_digest(token, tag)
    signed_url = base + "/signed?" + urlencode({
        "token": token, "utm_source": tag, "sig": sig
    })
    driver.get(signed_url)
    signed_ok = "UPC_SIGNED_OK" in driver.find_element(By.TAG_NAME, "body").text

    driver.get(base + "/auth/login?token=" + token)
    driver.get(base + "/auth/check?token=" + token)
    auth_ok = "UPC_AUTH_COOKIE_OK" in driver.find_element(By.TAG_NAME, "body").text

    driver.get(base + "/index?host=" + PAGE + "&token=" + token)
    media = driver.execute_async_script("""
        const done = arguments[arguments.length - 1];
        const token = arguments[0];
        fetch('/media?token=' + token, {headers: {Range: 'bytes=0-31'}})
            .then(async r => ({status:r.status, range:r.headers.get('Content-Range'),
                               length:(await r.arrayBuffer()).byteLength}))
            .then(done, e => done({error:e.name}));
    """, token)
    range_ok = (media == {"status": 206, "range": "bytes 0-31/256", "length": 32})
    with server.guard:
        observed = {(kind, event_token) for kind, event_token in server.flow_events}
    result = {
        "signed_url_preserved": signed_ok and ("signed", token) in observed,
        "auth_cookie_roundtrip": auth_ok and ("auth", token) in observed,
        "media_range_206": range_ok and ("range", token) in observed,
    }
    return result


def verify_before(server, driver):
    results = {host: observe(driver, server, host) for host in (PAGE, SAME_SITE, OTHER_SITE, TRACKER)}
    if not all(results.values()):
        raise ValueError("baseline cannot reach one or more synthetic HTTP hosts")
    return results


def run(xpi: Path, report_path: Path):
    from selenium import webdriver
    from selenium.webdriver.firefox.options import Options
    from selenium.webdriver.firefox.service import Service

    lock = json.loads(LOCKFILE.read_text(encoding="utf-8"))
    verify_bytes(xpi.read_bytes(), lock)
    server = IsolatedProxy()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    driver = None
    addon_id = None
    seen = {"before": {}, "with_addon": {}, "after_uninstall": {}}
    safety = {"before": {}, "with_addon": {}, "after_uninstall": {}}
    result = {
        "schema": "upc-firefox-isolated-proxy/v1",
        "status": "BLOCKED",
        "reason": "NOT_COMPLETED",
        "firefox_version": "NOT_RUN",
        "ubo_version": lock["tag"],
        "xpi_sha256": sha256(xpi.read_bytes()).hexdigest(),
        "network_scope": "HTTP_ONLY_RESTRICTED_PROXY_LOOPBACK_NO_FORWARD",
        "https_tunneling": "DENIED",
        "target_host": TRACKER,
        "controls": {"first_party": PAGE, "same_site": SAME_SITE, "other_site": OTHER_SITE},
        "observations": seen,
        "safety_controls": safety,
        "extension_uninstalled": False,
        "real_websites": "NOT_RUN",
        "user_profile": "NOT_TOUCHED",
        "candidate_rules_installed": False,
        "released_rules": 0,
        "publication": "NO_GO",
    }
    try:
        opts = Options()
        opts.add_argument("-headless")
        prefs = {
            "network.proxy.type": 1,
            "network.proxy.http": "127.0.0.1",
            "network.proxy.http_port": server.server_port,
            "network.proxy.ssl": "127.0.0.1",
            "network.proxy.ssl_port": server.server_port,
            "network.proxy.no_proxies_on": "",
            "network.proxy.socks_remote_dns": False,
            "network.trr.mode": 5,
            "privacy.trackingprotection.enabled": False,
            "privacy.trackingprotection.pbmode.enabled": False,
            "dom.security.https_only_mode": False,
            "dom.security.https_first": False,
            "browser.startup.homepage": "about:blank",
            "extensions.update.enabled": False,
        }
        for key, value in prefs.items():
            opts.set_preference(key, value)
        binpath = shutil.which("geckodriver")
        driver = webdriver.Firefox(
            options=opts,
            service=Service(executable_path=binpath) if binpath else Service(),
        )
        result["firefox_version"] = driver.capabilities.get("browserVersion", "UNKNOWN")
        driver.set_page_load_timeout(22)
        seen["before"] = verify_before(server, driver)
        safety["before"] = synthetic_safety(driver, server)
        addon_id = driver.install_addon(str(xpi), temporary=True)
        if not addon_id:
            result["reason"] = "INSTALL_ID_MISSING"
            raise ValueError("signed add-on ID unavailable")
        # Complete benign negative controls are essential before concluding
        # that a tracker-specific block is working.
        deadline = time.monotonic() + 58
        target_blocked = False
        while time.monotonic() < deadline:
            target_blocked = not observe(driver, server, TRACKER)
            if target_blocked:
                break
            time.sleep(1)
        safety["with_addon"] = synthetic_safety(driver, server)
        seen["with_addon"][TRACKER] = not target_blocked
        for host in (PAGE, SAME_SITE, OTHER_SITE):
            seen["with_addon"][host] = observe(driver, server, host)
        if not all(safety["before"].values()):
            result["reason"] = "SYNTHETIC_BASELINE_SAFETY_INVALID"
        elif not all(safety["with_addon"].values()):
            result["reason"] = "SYNTHETIC_SAFETY_REGRESSION"
        elif not target_blocked:
            result["reason"] = "TARGET_BLOCK_NOT_OBSERVED"
        elif not all(seen["with_addon"][key] for key in (PAGE, SAME_SITE, OTHER_SITE)):
            result["reason"] = "BENIGN_CONTROL_BLOCKED"
        else:
            result["reason"] = "CONTROLS_OK_PENDING_ROLLBACK"
    except Exception as error:
        if result["reason"] == "NOT_COMPLETED":
            result["reason"] = "PROBE_EXCEPTION_" + type(error).__name__.upper()
        # The report remains BLOCKED, even if the browser experienced an error.
    finally:
        if driver is not None:
            if addon_id is not None:
                try:
                    driver.uninstall_addon(addon_id)
                    result["extension_uninstalled"] = True
                    for host in (TRACKER, PAGE, SAME_SITE, OTHER_SITE):
                        seen["after_uninstall"][host] = observe(driver, server, host)
                    safety["after_uninstall"] = synthetic_safety(driver, server)
                except Exception:
                    result["reason"] += "_ROLLBACK_FAILED"
            try:
                driver.quit()
            except Exception:
                result["reason"] += "_BROWSER_QUIT_FAILED"
        with server.guard:
            result["denied_proxy_requests"] = server.denied
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)

    if (result["reason"] == "CONTROLS_OK_PENDING_ROLLBACK"
            and result["extension_uninstalled"]
            and len(seen["after_uninstall"]) == 4
            and all(seen["after_uninstall"].values())
            and all(safety[phase].get(k) is True
                    for phase in ("before", "with_addon", "after_uninstall")
                    for k in ("signed_url_preserved", "auth_cookie_roundtrip",
                              "media_range_206"))):
        result["status"] = "PASS"
        result["reason"] = "TARGET_SPECIFIC_LOOPBACK_ONLY"
    report_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("UPC FIREFOX PROXY LAB:", result["status"], result["reason"],
          "controls", seen["with_addon"], "rollback", seen["after_uninstall"],
          "denied_requests", result["denied_proxy_requests"],
          "safety", safety, flush=True)
    return result["status"] == "PASS"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xpi", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    try:
        xpi, report = args.xpi.resolve(), args.report.resolve()
        if xpi.is_relative_to(ROOT) or report.is_relative_to(ROOT) or report.exists():
            raise ValueError("source checkout and existing reports cannot be modified")
        passed = run(xpi, report)
        return 0 if passed else 1
    except (OSError, ValueError, TypeError) as error:
        print("UPC FIREFOX PROXY LAB FAIL:", error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
