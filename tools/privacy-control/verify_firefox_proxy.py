"""Independent verifier for the Firefox HTTP-only proxy experiment."""
import argparse
import json
from pathlib import Path
import re
import sys

HOSTS = ("pages.example.com", "assets.example.com",
         "unrelated.example.org", "probe.scorecardresearch.com")


def audit(report, lock):
    errors = []
    if (report.get("schema") != "upc-firefox-isolated-proxy/v1"
            or report.get("status") not in ("PASS", "BLOCKED")
            or report.get("ubo_version") != lock.get("tag")
            or report.get("xpi_sha256") != lock.get("sha256")
            or report.get("network_scope") != "HTTP_ONLY_RESTRICTED_PROXY_LOOPBACK_NO_FORWARD"
            or report.get("https_tunneling") != "DENIED"
            or report.get("target_host") != HOSTS[-1]
            or report.get("controls") != {
                "first_party": HOSTS[0], "same_site": HOSTS[1], "other_site": HOSTS[2]
            }
            or report.get("real_websites") != "NOT_RUN"
            or report.get("user_profile") != "NOT_TOUCHED"
            or report.get("candidate_rules_installed") is not False
            or type(report.get("released_rules")) is not int
            or report["released_rules"] != 0
            or report.get("publication") != "NO_GO"):
        errors.append("unsafe test provenance/scope or claims")
    if not isinstance(report.get("denied_proxy_requests"), int):
        errors.append("missing proxy safety enforcement metric")
    version = report.get("firefox_version")
    if not isinstance(version, str) or not (
            re.fullmatch(r"\d+(?:\.\d+){1,3}", version) or
            (report.get("status") == "BLOCKED" and version in ("UNKNOWN", "NOT_RUN"))):
        errors.append("Firefox version missing")
    states = report.get("observations", {})
    if not isinstance(states, dict) or set(states) != {
            "before", "with_addon", "after_uninstall"}:
        errors.append("observation stage missing")
        return errors
    for stage, observed in states.items():
        if not isinstance(observed, dict) or any(
                host not in HOSTS or type(value) is not bool
                for host, value in observed.items()):
            errors.append("invalid phase or host event: " + stage)
    if report.get("status") == "PASS":
        if (report.get("reason") != "TARGET_SPECIFIC_LOOPBACK_ONLY"
                or report.get("extension_uninstalled") is not True
                or set(states["before"]) != set(HOSTS)
                or set(states["with_addon"]) != set(HOSTS)
                or set(states["after_uninstall"]) != set(HOSTS)
                or not all(states["before"].values())
                or states["with_addon"][HOSTS[-1]] is not False
                or not all(states["with_addon"][host] for host in HOSTS[:-1])
                or not all(states["after_uninstall"].values())):
            errors.append("missing target-specific block or full rollback")
    else:
        if report.get("reason") == "TARGET_SPECIFIC_LOOPBACK_ONLY":
            errors.append("blocked result improperly marked specific")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--github-summary", type=Path)
    args = parser.parse_args()
    try:
        from fetch_firefox_xpi import verify_lock
        report = json.loads(args.report.read_text(encoding="utf-8"))
        lock = json.loads(args.lock.read_text(encoding="utf-8"))
        verify_lock(lock)
        problems = audit(report, lock)
        if problems:
            raise ValueError("; ".join(problems))
        if args.github_summary:
            with args.github_summary.open("a", encoding="utf-8") as out:
                out.write("## Firefox uBO restricted proxy experiment\n\n")
                out.write("Status **" + report["status"] + "**; " +
                          report["reason"] + ".\n\n")
                out.write("No internet forwarding; HTTPS CONNECT denied; only synthetic hosts.\n\n")
                out.write("Actual user stock configuration and live sites NOT_RUN; publication NO_GO.\n")
        print("UPC FIREFOX PROXY EVIDENCE:", report["status"], report["reason"])
        return 0 if report["status"] == "PASS" else 1
    except (KeyError, OSError, ValueError, TypeError) as error:
        print("UPC FIREFOX PROXY EVIDENCE FAIL:", error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
