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
    rounds=report.get("two_round_receipts")
    if not isinstance(rounds,dict) or set(rounds)!=set(stages):
        errors.append("missing independent repeated samples")
    else:
        for stage, samples in rounds.items():
            if (not isinstance(samples,list) or len(samples)!=2
                    or any(type(sample) is not dict or sample!=stages[stage]
                           for sample in samples)):
                errors.append("repeated samples disagree or are incomplete: "+stage)
    if report.get("auto_promote_candidates") is not False:
        errors.append("automatic rule promotion is forbidden")
    if report.get("additional_host_inference") != "ONE_IMAGE_FIXTURE_PER_HOST_NOT_REAL_WORLD_EFFICACY":
        errors.append("host outcome overclaim or missing experimental scope")
    already=[host for host in hosts if not stages["stock"][host]]
    if report.get("already_blocked_by_stock_synthetic_hosts") != already:
        errors.append("stock-covered candidate list not evidence based")
    incremental=[host for host in hosts if stages["stock"][host]]
    if (report.get("incremental_synthetic_hosts") != incremental
            or report.get("incremental_synthetic_host_count") != len(incremental)):
        errors.append("incremental host counts not evidence-based")
    scripts=report.get("script_stage_receipts")
    script_rounds=report.get("script_two_round_receipts")
    if not isinstance(scripts,dict) or set(scripts)!=set(stages):
        errors.append("script scenario stages incomplete")
    else:
        for phase, hit in scripts.items():
            if (not isinstance(hit,dict) or set(hit)!=expected
                    or any(type(value) is not bool for value in hit.values())):
                errors.append("script host response evidence invalid: "+phase)
                return errors
            if not all(hit[host] for host in CONTROL_HOSTS):
                errors.append("benign script control blocked: "+phase)
        if (not scripts["stock"][SENTINEL] or scripts["candidate"][SENTINEL]
                or not scripts["restored"][SENTINEL]):
            errors.append("script managed rule sentinel transition not proven")
        if any(scripts["candidate"][host] for host in hosts):
            errors.append("candidate script host not blocked")
        if any(scripts["stock"][host]!=scripts["restored"][host] for host in hosts):
            errors.append("script candidate rollback mismatch")
        scripts_new=[host for host in hosts if scripts["stock"][host]]
        scripts_old=[host for host in hosts if not scripts["stock"][host]]
        if (report.get("script_incremental_synthetic_hosts")!=scripts_new
                or report.get("script_incremental_synthetic_host_count")!=len(scripts_new)
                or report.get("script_already_blocked_by_stock_synthetic_hosts")!=scripts_old):
            errors.append("script effect counts not derived from observations")
        if not isinstance(script_rounds,dict) or set(script_rounds)!=set(stages):
            errors.append("missing independent script sampling")
        else:
            for phase, samples in script_rounds.items():
                if (not isinstance(samples,list) or len(samples)!=2
                        or any(type(row) is not dict or row!=scripts[phase] for row in samples)):
                    errors.append("inconsistent script rounds: "+phase)
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
        if data.get("schema") == "upc-firefox-managed-candidates-diagnostic/v1":
            stage = data.get("failed_stage", "UNKNOWN")
            reason = data.get("reason_code", "UNKNOWN")
            if (data.get("status") != "BLOCKED" or data.get("release") != "NO_GO"
                    or data.get("rules_published") != 0
                    or data.get("candidate_activation") != "NOT_VERIFIED"):
                raise ValueError("diagnostic violates NO_GO evidence boundaries")
            if args.github_summary:
                with args.github_summary.open("a", encoding="utf-8") as stream:
                    stream.write("## Firefox managed 38 candidates: BLOCKED\\n\\n")
                    stream.write("Stage: " + str(stage) + "; reason: " + str(reason) + ".\\n\\n")
                    stream.write("Candidate application not verified; browser stages may be incomplete. ")
                    stream.write("No publication, release NO_GO.\\n")
            print("UPC CANDIDATE EVIDENCE BLOCKED:", stage, reason,
                  "stage receipts", list(data.get("stage_receipts", {})))
            return 1
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
                stream.write(f"Additional synthetic hostnames vs stock: **{data['incremental_synthetic_host_count']}/38**.\\n\\n")
                stream.write("**Additional observed hostnames:** " +
                             (", ".join("`"+host+"`" for host in data["incremental_synthetic_hosts"]) or "none") +
                             ".\\n\\n")
                stream.write("**Already blocked in installed stock uBO image fixture:** "+
                             str(len(data["already_blocked_by_stock_synthetic_hosts"])) +
                             "/38. Two independent samples per stage agree.\\n\\n")
                stream.write("**Additional script-request hostnames:** " +
                             (", ".join("`"+host+"`" for host in data["script_incremental_synthetic_hosts"]) or "none") +
                             ". ("+str(data["script_incremental_synthetic_host_count"])+"/38).\\n\\n")
                stream.write("**Already blocked by stock in script fixture:** " +
                             str(len(data["script_already_blocked_by_stock_synthetic_hosts"]))+
                             "/38. Two independent script samples per stage agree.\\n\\n")
                stream.write("This is NOT real-site protection or proof of user stock configurations. ")
                stream.write("No public rules modified; release NO_GO.\n")
        print("UPC CANDIDATE EVIDENCE PASS: real Firefox, pinned 38, delta",
              data["incremental_synthetic_host_count"],
              ",".join(data["incremental_synthetic_hosts"]) or "(none)",
              "image hosts; script delta", data["script_incremental_synthetic_host_count"],
              ",".join(data["script_incremental_synthetic_hosts"]) or "(none)",
              "script hosts; 2 rounds/resource/stage; NO_GO")
        return 0
    except (OSError,ValueError,KeyError,TypeError) as error:
        print("UPC CANDIDATE EVIDENCE FAIL:",error,file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
