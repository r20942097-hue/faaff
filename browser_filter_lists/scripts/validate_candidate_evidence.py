from datetime import date, datetime
from pathlib import Path
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "manifest.json"

GITHUB_FILE_SNAPSHOT_RE = re.compile(
    r"^https://github\.com/([^/]+)/([^/]+)/blob/([0-9a-f]{40})/(.+)$"
)
GITHUB_ISSUE_RE = re.compile(r"^https://github\.com/([^/]+)/([^/]+)/issues/(\d+)$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def load_json(path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def parse_iso_date(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None
    return parsed if parsed.isoformat() == value else None


def evidence_is_stale(checked_at, today, max_age_days):
    return (today - checked_at).days > max_age_days


def validate(today=None):
    errors = []
    warnings = []
    today = today or date.today()

    try:
        manifest = load_json(MANIFEST_PATH)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"manifest.json cannot be read: {exc}"], warnings

    max_age_days = manifest.get("candidate_evidence_max_age_days")
    if not isinstance(max_age_days, int) or not 1 <= max_age_days <= 365:
        errors.append("manifest.json: candidate_evidence_max_age_days must be an integer from 1 to 365")
        return errors, warnings

    candidate_rel = manifest.get("candidate_queue")
    if not isinstance(candidate_rel, str):
        return ["manifest.json: candidate_queue is missing"], warnings

    candidate_path = (ROOT / candidate_rel).resolve()
    try:
        candidate_path.relative_to(ROOT)
    except ValueError:
        return ["manifest.json: candidate_queue escapes repository root"], warnings

    try:
        queue = load_json(candidate_path)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{candidate_rel}: cannot be read: {exc}"], warnings

    observed_at = parse_iso_date(queue.get("observed_at"))
    if observed_at is None:
        errors.append(f"{candidate_rel}: observed_at must use YYYY-MM-DD")
    elif observed_at > today:
        errors.append(f"{candidate_rel}: observed_at cannot be in the future")

    candidates = queue.get("candidates")
    if not isinstance(candidates, list):
        return [f"{candidate_rel}: candidates must be an array"], warnings

    latest_verified = None
    for index, candidate in enumerate(candidates, 1):
        prefix = f"{candidate_rel}:candidate[{index}]"
        if not isinstance(candidate, dict):
            errors.append(f"{prefix}: must be an object")
            continue

        domain = candidate.get("domain", "<unknown>")
        verified_at = parse_iso_date(candidate.get("verified_at"))
        if verified_at is None:
            errors.append(f"{prefix}: verified_at must use YYYY-MM-DD")
        else:
            if verified_at > today:
                errors.append(f"{prefix}: verified_at cannot be in the future")
            latest_verified = verified_at if latest_verified is None else max(latest_verified, verified_at)

        evidence = candidate.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"{prefix}: at least one evidence record is required")
            continue

        evidence_dates = []
        for evidence_index, record in enumerate(evidence, 1):
            ev_prefix = f"{prefix}:evidence[{evidence_index}]"
            if not isinstance(record, dict):
                errors.append(f"{ev_prefix}: must be an object")
                continue

            kind = record.get("kind")
            checked_at = parse_iso_date(record.get("checked_at"))
            if checked_at is None:
                errors.append(f"{ev_prefix}: checked_at must use YYYY-MM-DD")
            else:
                evidence_dates.append(checked_at)
                if checked_at > today:
                    errors.append(f"{ev_prefix}: checked_at cannot be in the future")
                elif evidence_is_stale(checked_at, today, max_age_days):
                    errors.append(
                        f"{ev_prefix}: evidence for {domain} is stale "
                        f"({(today - checked_at).days} days; maximum {max_age_days})"
                    )

            url = record.get("url")
            if not isinstance(url, str) or not url.startswith("https://"):
                errors.append(f"{ev_prefix}: url must be HTTPS")
                continue

            if kind == "github_file_snapshot":
                repository = record.get("repository")
                path = record.get("path")
                commit = record.get("commit")

                if not isinstance(repository, str) or not REPOSITORY_RE.fullmatch(repository):
                    errors.append(f"{ev_prefix}: invalid repository")
                if not isinstance(path, str) or not path or path.startswith("/") or ".." in Path(path).parts:
                    errors.append(f"{ev_prefix}: invalid repository path")
                if not isinstance(commit, str) or not COMMIT_RE.fullmatch(commit):
                    errors.append(f"{ev_prefix}: commit must be a lowercase 40-hex SHA")

                match = GITHUB_FILE_SNAPSHOT_RE.fullmatch(url)
                if not match:
                    errors.append(f"{ev_prefix}: url must be an immutable GitHub blob URL")
                else:
                    url_repository = f"{match.group(1)}/{match.group(2)}"
                    url_commit = match.group(3)
                    url_path = match.group(4)
                    if repository != url_repository:
                        errors.append(f"{ev_prefix}: repository does not match url")
                    if commit != url_commit:
                        errors.append(f"{ev_prefix}: commit does not match url")
                    if path != url_path:
                        errors.append(f"{ev_prefix}: path does not match url")

            elif kind == "github_issue":
                if not GITHUB_ISSUE_RE.fullmatch(url):
                    errors.append(f"{ev_prefix}: invalid GitHub issue URL")
            else:
                errors.append(f"{ev_prefix}: unsupported evidence kind: {kind!r}")

        if verified_at is not None and evidence_dates and verified_at != max(evidence_dates):
            errors.append(f"{prefix}: verified_at must equal the newest evidence checked_at date")

    if observed_at is not None and latest_verified is not None and observed_at != latest_verified:
        errors.append(f"{candidate_rel}: observed_at must equal the newest candidate verified_at date")

    return errors, warnings


def main():
    errors, warnings = validate()
    if errors:
        print("EVIDENCE VALIDATION FAILED")
        for error in errors:
            print("ERROR:", error)
        for warning in warnings:
            print("WARNING:", warning)
        return 1

    manifest = load_json(MANIFEST_PATH)
    queue = load_json(ROOT / manifest["candidate_queue"])
    print(
        "EVIDENCE VALIDATION PASSED: "
        f"{len(queue.get('candidates', []))} candidate(s), "
        f"maximum age {manifest['candidate_evidence_max_age_days']} days"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
