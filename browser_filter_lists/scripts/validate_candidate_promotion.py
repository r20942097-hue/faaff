from datetime import date
from pathlib import Path
import json
import re
import sys

import validate_candidate_evidence as evidence_validator

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "manifest.json"
SOURCE_FAMILY_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")


def load_json(path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate(today=None):
    errors = []
    warnings = []
    today = today or date.today()

    manifest = load_json(MANIFEST_PATH)
    minimum = manifest.get("candidate_min_independent_source_families")
    max_age = manifest.get("candidate_evidence_max_age_days")
    review_required = manifest.get("candidate_exception_review_required")

    if not isinstance(minimum, int) or not 2 <= minimum <= 5:
        errors.append("manifest.json: candidate_min_independent_source_families must be 2..5")
        return errors, warnings
    if review_required is not True:
        errors.append("manifest.json: candidate_exception_review_required must be true")

    queue = load_json(ROOT / manifest["candidate_queue"])
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
            if role not in {"classification", "exception"}:
                errors.append(f"{ev_prefix}: role must be classification or exception")
            if not isinstance(family, str) or not SOURCE_FAMILY_RE.fullmatch(family):
                errors.append(f"{ev_prefix}: invalid source_family")
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
