"""Audit faaff's pinned s-source provenance against an observed s/main commit.

Read-only and offline. The observed upstream HEAD must be supplied by the caller;
no remote is contacted by this script. This checks metadata, NOT source blobs.
For byte-level import integrity run the existing ai/check_hub.py as well.
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

SHA = re.compile(r"[0-9a-f]{40}\Z")
ROOT = Path(__file__).resolve().parents[1]


def valid_sha(value: object) -> bool:
    return isinstance(value, str) and SHA.fullmatch(value) is not None


def check(root: Path, upstream_head: str) -> dict:
    errors: list[str] = []
    root = Path(root)
    if not valid_sha(upstream_head):
        return {"status": "INVALID", "errors": ["invalid upstream SHA"], "pinned_commit": None,
                "upstream_commit": upstream_head, "scope": "metadata-only"}
    files = (("manifest", "ai/imports/s.json"), ("registry", "ai/projects.json"),
             ("state", "ai/PROJECT_STATE.json"))
    data = {}
    for name, rel in files:
        path = root / rel
        try:
            if path.is_symlink() or not path.is_file():
                raise ValueError("missing or linked file")
            value = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise ValueError("JSON object required")
            data[name] = value
        except (ValueError, OSError, UnicodeError) as exc:
            errors.append(f"{rel}: {type(exc).__name__}")
    if errors:
        return {"status": "INVALID", "errors": errors, "pinned_commit": None,
                "upstream_commit": upstream_head, "scope": "metadata-only"}
    manifest, registry, state = data["manifest"], data["registry"], data["state"]
    pinned = manifest.get("source_commit")
    if manifest.get("schema") != "pinned-source-import/v1" or manifest.get("source_repository") != "r20942097-hue/s":
        errors.append("invalid source manifest identity")
    if not valid_sha(pinned) or not valid_sha(manifest.get("source_tree_sha")):
        errors.append("invalid pinned source SHA/tree")
    if manifest.get("target_prefix") != "integrations/browser-filters/source/s/":
        errors.append("unexpected source import path")
    repos = registry.get("repositories")
    if registry.get("schema") != "ai-hub-registry/v1" or not isinstance(repos, list):
        errors.append("invalid AI registry")
        repo_entry = None
    else:
        entries = [r for r in repos if isinstance(r, dict) and r.get("id") == "s"]
        repo_entry = entries[0] if len(entries) == 1 else None
        if repo_entry is None:
            errors.append("missing/duplicate s registry entry")
    if repo_entry is not None and (repo_entry.get("observed_head") != pinned or repo_entry.get("url") != "https://github.com/r20942097-hue/s"):
        errors.append("registry pinned s source mismatch")
    if state.get("schema") != "project-state/v1" or state.get("repository") != "r20942097-hue/faaff":
        errors.append("invalid faaff project state")
    if not isinstance(state.get("pinned_import"), dict) or state["pinned_import"].get("source_commit") != pinned:
        errors.append("project state pinned source mismatch")
    if not isinstance(state.get("heads"), dict) or state["heads"].get("s_main_pinned_import") != pinned:
        errors.append("project state head mismatch")
    status = "INVALID" if errors else "IN_SYNC" if upstream_head == pinned else "UPSTREAM_DRIFT"
    return {"status": status, "errors": errors, "pinned_commit": pinned,
            "upstream_commit": upstream_head, "scope": "metadata-only",
            "next_action": "no re-import required" if status == "IN_SYNC" else
              "review new s commit and prepare separate provenance-verified faaff import PR" if status == "UPSTREAM_DRIFT" else
              "repair invalid metadata before accepting provenance"}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--upstream-head", required=True, help="observed 40-char s/main HEAD SHA")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = check(args.root, args.upstream_head)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"{result['status']}: pinned={result['pinned_commit']} upstream={result['upstream_commit']}")
        for error in result["errors"]:
            print(f"ERROR: {error}")
    return {"IN_SYNC": 0, "INVALID": 1, "UPSTREAM_DRIFT": 2}[result["status"]]


if __name__ == "__main__":
    sys.exit(main())
