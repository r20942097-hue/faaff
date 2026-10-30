"""Fail-closed report validation for pinned EasyPrivacy subset comparisons."""
import argparse
import json
from pathlib import Path
import sys

CASES = ("third-party-script", "third-party-image", "third-party-xhr",
         "subdomain-script", "first-party-script",
         "boundary-control", "url-text-control")
NEGATIVE = frozenset(("first-party-script", "boundary-control",
                      "url-text-control"))
ENGINES = ("ubo", "ghostery")


def audit(report, lock, source_index):
    errors = []
    counts = report.get("counts", {})
    original = report.get("source", {})
    candidate = report.get("candidate_source", {})
    if not isinstance(counts, dict):
        return ["missing count metadata"]
    if (report.get("schema") != "upc-stock-fragment-comparison/v1"
            or report.get("result") != "PASS"
            or report.get("synthetic_only") is not True
            or report.get("selected_upstream_fragments_not_full_list") is not True
            or report.get("actual_browser_enabled_lists") != "NOT_VERIFIED"
            or report.get("production_browser_site_e2e") != "NOT_RUN"
            or report.get("publication") != "NO_GO"
            or type(report.get("adopted_rules")) is not int
            or report["adopted_rules"] != 0):
        errors.append("report falsely claims verification/publication")
    manifest_files = lock.get("files", [])
    if (not isinstance(original, dict)
            or original.get("repository") != "easylist/easylist"
            or original.get("commit") != lock.get("upstream_commit")
            or original.get("scope") != lock.get("scope")
            or original.get("files") is None
            or len(original["files"]) != len(manifest_files)):
        errors.append("upstream source identity/scope mismatch")
    else:
        for declared, actual in zip(manifest_files, original["files"]):
            if (actual.get("path") != declared.get("path")
                    or actual.get("git_blob_sha") != declared.get("git_blob_sha")
                    or actual.get("bytes") != declared.get("size")
                    or len(actual.get("sha256", "")) != 64):
                errors.append("stock file identity or hash metadata incorrect")
                break
    expected_candidate = next(
        (x for x in source_index.get("files", []) if x.get("path") == "v2/tracking.txt"),
        None)
    if (not isinstance(candidate, dict)
            or expected_candidate is None
            or candidate.get("repository") != "r20942097-hue/s"
            or candidate.get("commit") != source_index.get("source_commit")
            or candidate.get("git_blob_sha") != expected_candidate.get("git_blob_sha")
            or candidate.get("path") != "v2/tracking.txt"):
        errors.append("candidate source provenance mismatch")
    if (counts.get("source_components") != 5
            or counts.get("candidates") != 38
            or counts.get("cases") != 266
            or counts.get("engine_observations") != 1064):
        errors.append("expected scenario/model counts missing")
    rows = report.get("findings", [])
    groups = report.get("per_host", [])
    if not isinstance(rows, list) or len(rows) != 266:
        errors.append("missing synthetic request evidence")
        return errors
    if not isinstance(groups, list) or len(groups) != 38:
        errors.append("missing per-host verdicts")
        return errors
    seen = set()
    actual = {
        "selected_source_baseline_blocked": dict.fromkeys(ENGINES, 0),
        "additional_synthetic_blocks": dict.fromkeys(ENGINES, 0),
        "baseline_regressions": dict.fromkeys(ENGINES, 0),
        "engine_disagreements": {"baseline": 0, "combined": 0},
    }
    for entry in rows:
        if not isinstance(entry, dict):
            errors.append("invalid request verdict"); break
        host, scenario = entry.get("host"), entry.get("scenario")
        if not isinstance(host, str) or scenario not in CASES or (host, scenario) in seen:
            errors.append("duplicate/invalid request scenario"); break
        seen.add((host, scenario))
        before, after = entry.get("stock_fragment_matches"), entry.get("candidate_plus_stock_matches")
        if (not isinstance(before, dict) or not isinstance(after, dict)
                or set(before) != set(ENGINES) or set(after) != set(ENGINES)
                or any(type(state[x]) is not bool for state in (before, after) for x in ENGINES)):
            errors.append("malformed two-engine match data"); break
        if (entry.get("actual_browser_stock_profile") != "NOT_VERIFIED"
                or entry.get("real_site_incremental_efficacy") != "NOT_ESTABLISHED"):
            errors.append("synthetic evidence overstated"); break
        for engine in ENGINES:
            if before[engine]:
                actual["selected_source_baseline_blocked"][engine] += 1
            if not before[engine] and after[engine]:
                actual["additional_synthetic_blocks"][engine] += 1
            if before[engine] and not after[engine]:
                actual["baseline_regressions"][engine] += 1
            if scenario in NEGATIVE and before[engine] != after[engine]:
                errors.append("candidate changed protected negative control")
        if before["ubo"] != before["ghostery"]:
            actual["engine_disagreements"]["baseline"] += 1
        if after["ubo"] != after["ghostery"]:
            actual["engine_disagreements"]["combined"] += 1
    if len(seen) != 266:
        errors.append("incomplete scenario coverage")
    if any(counts.get(key) != value for key, value in actual.items()):
        errors.append("aggregate counts do not match raw evidence")
    if any(v for v in actual["baseline_regressions"].values()):
        errors.append("adding candidate introduced blocking regression")
    hostnames = {name for name, _ in seen}
    if len(hostnames) != 38:
        errors.append("candidate host count mismatch")
    if {x.get("host") for x in groups if isinstance(x, dict)} != hostnames:
        errors.append("per-host labels incorrect")
    for item in groups:
        if not isinstance(item, dict):
            errors.append("invalid host summary"); break
        host = item.get("host")
        if (item.get("active_browser_stock_coverage") != "NOT_VERIFIED"
                or item.get("incremental_real_world_privacy") != "NOT_ESTABLISHED"
                or item.get("proposed_auto_adoption") is not False):
            errors.append("per-host safety gate removed"); break
        for engine in ENGINES:
            relevant = [x for x in rows if x["host"] == host]
            expected_increment = [x["scenario"] for x in relevant if
                                  not x["stock_fragment_matches"][engine] and
                                  x["candidate_plus_stock_matches"][engine]]
            expected_covered = [x["scenario"] for x in relevant if
                                x["stock_fragment_matches"][engine]]
            if (item["additional_synthetic_cases"][engine] != expected_increment
                    or item["selected_fragment_coverage"][engine] != expected_covered):
                errors.append("per-host outcomes differ from request evidence")
                break
    return errors


