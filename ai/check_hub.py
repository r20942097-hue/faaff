"""Validate the AI hub registry and Git blob integrity of the pinned source import.

This is an offline integrity check, not an upstream Git-tree or runtime E2E check.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
SHA = re.compile(r"[0-9a-f]{40}\Z")
STATES = {"bootstrap_only", "main_present", "pinned_snapshot", "open_draft"}
_WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def safe_path(value: object) -> bool:
    """Accept portable, repo-relative file paths; reject traversal and ambiguity."""
    if not isinstance(value, str) or not value or "\\" in value or value.startswith("/"):
        return False
    for part in value.split("/"):
        if (part in ("", ".", "..") or part.endswith((".", " "))
            or any(ord(c) < 32 or c in '<>:"|?*' for c in part)
            or part.split(".", 1)[0].upper() in _WINDOWS_RESERVED):
            return False
    return True


def blob_sha(content: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(content)).encode("ascii") + bytes((0,)) + content).hexdigest()


def _safe_descendant(root: Path, target: Path) -> bool:
    """Disallow symlinks in any path component, including the imported root."""
    try:
        relative = target.relative_to(root)
    except ValueError:
        return False
    cursor = root
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            return False
    return True


def verify(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    root = Path(root).resolve()
    try:
        projects = json.loads((root / "ai/projects.json").read_text(encoding="utf-8"))
        source = json.loads((root / "ai/imports/s.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        return [f"unreadable metadata: {exc}"]
    if not isinstance(projects, dict) or not isinstance(source, dict):
        return ["metadata root must be a JSON object"]

    if projects.get("schema") != "ai-hub-registry/v1" or projects.get("hub") != "r20942097-hue/faaff":
        errors.append("bad project registry schema/hub")
    repos = projects.get("repositories")
    valid_repos = (isinstance(repos, list) and len(repos) == 2
                   and all(isinstance(r, dict) for r in repos)
                   and {r.get("id") for r in repos} == {"faaff", "s"})
    if not valid_repos:
        errors.append("expected unique faaff and s repositories")
    else:
        for repo in repos:
            if not isinstance(repo.get("observed_head"), str) or not SHA.fullmatch(repo["observed_head"]):
                errors.append(f"invalid observed head: {repo.get('id')}")
    workstreams = projects.get("workstreams")
    if (not isinstance(workstreams, list) or
        any(not isinstance(w, dict) or not isinstance(w.get("id"), str)
            or not w["id"] or w.get("state") not in STATES for w in workstreams)):
        errors.append("bad workstream state")
    elif len({w["id"] for w in workstreams}) != len(workstreams):
        errors.append("duplicate workstream ID")

    if source.get("schema") != "pinned-source-import/v1" or source.get("source_repository") != "r20942097-hue/s":
        errors.append("bad import provenance")
    for name in ("source_commit", "source_tree_sha"):
        value = source.get(name)
        if not isinstance(value, str) or not SHA.fullmatch(value):
            errors.append(f"invalid {name}")
    observed_s = next((r.get("observed_head") for r in repos
                       if isinstance(r, dict) and r.get("id") == "s"), None) if isinstance(repos, list) else None
    if source.get("source_commit") != observed_s:
        errors.append("source commit / observed head mismatch")

    prefix = source.get("target_prefix")
    if prefix != "integrations/browser-filters/source/s/" or not safe_path(prefix.rstrip("/") if isinstance(prefix, str) else None):
        return errors + ["unsafe or unexpected import prefix"]
    imported = root / prefix
    if not _safe_descendant(root, imported) or not imported.is_dir():
        return errors + ["missing, linked or unsafe import directory"]

    excluded = source.get("excluded_paths")
    if (not isinstance(excluded, list) or any(not safe_path(p) for p in excluded)
        or len(excluded) != len(set(excluded))):
        errors.append("invalid excluded paths")
        excluded = []
    files = source.get("files")
    if not isinstance(files, list) or not files:
        return errors + ["empty import manifest"]

    seen: set[str] = set()
    portable_seen: set[str] = set()
    for entry in files:
        if not isinstance(entry, dict):
            errors.append("invalid file entry")
            continue
        name, sha, size = entry.get("path"), entry.get("git_blob_sha"), entry.get("size")
        if (not safe_path(name) or name in seen or not isinstance(sha, str)
            or not SHA.fullmatch(sha) or type(size) is not int or size < 0):
            errors.append(f"invalid or duplicate file entry: {name!r}")
            continue
        seen.add(name)
        folded = name.casefold()
        if folded in portable_seen:
            errors.append(f"case-insensitive path collision: {name}")
        portable_seen.add(folded)
        if name in excluded:
            errors.append(f"imported path also excluded: {name}")
        target = imported / name
        if not _safe_descendant(root, target) or not target.is_file():
            errors.append(f"missing, linked or unsafe source: {name}")
            continue
        try:
            content = target.read_bytes()
        except OSError as exc:
            errors.append(f"unreadable source: {name}: {exc}")
            continue
        if len(content) != size or blob_sha(content) != sha:
            errors.append(f"source blob mismatch: {name}")

    try:
        # Include linked directories as errors even if rglob does not follow them.
        paths = list(imported.rglob("*"))
        if any(p.is_symlink() for p in paths):
            errors.append("linked entry in import tree")
        actual = {p.relative_to(imported).as_posix() for p in paths
                  if p.is_file() and "__pycache__" not in p.parts}
    except OSError as exc:
        return errors + [f"unable to scan import tree: {exc}"]
    if actual != seen:
        errors.append(f"import file set drift: missing={sorted(seen - actual)}, extra={sorted(actual - seen)}")
    return errors


if __name__ == "__main__":
    problems = verify()
    for problem in problems:
        print("ERROR:", problem)
    print("AI HUB CHECK FAILED" if problems else "AI HUB CHECK PASSED: registry and pinned source blob integrity")
    sys.exit(bool(problems))
