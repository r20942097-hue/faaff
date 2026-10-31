"""Experimental Chromium MV3 DNR proof (NOT actual uBO Lite).

Generates an ephemeral, non-publishing extension from exactly the 38 pinned
v2 host filters and tests it in Playwright's bundled Chromium. Uses only a
local, deny-by-default HTTP proxy. Never changes user browser profiles.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import time
import threading
import re
import sys

from firefox_candidate_probe import pinned_candidate_rules
from firefox_proxy_probe import IsolatedProxy, PAGE, SAME_SITE, OTHER_SITE

ROOT = Path(__file__).resolve().parents[2]
SENTINEL = "upc-dnr-probe.example.org"
CONTROLS = (PAGE, SAME_SITE, OTHER_SITE)
KINDS = ("image", "script")


def compile_dnr():
    lines, hosts, provenance = pinned_candidate_rules()
    if len(lines) != 38 or len(set(hosts)) != 38 or SENTINEL in hosts:
        raise ValueError("candidate lock cannot be translated")
    # This mirrors only the supported domain-anchored, third-party rule
    # subset. It is not an implementation of uBO Lite's compiled rulesets.
    for rule, host in zip(lines, hosts):
        if rule != "||" + host + "^$third-party":
            raise ValueError("unsupported rule syntax for DNR")
        if not re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+", host):
            raise ValueError("unsafe DNR request domain")
    all_hosts = [*hosts, SENTINEL]
    rules = [{
        "id": i + 1,
        "priority": 1,
        "action": {"type": "block"},
        "condition": {
            "urlFilter": "||" + host + "^",
            "domainType": "thirdParty",
            "resourceTypes": ["image", "script"],
        },
    } for i, host in enumerate(all_hosts)]
    return hosts, rules, provenance


def build_extension(directory, rules):
    path = directory / "extension"
    path.mkdir(parents=True, exist_ok=False)
    manifest = {
        "manifest_version": 3,
        "name": "UPC Isolated DNR Synthetic Test Only",
        "version": "0.0.1",
        "description": "Test fixture: never publish or install in user profiles",
        "permissions": ["declarativeNetRequest"],
        "host_permissions": ["<all_urls>"],
        "declarative_net_request": {
            "rule_resources": [{
                "id": "upc-candidate",
                "enabled": True,
                "path": "rules.json",
            }]
        },
        "background": {"service_worker": "background.js"},
    }
    (path / "manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    (path / "rules.json").write_text(json.dumps(rules,indent=2)+"\n")
    (path / "background.js").write_text(
        "chrome.runtime.onInstalled.addListener(() => {});\n")
    return path


def read_browser(page, proxy, hosts, kind, token):
    url = (f"http://{PAGE}:{proxy.server_port}/batch"
           f"?token={token}&kind={kind}")
    page.goto(url, wait_until="load", timeout=40000)
    time.sleep(0.5)
    with proxy.guard:
        observed = {h for h, k in proxy.hits if k == token}
    return {host: host in observed for host in hosts}


def experiment(context, proxy, hosts):
    page = context.new_page()
    try:
        evidence = {}
        import secrets
        for kind in KINDS:
            attempts = [read_browser(page, proxy, hosts, kind,
                                     secrets.token_hex(16)) for _ in range(2)]
            if attempts[0] != attempts[1]:
                raise ValueError("Chromium DNR unstable " + kind + " verdicts")
            evidence[kind] = attempts
        return evidence
    finally:
        page.close()


def chromium_session(playwright, proxy, hosts, extension_path, profile_path):
    arguments = []
    if extension_path is not None:
        arguments = [
            "--disable-extensions-except=" + str(extension_path),
            "--load-extension=" + str(extension_path),
        ]
    context = playwright.chromium.launch_persistent_context(
        str(profile_path),
        channel="chromium",
        headless=True,
        args=arguments,
        proxy={"server": f"http://127.0.0.1:{proxy.server_port}",
               "bypass": "<-loopback>"},
        ignore_https_errors=False,
    )
    try:
        if extension_path is not None:
            if not context.service_workers:
                context.wait_for_event("serviceworker", timeout=15000)
            worker = next((x for x in context.service_workers
                           if x.url.startswith("chrome-extension://")), None)
            if worker is None:
                raise ValueError("Chromium did not install MV3 test extension")
            # Ensure exact ruleset is enabled rather than inferring installation.
            enabled = worker.evaluate("chrome.declarativeNetRequest.getEnabledRulesets()")
            if "upc-candidate" not in enabled:
                raise ValueError("DNR static candidate ruleset not active")
        return experiment(context, proxy, hosts)
    finally:
        context.close()


def verify_lifecycle(stock, active, restored, hosts):
    checked = [*hosts, SENTINEL, *CONTROLS]
    for stage, document in (("baseline", stock), ("DNR", active), ("restored", restored)):
        if set(document) != set(KINDS):
            raise ValueError(stage+" missing request types")
        for kind in KINDS:
            rounds = document[kind]
            if (len(rounds)!=2 or rounds[0]!=rounds[1]
                    or set(rounds[0])!=set(checked)):
                raise ValueError(stage+" incomplete or unstable "+kind)
            if not all(rounds[0][h] for h in CONTROLS):
                raise ValueError(stage+" benign host blocked for "+kind)
    for kind in KINDS:
        if not all(stock[kind][0].values()) or restored[kind][0]!=stock[kind][0]:
            raise ValueError(kind+" baseline not accessible or restored")
        if any(active[kind][0][h] for h in [*hosts,SENTINEL]):
            raise ValueError(kind+" candidate DNR request not blocked")
    return True


def run(output):
    from playwright.sync_api import sync_playwright
    hosts, rules, provenance = compile_dnr()
    test_hosts = [*hosts, SENTINEL, *CONTROLS]
    proxy = IsolatedProxy(extra_hosts=[*hosts, SENTINEL])
    service = threading.Thread(target=proxy.serve_forever,daemon=True)
    service.start()
    try:
        with tempfile.TemporaryDirectory(prefix="upc-chromium-dnr-") as d:
            work = Path(d)
            extension = build_extension(work, rules)
            with sync_playwright() as pw:
                stock = chromium_session(pw,proxy,test_hosts,None,work/"stock")
                active = chromium_session(pw,proxy,test_hosts,extension,work/"active")
                restored = chromium_session(pw,proxy,test_hosts,None,work/"restored")
        try:
            verify_lifecycle(stock,active,restored,hosts)
        except ValueError as error:
            output.write_text(json.dumps({
                "schema":"upc-chromium-mv3-dnr-diagnostic/v1",
                "status":"BLOCKED",
                "reason":"LIFECYCLE_VALIDATION_FAILURE",
                "detail":str(error),
                "candidate_source":provenance,
                "stock_receipts":stock,
                "active_receipts":active,
                "restored_receipts":restored,
                "real_websites":"NOT_RUN",
                "actual_ubol_loaded":"NOT_RUN",
                "rules_published":0,
                "release":"NO_GO",
            }, indent=2,sort_keys=True)+"\\n",encoding="utf-8")
            for stage, doc in (("stock", stock), ("active", active), ("restored", restored)):
                for kind in KINDS:
                    missing=[host for host,received in doc[kind][0].items() if not received]
                    print("UPC CHROMIUM DIAGNOSTIC:", stage, kind,
                          "missing_count",len(missing), "missing",",".join(missing),
                          flush=True)
            raise
        output_data = {
            "schema":"upc-chromium-mv3-dnr-lab/v1",
            "result":"PASS",
            "browser":"PLAYWRIGHT_BUNDLED_CHROMIUM",
            "actual_ubol_loaded":"NOT_RUN",
            "candidate_source":provenance,
            "compiled_rules":len(rules),
            "candidate_hosts":hosts,
            "sentinel":SENTINEL,
            "controls":list(CONTROLS),
            "resource_types":list(KINDS),
            "baseline_receipts":stock,
            "dnr_receipts":active,
            "restored_receipts":restored,
            "proxy_forwarding":"DISABLED",
            "https_connect":"DENIED",
            "real_website_traffic":"NOT_RUN",
            "real_user_stock_lists":"NOT_RUN",
            "user_browser_profiles":"NOT_TOUCHED",
            "rules_published":0,
            "release":"NO_GO",
        }
        output.write_text(json.dumps(output_data,indent=2,sort_keys=True)+"\n",
                          encoding="utf-8")
        print("UPC CHROMIUM DNR LAB PASS: 38 temporary candidate rules, 1 activation sentinel, "
              "2 image + 2 script rounds each in baseline/DNR/restored; NO_GO")
    finally:
        proxy.shutdown()
        proxy.server_close()
        service.join(timeout=4)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report",type=Path,required=True)
    args = parser.parse_args()
    try:
        out = args.report.resolve()
        if out.is_relative_to(ROOT) or out.exists():
            raise ValueError("reports must be new files outside repository")
        run(out)
        return 0
    except (OSError,ValueError,RuntimeError,TypeError) as error:
        print("UPC CHROMIUM DNR LAB BLOCKED:", error,file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
