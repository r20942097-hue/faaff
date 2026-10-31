"""Independent evidence validator: official uBO Lite stock, not UPC candidate installation."""
import argparse
import json
from pathlib import Path
import sys
from fetch_official_ubol import LOCK,verify_lock
from chromium_dnr_probe import compile_dnr,CONTROLS,KINDS,SENTINEL
from ubol_official_probe import audit_lifecycle


def audit(doc):
    errors=[]
    lock=verify_lock(json.loads(LOCK.read_text(encoding="utf-8")))
    hosts,_,source=compile_dnr()
    if (doc.get("schema")!="upc-official-ubol-chromium-stock/v1"
            or doc.get("result")!="PASS"
            or doc.get("source")!=lock["source"]
            or doc.get("official_tag")!=lock["release_tag"]
            or doc.get("official_asset_sha256")!=lock["sha256"]
            or doc.get("official_asset_size")!=lock["size"]
            or doc.get("browser")!="PLAYWRIGHT_BUNDLED_CHROMIUM"
            or doc.get("official_ubol_installed") is not True
            or doc.get("candidate_source")!=source
            or doc.get("candidate_rules_installed") is not False
            or doc.get("candidate_hosts")!=hosts
            or doc.get("sentinel")!=SENTINEL
            or doc.get("controls")!=list(CONTROLS)
            or doc.get("resource_types")!=list(KINDS)
            or doc.get("comparison_limitation")!=
               "BROWSER_ONLY_VS_OFFICIAL_UBOL_NOT_UBOL_PLUS_CANDIDATES"
            or doc.get("browser_baseline_missing_root_cause")!="NOT_ESTABLISHED"
            or doc.get("no_second_active_blocker") is not True
            or doc.get("outbound_proxy")!="DENIED"
            or doc.get("real_site_requests")!="NOT_RUN"
            or doc.get("user_profiles")!="NOT_TOUCHED"
            or type(doc.get("rules_published")) is not int
            or doc["rules_published"]!=0
            or doc.get("publication")!="NO_GO"):
        errors.append("invalid official provenance, claims or publication boundary")
    enabled=doc.get("official_enabled_static_rulesets")
    if (not isinstance(enabled,list) or not all(isinstance(x,str) for x in enabled)
            or not set(lock["expected_static_rulesets"]).issubset(enabled)):
        errors.append("official active stock rulesets unverified")
    try:
        audit_lifecycle(doc["before"],doc["official_stock"],doc["restored"],
                        doc["first_party_candidate_receipts"],hosts,
                        doc.get("synthetic_protocol_safety"))
        cover=doc["coverage"]
        if set(cover)!=set(KINDS):
            raise ValueError("missing resource-specific stock comparisons")
        for kind in KINDS:
            base=doc["before"][kind][0]
            ubol=doc["official_stock"][kind][0]
            derived={
                "browser_baseline_received":[h for h in hosts if base[h]],
                "browser_baseline_not_received_unknown_cause":[h for h in hosts if not base[h]],
                "blocked_by_official_ubol_stock_vs_browser_only":[h for h in hosts if base[h] and not ubol[h]],
                "still_received_with_official_stock":[h for h in hosts if base[h] and ubol[h]],
                "candidate_hosts_total":len(hosts),
            }
            if cover[kind]!=derived:
                raise ValueError("official uBOL stock coverage is not directly derived from HTTP evidence")
    except (ValueError,KeyError,TypeError,IndexError,AttributeError) as e:
        errors.append("browser stock receipt/restore not proven: "+str(e))
    return errors


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--report",type=Path,required=True)
    p.add_argument("--github-summary",type=Path)
    a=p.parse_args()
    try:
        data=json.loads(a.report.read_text(encoding="utf-8"))
        errors=audit(data)
        if errors:
            raise ValueError("; ".join(errors))
        if a.github_summary:
            with a.github_summary.open("a",encoding="utf-8") as out:
                out.write("## Official uBO Lite Chromium stock (synthetic HTTP)\n\n")
                out.write("Verified vendor tag and SHA-256, actual enabled DNR rulesets, ")
                out.write("two independent image and script rounds in each of 3 isolated Chromium profiles.\n\n")
                for kind in KINDS:
                    row=data["coverage"][kind]
                    out.write(f"**{kind}**: {len(row['blocked_by_official_ubol_stock_vs_browser_only'])}/38 ")
                    out.write("host fixtures blocked by official uBO Lite relative to extension-free browser; ")
                    out.write(f"{len(row['browser_baseline_not_received_unknown_cause'])}/38 ")
                    out.write("not received even without any extension.\n\n")
                    out.write("Received despite uBO Lite: "+
                              (", ".join("`"+x+"`" for x in row["still_received_with_official_stock"]) or "none")+".\n\n")
                out.write("Synthetic HMAC query, HttpOnly cookie auth and HTTP Range 206 ")
                out.write("preserved in all three actual Chromium sessions.\\n\\n")
                out.write("**Not measured:** candidate rules added inside uBO Lite, ")
                out.write("actual user settings, live websites or production HTTPS. Publication NO_GO.\n")
        print("UPC OFFICIAL UBOL EVIDENCE PASS: vendor stock, no added candidate rules, NO_GO")
        return 0
    except (ValueError,OSError,KeyError,TypeError) as e:
        print("UPC OFFICIAL UBOL EVIDENCE FAIL:",e,file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
