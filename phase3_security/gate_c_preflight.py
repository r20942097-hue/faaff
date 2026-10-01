#!/usr/bin/env python3
"""Fail-closed readiness check for complete Phase 3 dependency/vulnerability evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from pathlib import PurePosixPath
import re
import sys

from phase3_security.product_source_intake import validate_registry, validate_source_ref

SHA256_RE = re.compile(r"[0-9a-f]{64}")
ALLOWED_GATE_STATUS = {"NOT_RUN", "READY_FOR_REVIEW"}
REQUIRED_SECTIONS = ("dependency_resolution", "sbom", "scanner_results", "policy_evaluation")
BASELINE_IDS = {
    "universal-control-suite", "universal-live-watcher", "windows-control",
    "ai-orchestrator", "shared-foundation", "browser-control", "media-download-tools",
}


def _valid_sha(value: object) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None


def validate_gate_c_evidence(doc: dict, product_ids: set[str]) -> dict:
    if not isinstance(doc, dict) or doc.get("schema_version") != 1:
        raise ValueError("unsupported Gate C evidence schema")
    status = doc.get("gate_c_status")
    if status not in ALLOWED_GATE_STATUS:
        raise ValueError("Gate C status must be NOT_RUN or READY_FOR_REVIEW; PASS is not a valid preflight status")
    if doc.get("unknown_not_pass") is not True:
        raise ValueError("unknown_not_pass must be true")
    for section in REQUIRED_SECTIONS:
        if section not in doc:
            raise ValueError(f"Gate C evidence missing section: {section}")

    resolution = doc["dependency_resolution"]
    sbom = doc["sbom"]
    scans = doc["scanner_results"]
    policy = doc["policy_evaluation"]
    if not isinstance(resolution, dict) or not isinstance(sbom, dict) or not isinstance(scans, list) or not isinstance(policy, dict):
        raise ValueError("Gate C evidence sections have invalid types")

    if status == "NOT_RUN":
        if resolution.get("status") != "NOT_RUN" or sbom.get("status") != "NOT_RUN":
            raise ValueError("NOT_RUN Gate C evidence cannot claim dependency resolution or SBOM verification")
        if scans or policy.get("status") != "NOT_RUN" or policy.get("result") != "UNKNOWN":
            raise ValueError("NOT_RUN Gate C evidence cannot contain scan or policy clearance")
        return {"gate_c_status": "NOT_RUN", "blockers": ["complete scan evidence has not been produced"]}

    if resolution.get("status") != "VERIFIED":
        raise ValueError("READY_FOR_REVIEW requires verified dependency resolution")
    if not all(isinstance(resolution.get(k), str) and resolution[k].strip() for k in ("resolver", "resolver_version", "lock_artifact")):
        raise ValueError("dependency resolution provenance is incomplete")
    if not _valid_sha(resolution.get("lock_sha256")):
        raise ValueError("dependency lock evidence requires a valid SHA-256")
    if not isinstance(resolution.get("package_count"), int) or isinstance(resolution["package_count"], bool) or resolution["package_count"] <= 0:
        raise ValueError("dependency resolution package_count must be positive")

    if sbom.get("status") != "VERIFIED" or sbom.get("format") != "CycloneDX" or sbom.get("spec_version") != "1.6":
        raise ValueError("READY_FOR_REVIEW requires a verified complete CycloneDX 1.6 SBOM")
    if not isinstance(sbom.get("artifact"), str) or not sbom["artifact"].strip() or not _valid_sha(sbom.get("sha256")):
        raise ValueError("SBOM artifact provenance is incomplete")
    covered = sbom.get("covered_product_ids")
    if not isinstance(covered, list) or any(not isinstance(x, str) for x in covered) or len(covered) != len(set(covered)) or set(covered) != product_ids:
        raise ValueError("SBOM must cover every baseline product exactly")

    scan_ids: set[str] = set()
    for item in scans:
        if not isinstance(item, dict):
            raise ValueError("scanner result must be an object")
        product_id = item.get("product_id")
        if not isinstance(product_id, str) or product_id not in product_ids or product_id in scan_ids:
            raise ValueError("scanner results contain an unknown or duplicate product_id")
        scan_ids.add(product_id)
        if item.get("status") != "COMPLETED":
            raise ValueError(f"scanner result is incomplete for {product_id}")
        if not all(isinstance(item.get(k), str) and item[k].strip() for k in ("scanner", "scanner_version", "report")):
            raise ValueError(f"scanner provenance is incomplete for {product_id}")
        if not _valid_sha(item.get("report_sha256")):
            raise ValueError(f"scanner report SHA-256 is invalid for {product_id}")
        database = item.get("vulnerability_database")
        if not isinstance(database, dict) or not all(isinstance(database.get(k), str) and database[k].strip() for k in ("name", "version", "updated_at")):
            raise ValueError(f"vulnerability database provenance is incomplete for {product_id}")
    if scan_ids != product_ids:
        raise ValueError("scanner results must cover every baseline product exactly")

    if policy.get("status") != "EVALUATED" or policy.get("result") not in {"PASS", "FAIL"}:
        raise ValueError("READY_FOR_REVIEW requires an explicit policy evaluation")
    if not all(isinstance(policy.get(k), str) and policy[k].strip() for k in ("policy_id", "policy_version")):
        raise ValueError("policy provenance is incomplete")
    decisions = policy.get("product_results")
    if not isinstance(decisions, list) or any(not isinstance(x, dict) or not isinstance(x.get("product_id"), str) for x in decisions):
        raise ValueError("policy evaluation must contain one result for every baseline product")
    if {x["product_id"] for x in decisions} != product_ids:
        raise ValueError("policy evaluation must contain one result for every baseline product")
    if len(decisions) != len(product_ids) or any(x.get("result") not in {"PASS", "FAIL"} for x in decisions):
        raise ValueError("policy evaluation contains duplicate or invalid product results")
    return {"gate_c_status": "READY_FOR_REVIEW", "blockers": []}


def verify_scanner_sources(products: list[dict], source_root: Path) -> list[str]:
    root = source_root.resolve(strict=True)
    blockers: list[str] = []
    for item in products:
        if item["source_status"] != "VERIFIED":
            continue
        source = item["immutable_source"]
        validate_source_ref(source)
        relative = PurePosixPath(source)
        path = root
        has_symlink = False
        for part in relative.parts:
            path = path / part
            if path.is_symlink():
                has_symlink = True
                break
        if has_symlink:
            blockers.append(f"source path contains a symlink: {item['product_id']}")
            continue
        try:
            resolved = path.resolve(strict=True)
        except OSError:
            blockers.append(f"source file is missing: {item['product_id']}")
            continue
        if not resolved.is_relative_to(root) or not resolved.is_file():
            blockers.append(f"source file is not a regular file under the intake root: {item['product_id']}")
            continue
        data = resolved.read_bytes()
        if len(data) != item["size"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
            blockers.append(f"source bytes do not match immutable metadata: {item['product_id']}")
    return blockers


def verify_gate_c_artifacts(evidence: dict, source_root: Path) -> list[str]:
    """Check the bytes behind Gate C evidence references before review readiness."""
    root = source_root.resolve(strict=True)
    references = [("dependency lock", evidence["dependency_resolution"]["lock_artifact"], evidence["dependency_resolution"]["lock_sha256"])]
    references.append(("SBOM", evidence["sbom"]["artifact"], evidence["sbom"]["sha256"]))
    references.extend((f"scanner report {item['product_id']}", item["report"], item["report_sha256"]) for item in evidence["scanner_results"])
    blockers: list[str] = []
    sbom_bytes: bytes | None = None
    for label, name, expected_sha in references:
        validate_source_ref(name)
        path = root
        for part in PurePosixPath(name).parts:
            path = path / part
            if path.is_symlink():
                blockers.append(f"{label} path contains a symlink")
                break
        else:
            try:
                resolved = path.resolve(strict=True)
            except OSError:
                blockers.append(f"{label} file is missing")
                continue
            if not resolved.is_relative_to(root) or not resolved.is_file():
                blockers.append(f"{label} is not a regular file under the evidence root")
                continue
            data = resolved.read_bytes()
            if hashlib.sha256(data).hexdigest() != expected_sha:
                blockers.append(f"{label} SHA-256 mismatch")
            if label == "SBOM":
                sbom_bytes = data
    if sbom_bytes is not None:
        try:
            sbom = json.loads(sbom_bytes)
        except (UnicodeDecodeError, json.JSONDecodeError):
            blockers.append("SBOM is not valid JSON")
        else:
            if sbom.get("bomFormat") != "CycloneDX" or sbom.get("specVersion") != "1.6":
                blockers.append("SBOM bytes do not identify CycloneDX 1.6")
    return blockers


def evaluate_gate_c(registry: dict, evidence: dict, source_root: Path) -> dict:
    intake = validate_registry(registry)
    product_ids = {item["product_id"] for item in intake["products"]}
    if product_ids != BASELINE_IDS:
        raise ValueError("Gate C requires the exact seven-product Candidate Baseline")
    gate_evidence = validate_gate_c_evidence(evidence, product_ids)
    ready = intake["summary"]["ready_for_complete_dependency_scan"]
    source_blockers = verify_scanner_sources(intake["products"], source_root)
    evidence_blockers = verify_gate_c_artifacts(evidence, source_root) if gate_evidence["gate_c_status"] == "READY_FOR_REVIEW" else []
    if not ready or source_blockers or evidence_blockers:
        status = "NOT_RUN"
        blockers = [
            f"scanner-consumable product sources are {intake['summary']['verified']}/{intake['summary']['product_count']} VERIFIED",
            *source_blockers,
            *evidence_blockers,
            *gate_evidence["blockers"],
        ]
    else:
        status = gate_evidence["gate_c_status"]
        blockers = gate_evidence["blockers"]
    return {
        "schema_version": 1,
        "gate_c_status": status,
        "verified_product_count": intake["summary"]["verified"],
        "baseline_product_count": intake["summary"]["product_count"],
        "blockers": blockers,
        "vulnerability_posture": "UNKNOWN" if status == "NOT_RUN" else "NOT_RUN",
        "unknown_not_pass": True,
        "promotion_rule": "Gate C preflight never grants vulnerability clearance; READY_FOR_REVIEW is not PASS.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-root", type=Path)
    args = parser.parse_args()
    try:
        report = evaluate_gate_c(
            json.loads(args.registry.read_text(encoding="utf-8")),
            json.loads(args.evidence.read_text(encoding="utf-8")),
            args.source_root or args.registry.parent.parent,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        print(f"{report['gate_c_status']}: {report['verified_product_count']}/{report['baseline_product_count']} scanner-consumable sources; vulnerability_posture={report['vulnerability_posture']}")
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
