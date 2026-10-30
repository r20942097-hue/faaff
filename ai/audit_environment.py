#!/usr/bin/env python3
"""Read-only runtime readiness audit. CI success is not runtime verification."""
import argparse
import hashlib
import json
import platform
from pathlib import Path

REQUIRED = {
    "watcher": ["rplay_watcher/__init__.py", "pyproject.toml"],
    "extension": ["extension/manifest.json"],
}

def inspect(root):
    root = Path(root).resolve()
    products = {}
    for name, files in REQUIRED.items():
        missing = [path for path in files if not (root / path).is_file()]
        products[name] = {
            "status": "SOURCE_MISSING" if missing else "SOURCE_PRESENT_UNTESTED",
            "missing": missing,
        }
    workflow_dir = root / ".github" / "workflows"
    workflows = sorted(str(p.relative_to(root)) for p in workflow_dir.glob("*.yml"))
    return {
        "schema": "dev-env-audit/v1",
        "environment": {"python": platform.python_version(), "os": platform.system()},
        "workflows": workflows,
        "products": products,
        "browser_e2e": "NOT_RUN",
        "release_readiness": "NO_GO",
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--output")
    args = parser.parse_args()
    payload = json.dumps(inspect(args.root), indent=2, ensure_ascii=False) + "\n"
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")
        print(f"{path}: sha256={hashlib.sha256(path.read_bytes()).hexdigest()}")
    else:
        print(payload, end="")

if __name__ == "__main__":
    main()
