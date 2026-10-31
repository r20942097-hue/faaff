"""Installed real official uBO Lite stock-only verification in Chromium.

The vendor-signed/tagged Chromium zip must be preverified against the
official release checksum. Browser contexts are disposable; custom UPC
DNR candidate rules are never loaded concurrently with uBO Lite.
"""
import argparse
import json
import secrets
from urllib.parse import urlencode
from pathlib import Path
import sys
import tempfile
import time
import threading

from chromium_dnr_probe import (
    compile_dnr, CONTROLS, KINDS, SENTINEL,
    experiment, candidate_first_party_experiment, verify_first_party
)
from firefox_proxy_probe import IsolatedProxy
from fetch_official_ubol import LOCK, verify_lock


def synthetic_protocol_safety(context, proxy):
    """No live site: exercise HMAC URL, HttpOnly cookie and 206 byte range."""
    page=context.new_page()
    try:
        token=secrets.token_hex(16)
        base=f"http://pages.example.com:{proxy.server_port}"
        signature=proxy.signed_digest(token,"synthetic-campaign")
        page.goto(base+"/signed?"+urlencode({
            "token":token,"utm_source":"synthetic-campaign","sig":signature,
        }),wait_until="load",timeout=20000)
        signed="UPC_SIGNED_OK" in page.locator("body").inner_text()
        page.goto(base+"/auth/login?token="+token,wait_until="load",timeout=20000)
        page.goto(base+"/auth/check?token="+token,wait_until="load",timeout=20000)
        authenticated="UPC_AUTH_COOKIE_OK" in page.locator("body").inner_text()
        page.goto(base+"/index?host=pages.example.com&token="+token,
                  wait_until="load",timeout=20000)
        response=page.evaluate("""async token => {
            try {
                const response = await fetch('/media?token='+token, {
                    headers: {Range: 'bytes=0-31'}
                });
                return {
                    status:response.status,
                    range:response.headers.get('Content-Range'),
                    length:(await response.arrayBuffer()).byteLength
                };
            } catch (e) { return { error:e.name }; }
        }""",token)
        ranged=(response=={"status":206,"range":"bytes 0-31/256","length":32})
        with proxy.guard:
            events=set(proxy.flow_events)
        result={
            "signed_url_preserved":signed and ("signed",token) in events,
            "auth_cookie_roundtrip":authenticated and ("auth",token) in events,
            "media_range_206":ranged and ("range",token) in events,
        }
        if not all(result.values()):
            raise ValueError("official uBOL synthetic signed query/auth/Range failed")
        return result
    finally:
        page.close()


def measure(context, proxy, hosts):
    """No extension or exactly official uBOL, never both blocking engines."""
    receipt=experiment(context,proxy,hosts)
    firstparty=candidate_first_party_experiment(context,proxy)
    safety=synthetic_protocol_safety(context,proxy)
    return receipt,firstparty,safety


def context_run(pw, proxy, hosts, package, directory, expected_enabled):
    opts=[]
    if package is not None:
        opts=[
            "--disable-extensions-except="+str(package),
            "--load-extension="+str(package),
        ]
    context=pw.chromium.launch_persistent_context(
        str(directory),channel="chromium",headless=True,args=opts,
        proxy={"server":f"http://127.0.0.1:{proxy.server_port}",
               "bypass":"<-loopback>"},ignore_https_errors=False)
    try:
        rules=[]
        if package is not None:
            end=time.monotonic()+28
            while time.monotonic()<end:
                workers=[w for w in context.service_workers
                         if w.url.startswith("chrome-extension://")]
                if workers:
                    try:
                        rules=workers[0].evaluate(
                            "() => chrome.declarativeNetRequest.getEnabledRulesets()")
                        if set(expected_enabled).issubset(set(rules)):
                            break
                    except Exception:
                        pass
                time.sleep(0.5)
            if not set(expected_enabled).issubset(set(rules)):
                raise ValueError("official uBO Lite default DNR rule sets not loaded")
        receipt,firstparty,safety=measure(context,proxy,hosts)
        return receipt,firstparty,safety,sorted(rules)
    finally:
        context.close()


def audit_lifecycle(before,stock,restored,firstparty,hosts,safety=None):
    expected=set([*hosts,SENTINEL,*CONTROLS])
    for name,stage in (("before",before),("ubol",stock),("after",restored)):
        if set(stage)!=set(KINDS):
            raise ValueError("missing real uBOL resource type: "+name)
        for kind in KINDS:
            rows=stage[kind]
            if (not isinstance(rows,list) or len(rows)!=2 or
                    rows[0]!=rows[1] or set(rows[0])!=expected or
                    any(type(v) is not bool for v in rows[0].values())):
                raise ValueError("incomplete or inconsistent uBOL stage: "+name+"/"+kind)
            if not all(rows[0][host] for host in CONTROLS):
                raise ValueError("uBOL benign host false positive: "+name+"/"+kind)
            if name=="after" and rows!=before[kind]:
                raise ValueError("no-extension browser request baseline not restored")
    verify_first_party(firstparty)
    if safety is None or set(safety)!={"baseline","ubol","restored"}:
        raise ValueError("missing uBO Lite protocol safety stages")
    cases={"signed_url_preserved","auth_cookie_roundtrip","media_range_206"}
    for stage,checks in safety.items():
        if not isinstance(checks,dict) or set(checks)!=cases or not all(
                value is True for value in checks.values()):
            raise ValueError("uBO Lite signed URL/auth/Range control regression: "+stage)
    if not any(not stock[kind][0][h] and before[kind][0][h]
               for kind in KINDS for h in hosts):
        raise ValueError("no verified additional stock uBOL network blocking")
    return True


