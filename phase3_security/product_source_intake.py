#!/usr/bin/env python3
"""Validate Phase 3 immutable product-source intake without inventing missing evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import re
import sys

ALLOWED_STATUS = {"MISSING", "UNVERIFIED", "VERIFIED"}
SHA256_RE = re.compile(r"[0-9a-f]{64}")
PRODUCT_ID_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def validate_source_ref(value: str) -> None:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or "\\" in value or "\x00" in value:
        raise ValueError(f"unsafe immutable source reference: {value!r}")


def validate_registry(doc: dict) -> dict:
    if not isinstance(doc, dict) or doc.get("schema_version") != 1:
        raise ValueError("unsupported source-intake schema")
    baseline = doc.get("baseline")
    if not isinstance(baseline, list) or not baseline:
        raise ValueError("baseline must be a non-empty array")

    seen_ids: set[str] = set()
    verified = 0
    missing = 0
    unverified = 0
    normalized: list[dict] = []

    for index, item in enumerate(baseline):
        if not isinstance(item, dict):
            raise ValueError(f"baseline[{index}] must be an object")
        product_id = item.get("product_id")
        product_name = item.get("product_name")
        version = item.get("version")
        status = item.get("source_status")
        source = item.get("immutable_source")
        sha = item.get("sha256")
        size = item.get("size")

        if not isinstance(product_id, str) or not PRODUCT_ID_RE.fullmatch(product_id):
            raise ValueError(f"invalid product_id at baseline[{index}]")
        if product_id in seen_ids:
            raise ValueError(f"duplicate product_id: {product_id}")
        seen_ids.add(product_id)
        if not isinstance(product_name, str) or not product_name.strip():
            raise ValueError(f"invalid product_name for {product_id}")
        if not isinstance(version, str) or not version.strip():
            raise ValueError(f"invalid version for {product_id}")
        if status not in ALLOWED_STATUS:
            raise ValueError(f"invalid source_status for {product_id}: {status!r}")

        if status == "VERIFIED":
            if not isinstance(source, str):
                raise ValueError(f"VERIFIED source missing immutable_source for {product_id}")
            validate_source_ref(source)
            if not isinstance(sha, str) or not SHA256_RE.fullmatch(sha):
                raise ValueError(f"VERIFIED source missing valid sha256 for {product_id}")
            if not isinstance(size, int) or isinstance(size, bool) or size < 0:
                raise ValueError(f"VERIFIED source missing valid size for {product_id}")
            verified += 1
        elif status == "MISSING":
            if source is not None or sha is not None or size is not None:
                raise ValueError(f"MISSING source must not carry invented evidence for {product_id}")
            missing += 1
        else:
            if sha is not None and (not isinstance(sha, str) or not SHA256_RE.fullmatch(sha)):
                raise ValueError(f"UNVERIFIED source has invalid sha256 for {product_id}")
            if source is not None:
                if not isinstance(source, str):
                    raise ValueError(f"UNVERIFIED immutable_source must be a string for {product_id}")
                validate_source_ref(source)
            if size is not None and (not isinstance(size, int) or isinstance(size, bool) or size < 0):
                raise ValueError(f"UNVERIFIED source has invalid size for {product_id}")
            unverified += 1

        normalized.append(
            {
                "product_id": product_id,
                "product_name": product_name,
                "version": version,
                "source_status": status,
                "immutable_source": source,
                "sha256": sha,
                "size": size,
            }
        )

    ready = verified == len(normalized)
    return {
        "schema_version": 1,
        "products": sorted(normalized, key=lambda x: x["product_id"]),
        "summary": {
            "product_count": len(normalized),
            "verified": verified,
            "unverified": unverified,
            "missing": missing,
            "ready_for_complete_dependency_scan": ready,
            "vulnerability_posture": "UNKNOWN" if not ready else "NOT_RUN",
        },
        "promotion_rule": "Complete dependency/vulnerability scanning may start only when every product source is VERIFIED. MISSING or UNVERIFIED inputs never count as PASS.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args()

    try:
        doc = json.loads(args.registry.read_text(encoding="utf-8"))
        report = validate_registry(doc)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        ready = report["summary"]["ready_for_complete_dependency_scan"]
        print(
            f"PASS: source-intake structure valid; verified={report['summary']['verified']}/"
            f"{report['summary']['product_count']}; ready={str(ready).lower()}; "
            f"vulnerability_posture={report['summary']['vulnerability_posture']}"
        )
        if args.require_ready and not ready:
            print("BLOCKED: complete dependency-bearing product sources are not all VERIFIED", file=sys.stderr)
            return 2
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
