#!/usr/bin/env python3
"""Validate the source intake RECORD. It does not validate absent ZIP bytes."""
import json
import re
from pathlib import Path

EVIDENCE = Path(__file__).with_name("2026-10-30-evidence.json")
SHA256 = re.compile(r"^[a-f0-9]{64}$")

def check(doc):
    if doc.get("schema") != "faaff/source-intake/v1":
        raise ValueError("unsupported intake schema")
    if doc.get("intake_state") != "METADATA_VERIFIED_RELEASE_BLOCKED":
        raise ValueError("release must remain blocked")
    controls = doc.get("controls", {})
    for key in ("main_merge", "release"):
        if controls.get(key) != "NOT_AUTHORIZED":
            raise ValueError("source review cannot grant publishing authority")
    if controls.get("source_sync") != "BLOCKED_PENDING_PROVENANCE_SECURITY_REVIEW":
        raise ValueError("unsafe source-sync state")
    sources = doc.get("archives", [])
    if len(sources) != 2 or len({s.get("name") for s in sources}) != 2:
        raise ValueError("expected exactly two distinct source observations")
    for a in sources:
        if not SHA256.fullmatch(a.get("sha256", "")):
            raise ValueError("bad source digest")
        if a.get("size_bytes", 0) <= 0 or a.get("integrity") != "PASS":
            raise ValueError("source metadata incomplete")
        if a.get("real_browser_e2e") != "NOT_RUN":
            raise ValueError("real-device gate cannot be inferred from static test")
    addons = next((x for x in sources if x["name"].startswith("Three_Addons_")), None)
    repair = next((x for x in sources if x["name"].startswith("RPLAY_OPFS_")), None)
    if not addons or not repair or repair.get("product_state") != "NO_GO":
        raise ValueError("RPLAY repair kit must be NO_GO")
    if addons.get("product_state") != "GO_CANDIDATE_ONLY":
        raise ValueError("candidate package cannot be promoted by this record")
    packages = addons.get("packages", [])
    if len(packages) != 6 or len({p.get("path") for p in packages}) != 6:
        raise ValueError("six distinct extension packages required")
    for p in packages:
        if not SHA256.fullmatch(p.get("sha256","")) or not re.fullmatch(r"\d+\.\d+\.\d+",p.get("version","")):
            raise ValueError("extension digest/version invalid")
    chrome = sum("/Chrome/" in p["path"] for p in packages)
    firefox = sum("/Firefox/" in p["path"] for p in packages)
    if (chrome, firefox) != (3, 3):
        raise ValueError("expected three browser packages per platform")
    if addons.get("data_tool",{}).get("selftest","").startswith("41/41 PASS") is False:
        raise ValueError("data tool selftest result missing")
    return True

if __name__ == "__main__":
    doc = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    check(doc)
    print("PASS METADATA_SCHEMA_ONLY: originals absent from GitHub, not re-hashed in CI")
