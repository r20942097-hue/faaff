from datetime import date
from pathlib import Path
import re
import sys

import validate_candidate_evidence as evidence_validator
from registry_io import integer_in_range, load_json_object as load_json, safe_path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "manifest.json"
SOURCE_FAMILY_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")


def validate(today=None):
    errors = []
    warnings = []
    today = today or date.today()

    # Share the evidence gate: promotion checks cannot bypass stale/invalid evidence.
    evidence_errors, evidence_warnings = evidence_validator.validate(today=today)
    if evidence_errors:
        return evidence_errors, evidence_warnings
    try:
        manifest = load_json(MANIFEST_PATH)
    except (OSError, ValueError) as exc:
        return [f"manifest.json cannot be read: {exc}"], warnings
    minimum = manifest.get("candidate_min_independent_source_families")
    max_age = manifest.get("candidate_evidence_max_age_days")
    review_required = manifest.get("candidate_exception_review_required")
    family_repositories = manifest.get('source_family_repositories')
    if not isinstance(family_repositories, dict) or not family_repositories:
        return ['manifest.json: source_family_repositories must be a nonempty object'], warnings
    registered_repositories = set()
    for family, repositories in family_repositories.items():
        if (not isinstance(family, str) or not SOURCE_FAMILY_RE.fullmatch(family)
                or not isinstance(repositories, list) or not repositories
                or any(not isinstance(repo, str) or not evidence_validator.REPOSITORY_RE.fullmatch(repo) for repo in repositories)):
            return ['manifest.json: invalid source-family repository registry'], warnings
        normalized = [repository.lower() for repository in repositories]
        if len(set(normalized)) != len(normalized) or registered_repositories.intersection(normalized):
            return ['manifest.json: a repository can belong to only one source family'], warnings
        registered_repositories.update(normalized)

    if not integer_in_range(minimum, 2, 5):
        errors.append("manifest.json: candidate_min_independent_source_families must be 2..5")
        return errors, warnings
    if review_required is not True:
        errors.append("manifest.json: candidate_exception_review_required must be true")

    queue_path = safe_path(ROOT, manifest.get('candidate_queue'))
    if queue_path is None:
        return ["manifest.json: candidate_queue is unsafe"], warnings
    try:
        queue = load_json(queue_path)
    except (OSError, ValueError) as exc:
        return [f"candidate queue cannot be read: {exc}"], warnings
    for index, candidate in enumerate(queue.get("candidates", []), 1):
        prefix = f"candidate[{index}] {candidate.get('domain', '<unknown>')}"
        state = candidate.get("state")

        review = candidate.get("exception_review")
        if not isinstance(review, dict):
            errors.append(f"{prefix}: exception_review is required")
            continue
        checked_at = evidence_validator.parse_iso_date(review.get("checked_at"))
        if checked_at is None:
            errors.append(f"{prefix}: exception_review.checked_at must use YYYY-MM-DD")
        elif checked_at > today:
            errors.append(f"{prefix}: exception_review.checked_at cannot be in the future")
        elif evidence_validator.evidence_is_stale(checked_at, today, max_age):
            errors.append(f"{prefix}: exception review is stale")

        known_exception = review.get("known_exception")
        if not isinstance(known_exception, bool):
            errors.append(f"{prefix}: exception_review.known_exception must be boolean")
        if not isinstance(review.get("summary"), str) or not review.get("summary", "").strip():
            errors.append(f"{prefix}: exception_review.summary is required")

        classification_families = set()
        exception_records = 0
        for evidence_index, record in enumerate(candidate.get("evidence", []), 1):
            ev_prefix = f"{prefix}:evidence[{evidence_index}]"
            role = record.get("role")
            family = record.get("source_family")
            if not isinstance(role, str) or role not in {"classification", "exception"}:
                errors.append(f"{ev_prefix}: role must be classification or exception")
            if not isinstance(family, str) or not SOURCE_FAMILY_RE.fullmatch(family):
                errors.append(f"{ev_prefix}: invalid source_family")
                continue
            repository = record.get('repository')
            if record.get('kind') == 'github_issue':
                issue = evidence_validator.GITHUB_ISSUE_RE.fullmatch(record.get('url', ''))
                repository = f'{issue.group(1)}/{issue.group(2)}' if issue else None
            if repository not in family_repositories.get(family, []):
                errors.append(f'{ev_prefix}: repository does not belong to the declared source_family')
                continue
            if role == "classification":
                if record.get("kind") != "github_file_snapshot":
                    errors.append(f"{ev_prefix}: classification evidence must be a pinned file snapshot")
                classification_families.add(family)
            elif role == "exception":
                exception_records += 1

        if state == "candidate":
            if len(classification_families) < minimum:
                errors.append(
                    f"{prefix}: candidate needs at least {minimum} independent classification source families; "
                    f"found {len(classification_families)}"
                )
            if known_exception is not False:
                errors.append(f"{prefix}: candidate state is forbidden when a known exception exists")
        elif state == "hold":
            if not candidate.get("promotion_blocker"):
                errors.append(f"{prefix}: hold requires promotion_blocker")
        elif state != "rejected":
            errors.append(f"{prefix}: unsupported state {state!r}")

        if known_exception is True:
            if state == "candidate":
                errors.append(f"{prefix}: known exception requires hold or rejected state")
            if exception_records == 0:
                errors.append(f"{prefix}: known exception requires exception evidence")
        elif exception_records:
            errors.append(f"{prefix}: exception evidence exists but known_exception is false")

    return errors, warnings


def main():
    errors, warnings = validate()
    if errors:
        print("PROMOTION GATE FAILED")
        for error in errors:
            print("ERROR:", error)
        return 1
    manifest = load_json(MANIFEST_PATH)
    queue = load_json(ROOT / manifest["candidate_queue"])
    candidates = sum(1 for item in queue.get("candidates", []) if item.get("state") == "candidate")
    holds = sum(1 for item in queue.get("candidates", []) if item.get("state") == "hold")
    print(
        "PROMOTION GATE PASSED: "
        f"minimum independent sources={manifest['candidate_min_independent_source_families']}, "
        f"candidate={candidates}, hold={holds}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
