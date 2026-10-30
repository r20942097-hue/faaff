"""Compare a pinned-source manifest with independently saved GitHub Git API data.

No network calls: pass immutable commit and recursive tree JSON from GitHub API.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

HEX40 = re.compile(r"[0-9a-f]{40}\Z")


def compare(manifest: object, commit: object, tree: object) -> list[str]:
    """Return mismatches; empty list proves parity with supplied Git API records."""
    if not all(isinstance(v, dict) for v in (manifest, commit, tree)):
        return ["inputs must be JSON objects"]
    errors: list[str] = []
    source_sha = manifest.get("source_commit")
    source_tree = manifest.get("source_tree_sha")
    if not isinstance(source_sha, str) or not HEX40.fullmatch(source_sha) or commit.get("sha") != source_sha:
        errors.append("commit SHA does not match manifest")
    commit_tree = commit.get("tree")
    commit_tree_sha = commit_tree.get("sha") if isinstance(commit_tree, dict) else None
    if not isinstance(source_tree, str) or not HEX40.fullmatch(source_tree) or commit_tree_sha != source_tree or tree.get("sha") != source_tree:
        errors.append("commit/tree/manifest tree SHA mismatch")
    if tree.get("truncated") is not False:
        errors.append("recursive Git tree is truncated or has no complete flag")
    files, excluded, entries = manifest.get("files"), manifest.get("excluded_paths"), tree.get("tree")
    if not isinstance(files, list) or not isinstance(excluded, list) or not isinstance(entries, list):
        return errors + ["invalid manifest or upstream tree arrays"]
    if any(not isinstance(s, str) for s in excluded) or len(set(excluded)) != len(excluded):
        return errors + ["invalid excluded path list"]
    excluded_set = set(excluded)
    expected: dict[str, tuple[str, int]] = {}
    upstream_paths: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            errors.append("malformed upstream tree entry")
            continue
        name, kind, sha, size = entry.get("path"), entry.get("type"), entry.get("sha"), entry.get("size")
        if not isinstance(name, str) or name in upstream_paths:
            errors.append(f"invalid or duplicate upstream path: {name!r}")
            continue
        upstream_paths.add(name)
        if kind in ("commit",) and name not in excluded_set:
            errors.append(f"unexcluded git submodule: {name}")
        if kind != "blob" or name in excluded_set:
            continue
        if entry.get("mode") == "120000":
            errors.append(f"unexcluded symbolic link: {name}")
        if not isinstance(sha, str) or not HEX40.fullmatch(sha) or type(size) is not int or size < 0:
            errors.append(f"invalid upstream blob record: {name}")
            continue
        expected[name] = (sha, size)
    missing_exclusions = excluded_set - upstream_paths
    if missing_exclusions:
        errors.append(f"excluded upstream paths missing: {sorted(missing_exclusions)}")
    actual: dict[str, tuple[str, int]] = {}
    for entry in files:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            errors.append("malformed manifest file entry")
            continue
        name = entry["path"]
        if name in actual:
            errors.append(f"duplicate manifest path: {name}")
        actual[name] = (entry.get("git_blob_sha"), entry.get("size"))
    if actual.keys() != expected.keys():
        errors.append(f"file set differs: absent={sorted(expected.keys() - actual.keys())}, extra={sorted(actual.keys() - expected.keys())}")
    changed = sorted(name for name in expected.keys() & actual.keys() if expected[name] != actual[name])
    if changed:
        errors.append(f"Git blob SHA or size mismatch: {changed}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path(__file__).parent / "imports/s.json")
    parser.add_argument("--commit-json", type=Path, required=True)
    parser.add_argument("--tree-json", type=Path, required=True)
    args = parser.parse_args()
    try:
        docs = [json.loads(path.read_text(encoding="utf-8")) for path in (args.manifest, args.commit_json, args.tree_json)]
    except (OSError, UnicodeError, ValueError) as exc:
        print("BLOCKED: cannot read Git evidence:", exc)
        return 2
    issues = compare(*docs)
    for issue in issues:
        print("FAIL:", issue)
    print("UPSTREAM TREE CHECK FAILED" if issues else "UPSTREAM TREE CHECK PASSED: supplied Git commit/tree and manifest are identical")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
