"""Independent fail-closed verifier for isolated full Firefox uBO probe evidence."""
import argparse
import json
from pathlib import Path
import re
import sys


def audit(record, lock):
    errors = []
    if (record.get("schema") != "upc-firefox-ubo-loopback/v1"
            or record.get("status") not in ("PASS", "PARTIAL")
            or record.get("official_ubo_version") != lock["tag"]
            or record.get("xpi_sha256") != lock["sha256"]
            or record.get("target") != "probe.scorecardresearch.com"
            or record.get("baseline") != "RECEIVED"
            or record.get("control_before") != "RECEIVED"
            or record.get("extension_on") != "BLOCKED"
            or record.get("control_while_installed") != "RECEIVED"
            or record.get("same_origin_while_installed") != "RECEIVED"
            or record.get("control_site_relation") != "SAME_SITE_DIFFERENT_HOST"
            or record.get("after_uninstall") != "RECEIVED"):
        errors.append("actual HTTP blocking/unblocking sequence unverified")
    if record.get("status") == "PASS":
        if (record.get("independent_third_party_control") != "RECEIVED"
                or record.get("target_specificity") != "PROVISIONAL_LOOPBACK_ONLY"):
            errors.append("third-party specificity was not independently observed")
    elif (record.get("independent_third_party_control") != "BLOCKED_IN_SYNTHETIC_LOOPBACK"
          or record.get("target_specificity") != "NOT_ESTABLISHED"):
        errors.append("partial outcome or third-party blocked control misrepresented")
    version = record.get("firefox_version")
    if not isinstance(version, str) or not re.fullmatch(r"\d+(?:\.\d+){1,3}", version):
        errors.append("missing real Firefox version")
    if (record.get("network_scope") != "RFC5737_TEST_NET_IP_ASSIGNED_TO_CI_LOOPBACK"
            or record.get("actual_live_websites") != "NOT_RUN"
            or record.get("actual_user_configuration") != "NOT_VERIFIED"
            or record.get("real_signed_url_safety") != "NOT_RUN"
            or record.get("published_rules") != 0
            or record.get("release") != "NO_GO"):
        errors.append("live-site, network or release scope overstated")
    return errors


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--report", required=True, type=Path)
    p.add_argument("--lock", required=True, type=Path)
    p.add_argument("--github-summary", type=Path)
    args = p.parse_args()
    try:
        record = json.loads(args.report.read_text(encoding="utf-8"))
        lock = json.loads(args.lock.read_text(encoding="utf-8"))
        from fetch_firefox_xpi import verify_lock
        verify_lock(lock)
        failures = audit(record, lock)
        if failures:
            raise ValueError("; ".join(failures))
        if args.github_summary:
            with args.github_summary.open("a", encoding="utf-8") as out:
                out.write("## Firefox full uBlock Origin (isolated real HTTP)\n\n")
                out.write("Version: Firefox " + record["firefox_version"]
                          + ", uBO " + record["official_ubo_version"] + ".\n\n")
                out.write("Loopback: baseline RECEIVED → extension BLOCKED → "
                          "uninstall RESTORED; same-site and same-origin controls PRESERVED.\n\n")
                out.write("Independent third-party control: " + record["independent_third_party_control"]
                          + "; target specificity " + record["target_specificity"] + ".\n\n")
                out.write("**Real websites, actual browser profile, authentication, "
                          "checkout and signed URLs NOT_RUN / NOT_VERIFIED. Release NO_GO.**\n")
        print("UPC FIREFOX EVIDENCE REPORT:", record["status"],
              "target_specificity", record["target_specificity"],
              "real sites NOT_RUN, release NO_GO")
        return 0
    except (KeyError, OSError, ValueError, TypeError) as error:
        print("UPC FIREFOX EVIDENCE FAIL:", error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