def run(package, report):
    from playwright.sync_api import sync_playwright
    lock=verify_lock(json.loads(LOCK.read_text(encoding="utf-8")))
    manifest=json.loads((package/"manifest.json").read_text(encoding="utf-8"))
    if manifest.get("version")!=lock["release_tag"] or manifest.get("manifest_version")!=3:
        raise ValueError("official uBOL install package not verified")
    enabled=[r["id"] for r in manifest["declarative_net_request"]["rule_resources"]
             if r.get("enabled") is True]
    if not set(lock["expected_static_rulesets"]).issubset(enabled):
        raise ValueError("uBOL static default rulesets differ from source lock")
    hosts,_,provenance=compile_dnr()
    allhosts=[*hosts,SENTINEL,*CONTROLS]
    server=IsolatedProxy(extra_hosts=[*hosts,SENTINEL])
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix="upc-official-ubol-") as folder:
            root=Path(folder)
            with sync_playwright() as pw:
                before,bf,bs,_=context_run(pw,server,allhosts,None,root/"without-before",enabled)
                ubol,uf,us,enabled_actual=context_run(pw,server,allhosts,package,root/"only-ubol",enabled)
                after,af,rs,_=context_run(pw,server,allhosts,None,root/"without-after",enabled)
        firstparty={"baseline":bf,"dnr":uf,"restored":af}
        safety={"baseline":bs,"ubol":us,"restored":rs}
        audit_lifecycle(before,ubol,after,firstparty,hosts,safety)
        summary={}
        for kind in KINDS:
            initially_reachable=[h for h in hosts if before[kind][0][h]]
            already_unreachable=[h for h in hosts if not before[kind][0][h]]
            blocked_by_real_stock=[h for h in initially_reachable if not ubol[kind][0][h]]
            not_blocked=[h for h in initially_reachable if ubol[kind][0][h]]
            summary[kind]={
                "browser_baseline_received":initially_reachable,
                "browser_baseline_not_received_unknown_cause":already_unreachable,
                "blocked_by_official_ubol_stock_vs_browser_only":blocked_by_real_stock,
                "still_received_with_official_stock":not_blocked,
                "candidate_hosts_total":len(hosts)
            }
        result={
            "schema":"upc-official-ubol-chromium-stock/v1",
            "result":"PASS",
            "source":"uBlockOrigin/uBOL-home",
            "official_tag":lock["release_tag"],
            "official_asset_sha256":lock["sha256"],
            "official_asset_size":lock["size"],
            "browser":"PLAYWRIGHT_BUNDLED_CHROMIUM",
            "official_ubol_installed":True,
            "official_enabled_static_rulesets":enabled_actual,
            "candidate_source":provenance,
            "candidate_rules_installed":False,
            "candidate_hosts":hosts,
            "sentinel":SENTINEL,
            "controls":list(CONTROLS),
            "resource_types":list(KINDS),
            "before":before,"official_stock":ubol,"restored":after,
            "first_party_candidate_receipts":firstparty,
            "synthetic_protocol_safety":safety,
            "coverage":summary,
            "comparison_limitation":"BROWSER_ONLY_VS_OFFICIAL_UBOL_NOT_UBOL_PLUS_CANDIDATES",
            "browser_baseline_missing_root_cause":"NOT_ESTABLISHED",
            "no_second_active_blocker":True,
            "outbound_proxy":"DENIED",
            "real_site_requests":"NOT_RUN",
            "user_profiles":"NOT_TOUCHED",
            "rules_published":0,
            "publication":"NO_GO"
        }
        report.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",
                          encoding="utf-8")
        for kind in KINDS:
            v=summary[kind]
            print("UPC OFFICIAL UBOL STOCK",kind,
                  "baseline_received",len(v["browser_baseline_received"]),
                  "stock_blocked",len(v["blocked_by_official_ubol_stock_vs_browser_only"]),
                  "stock_still_received",",".join(v["still_received_with_official_stock"]) or "(none)",
                  "baseline_missing",",".join(v["browser_baseline_not_received_unknown_cause"]) or "(none)",
                  flush=True)
        print("UPC OFFICIAL UBOL STOCK PASS:",lock["release_tag"],
              "default enabled sets:",",".join(enabled_actual),"publication NO_GO")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=4)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--package",type=Path,required=True)
    p.add_argument("--report",type=Path,required=True)
    a=p.parse_args()
    try:
        package,report=a.package.resolve(),a.report.resolve()
        if not package.is_dir() or report.exists() or report.is_relative_to(
                Path(__file__).resolve().parents[2]):
            raise ValueError("invalid temporary uBOL package or report location")
        run(package,report)
        return 0
    except (OSError,ValueError,RuntimeError,TypeError,KeyError) as error:
        print("UPC OFFICIAL UBOL STOCK BLOCKED:",error,file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
