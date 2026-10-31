"""Independent fail-closed audit for a synthetic Chromium MV3 DNR lab."""
import argparse
import json
from pathlib import Path
import sys

from chromium_dnr_probe import compile_dnr, verify_lifecycle, verify_first_party, SENTINEL, CONTROLS, KINDS


def audit(doc):
    errors=[]
    hosts, rules, source=compile_dnr()
    if (doc.get("schema")!="upc-chromium-mv3-dnr-lab/v1"
            or doc.get("result")!="PASS"
            or doc.get("browser")!="PLAYWRIGHT_BUNDLED_CHROMIUM"
            or doc.get("actual_ubol_loaded")!="NOT_RUN"
            or doc.get("compiled_rules")!=39
            or doc.get("candidate_hosts")!=hosts
            or doc.get("candidate_source")!=source
            or doc.get("sentinel")!=SENTINEL
            or doc.get("controls")!=list(CONTROLS)
            or doc.get("resource_types")!=list(KINDS)
            or doc.get("proxy_forwarding")!="DISABLED"
            or doc.get("https_connect")!="DENIED"
            or doc.get("real_website_traffic")!="NOT_RUN"
            or doc.get("real_user_stock_lists")!="NOT_RUN"
            or doc.get("user_browser_profiles")!="NOT_TOUCHED"
            or type(doc.get("rules_published")) is not int
            or doc["rules_published"]!=0
            or doc.get("release")!="NO_GO"):
        errors.append("scope, provenance, binary identity or release boundary invalid")
    if doc.get("first_party_candidate_host")!="rudderstack.com":
        errors.append("missing named first-party candidate safety control")
    try:
        verify_first_party(doc.get("first_party_candidate_receipts"))
    except (ValueError,TypeError,KeyError) as error:
        errors.append("third-party-only DNR rules overblock first-party requests: "+str(error))
    candidate_hostnames = hosts
    baselines=doc.get("baseline_receipts")
    if isinstance(baselines,dict) and set(baselines)==set(KINDS):
        preblocked={}
        reachable={}
        for kind in KINDS:
            rounds=baselines.get(kind)
            if (not isinstance(rounds,list) or not rounds or
                    not isinstance(rounds[0],dict)):
                errors.append("invalid baseline receipt type: "+kind)
                continue
            preblocked[kind]=[host for host in candidate_hostnames
                              if rounds[0].get(host) is False]
            reachable[kind]=[host for host in candidate_hostnames
                              if rounds[0].get(host) is True]
        if (doc.get("baseline_preblocked_hosts")!=preblocked
                or doc.get("newly_blocked_relative_to_no_extension")!=reachable):
            errors.append("preblocked/additional host classification not raw-evidence-derived")
    if doc.get("baseline_missing_attribution") != "UNKNOWN_BROWSER_OR_PROXY_CAUSE_NOT_DNR":
        errors.append("unknown baseline missing requests incorrectly attributed to DNR")
    names=("baseline_receipts","dnr_receipts","restored_receipts")
    if any(name not in doc for name in names):
        errors.append("required original browser receipts missing")
    else:
        try:
            verify_lifecycle(*(doc[name] for name in names),hosts)
        except (ValueError,KeyError,TypeError,IndexError,AttributeError) as error:
            errors.append("browser outcome or rollback not proven: "+str(error))
    return errors


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--report",type=Path,required=True)
    p.add_argument("--github-summary",type=Path)
    args=p.parse_args()
    try:
        document=json.loads(args.report.read_text(encoding="utf-8"))
        failures=audit(document)
        if failures:
            raise ValueError("; ".join(failures))
        if args.github_summary:
            with args.github_summary.open("a",encoding="utf-8") as out:
                out.write("## Chromium MV3 static DNR synthetic lab PASS\n\n")
                out.write("38 pinned candidate rules, 1 sentinel; ")
                out.write("two independent third-party image and script rounds ")
                out.write("for baseline, enabled DNR and restored baseline.\n\n")
                out.write("**NOT uBO Lite. NOT a stock-list overlap comparison.** ")
                out.write("No public website traffic or user profile. Release NO_GO.\n")
        print("UPC CHROMIUM DNR EVIDENCE PASS: real bundled Chromium + MV3 static rules, NO_GO")
        return 0
    except (ValueError,OSError,TypeError,KeyError) as error:
        print("UPC CHROMIUM DNR EVIDENCE FAIL:",error,file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
