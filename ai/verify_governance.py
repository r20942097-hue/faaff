#!/usr/bin/env python3
"""Fail-closed governance metadata check for faaff. Read-only; stdlib only.

Checks consistent source-of-truth references and owner gate structure; it does
NOT determine whether a historical observed HEAD is the current remote HEAD.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
CANONICAL = (
    "AGENTS.md", "ai/README.md", "ai/PROJECT_STATE.json",
    "ai/HANDOFF.md", "ai/projects.json", "ai/imports/s.json",
    "ai/check_hub.py",
)


def _load_object(root: Path, relative: str, problems: list[str]) -> dict:
    try:
        value = json.loads((root / relative).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        problems.append(f"missing/invalid JSON: {relative}")
        return {}
    if not isinstance(value, dict):
        problems.append(f"JSON must contain an object: {relative}")
        return {}
    return value


def verify(root: Path = ROOT) -> list[str]:
    """Return blocking problems; no writes, network, or Git commands."""
    root = Path(root).resolve()
    problems: list[str] = []
    for path in CANONICAL:
        target = root / path
        if target.is_symlink() or not target.is_file():
            problems.append(f"canonical file missing or symlinked: {path}")
    state = _load_object(root, "ai/PROJECT_STATE.json", problems)
    projects = _load_object(root, "ai/projects.json", problems)
    imported = _load_object(root, "ai/imports/s.json", problems)

    if state.get("schema") != "project-state/v1":
        problems.append("unexpected PROJECT_STATE schema")
    if state.get("repository") != "r20942097-hue/faaff":
        problems.append("unexpected PROJECT_STATE repository")
    if state.get("default_branch") != "main":
        problems.append("unexpected PROJECT_STATE default_branch")

    gates = state.get("gates")
    if not isinstance(gates, dict) or any(
        not isinstance(gates.get(k), str) or not gates[k].strip()
        for k in ("P0", "PUBLICATION_HOLD", "NO_NEW_INTERNAL_PUSH")
    ):
        problems.append("required publication gates absent from PROJECT_STATE")
    permissions = state.get("permissions")
    if not isinstance(permissions, dict):
        problems.append("permissions must be an object")
    else:
        for group in ("always_allowed", "requires_owner_approval"):
            values = permissions.get(group)
            if (not isinstance(values, list) or not values or
                any(not isinstance(v, str) or not v.strip() for v in values) or
                len(set(values)) != len(values)):
                problems.append(f"permissions.{group} must be nonempty unique strings")

    pin = state.get("pinned_import")
    pin_sha = pin.get("source_commit") if isinstance(pin, dict) else None
    source_sha = imported.get("source_commit")
    repositories = projects.get("repositories")
    observed = None
    if not isinstance(repositories, list):
        problems.append("projects.repositories must be a list")
    else:
        matching = [r for r in repositories if isinstance(r, dict) and r.get("id") == "s"]
        if len(matching) != 1:
            problems.append("projects must contain exactly one s repository")
        else:
            observed = matching[0].get("observed_head")
    if (not isinstance(pin_sha, str) or not COMMIT.fullmatch(pin_sha)
        or pin_sha != source_sha or pin_sha != observed):
        problems.append("s pinned source commit differs between state / manifest / registry")

    # Historical faaff observed_head is deliberately not compared with Git HEAD.
    # A pinned import is intentionally separate from the live s/main branch.
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=ROOT)
    args = parser.parse_args()
    problems = verify(args.repo)
    for issue in problems:
        print("ERROR:", issue)
    print("GOVERNANCE CHECK FAILED" if problems else "GOVERNANCE CHECK PASSED")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
