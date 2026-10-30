"""Read-only, fail-closed GitHub PR evidence assessment.

Inputs must be actual GitHub REST payloads. This is an advisory evidence
consumer, not authorization, automatic review, or a merge service.
"""
from __future__ import annotations

import re
from typing import Any

from ai.decision_contract import assess_change

SHA = re.compile(r"[0-9a-f]{40}\Z")


def review_evidence(
    *,
    repository: str,
    pull: object,
    paths: object,
    ruleset: object,
    check_runs: object,
) -> dict[str, Any]:
    """Return a conservative assessment and explain any evidence defect.

    No 'owner_approved' input exists by design: an API observation cannot
    prove owner authorization or a real product acceptance test.
    """
    failures: list[str] = []
    if not isinstance(pull, dict) or not isinstance(paths, list):
        return {"status": "BLOCKED", "reasons": ["invalid_pr_or_file_evidence"]}
    if not isinstance(ruleset, dict) or not isinstance(check_runs, dict):
        return {"status": "BLOCKED", "reasons": ["invalid_ruleset_or_checks"]}
    head = pull.get("head")
    base = pull.get("base")
    if not isinstance(head, dict) or not isinstance(base, dict):
        return {"status": "BLOCKED", "reasons": ["missing_pr_refs"]}
    head_sha = head.get("sha")
    base_repo = base.get("repo")
    if not isinstance(head_sha, str) or not SHA.fullmatch(head_sha):
        failures.append("invalid_head_sha")
    if not isinstance(base_repo, dict) or base_repo.get("full_name") != repository:
        failures.append("repository_mismatch")
    if base.get("ref") != "main":
        failures.append("unexpected_base_branch")
    if pull.get("state") != "open" or pull.get("draft") is not False:
        failures.append("not_open_ready_pr")
    if pull.get("merged") is True:
        failures.append("already_merged")
    if pull.get("mergeable") is not True:
        failures.append("not_confirmed_mergeable")
    if not paths or any(not isinstance(p, str) or not p for p in paths):
        failures.append("invalid_changed_files")
    if len(paths) != len(set(str(p) for p in paths)):
        failures.append("duplicate_changed_files")
    if ruleset.get("target") != "branch" or ruleset.get("enforcement") != "active":
        failures.append("ruleset_not_active_branch")
    condition = ruleset.get("conditions")
    ref_names = condition.get("ref_name") if isinstance(condition, dict) else None
    include = ref_names.get("include") if isinstance(ref_names, dict) else None
    exclude = ref_names.get("exclude") if isinstance(ref_names, dict) else None
    if (not isinstance(include, list) or
            not any(name in ("~DEFAULT_BRANCH", "refs/heads/main") for name in include) or
            not isinstance(exclude, list) or exclude):
        failures.append("unverified_ruleset_scope")
    rule_list = ruleset.get("rules")
    if not isinstance(rule_list, list):
        return {"status": "BLOCKED", "reasons": failures + ["missing_rules"]}
    required = []
    for item in rule_list:
        if isinstance(item, dict) and item.get("type") == "required_status_checks":
            parameters = item.get("parameters")
            required = parameters.get("required_status_checks", []) if isinstance(parameters, dict) else []
            break
    if not isinstance(required, list) or not required:
        failures.append("no_required_checks_in_ruleset")
        required = []
    names: list[str] = []
    app_ids: dict[str, int] = {}
    for item in required:
        if not isinstance(item, dict):
            failures.append("invalid_required_check_entry")
            continue
        name = item.get("context")
        app_id = item.get("integration_id")
        if not isinstance(name, str) or not name or type(app_id) is not int or app_id <= 0:
            failures.append("invalid_required_check_entry")
            continue
        if name in app_ids:
            failures.append("duplicate_required_context:" + name)
        names.append(name)
        app_ids[name] = app_id
    if not names:
        failures.append("empty_valid_required_contexts")
    raw_checks = check_runs.get("check_runs")
    total_count = check_runs.get("total_count")
    if (not isinstance(raw_checks, list) or
            type(total_count) is not int or total_count != len(raw_checks)):
        return {"status": "BLOCKED", "reasons": failures + ["incomplete_check_runs_collection"]}
    observed: dict[str, str] = {}
    pending_checks: list[str] = []
    nonpassing_checks: list[str] = []
    for name in names:
        candidates = [c for c in raw_checks if isinstance(c, dict) and c.get("name") == name]
        if len(candidates) != 1:
            failures.append("missing_or_ambiguous_check:" + name)
            continue
        c = candidates[0]
        app = c.get("app")
        if not isinstance(app, dict) or app.get("id") != app_ids[name]:
            failures.append("check_publisher_mismatch:" + name)
        if c.get("head_sha") != head_sha:
            failures.append("check_head_mismatch:" + name)
        status, conclusion = c.get("status"), c.get("conclusion")
        if status in ("queued", "pending", "in_progress"):
            pending_checks.append(name)
        elif status != "completed" or conclusion != "success":
            nonpassing_checks.append(name)
        observed[name] = "success" if status == "completed" and conclusion == "success" else "incomplete"
    if failures:
        return {
            "status": "BLOCKED", "reasons": sorted(set(failures)),
            "head_sha": head_sha, "required_checks": names,
            "pending_checks": pending_checks, "nonpassing_checks": nonpassing_checks,
        }
    result = assess_change(
        paths=paths,
        head_sha=head_sha,
        checked_sha=head_sha,
        checks=observed,
        required_checks=names,
        owner_approved=False,
        product_verified=False,
    )
    return {
        "status": result.status,
        "risk": result.risk,
        "reasons": list(result.reasons),
        "head_sha": head_sha,
        "required_checks": names,
        "pending_checks": pending_checks, "nonpassing_checks": nonpassing_checks,
    }
