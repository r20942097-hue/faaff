"""Install exactly the 38 pinned candidate rules through official Firefox managed storage.

Only in an ephemeral GitHub Actions runner. Three independent disposable
Firefox sessions: stock uBO, stock uBO + managed candidate list, stock uBO
after policy removal. All destinations are served by an explicit local
HTTP proxy that refuses forwarding and HTTPS tunnels. This does not publish
or activate the filters on any user's browser.
"""
import argparse
from hashlib import sha1, sha256
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import sys
import threading
import time

from fetch_firefox_xpi import LOCKFILE, verify_bytes
from firefox_proxy_probe import IsolatedProxy, PAGE, TRACKER, SAME_SITE, OTHER_SITE, synthetic_safety

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "integrations/browser-filters/source/s/v2/tracking.txt"
INDEX = ROOT / "ai/imports/s.json"
EXTENSION = "uBlock0@raymondhill.net"
SENTINEL = "upc-candidate.example.org"
CONTROL_HOSTS = (PAGE, SAME_SITE, OTHER_SITE)


def pinned_candidate_rules():
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    assert index["source_repository"] == "r20942097-hue/s"
    entry = next(x for x in index["files"] if x["path"] == "v2/tracking.txt")
    raw = SOURCE.read_bytes()
    digest = sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    if digest != entry["git_blob_sha"] or len(raw) != entry["size"]:
        raise ValueError("candidate source is not the pinned git blob")
    lines = [x.strip() for x in raw.decode("utf-8").splitlines()
             if x.strip() and not x.startswith(("!", "["))]
    if len(lines) != 38:
        raise ValueError("unexpected candidate rule count")
    hosts = []
    for line in lines:
        m = re.fullmatch(r"\|\|([a-z0-9.-]+)\^\$third-party", line)
        if not m:
            raise ValueError("unsupported candidate rule: " + line)
        hosts.append(m.group(1))
    if len(set(hosts)) != 38 or SENTINEL in hosts:
        raise ValueError("duplicate/colliding candidate domain")
    return lines, hosts, {"source_commit":index["source_commit"],
                          "git_blob_sha":digest, "sha256":sha256(raw).hexdigest()}


def managed_policy(rules):
    return {"name": EXTENSION, "description": "UPC ephemeral synthetic fixture",
            "type": "storage", "data": {"toOverwrite": {
                "filters": rules + ["||" + SENTINEL + "^$third-party"]
            }}}


def sample_browser(driver, proxy, hosts):
    token = secrets.token_hex(16)
    url = f"http://{PAGE}:{proxy.server_port}/batch?token={token}"
    driver.get(url)
    end = time.monotonic() + 5.0
    while time.monotonic() < end:
        time.sleep(0.15)
    with proxy.guard:
        seen = {h for h, t in proxy.hits if t == token}
    return {host: host in seen for host in hosts}


def browser_session(proxy, xpi, test_hosts, stage):
    from selenium import webdriver
    from selenium.webdriver.firefox.options import Options
    from selenium.webdriver.firefox.service import Service

    opts = Options()
    opts.add_argument("-headless")
    settings = {
        "network.proxy.type": 1,
        "network.proxy.http": "127.0.0.1",
        "network.proxy.http_port": proxy.server_port,
        "network.proxy.ssl": "127.0.0.1",
        "network.proxy.ssl_port": proxy.server_port,
        "network.proxy.no_proxies_on": "",
        "network.trr.mode": 5,
        "privacy.trackingprotection.enabled": False,
        "privacy.trackingprotection.pbmode.enabled": False,
        "dom.security.https_only_mode": False,
        "dom.security.https_first": False,
        "extensions.update.enabled": False,
        "browser.startup.homepage": "about:blank",
    }
    for key, value in settings.items():
        opts.set_preference(key, value)
    gecko = shutil.which("geckodriver")
    driver = None
    try:
        driver = webdriver.Firefox(
            options=opts, service=Service(executable_path=gecko) if gecko else Service())
        driver.set_page_load_timeout(25)
        extension_id = driver.install_addon(str(xpi), temporary=True)
        if extension_id != EXTENSION:
            raise ValueError("signed extension identity mismatch")
        # Warm up the add-on and stock list processing using a known preblocked
        # tracking host. An initial miss is not proof the add-on has no filters.
        ready = False
        for _ in range(25):
            token = secrets.token_hex(16)
            driver.get(f"http://{PAGE}:{proxy.server_port}/index?host={TRACKER}&token={token}")
            time.sleep(0.55)
            if not proxy.seen(TRACKER, token):
                ready = True
                break
        if not ready:
            raise ValueError("official uBO tracking filter not observed ready")
        result = sample_browser(driver, proxy, test_hosts)
        safety = synthetic_safety(driver, proxy)
        return result, driver.capabilities.get("browserVersion"), safety
    finally:
        if driver is not None:
            driver.quit()


def write_blocked_report(report, *, stage, reason, results, versions,
                         safety, policy_removed, source, xpi_sha):
    """Persist partial evidence without ever treating incomplete stages as PASS."""
    if not isinstance(reason, str) or not re.fullmatch(r"[A-Z0-9_]{3,100}", reason):
        reason = "INTERNAL_VALIDATION_FAILURE"
    output = {
        "schema": "upc-firefox-managed-candidates-diagnostic/v1",
        "status": "BLOCKED",
        "failed_stage": stage,
        "reason_code": reason,
        "stage_receipts": results,
        "firefox_versions": versions,
        "synthetic_safety": safety,
        "policy_removed": policy_removed,
        "candidate_source": source,
        "xpi_sha256": xpi_sha,
        "candidate_activation": "NOT_VERIFIED",
        "real_site_efficacy": "NOT_RUN",
        "actual_user_configuration": "NOT_VERIFIED",
        "rules_published": 0,
        "release": "NO_GO",
    }
    report.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")
    return output


