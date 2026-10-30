"""Read-only GitHub PR risk/evidence audit; no CI secret or merge permission needed.

Usage:
  python -m ai.inspect_pr r20942097-hue/faaff 44 --ruleset-id 26005483

The ruleset ID must be confirmed against the currently applicable branch
rulesets. A single ruleset is not proof that no other protections apply.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from ai.github_evidence import review_evidence

REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
API = "https://api.github.com"


class CollectionError(Exception):
    pass


def get_json(path: str) -> object:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "read-only-ai-pr-evidence",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    request = Request(API + path, headers=headers)
    try:
        with urlopen(request, timeout=20) as response:
            data = response.read(4_000_001)
    except HTTPError as exc:
        raise CollectionError("GitHub API returned HTTP " + str(exc.code)) from None
    except (URLError, TimeoutError) as exc:
        raise CollectionError("GitHub API request failed (" + type(exc).__name__ + ")") from None
    if len(data) > 4_000_000:
        raise CollectionError("GitHub API response too large")
    try:
        return json.loads(data)
    except (ValueError, UnicodeDecodeError):
        raise CollectionError("GitHub API returned invalid JSON") from None


def collect_pages(path: str, *, key: str, max_pages: int = 20) -> tuple[list, int | None]:
    result = []
    expected = None
    for page in range(1, max_pages + 1):
        separator = "&" if "?" in path else "?"
        payload = get_json(f"{path}{separator}per_page=100&page={page}")
        if isinstance(payload, list):
            records = payload
        elif isinstance(payload, dict):
            records = payload.get(key)
            count = payload.get("total_count")
            if type(count) is not int or count < 0:
                raise CollectionError("invalid collection total_count")
            if expected is None:
                expected = count
            elif expected != count:
                raise CollectionError("collection changed during pagination")
        else:
            raise CollectionError("invalid collection response")
        if not isinstance(records, list):
            raise CollectionError("missing collection records")
        result.extend(records)
        if expected is not None:
            if len(result) >= expected:
                if len(result) != expected:
                    raise CollectionError("collection count mismatch")
                return result, expected
        elif len(records) < 100:
            return result, None
        if not records:
            raise CollectionError("incomplete collection")
    raise CollectionError("pagination limit reached; refusing partial evidence")


def inspect(repository: str, pr_number: int, ruleset_id: int) -> dict:
    if not REPO.fullmatch(repository) or pr_number < 1 or ruleset_id < 1:
        raise CollectionError("invalid repository, PR number or ruleset ID")
    owner, name = repository.split("/")
    prefix = f"/repos/{quote(owner)}/{quote(name)}"
    pull_path = f"{prefix}/pulls/{pr_number}"
    before = get_json(pull_path)
    if not isinstance(before, dict):
        raise CollectionError("invalid pull request payload")
    head = before.get("head")
    if not isinstance(head, dict) or not isinstance(head.get("sha"), str) or not re.fullmatch(r"[0-9a-f]{40}", head["sha"]):
        raise CollectionError("missing PR head SHA")
    changed, _ = collect_pages(pull_path + "/files", key="files")
    changed_count = before.get("changed_files")
    if type(changed_count) is not int or changed_count != len(changed):
        raise CollectionError("PR changed-file count mismatch")
    paths = []
    for record in changed:
        if not isinstance(record, dict) or not isinstance(record.get("filename"), str):
            raise CollectionError("invalid changed-file record")
        paths.append(record["filename"])
        if record.get("status") == "renamed":
            previous = record.get("previous_filename")
            if not isinstance(previous, str) or not previous:
                raise CollectionError("renamed file missing previous filename")
            paths.append(previous)
    ruleset = get_json(f"{prefix}/rulesets/{ruleset_id}")
    checks, total = collect_pages(
        f"{prefix}/commits/{head['sha']}/check-runs",
        key="check_runs",
    )
    after = get_json(pull_path)
    if (not isinstance(after, dict) or
            not isinstance(after.get("head"), dict) or
            not isinstance(after.get("base"), dict) or
            after["head"].get("sha") != head["sha"] or
            after["base"].get("sha") != before.get("base", {}).get("sha")):
        raise CollectionError("PR HEAD/base changed during audit")
    if not isinstance(ruleset, dict):
        raise CollectionError("invalid ruleset response")
    if ruleset.get("id") != ruleset_id:
        raise CollectionError("ruleset ID mismatch")
    return review_evidence(
        repository=repository,
        pull=after,
        paths=paths,
        ruleset=ruleset,
        check_runs={"total_count": total, "check_runs": checks},
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", help="owner/name")
    parser.add_argument("pull_request", type=int)
    parser.add_argument("--ruleset-id", type=int, required=True)
    args = parser.parse_args()
    try:
        result = inspect(args.repository, args.pull_request, args.ruleset_id)
    except CollectionError as exc:
        result = {"status": "BLOCKED", "reasons": [str(exc)]}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if result["status"] == "AWAITING_OWNER_APPROVAL" else 1


if __name__ == "__main__":
    sys.exit(main())
