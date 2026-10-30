"""Conservative, deterministic decision contract for GitHub AI change reviews.

This is *not* a model evaluation or an authorization service. It helps an
agent surface missing evidence before proposing a merge. AGENTS.md and active
GitHub Rulesets remain authoritative.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence
import re

SHA40 = re.compile(r"[0-9a-f]{40}\Z")
RISK_ORDER = ("documentation", "metadata", "infrastructure", "implementation", "publication", "prohibited")


@dataclass(frozen=True)
class Assessment:
    risk: str
    status: str
    reasons: tuple[str, ...]


def _clean_path(path: object) -> bool:
    return (
        isinstance(path, str)
        and bool(path)
        and "\\" not in path
        and not path.startswith("/")
        and all(part not in ("", ".", "..") for part in path.split("/"))
    )


def classify_path(path: str) -> str:
    """Classify by worst plausible effect, not by filename alone."""
    if not _clean_path(path):
        return "prohibited"
    lower = path.lower()
    if lower.endswith((".zip", ".7z", ".exe", ".dll", ".key", ".pem", ".p12")):
        return "prohibited"
    parts = lower.split("/")
    if (
        any(part in {".git", ".ssh", "secrets", ".env", ".env.local"} for part in parts)
        or lower.endswith((".token", ".secret"))
        or any(ord(char) < 32 or ord(char) == 127 for char in path)
    ):
        return "prohibited"
    if (
        path.startswith("browser_filter_lists/")
        or path.startswith("releases/")
        or path.startswith("dist/")
    ):
        return "publication"
    if path.startswith((".github/workflows/", "ai/imports/")):
        return "infrastructure"
    if path.startswith(("rplay_watcher/", "extension/", "integrations/")):
        return "implementation"
    if path in {"AGENTS.md", "ai/PROJECT_STATE.json", "ai/projects.json"}:
        return "metadata"
    if path.startswith("ai/") and path.endswith(".md"):
        return "documentation"
    if path.startswith("ai/"):
        return "infrastructure" if lower.endswith((".py", ".sh", ".js", ".yml", ".yaml")) else "metadata"
    if lower.endswith((".md", ".rst")):
        return "documentation"
    # Unknown file types are not automatically low risk.
    return "implementation"


def classify_paths(paths: Sequence[str]) -> str:
    if not paths:
        return "prohibited"
    categories = {classify_path(path) for path in paths}
    return max(categories, key=RISK_ORDER.index)


def assess_change(
    *,
    paths: Sequence[str],
    head_sha: str,
    checked_sha: str,
    checks: Mapping[str, str],
    required_checks: Sequence[str],
    owner_approved: bool,
    product_verified: bool = False,
) -> Assessment:
    """Evaluate supplied evidence; never fetch credentials or perform a merge.

    The caller must obtain required check contexts from the *current* Ruleset
    and supply results bound to the exact PR head SHA. An empty list is not a
    shortcut to approval.
    """
    risk = classify_paths(paths)
    failures: list[str] = []
    if risk == "prohibited":
        failures.append("prohibited_or_invalid_path")
    if risk == "publication":
        failures.append("publication_hold")
    if not SHA40.fullmatch(head_sha) or checked_sha != head_sha:
        failures.append("stale_or_invalid_check_sha")
    if not required_checks or len(set(required_checks)) != len(required_checks):
        failures.append("invalid_required_checks")
    else:
        for check in required_checks:
            if checks.get(check) != "success":
                failures.append("missing_or_nonpassing_check:" + check)
    if risk == "implementation" and not product_verified:
        # A real product change must not be treated as release-ready merely
        # because unrelated infrastructure CI succeeded.
        failures.append("implementation_verification_not_supplied")
    if failures:
        return Assessment(risk, "BLOCKED", tuple(failures))
    if not owner_approved:
        return Assessment(risk, "AWAITING_OWNER_APPROVAL", ("approval_required_by_repo_policy",))
    return Assessment(
        risk, "ELIGIBLE_FOR_REVIEW", ("github_ruleset_and_release_gates_still_apply",)
    )
