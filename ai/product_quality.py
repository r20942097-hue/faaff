"""Fail-closed, evidence-aware product QA registry validation.

This validates claims and their references, not actual browser results.
Never approves, deploys, publishes, or declares a release-ready product.
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "gpt1-product-quality/v1"
PRODUCTS = ("rplay", "streamharbor", "youtube-optimizer")
GATES = ("source_integrity", "archive_integrity", "unit_tests",
         "browser_install", "real_site_e2e", "windows_device")
STATUSES = {"PASS", "FAIL", "BLOCKED", "NOT_RUN", "PARTIAL"}
SHA = re.compile(r"[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
REF = re.compile(r"(?:https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/actions/runs/[0-9]+(?:/job/[0-9]+)?|(?:docs|ai|tests|verification)/[A-Za-z0-9_./-]+)\Z")


def validate(data: object) -> dict:
    errors: list[str] = []
    counts = {status: 0 for status in sorted(STATUSES)}
    if not isinstance(data, dict):
        return {"status": "INVALID", "decision": "CANDIDATE_NO_GO", "errors": ["root must be an object"], "counts": counts}
    if data.get("schema") != SCHEMA:
        errors.append("unsupported schema")
    if data.get("release_gate") != "PUBLICATION_HOLD":
        errors.append("release governance gate must remain PUBLICATION_HOLD")
    products = data.get("products")
    if not isinstance(products, list):
        return {"status": "INVALID", "decision": "CANDIDATE_NO_GO", "errors": errors + ["products must be a list"], "counts": counts}
    seen = set()
    for item in products:
        if not isinstance(item, dict):
            errors.append("product must be object")
            continue
        pid = item.get("id")
        if not isinstance(pid, str) or pid not in PRODUCTS or pid in seen:
            errors.append("unknown or duplicate product id")
            continue
        seen.add(pid)
        if item.get("decision") != "CANDIDATE_NO_GO":
            errors.append(f"{pid}: decision must remain CANDIDATE_NO_GO")
        commit = item.get("source_commit")
        if commit is not None and (not isinstance(commit, str) or not COMMIT.fullmatch(commit)):
            errors.append(f"{pid}: invalid source commit SHA")
        digest = item.get("artifact_sha256")
        if digest is not None and (not isinstance(digest, str) or not SHA.fullmatch(digest)):
            errors.append(f"{pid}: invalid artifact SHA-256")
        gates = item.get("gates")
        if not isinstance(gates, dict) or set(gates) != set(GATES):
            errors.append(f"{pid}: required gate names missing or unexpected")
            continue
        for gate in GATES:
            claim = gates[gate]
            if not isinstance(claim, dict) or set(claim) != {"status", "evidence"}:
                errors.append(f"{pid}/{gate}: invalid gate claim object")
                continue
            state, evidence = claim.get("status"), claim.get("evidence")
            if not isinstance(state, str) or state not in STATUSES:
                errors.append(f"{pid}/{gate}: unsupported status")
                continue
            counts[state] += 1
            if state == "PASS":
                if not isinstance(evidence, str) or not REF.fullmatch(evidence) or ".." in Path(evidence).parts:
                    errors.append(f"{pid}/{gate}: PASS needs a safe evidence reference")
                if gate in ("archive_integrity", "source_integrity") and not (digest if gate == "archive_integrity" else commit):
                    errors.append(f"{pid}/{gate}: PASS needs matching artifact/source hash metadata")
            elif evidence is not None:
                errors.append(f"{pid}/{gate}: non-PASS status must not carry a success reference")
    if seen != set(PRODUCTS):
        errors.append("exactly three known product records required")
    return {"schema": "gpt1-product-quality-audit/v1", "status": "INVALID" if errors else "PASS",
            "decision": "CANDIDATE_NO_GO", "scope": "evidence claim syntax/coverage only; not authentication of evidence",
            "counts": counts, "errors": errors,
            "missing_e2e": {pid: True for pid in PRODUCTS if pid in seen}}


def run(path: Path) -> dict:
    try:
        if path.is_symlink() or not path.is_file():
            raise ValueError("missing or linked registry")
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError, UnicodeError) as exc:
        return {"status": "INVALID", "decision": "CANDIDATE_NO_GO", "errors": [f"unreadable registry: {type(exc).__name__}"]}
    return validate(data)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=ROOT / "ai/product_quality.json")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = run(args.registry)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"{result['status']}: {result['decision']}")
        for err in result.get("errors", []):
            print("ERROR:", err)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
