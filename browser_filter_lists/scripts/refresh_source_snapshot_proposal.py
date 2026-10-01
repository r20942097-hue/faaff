"""Create a read-only proposal for refreshing pinned upstream source metadata."""

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
import argparse
import hashlib
import json
import os
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INVENTORY = ROOT / "upstream" / "current-source-snapshot-inventory.json"
API_BASE = "https://api.github.com"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class GitHubApiError(RuntimeError):
    pass


def github_json(url, token=None, opener=urlopen):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "browser-filter-source-snapshot-proposer/1",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers)
    try:
        with opener(request, timeout=30) as response:
            payload = response.read()
    except (HTTPError, URLError, TimeoutError) as exc:
        raise GitHubApiError(f"GitHub API request failed: {url}: {exc}") from exc
    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GitHubApiError(f"GitHub API returned invalid JSON: {url}") from exc


def latest_commit(repository, token=None, fetch_json=github_json):
    url = f"{API_BASE}/repos/{repository}/commits?{urlencode({'per_page': 1})}"
    response = fetch_json(url, token=token)
    if not isinstance(response, list) or not response or not isinstance(response[0], dict):
        raise GitHubApiError(f"No latest commit returned for {repository}")
    item = response[0]
    sha = item.get("sha")
    commit = item.get("commit")
    committer = commit.get("committer") if isinstance(commit, dict) else None
    date = committer.get("date") if isinstance(committer, dict) else None
    if not isinstance(sha, str) or not SHA_RE.fullmatch(sha):
        raise GitHubApiError(f"Invalid latest commit SHA for {repository}")
    if not valid_utc_timestamp(date):
        raise GitHubApiError(f"Invalid latest commit timestamp for {repository}")
    return sha, date


def valid_utc_timestamp(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return False
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ") == value


def fetch_blob_metadata(repository, commit, path, token=None, fetch_json=github_json):
    encoded_path = "/".join(quote(part, safe="") for part in path.split("/"))
    query = urlencode({"ref": commit})
    url = f"{API_BASE}/repos/{repository}/contents/{encoded_path}?{query}"
    item = fetch_json(url, token=token)
    if not isinstance(item, dict) or item.get("type") != "file":
        raise GitHubApiError(f"Expected a file at {repository}:{path}@{commit}")
    blob_sha = item.get("sha")
    size = item.get("size")
    if not isinstance(blob_sha, str) or not SHA_RE.fullmatch(blob_sha):
        raise GitHubApiError(f"Invalid blob SHA for {repository}:{path}@{commit}")
    if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
        raise GitHubApiError(f"Invalid file size for {repository}:{path}@{commit}")
    return {"path": path, "blob_sha": blob_sha, "size_bytes": size}


def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_proposal(inventory, generated_at=None, token=None, fetch_json=github_json):
    if not isinstance(inventory, dict) or inventory.get("schema") != "browser-filter-snapshot-inventory/v1":
        raise ValueError("Unsupported or invalid source inventory")
    snapshots = inventory.get("snapshots")
    if not isinstance(snapshots, list):
        raise ValueError("Source inventory snapshots must be an array")

    generated_at = generated_at or utc_now()
    if not valid_utc_timestamp(generated_at):
        raise ValueError("generated_at must use YYYY-MM-DDTHH:MM:SSZ")
    proposed = deepcopy(inventory)
    proposed["retrieved_at"] = generated_at[:10]
    commits = {}

    for snapshot in proposed["snapshots"]:
        if not isinstance(snapshot, dict):
            raise ValueError("Every source snapshot must be an object")
        status = snapshot.get("status")
        if status == "verified":
            repository = snapshot.get("repository")
            paths = snapshot.get("files")
            if not isinstance(repository, str) or not isinstance(paths, list) or not paths:
                raise ValueError("Verified snapshots require a repository and files")
            if repository not in commits:
                commits[repository] = latest_commit(repository, token=token, fetch_json=fetch_json)
            commit, commit_date = commits[repository]
            files = []
            for old_file in paths:
                if not isinstance(old_file, dict) or not isinstance(old_file.get("path"), str):
                    raise ValueError(f"Invalid file entry in {repository}")
                files.append(fetch_blob_metadata(repository, commit, old_file["path"], token=token, fetch_json=fetch_json))
            snapshot["commit"] = commit
            snapshot["commit_date"] = commit_date
            snapshot["files"] = files
        elif status == "mirror_only" and snapshot.get("source_family") == "peter_lowe":
            mirror = snapshot.get("mirror")
            if not isinstance(mirror, dict):
                raise ValueError("Peter Lowe mirror metadata is required")
            repository = mirror.get("repository")
            path = mirror.get("path")
            if not isinstance(repository, str) or not isinstance(path, str):
                raise ValueError("Peter Lowe mirror repository and path are required")
            if repository not in commits:
                commits[repository] = latest_commit(repository, token=token, fetch_json=fetch_json)
            commit, commit_date = commits[repository]
            blob = fetch_blob_metadata(repository, commit, path, token=token, fetch_json=fetch_json)
            mirror.update({"commit": commit, "commit_date": commit_date, "blob_sha": blob["blob_sha"], "size_bytes": blob["size_bytes"]})
        elif status == "stale_excluded":
            continue
        else:
            raise ValueError(f"Unsupported source status/family: {status!r}/{snapshot.get('source_family')!r}")

    canonical = json.dumps(inventory, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "schema": "browser-filter-snapshot-proposal/v1",
        "generated_at": generated_at,
        "base_inventory_sha256": hashlib.sha256(canonical).hexdigest(),
        "manual_review_required": True,
        "active_rules_changed": False,
        "inventory_proposal": proposed,
        "review_notes": [
            "Re-audit overlap and candidate evidence against the proposed commits before replacing the current inventory.",
            "Stale-excluded sources remain excluded; research findings are not promoted automatically.",
            "This proposal does not add or remove stable or canary rules.",
        ],
    }


def write_atomic(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--output", type=Path, help="write proposal JSON to this path; never replace the source inventory")
    args = parser.parse_args(argv)

    if args.output and args.output.resolve() == args.inventory.resolve():
        parser.error("--output must not overwrite the source inventory")
    try:
        inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        proposal = build_proposal(inventory, token=token)
        rendered = json.dumps(proposal, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            write_atomic(args.output, rendered)
            print(f"Wrote review proposal to {args.output}")
        else:
            sys.stdout.write(rendered)
    except (OSError, json.JSONDecodeError, GitHubApiError, ValueError) as exc:
        print(f"snapshot proposal failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
