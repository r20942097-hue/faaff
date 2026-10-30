"""Independent evidence validator: real managed Firefox candidates, never publication."""
import argparse
import json
from pathlib import Path
import re
import sys

from firefox_candidate_probe import SENTINEL, CONTROL_HOSTS, pinned_candidate_rules


def audit(report):
    errors = []
    rules, hosts, source = pinned_candidate_rules()
    expected = set([*hosts, SENTINEL, *CONTROL_HOSTS])
    if (report.get("schema") != "upc-firefox-managed-candidates/v1"
            or report.get("status") != "PASS"
            or report.get("mode") != "EPHEMERAL_MANAGED_STORAGE_THREE_BROWSER_SESSIONS"
            or report.get("candidate_source") != source
            or report.get("selected_candidate_count") != 38
            or report.get("candidate_hosts") != hosts
            or report.get("sentinel") != SENTINEL
            or report.get("controls") != list(CONTROL_HOSTS)
            or report.get("policy_removed") is not True
            or report.get("https_connect") != "DENIED"
            or report.get("proxy_forwarding") != "DISABLED"
            or report.get("real_site_efficacy") != "NOT_RUN"
            or report.get("actual_user_configuration") != "NOT_VERIFIED"
            or report.get("credentials_and_site_media") != "NOT_RUN"
            or report.get("rules_published") != 0
            or report.get("release") != "NO_GO"):
        errors.append("invalid candidate provenance or release/evidence boundary")
    stages = report.get("stage_receipts")
    if not isinstance(stages, dict) or set(stages) != {"stock", "candidate", "restored"}:
        errors.append("missing browser stages")
        return errors
    for name, hits in stages.items():
        if not isinstance(hits,dict) or set(hits)!=expected or any(
                type(value) is not bool for value in hits.values()):
            errors.append("invalid receipt or missing test host: " + name)
            return errors
        if not all(hits[host] for host in CONTROL_HOSTS):
            errors.append("unrelated normal browser traffic lost: " + name)
    if not stages["stock"][SENTINEL] or stages["candidate"][SENTINEL] or not stages["restored"][SENTINEL]:
        errors.append("sentinel activation or removal not proven")
    if any(stages["candidate"][host] for host in hosts):
        errors.append("not all pinned candidate rules block in browser")
    if any(stages["stock"][host] != stages["restored"][host] for host in hosts):
        errors.append("candidate removal does not restore baseline")
    incremental=[host for host in hosts if stages["stock"][host]]
    if (report.get("incremental_synthetic_hosts") != incremental
            or report.get("incremental_synthetic_host_count") != len(incremental)):
        errors.append("incremental host counts not evidence-based")
    safe = report.get("synthetic_safety")
    checks = {"signed_url_preserved", "auth_cookie_roundtrip", "media_range_206"}
    if not isinstance(safe, dict) or set(safe) != set(stages):
        errors.append("missing signed URL/auth/media results by candidate stage")
    else:
        for stage, checks_seen in safe.items():
            if (not isinstance(checks_seen, dict) or set(checks_seen) != checks
                    or any(value is not True for value in checks_seen.values())):
                errors.append("candidate stage breaks synthetic normal workflows: " + stage)
    versions=report.get("firefox_versions")
    if not isinstance(versions,dict) or set(versions)!=set(stages) or any(
        not isinstance(value,str) or re.fullmatch(r"\d+(?:\.\d+){1,3}",value) is None
        for value in versions.values()
    ):
        errors.append("missing actual Firefox version evidence")
    return errors


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--report",required=True,type=Path)
    p.add_argument("--github-summary",type=Path)
    args=p.parse_args()
    try:
        data=json.loads(args.report.read_text(encoding="utf-8"))
        errors=audit(data)
        if errors:
            raise ValueError("; ".join(errors))
        if args.github_summary:
            with args.github_summary.open("a",encoding="utf-8") as stream:
                stream.write("## Firefox managed candidate test (isolated)\n\n")
                stream.write("Official signed uBO, 38 pinned candidate filters. ")
                stream.write("Stock → managed candidates → policy removed; ")
                stream.write("three separate disposable Firefox sessions and ")
                stream.write("sentinel/benign-control gates passed.\n\n")
                stream.write(f"Additional synthetic hostnames vs stock: **{data['incremental_synthetic_host_count']}/38**. ")
                stream.write("This is NOT real-site protection or proof of user stock configurations. ")
                stream.write("No public rules modified; release NO_GO.\n")
        print("UPC CANDIDATE EVIDENCE PASS: real Firefox, pinned 38, delta",
              data["incremental_synthetic_host_count"], "synthetic hosts; NO_GO")
        return 0
    except (OSError,ValueError,KeyError,TypeError) as error:
        print("UPC CANDIDATE EVIDENCE FAIL:",error,file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
