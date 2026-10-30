#!/usr/bin/env python3
"""Check an engineering inventory without importing untrusted project code."""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
data = json.loads((ROOT / "tooling-readiness.json").read_text(encoding="utf-8"))
assert data["schema"] == "engineering-tool-readiness/v1"
assert data["repository"] == "r20942097-hue/faaff"
assert data["release_gate"] == "P0/PUBLICATION_HOLD"
assert data["authority"]["filter_distribution"] == "r20942097-hue/s"
tools = data["toolchains"]
requirements = data["requirements"]
assert len({t["id"] for t in tools}) == len(tools) and len(tools) >= 4
assert len({x["id"] for x in requirements}) == len(requirements) and len(requirements) >= 5
assert {"rplay-source", "addons-source", "python-lock", "native-firefox"} <= {x["id"] for x in requirements}
assert all(t["state"] in {"MAIN_PRESENT","DRAFT_VERIFIED","DRAFT_VERIFIED_SYNTHETIC"} for t in tools)
assert all(r["state"] in {"MISSING_MAIN", "PARTIAL", "BLOCKED_BY_SOURCE_AND_ENV", "NEEDS_SCOPE"} for r in requirements)
assert all(isinstance(t.get("tools"), list) and t["tools"] for t in tools)
assert all(bool(x.get("action")) and bool(x.get("blocks")) for x in requirements)
assert {t["pr"] for t in tools if "pr" in t} == {35,36,37,38}
assert data["acceptance"]["real_device_required_for_product_pass"] is True
assert data["acceptance"]["merge_requires_approval"] is True
text = (ROOT / "TOOLING_READINESS.md").read_text(encoding="utf-8")
assert "P0 / PUBLICATION_HOLD" in text and "uv.lock" in text
assert "real-device" in text or "Real-device" in text
print(f"PASS: {len(tools)} toolchains, {len(requirements)} source/data requirements, PR35-38 pointers")
