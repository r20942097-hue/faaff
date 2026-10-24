"""Validate the AI hub registry and Git blob integrity of the pinned source import."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
SHA = re.compile(r"[0-9a-f]{40}")
STATES = {"bootstrap_only", "main_present", "pinned_snapshot", "open_draft"}


def safe_path(value: object) -> bool:
    return (
        isinstance(value, str) and bool(value) and chr(92) not in value
        and not value.startswith("/")
        and all(part not in ("", ".", "..") for part in value.split("/"))
    )


def blob_sha(content: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(content)).encode("ascii") + bytes((0,)) + content).hexdigest()


def verify(root: Path = ROOT) -> list[str]:
    errors = []
    try:
        projects = json.loads((root / "ai/projects.json").read_text(encoding="utf-8"))
        source = json.loads((root / "ai/imports/s.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"unreadable metadata: {exc}"]

    if projects.get("schema") != "ai-hub-registry/v1" or projects.get("hub") != "r20942097-hue/faaff":
        errors.append("bad project registry schema/hub")
    repos = projects.get("repositories", [])
    if not isinstance(repos, list) or len(repos) != 2 or {r.get("id") for r in repos if isinstance(r, dict)} != {"faaff", "s"}:
        errors.append("expected unique faaff and s repositories")
    else:
        for repo in repos:
            if not isinstance(repo.get("observed_head"), str) or not SHA.fullmatch(repo["observed_head"]):
                errors.append(f"invalid observed head: {repo.get('id')}")
    workstreams = projects.get("workstreams", [])
    if not isinstance(workstreams, list) or any(not isinstance(w, dict) or not w.get("id") or w.get("state") not in STATES for w in workstreams):
        errors.append("bad workstream state")
    elif len({w["id"] for w in workstreams}) != len(workstreams):
        errors.append("duplicate workstream ID")
    if source.get("schema") != "pinned-source-import/v1" or source.get("source_repository") != "r20942097-hue/s":
        errors.append("bad import provenance")
    observed_s = next((r.get("observed_head") for r in repos if isinstance(r, dict) and r.get("id") == "s"), None)
    if source.get("source_commit") != observed_s:
        errors.append("source commit / observed head mismatch")

    prefix = source.get("target_prefix", "")
    if not safe_path(prefix.rstrip("/")) or prefix != "integrations/browser-filters/source/s/":
        return errors + ["unsafe or unexpected import prefix"]
    files = source.get("files", [])
    if not isinstance(files, list) or not files:
        return errors + ["empty import manifest"]
    seen = set()
    imported = root / prefix
    for entry in files:
        if not isinstance(entry, dict):
            errors.append("invalid file entry")
            continue
        name, sha, size = entry.get("path"), entry.get("git_blob_sha"), entry.get("size")
        if not safe_path(name) or name in seen or not isinstance(sha, str) or not SHA.fullmatch(sha) or type(size) is not int or size < 0:
            errors.append(f"invalid or duplicate file entry: {name!r}")
            continue
        seen.add(name)
        target = imported / name
        if target.is_symlink() or not target.is_file():
            errors.append(f"missing or linked source: {name}")
            continue
        content = target.read_bytes()
        if len(content) != size or blob_sha(content) != sha:
            errors.append(f"source blob mismatch: {name}")
    actual = {p.relative_to(imported).as_posix() for p in imported.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
    if actual != seen:
        errors.append(f"import file set drift: missing={sorted(seen - actual)}, extra={sorted(actual - seen)}")
    return errors


if __name__ == "__main__":
    problems = verify()
    for problem in problems:
        print("ERROR:", problem)
    print("AI HUB CHECK FAILED" if problems else "AI HUB CHECK PASSED: registry and pinned source blob integrity")
    sys.exit(bool(problems))
