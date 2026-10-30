"""Offline candidate ZIP quality catalog. Does NOT authenticate or approve products.

For each input, combine bounded ZIP CRC/SHA256 and extension manifest inventory.
No file extraction, execution, network access, publishing, or metadata leakage
beyond explicitly named local files. Report paths are filenames, not full paths.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from artifact_gate import inspect as inspect_archive
from extension_inventory import scan as inspect_manifests

MAX_INPUTS = 25


def build_catalog(paths: list[Path]) -> dict:
    if not paths:
        return {"status": "INVALID", "errors": ["no candidate ZIP files supplied"], "items": []}
    if len(paths) > MAX_INPUTS:
        return {"status": "INVALID", "errors": ["too many candidate ZIP files"], "items": []}
    records = []
    errors = []
    seen = set()
    for path in paths:
        path = Path(path)
        canonical = str(path.absolute()).casefold()
        if canonical in seen:
            errors.append("duplicate candidate input")
            continue
        seen.add(canonical)
        if path.suffix.lower() != ".zip":
            errors.append(f"{path.name}: expected .zip input")
            continue
        static = inspect_archive(path)
        if static["status"] == "PASS":
            inventory = inspect_manifests(path)
            manifest_status = inventory["status"]
            manifest_counts = inventory["manifest_count"]
            manifest_rows = [{
                "location": r["location"], "browser_hint": r["browser_hint"],
                "name": r["name"], "version": r["version"],
                "permission_count": r["permission_count"],
                "host_permission_count": r.get("host_permission_count", 0),
            } for r in inventory["manifests"]]
            warnings = inventory.get("warnings", [])
            issues = inventory["issues"]
        else:
            manifest_status = "BLOCKED"
            manifest_counts = 0
            manifest_rows = []
            warnings = []
            issues = ["manifest inventory blocked by ZIP integrity failure"]
        item_status = "PASS" if static["status"] == "PASS" and manifest_status == "PASS" else "FAIL"
        records.append({
            "filename": path.name, "status": item_status,
            "zip_integrity": static["status"], "sha256": static["sha256"],
            "archives_checked": static["summary"]["archives_checked"],
            "entries_checked": static["summary"]["members_checked"],
            "extension_inventory": manifest_status,
            "extension_manifest_count": manifest_counts,
            "extensions": manifest_rows, "warnings": warnings,
            "issues": static["issues"] + issues, "real_browser": "NOT_RUN",
            "source_provenance": "NOT_VERIFIED",
        })
    return {
        "schema": "gpt1-local-candidate-catalog/v1",
        "status": "INVALID" if errors else "FAIL" if any(x["status"] != "PASS" for x in records) else "PASS",
        "scope": "bounded static ZIP + extension manifest metadata only",
        "decision": "CANDIDATE_NO_GO",
        "items": records, "errors": errors,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zip_paths", nargs="+", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = build_catalog(args.zip_paths)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result["status"], len(result["items"]), "candidates; CANDIDATE_NO_GO")
        for row in result["items"]:
            print(f" {row['status']} {row['filename']}: {row['extension_manifest_count']} extension manifests")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