def run(xpi, report):
    lock = json.loads(LOCKFILE.read_text(encoding="utf-8"))
    verify_bytes(xpi.read_bytes(), lock)
    lines, candidate_hosts, provenance = pinned_candidate_rules()
    hosts = [*candidate_hosts, SENTINEL, *CONTROL_HOSTS]
    base = Path.home() / ".mozilla" / "managed-storage"
    policy = base / (EXTENSION + ".json")
    if policy.exists():
        raise ValueError("refusing existing managed policy; must be an isolated runner")
    server = IsolatedProxy(extra_hosts=[*candidate_hosts, SENTINEL])
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    stage = "initial"
    results = {}
    versions = {}
    safety = {}
    failure = None
    try:
        stage = "stock"
        results["stock"], versions["stock"], safety["stock"] = browser_session(server, xpi, hosts, stage)
        stage = "candidate"
        base.mkdir(parents=True, exist_ok=True)
        policy.write_text(json.dumps(managed_policy(lines), sort_keys=True) + "\n",
                          encoding="utf-8")
        results["candidate"], versions["candidate"], safety["candidate"] = browser_session(server, xpi, hosts, stage)
        stage = "restored"
        policy.unlink()
        results["restored"], versions["restored"], safety["restored"] = browser_session(server, xpi, hosts, stage)
    except Exception as error:
        failure = (stage, "STAGE_" + type(error).__name__.upper())
    finally:
        try:
            if policy.exists():
                policy.unlink()
        except OSError:
            failure = ("cleanup", "POLICY_REMOVAL_FAILED")
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
    if failure is not None:
        write_blocked_report(report, stage=failure[0], reason=failure[1],
                             results=results, versions=versions, safety=safety,
                             policy_removed=not policy.exists(),
                             source=provenance, xpi_sha=lock["sha256"])
        raise ValueError("candidate test BLOCKED: " + failure[0] + "/" + failure[1])

    # Every individual check below is independently recorded if it fails.
    try:
        if any(not all(results[name].get(host) is True for host in CONTROL_HOSTS)
               for name in ("stock", "candidate", "restored")):
            raise ValueError("normal cross-host fixture blocked or not received")
        if not results["stock"][SENTINEL]:
            raise ValueError("sentinel pre-policy baseline did not arrive")
        if results["candidate"][SENTINEL]:
            raise ValueError("managed policy sentinel not blocked: candidate activation NOT_VERIFIED")
        if not results["restored"][SENTINEL]:
            raise ValueError("sentinel did not restore after managed policy removal")
        if any(results["candidate"][host] for host in candidate_hosts):
            raise ValueError("one or more candidate rules were not active in actual Firefox")
        if any(results["stock"][host] != results["restored"][host]
               for host in candidate_hosts):
            raise ValueError("rollback did not restore stock coverage")
        if any(not all(safety[stage].values()) for stage in ("stock", "candidate", "restored")):
            raise ValueError("candidate filter broke signed URL, auth cookie, or media range")
    except (ValueError, KeyError, TypeError) as error:
        write_blocked_report(report, stage="evaluation",
                             reason="EVALUATION_" + type(error).__name__.upper(),
                             results=results, versions=versions, safety=safety,
                             policy_removed=not policy.exists(), source=provenance,
                             xpi_sha=lock["sha256"])
        raise
    incremental = [host for host in candidate_hosts if results["stock"][host]]
    evidence = {
        "schema":"upc-firefox-managed-candidates/v1",
        "status":"PASS",
        "mode":"EPHEMERAL_MANAGED_STORAGE_THREE_BROWSER_SESSIONS",
        "candidate_source":provenance,
        "xpi_sha256":lock["sha256"],
        "ubo_version":lock["tag"],
        "firefox_versions":versions,
        "selected_candidate_count":len(candidate_hosts),
        "candidate_hosts":candidate_hosts,
        "sentinel":SENTINEL,
        "stage_receipts":results,
        "synthetic_safety":safety,
        "incremental_synthetic_hosts":incremental,
        "incremental_synthetic_host_count":len(incremental),
        "policy_removed":not policy.exists(),
        "controls":list(CONTROL_HOSTS),
        "https_connect":"DENIED",
        "proxy_forwarding":"DISABLED",
        "real_site_efficacy":"NOT_RUN",
        "actual_user_configuration":"NOT_VERIFIED",
        "credentials_and_site_media":"NOT_RUN",
        "rules_published":0,
        "release":"NO_GO"
    }
    report.write_text(json.dumps(evidence,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("UPC CANDIDATE FIREFOX PASS: 38 pinned managed filters, incremental synthetic hosts",
          len(incremental), "controls maintained, three disposable profiles and rollback PASS")
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--xpi",type=Path,required=True)
    p.add_argument("--report",type=Path,required=True)
    args=p.parse_args()
    try:
        xpi, report = args.xpi.resolve(), args.report.resolve()
        if xpi.is_relative_to(ROOT) or report.is_relative_to(ROOT) or report.exists():
            raise ValueError("cannot modify checkout or overwrite prior evidence")
        return run(xpi,report)
    except (ValueError,OSError,KeyError,TypeError) as error:
        print("UPC CANDIDATE FIREFOX BLOCKED:", error, file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
