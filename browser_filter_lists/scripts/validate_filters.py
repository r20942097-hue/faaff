from pathlib import Path
import ipaddress
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "manifest.json"

hostname_rule = re.compile(r"^\|\|([A-Za-z0-9.-]+)\^\$third-party$")
dangerous_all = re.compile(r"\$(?:all|document)(?:,|$)", re.I)
version_re = re.compile(r"^\d{8}\.\d+$")
expires_re = re.compile(r"^\d+\s+days?$", re.I)
label_re = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")


def load_json(path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def valid_hostname(host):
    if not isinstance(host, str) or not host or len(host) > 253 or "." not in host:
        return False
    if host.startswith(".") or host.endswith(".") or ".." in host:
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    return all(label_re.fullmatch(label) for label in host.split("."))


def safe_repo_path(relative_path):
    if not isinstance(relative_path, str) or not relative_path:
        return None
    candidate = (ROOT / relative_path).resolve()
    try:
        candidate.relative_to(ROOT)
    except ValueError:
        return None
    return candidate


def active_rules(path):
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith(("!", "["))
    ]


def validate():
    errors = []
    warnings = []

    if not MANIFEST_PATH.is_file():
        return ["manifest.json is missing"], warnings

    try:
        manifest = load_json(MANIFEST_PATH)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"manifest.json cannot be read: {exc}"], warnings

    if manifest.get("schema") != "browser-filter-lists/v1":
        errors.append("manifest.json: unsupported schema")

    homepage = manifest.get("homepage")
    raw_base = manifest.get("raw_base")
    stable_lists = manifest.get("stable_lists")
    if not isinstance(homepage, str) or not homepage.startswith("https://"):
        errors.append("manifest.json: homepage must be HTTPS")
    if not isinstance(raw_base, str) or not raw_base.startswith("https://"):
        errors.append("manifest.json: raw_base must be HTTPS")
    if not isinstance(stable_lists, list) or not stable_lists:
        errors.append("manifest.json: stable_lists must be a non-empty array")
        stable_lists = []

    declared_paths = set()
    declared_ids = set()
    all_hosts = {}

    for entry in stable_lists:
        if not isinstance(entry, dict):
            errors.append("manifest.json: every stable list entry must be an object")
            continue

        list_id = entry.get("id")
        rel_path = entry.get("path")
        title = entry.get("title")
        expected_count = entry.get("expected_rule_count")
        max_count = entry.get("max_rule_count")

        if not isinstance(list_id, str) or not list_id:
            errors.append("manifest.json: stable list id is missing")
        elif list_id in declared_ids:
            errors.append(f"manifest.json: duplicate stable list id: {list_id}")
        else:
            declared_ids.add(list_id)

        if rel_path in declared_paths:
            errors.append(f"manifest.json: duplicate stable list path: {rel_path}")
        elif isinstance(rel_path, str):
            declared_paths.add(rel_path)

        path = safe_repo_path(rel_path)
        if path is None or not isinstance(rel_path, str) or not rel_path.startswith("filters/"):
            errors.append(f"manifest.json: unsafe or invalid stable list path: {rel_path!r}")
            continue
        if path.is_symlink():
            errors.append(f"{rel_path}: symlinks are not allowed")
            continue
        if not path.is_file():
            errors.append(f"{rel_path}: declared stable list is missing")
            continue

        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(f"{rel_path}: cannot read UTF-8 text: {exc}")
            continue

        if text and not text.endswith("\n"):
            errors.append(f"{rel_path}: file must end with a newline")
        lines = text.splitlines()
        if not lines or lines[0].strip() != "[Adblock Plus 2.0]":
            errors.append(f"{rel_path}: missing [Adblock Plus 2.0] header")

        header_values = {}
        required_headers = [
            "! Title:",
            "! Version:",
            "! Expires:",
            "! Homepage:",
            "! Subscription:",
            "! Description:",
            "! License:",
        ]
        for header in required_headers:
            matches = [line for line in lines[:30] if line.startswith(header)]
            if len(matches) != 1:
                errors.append(f"{rel_path}: expected exactly one header {header}")
            else:
                header_values[header] = matches[0][len(header):].strip()

        if header_values.get("! Title:") not in (None, title):
            errors.append(f"{rel_path}: Title does not match manifest")
        if header_values.get("! Homepage:") not in (None, homepage):
            errors.append(f"{rel_path}: Homepage does not match manifest")

        expected_subscription = f"{raw_base}/{path.name}" if isinstance(raw_base, str) else None
        if header_values.get("! Subscription:") not in (None, expected_subscription):
            errors.append(f"{rel_path}: Subscription does not match stable raw URL")

        version = header_values.get("! Version:")
        if version is not None and not version_re.fullmatch(version):
            errors.append(f"{rel_path}: Version must use YYYYMMDD.N format")

        expires = header_values.get("! Expires:")
        if expires is not None and not expires_re.fullmatch(expires):
            errors.append(f"{rel_path}: Expires must use '<number> day(s)' format")

        rules = active_rules(path)
        seen_rules = set()
        seen_hosts = set()
        for n, raw in enumerate(lines, 1):
            line = raw.strip()
            if not line or line.startswith("!") or line.startswith("["):
                continue

            if line in seen_rules:
                errors.append(f"{rel_path}:{n}: duplicate rule: {line}")
            seen_rules.add(line)

            if dangerous_all.search(line):
                errors.append(f"{rel_path}:{n}: broad $all/$document rule requires manual review: {line}")

            match = hostname_rule.fullmatch(line)
            if not match:
                errors.append(f"{rel_path}:{n}: rule outside conservative policy: {line}")
                continue

            host = match.group(1).lower()
            if not valid_hostname(host):
                errors.append(f"{rel_path}:{n}: invalid hostname: {host}")
                continue
            if host in seen_hosts:
                errors.append(f"{rel_path}:{n}: duplicate hostname: {host}")
            seen_hosts.add(host)

            if host in all_hosts:
                errors.append(f"{rel_path}:{n}: hostname also appears in {all_hosts[host]}: {host}")
            else:
                all_hosts[host] = rel_path

        if not isinstance(expected_count, int) or expected_count < 0:
            errors.append(f"manifest.json: invalid expected_rule_count for {list_id}")
        elif len(rules) != expected_count:
            errors.append(f"{rel_path}: expected {expected_count} active rules, found {len(rules)}")

        if not isinstance(max_count, int) or max_count < 1:
            errors.append(f"manifest.json: invalid max_rule_count for {list_id}")
        elif len(rules) > max_count:
            errors.append(f"{rel_path}: rule count {len(rules)} exceeds safety cap {max_count}")

        if not rules:
            warnings.append(f"{rel_path}: contains no active rules")

    actual_filter_paths = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "filters").glob("*.txt")
        if path.is_file()
    }
    undeclared = sorted(actual_filter_paths - declared_paths)
    missing = sorted(declared_paths - actual_filter_paths)
    for rel_path in undeclared:
        errors.append(f"{rel_path}: stable filter exists but is not declared in manifest.json")
    for rel_path in missing:
        errors.append(f"{rel_path}: manifest entry has no matching stable filter")

    candidate_rel = manifest.get("candidate_queue")
    candidate_path = safe_repo_path(candidate_rel)
    if candidate_path is None or not candidate_path.is_file():
        errors.append("manifest.json: candidate_queue is missing or unsafe")
    else:
        try:
            queue = load_json(candidate_path)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{candidate_rel}: cannot be read: {exc}")
            queue = {}

        if queue.get("schema") != "browser-filter-candidates/v1":
            errors.append(f"{candidate_rel}: unsupported schema")
        candidates = queue.get("candidates")
        if not isinstance(candidates, list):
            errors.append(f"{candidate_rel}: candidates must be an array")
            candidates = []

        seen_candidates = set()
        for index, candidate in enumerate(candidates, 1):
            prefix = f"{candidate_rel}:candidate[{index}]"
            if not isinstance(candidate, dict):
                errors.append(f"{prefix}: must be an object")
                continue

            domain = candidate.get("domain")
            category = candidate.get("category")
            state = candidate.get("state")
            risk = candidate.get("risk")
            proposed_rule = candidate.get("proposed_rule")
            reason = candidate.get("reason")
            sources = candidate.get("sources")

            if not valid_hostname(domain):
                errors.append(f"{prefix}: invalid domain: {domain!r}")
                continue
            domain = domain.lower()
            if domain in seen_candidates:
                errors.append(f"{prefix}: duplicate candidate domain: {domain}")
            seen_candidates.add(domain)
            if domain in all_hosts:
                errors.append(f"{prefix}: candidate already exists in stable list: {domain}")

            if category not in {"ads", "tracking"}:
                errors.append(f"{prefix}: category must be ads or tracking")
            if state not in {"candidate", "hold", "rejected"}:
                errors.append(f"{prefix}: invalid state")
            if risk not in {"low", "medium", "high"}:
                errors.append(f"{prefix}: invalid risk")
            if risk == "high" and state == "candidate":
                errors.append(f"{prefix}: high-risk entries must be hold or rejected")
            if state == "hold" and not candidate.get("promotion_blocker"):
                errors.append(f"{prefix}: hold entry requires promotion_blocker")

            if proposed_rule is not None:
                expected_rule = f"||{domain}^$third-party"
                if proposed_rule != expected_rule:
                    errors.append(f"{prefix}: proposed_rule must exactly match {expected_rule}")

            if not isinstance(reason, str) or not reason.strip():
                errors.append(f"{prefix}: reason is required")
            if not isinstance(sources, list) or not sources:
                errors.append(f"{prefix}: at least one source is required")
            else:
                for source in sources:
                    if not isinstance(source, str) or not source.startswith("https://"):
                        errors.append(f"{prefix}: every source must be HTTPS")

    return errors, warnings


def main():
    errors, warnings = validate()
    if errors:
        print("VALIDATION FAILED")
        for error in errors:
            print("ERROR:", error)
        for warning in warnings:
            print("WARNING:", warning)
        return 1

    manifest = load_json(MANIFEST_PATH)
    print(f"VALIDATION PASSED: {len(manifest['stable_lists'])} stable list(s)")
    for entry in manifest["stable_lists"]:
        path = ROOT / entry["path"]
        print(f"- {entry['path']}: {len(active_rules(path))} active rules")
    queue = load_json(ROOT / manifest["candidate_queue"])
    print(f"- {manifest['candidate_queue']}: {len(queue.get('candidates', []))} inactive candidate(s)")
    for warning in warnings:
        print("WARNING:", warning)
    return 0


if __name__ == "__main__":
    sys.exit(main())
