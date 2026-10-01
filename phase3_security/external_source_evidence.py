#!/usr/bin/env python3
"""Validate external Library evidence without promoting it to runner evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

BASELINE = {
    "universal-control-suite": ("Universal Control Suite", "0.30"),
    "universal-live-watcher": ("Universal Live Watcher", "6.49.12"),
    "windows-control": ("Windows Control", "0.1.8"),
    "ai-orchestrator": ("AI Orchestrator", "1.51"),
    "shared-foundation": ("Shared Foundation", "0.10"),
    "browser-control": ("Browser Control", "0.3.0"),
    "media-download-tools": ("Media / Download Tools", "0.1.0"),
}
SHA256_RE = re.compile(r"[0-9a-f]{64}")


def validate_external_evidence(doc: dict) -> dict:
    if not isinstance(doc, dict) or doc.get("schema_version") != 1:
        raise ValueError("unsupported external-evidence schema")
    if doc.get("baseline_product_count") != len(BASELINE):
        raise ValueError("baseline_product_count does not match the seven-product baseline")
    if doc.get("github_scan_ready") is not False:
        raise ValueError("external Library evidence cannot establish GitHub scan readiness")
    if doc.get("vulnerability_posture") != "UNKNOWN":
        raise ValueError("external evidence cannot establish vulnerability clearance")
    interpretation = doc.get("security_interpretation")
    if not isinstance(interpretation, dict) or interpretation.get("complete_dependency_bearing_source_scan") != "NOT_RUN":
        raise ValueError("complete dependency-bearing source scan must remain NOT_RUN")

    products = doc.get("products")
    if not isinstance(products, list):
        raise ValueError("products must be an array")
    seen: set[str] = set()
    verified = 0
    for index, item in enumerate(products):
        if not isinstance(item, dict):
            raise ValueError(f"products[{index}] must be an object")
        product_id = item.get("product_id")
        if not isinstance(product_id, str) or product_id not in BASELINE or product_id in seen:
            raise ValueError(f"unknown or duplicate product_id: {product_id!r}")
        seen.add(product_id)
        name, version = BASELINE[product_id]
        if item.get("product_name") != name or item.get("version") != version:
            raise ValueError(f"baseline identity mismatch for {product_id}")
        expected = item.get("expected_sha256")
        if not isinstance(expected, str) or not SHA256_RE.fullmatch(expected):
            raise ValueError(f"invalid expected_sha256 for {product_id}")
        size = item.get("expected_size", item.get("size"))
        if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
            raise ValueError(f"invalid expected size for {product_id}")

        current_status = item.get("current_retrieval_status")
        # Earlier Phase 3 evidence used the matched digest and CRC fields instead
        # of an explicit status field; accept that exact, verifiable shape.
        is_verified = current_status == "VERIFIED_EXTERNAL" or (
            current_status is None
            and item.get("sha256_match") is True
            and item.get("actual_sha256") == expected
            and item.get("zip_crc") == "PASS"
        )
        if is_verified:
            if item.get("actual_sha256") != expected or item.get("sha256_match") is not True:
                raise ValueError(f"verified external SHA-256 mismatch for {product_id}")
            actual_size = item.get("size", item.get("expected_size"))
            if actual_size != size:
                raise ValueError(f"verified external size mismatch for {product_id}")
            if item.get("zip_crc") != "PASS":
                raise ValueError(f"verified external ZIP CRC missing for {product_id}")
            manifest_count = item.get("dependency_manifest_count")
            declaration_count = item.get("dependency_declaration_count")
            manifests = item.get("manifests")
            if not isinstance(manifest_count, int) or isinstance(manifest_count, bool) or manifest_count < 0 or not isinstance(manifests, list):
                raise ValueError(f"invalid manifest inventory for {product_id}")
            if manifest_count != len(manifests):
                raise ValueError(f"manifest count mismatch for {product_id}")
            if not isinstance(declaration_count, int) or isinstance(declaration_count, bool) or declaration_count < 0:
                raise ValueError(f"invalid declaration count for {product_id}")
            declarations = 0
            for manifest in manifests:
                if not isinstance(manifest, dict) or not isinstance(manifest.get("declarations"), list):
                    raise ValueError(f"invalid manifest record for {product_id}")
                if any(not isinstance(d, dict) or not isinstance(d.get("group"), str) or not isinstance(d.get("raw"), str) for d in manifest["declarations"]):
                    raise ValueError(f"invalid dependency declaration for {product_id}")
                declarations += len(manifest["declarations"])
            if declarations != declaration_count:
                raise ValueError(f"declaration count mismatch for {product_id}")
            verified += 1
        elif current_status not in {"NOT_RUN", "UNAVAILABLE"}:
            raise ValueError(f"unsupported current retrieval status for {product_id}")

    if seen != set(BASELINE):
        raise ValueError("external evidence must contain exactly the seven baseline products")
    if doc.get("current_retrievable_verified") != verified:
        raise ValueError("current_retrievable_verified does not match verified product evidence")
    return {
        "schema_version": 1,
        "baseline_product_count": len(BASELINE),
        "current_retrievable_verified": verified,
        "github_scan_ready": False,
        "complete_dependency_bearing_source_scan": "NOT_RUN",
        "vulnerability_posture": "UNKNOWN",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = validate_external_evidence(json.loads(args.evidence.read_text(encoding="utf-8")))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        print(f"PASS: external evidence valid; verified={report['current_retrievable_verified']}/7; GitHub scan readiness=false; vulnerability_posture=UNKNOWN")
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
