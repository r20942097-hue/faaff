#!/usr/bin/env python3
"""Read-only source readiness audit. Toolchain success is not product E2E."""
import argparse
import hashlib
import json
import platform
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "dev-env-audit/v2"
REQUIRED = {
    "watcher": ("pyproject.toml", "rplay_watcher/__init__.py", "rplay_watcher/__main__.py"),
    "extension": ("extension/manifest.json", "extension/bridge.js", "extension/content.js",
                  "extension/popup.js", "extension/options.js"),
}
CHECKS = ("unit_tests", "chromium_toolchain_smoke", "firefox_toolchain_smoke",
          "chromium_extension_e2e", "firefox_extension_e2e", "windows_real_browser",
          "media_integrity", "site_integration")

def source_item(root: Path, relative: str) -> dict:
    path = root / relative
    try:
        if not path.resolve().is_relative_to(root) or not path.is_file():
            return {"path": relative, "present": False}
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for data in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(data)
        return {"path": relative, "present": True, "size": path.stat().st_size,
                "sha256": digest.hexdigest()}
    except (OSError, ValueError):
        return {"path": relative, "present": False}

def inspect(root) -> dict:
    root = Path(root).resolve()
    products = {}
    for product, paths in REQUIRED.items():
        sources = [source_item(root, path) for path in paths]
        missing = [item["path"] for item in sources if not item["present"]]
        products[product] = {"status": "SOURCE_MISSING" if missing else "SOURCE_PRESENT_UNTESTED",
                             "missing": missing, "sources": sources}
    workflow_dir = root / ".github" / "workflows"
    workflows = sorted(str(p.relative_to(root)).replace("\\", "/")
                       for p in workflow_dir.glob("*.yml") if p.is_file()) if workflow_dir.is_dir() else []
    return {"schema": SCHEMA, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "environment": {"python": platform.python_version(), "os": platform.system(),
                            "tool_available": {name: bool(shutil.which(name)) for name in
                                               ("git", "node", "npm", "ffmpeg", "firefox",
                                                "chromium", "google-chrome")}},
            "workflows": workflows, "products": products,
            "checks": {name: "NOT_RUN" for name in CHECKS},
            "release_readiness": "NO_GO",
            "warning": "Source presence and infrastructure CI do not prove runtime acceptance."}

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--output")
    parser.add_argument("--require-source", choices=tuple(REQUIRED), action="append", default=[])
    args = parser.parse_args(argv)
    report = inspect(args.root)
    payload = (json.dumps(report, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    if args.output:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        print(f"report_sha256={hashlib.sha256(payload).hexdigest()} path={target}")
    else:
        sys.stdout.write(payload.decode("utf-8"))
    missing = [p for p in args.require_source if report["products"][p]["status"] == "SOURCE_MISSING"]
    if missing:
        print("Missing required source groups: " + ", ".join(sorted(missing)), file=sys.stderr)
        return 2
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
