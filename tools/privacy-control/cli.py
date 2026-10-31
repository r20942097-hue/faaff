"""UPC Phase 1 offline assessment. No network, browser or OS writes."""
import argparse
import json
from pathlib import Path
import sys

from core import build_report, verify_report
from render_html import render


def summary(report):
    counts = report["coverage"]["counts"]
    total = report["candidate_rules"]
    exact = counts.get("EXACT_OVERLAP_WITH_PINNED_STABLE", 0)
    unknown = counts.get("NO_EXACT_STABLE_OVERLAP_NOT_VERIFIED", 0)
    unsupported = counts.get("UNSUPPORTED_NOT_VERIFIED", 0)
    return "\n".join([
        "## UPC Phase 1 — read-only pinned stable overlap",
        "",
        "| Evidence | Observation |",
        "|---|---|",
        "| Pinned source commit | `" + report["source"]["source_commit"] + "` |",
        "| Stable tracking rules | " + str(report["stable_rules"]) + " |",
        "| Optional candidate tracking rules | " + str(total) + " |",
        "| Exact normalized stable overlaps | " + str(exact) + " |",
        "| No exact stable overlap (not proven incremental) | " + str(unknown) + " |",
        "| Unsupported syntax (not proven) | " + str(unsupported) + " |",
        "| Actual enabled browser stock lists | NOT_RUN |",
        "| Firefox/uBO, uBOL or real-site efficacy | NOT_RUN |",
        "| Public subscription modifications | 0 |",
        "| Release | **NO_GO** |",
        "",
        "Exact overlap is not proof of browser behavior; lack of exact overlap"
        " is not proof of useful incremental blocking.",
        "",
    ])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path,
                        default=Path(__file__).resolve().parents[2])
    parser.add_argument("--report", type=Path)
    parser.add_argument("--html", type=Path, help="write a static offline viewer outside checkout")
    parser.add_argument("--github-summary", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        base = args.repository.resolve()
        report = build_report(base)
        if args.check:
            verify_report(report)
        payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        if args.report:
            output = args.report.resolve()
            if output.is_relative_to(base):
                raise ValueError("reports cannot be written inside source checkout")
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(payload, encoding="utf-8")
        else:
            print(payload)
        if args.html:
            viewer = args.html.resolve()
            if viewer.is_relative_to(base):
                raise ValueError("HTML viewer must be written outside checkout")
            viewer.parent.mkdir(parents=True, exist_ok=True)
            viewer.write_text(render(report), encoding="utf-8")
        if args.github_summary:
            output = args.github_summary.resolve()
            if output.is_relative_to(base):
                raise ValueError("CI summary path must be outside checkout")
            with output.open("a", encoding="utf-8") as stream:
                stream.write(summary(report))
        print("UPC OFFLINE CHECK: PASS; pinned stable", report["stable_rules"],
              "candidate", report["candidate_rules"],
              "release NO_GO", file=sys.stderr)
        return 0
    except (OSError, ValueError, UnicodeError, KeyError, TypeError) as error:
        print("UPC OFFLINE CHECK: FAIL:", error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
