"""Classify CI runtime evidence independently from release approval (stdlib only)."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
import sys


@dataclass(frozen=True)
class Decision:
    engineering_ci: str
    product_ci: str
    release_gate: str
    reason: str
    checks_consistent: bool


def evaluate(source_check: str, source_present: str, runtime_test: str) -> Decision:
    """Fail closed for missing or contradictory GitHub Actions needs results."""
    if source_check != "success":
        return Decision("FAIL", "NOT_RUN", "NO_GO", "Source check did not succeed", False)
    if source_present not in ("true", "false"):
        return Decision("FAIL", "NOT_RUN", "NO_GO", "Invalid or missing source presence output", False)
    if source_present == "false":
        if runtime_test == "skipped":
            return Decision("PASS", "NOT_RUN", "NO_GO", "Bootstrap-only: runtime source absent; product tests skipped", True)
        return Decision("FAIL", "UNVERIFIED", "NO_GO", "Runtime result inconsistent with absent source", False)
    if runtime_test == "success":
        return Decision("PASS", "CI_PASS", "NO_GO", "Runtime CI passed; real-site/device/release gates are separate", True)
    return Decision("FAIL", "FAIL", "NO_GO", f"Runtime CI did not succeed: {runtime_test or 'missing'}", False)


def report(decision: Decision, source_check: str, source_present: str, runtime_test: str) -> str:
    return ("## Product readiness evidence (not a release approval)\n\n"
            "| Evidence | Observed |\n| --- | --- |\n"
            f"| Source check job | `{source_check or 'missing'}` |\n"
            f"| Runtime source present | `{source_present or 'missing'}` |\n"
            f"| Runtime test job | `{runtime_test or 'missing'}` |\n"
            f"| Engineering CI | **{decision.engineering_ci}** |\n"
            f"| Product runtime CI | **{decision.product_ci}** |\n"
            f"| Release gate | **{decision.release_gate}** |\n\n"
            f"{decision.reason}. Product CI success never establishes real-site, "
            "native Firefox/Windows, long-duration recording or release approval.\n")


def main() -> int:
    source_check = os.environ.get("SOURCE_CHECK_RESULT", "")
    source_present = os.environ.get("SOURCE_PRESENT", "")
    runtime_test = os.environ.get("RUNTIME_TEST_RESULT", "")
    decision = evaluate(source_check, source_present, runtime_test)
    print(json.dumps(asdict(decision), ensure_ascii=False, sort_keys=True))
    summary = report(decision, source_check, source_present, runtime_test)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as stream:
            stream.write(summary)
    if os.environ.get("GITHUB_OUTPUT"):
        with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as stream:
            stream.write(f"product_ci={decision.product_ci}\nrelease_gate={decision.release_gate}\n")
    if not decision.checks_consistent:
        print("::error::Product CI evidence is incomplete or inconsistent", file=sys.stderr)
        return 1
    if decision.product_ci == "NOT_RUN":
        print("::notice::Product runtime NOT_RUN; bootstrap-only CI must not be considered a release PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
