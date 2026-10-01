from datetime import date, datetime, timedelta
from pathlib import Path
import json
import re
import sys

import validate_filters as stable_validator

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "manifest.json"
ALLOWED_LEGACY_STATUSES = {"default-covered", "overbroad-vs-default"}
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


def load_json(path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def parse_date(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None
    return parsed if parsed.isoformat() == value else None


def active_hosts(path):
    hosts = []
    for rule in stable_validator.active_rules(path):
        match = stable_validator.hostname_rule.fullmatch(rule)
        if match:
            hosts.append(match.group(1).lower())
    return hosts


def validate(today=None):
    errors = []
    warnings = []
    today = today or date.today()
    manifest = load_json(MANIFEST_PATH)

    if manifest.get("policy_version") != 4:
        errors.append("manifest.json: delta policy requires policy_version 4")
    if manifest.get("recommended_profile") != "ubo-default-delta":
        errors.append("manifest.json: recommended_profile must be ubo-default-delta")
    if manifest.get("candidate_default_overlap_forbidden") is not True:
        errors.append("manifest.json: candidate_default_overlap_forbidden must be true")

    audit_max_age = manifest.get("upstream_audit_max_age_days")
    if not isinstance(audit_max_age, int) or not 1 <= audit_max_age <= 30:
        errors.append("manifest.json: upstream_audit_max_age_days must be 1..30")
        return errors, warnings

    stable_lists = manifest.get("stable_lists", [])
    recommended = [entry for entry in stable_lists if entry.get("recommended") is True]
    if len(recommended) != 1:
        errors.append(f"manifest.json: exactly one recommended stable list is required; found {len(recommended)}")
        return errors, warnings
    delta_entry = recommended[0]
    if delta_entry.get("profile") != "ubo-default-delta":
        errors.append("manifest.json: recommended list must use profile ubo-default-delta")
    delta_path = ROOT / delta_entry["path"]
    delta_hosts = set(active_hosts(delta_path))

    legacy_entries = [entry for entry in stable_lists if entry.get("profile") == "legacy-compat"]
    legacy_hosts = set()
    for entry in legacy_entries:
        legacy_hosts.update(active_hosts(ROOT / entry["path"]))

    audit_rel = manifest.get("upstream_audit")
    audit_path = ROOT / audit_rel if isinstance(audit_rel, str) else None
    if audit_path is None or not audit_path.is_file():
        return ["manifest.json: upstream_audit is missing"], warnings
    audit = load_json(audit_path)
    if audit.get("schema") != "browser-filter-upstream-audit/v1":
        errors.append(f"{audit_rel}: unsupported schema")

    audit_date = parse_date(audit.get("checked_at"))
    if audit_date is None:
        errors.append(f"{audit_rel}: checked_at must use YYYY-MM-DD")
    elif audit_date > today:
        errors.append(f"{audit_rel}: checked_at cannot be in the future")
    elif (today - audit_date).days > audit_max_age:
        errors.append(
            f"{audit_rel}: upstream audit is stale ({(today - audit_date).days} days; maximum {audit_max_age})"
        )

    baseline = audit.get("baseline")
    if not isinstance(baseline, dict):
        errors.append(f"{audit_rel}: baseline is required")
        baseline = {}
    for key in ["easylist", "easyprivacy", "uassets", "adguard_tracking"]:
        section = baseline.get(key)
        if not isinstance(section, dict):
            errors.append(f"{audit_rel}: baseline.{key} is required")
            continue
        commit = section.get("commit")
        if not isinstance(commit, str) or not COMMIT_RE.fullmatch(commit):
            errors.append(f"{audit_rel}: baseline.{key}.commit must be lowercase 40-hex")
    default_assets = baseline.get("ubo_default_assets")
    if not isinstance(default_assets, list) or not {"easylist", "easyprivacy", "plowe-0", "ublock-unbreak"}.issubset(set(default_assets)):
        errors.append(f"{audit_rel}: baseline.ubo_default_assets is incomplete")

    legacy_records = audit.get("legacy_rules")
    if not isinstance(legacy_records, list):
        return [f"{audit_rel}: legacy_rules must be an array"], warnings
    record_map = {}
    for index, record in enumerate(legacy_records, 1):
        domain = record.get("domain") if isinstance(record, dict) else None
        if not stable_validator.valid_hostname(domain):
            errors.append(f"{audit_rel}:legacy_rules[{index}]: invalid domain")
            continue
        domain = domain.lower()
        if domain in record_map:
            errors.append(f"{audit_rel}: duplicate legacy domain: {domain}")
        record_map[domain] = record
        if record.get("status") not in ALLOWED_LEGACY_STATUSES:
            errors.append(f"{audit_rel}:{domain}: invalid legacy status")
        sources = record.get("default_sources")
        if not isinstance(sources, list) or not sources:
            errors.append(f"{audit_rel}:{domain}: default_sources are required")

    audited_legacy_hosts = set(record_map)
    if audited_legacy_hosts != legacy_hosts:
        for domain in sorted(legacy_hosts - audited_legacy_hosts):
            errors.append(f"{audit_rel}: legacy host is missing from overlap audit: {domain}")
        for domain in sorted(audited_legacy_hosts - legacy_hosts):
            errors.append(f"{audit_rel}: overlap audit contains non-legacy host: {domain}")

    for domain in sorted(delta_hosts & legacy_hosts):
        errors.append(f"{delta_entry['path']}: recommended delta duplicates a legacy/default-covered host: {domain}")

    gap_records = {}
    for record in audit.get("canary_gaps", []):
        if isinstance(record, dict) and stable_validator.valid_hostname(record.get("domain")):
            gap_records[record["domain"].lower()] = record

    for domain in sorted(delta_hosts):
        record = gap_records.get(domain)
        if not record:
            errors.append(f"{delta_entry['path']}: delta host lacks upstream gap audit: {domain}")
            continue
        if record.get("status") != "delta-approved":
            errors.append(f"{delta_entry['path']}: {domain} is not delta-approved")
        if record.get("known_exception") is not False:
            errors.append(f"{delta_entry['path']}: {domain} has unresolved exception status")

    queue = load_json(ROOT / manifest["candidate_queue"])
    for index, item in enumerate(queue.get("candidates", []), 1):
        state = item.get("state")
        overlap_info = item.get("upstream_overlap")
        if state == "candidate":
            if not isinstance(overlap_info, dict) or overlap_info.get("covered") is not False:
                errors.append(
                    f"{manifest['candidate_queue']}:candidate[{index}]: candidate must explicitly prove no default overlap"
                )
        if isinstance(overlap_info, dict) and overlap_info.get("covered") is True and state == "candidate":
            errors.append(
                f"{manifest['candidate_queue']}:candidate[{index}]: default-covered entry cannot remain candidate"
            )

    canary_rel = manifest.get("canary_manifest")
    canary_filter_rel = manifest.get("canary_filter")
    canary_path = ROOT / canary_rel if isinstance(canary_rel, str) else None
    canary_filter_path = ROOT / canary_filter_rel if isinstance(canary_filter_rel, str) else None
    if canary_path is None or not canary_path.is_file():
        errors.append("manifest.json: canary_manifest is missing")
        return errors, warnings
    if canary_filter_path is None or not canary_filter_path.is_file():
        errors.append("manifest.json: canary_filter is missing")
        return errors, warnings

    canary = load_json(canary_path)
    if canary.get("schema") != "browser-filter-canary/v1":
        errors.append(f"{canary_rel}: unsupported schema")
    minimum_soak = manifest.get("canary_min_soak_days")
    if not isinstance(minimum_soak, int) or minimum_soak < 7:
        errors.append("manifest.json: canary_min_soak_days must be at least 7")
    if canary.get("minimum_soak_days") != minimum_soak:
        errors.append(f"{canary_rel}: minimum_soak_days must match manifest")

    declared_canary_rules = set()
    for index, item in enumerate(canary.get("candidates", []), 1):
        prefix = f"{canary_rel}:candidate[{index}]"
        domain = item.get("domain")
        if not stable_validator.valid_hostname(domain):
            errors.append(f"{prefix}: invalid domain")
            continue
        domain = domain.lower()
        expected_rule = f"||{domain}^$third-party"
        if item.get("rule") != expected_rule:
            errors.append(f"{prefix}: rule must exactly match {expected_rule}")
        declared_canary_rules.add(expected_rule)
        if item.get("state") != "canary":
            errors.append(f"{prefix}: state must be canary")
        if item.get("default_coverage") != "absent-in-reviewed-default-sources":
            errors.append(f"{prefix}: default coverage must be absent")
        review = item.get("exception_review")
        if not isinstance(review, dict) or review.get("known_exception") is not False:
            errors.append(f"{prefix}: canary requires a no-known-exception review")
        else:
            review_date = parse_date(review.get("checked_at"))
            max_review_age = manifest.get("candidate_evidence_max_age_days")
            if review_date is None:
                errors.append(f"{prefix}: exception review date is invalid")
            elif review_date > today:
                errors.append(f"{prefix}: exception review date cannot be in the future")
            elif isinstance(max_review_age, int) and (today - review_date).days > max_review_age:
                errors.append(f"{prefix}: exception review is stale")
        if domain in legacy_hosts or domain in delta_hosts:
            errors.append(f"{prefix}: canary domain must not already be legacy or stable delta")
        audit_record = gap_records.get(domain)
        if not audit_record or audit_record.get("status") != "canary":
            errors.append(f"{prefix}: canary domain must have matching canary gap audit")

        started = parse_date(item.get("started_at"))
        earliest = parse_date(item.get("earliest_promotion_at"))
        if started is None or earliest is None:
            errors.append(f"{prefix}: invalid canary dates")
        elif isinstance(minimum_soak, int) and earliest < started + timedelta(days=minimum_soak):
            errors.append(f"{prefix}: earliest promotion is before minimum soak completes")

    file_rules = set(stable_validator.active_rules(canary_filter_path))
    if file_rules != declared_canary_rules:
        for rule in sorted(declared_canary_rules - file_rules):
            errors.append(f"{canary_filter_rel}: missing declared canary rule: {rule}")
        for rule in sorted(file_rules - declared_canary_rules):
            errors.append(f"{canary_filter_rel}: undeclared canary rule: {rule}")

    if not delta_hosts:
        warnings.append("recommended delta list currently has zero active rules; this is valid when upstream defaults cover all vetted stable rules")

    return errors, warnings


def main():
    errors, warnings = validate()
    if errors:
        print("DELTA POLICY VALIDATION FAILED")
        for error in errors:
            print("ERROR:", error)
        for warning in warnings:
            print("WARNING:", warning)
        return 1
    manifest = load_json(MANIFEST_PATH)
    recommended = next(entry for entry in manifest["stable_lists"] if entry.get("recommended") is True)
    delta_count = len(active_hosts(ROOT / recommended["path"]))
    canary = load_json(ROOT / manifest["canary_manifest"])
    print(f"DELTA POLICY VALIDATION PASSED: stable delta={delta_count}, canary={len(canary.get('candidates', []))}")
    for warning in warnings:
        print("WARNING:", warning)
    return 0


if __name__ == "__main__":
    sys.exit(main())