def summary(report):
    c = report["counts"]
    lines = [
        "## UPC: selected EasyPrivacy fragment comparison (synthetic)",
        "",
        f"Immutable source components: {c['source_components']} (NOT full EasyPrivacy).",
        f"Candidate hosts: {c['candidates']}; request scenarios: {c['cases']}; engine observations: {c['engine_observations']}.",
        f"Baseline synthetic blocks — uBO {c['selected_source_baseline_blocked']['ubo']}, Ghostery {c['selected_source_baseline_blocked']['ghostery']}.",
        f"Additional synthetic blocks — uBO {c['additional_synthetic_blocks']['ubo']}, Ghostery {c['additional_synthetic_blocks']['ghostery']}.",
        f"Engine disagreements — before {c['engine_disagreements']['baseline']}, after {c['engine_disagreements']['combined']}.",
        "",
        "**Not a full subscription, actual active browser configuration, or live-site privacy measurement.**",
        "No automatic candidate adoption. Release **NO_GO**.",
        "",
        "### Candidate hosts with additional synthetic matches",
        "",
        "| Candidate hostname | Additional uBO cases | Additional Ghostery cases |",
        "|---|---:|---:|",
        *[
            "| `" + entry["host"] + "` | "
            + str(len(entry["additional_synthetic_cases"]["ubo"])) + " | "
            + str(len(entry["additional_synthetic_cases"]["ghostery"])) + " |"
            for entry in report["per_host"]
            if entry["additional_synthetic_cases"]["ubo"]
               or entry["additional_synthetic_cases"]["ghostery"]
        ],
        "",
        "These are **fixture cases**, not proven tracking hosts newly blocked for any real user.",
        "",
    ]
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--github-summary", type=Path)
    args = p.parse_args()
    try:
        home = Path(__file__).resolve().parent
        project = home.parents[1]
        report = json.loads(args.report.read_text(encoding="utf-8"))
        lock = json.loads((home / "verification/stock-source-lock.json").read_text(encoding="utf-8"))
        source = json.loads((project / "ai/imports/s.json").read_text(encoding="utf-8"))
        failures = audit(report, lock, source)
        for item in failures:
            print("UPC STOCK EVIDENCE FAIL:", item, file=sys.stderr)
        if failures:
            return 1
        if args.github_summary:
            with args.github_summary.open("a", encoding="utf-8") as f:
                f.write(summary(report))
        else:
            print(summary(report))
        return 0
    except (ValueError, OSError, TypeError, KeyError) as e:
        print("UPC STOCK EVIDENCE FAIL:", e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
