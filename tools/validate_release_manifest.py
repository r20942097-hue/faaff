#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path

HEX64 = re.compile(r"^[0-9a-f]{64}$")

path = Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))
errors = []

for key in (
    "schema_version", "product_id", "version", "state", "source",
    "artifact", "evidence", "release_decision", "blockers"
):
    if key not in data:
        errors.append(f"missing: {key}")

if data.get("schema_version") != 1:
    errors.append("schema_version must be 1")
if data.get("state") not in {"DEV", "CANDIDATE", "STABLE"}:
    errors.append("invalid state")

source = data.get("source", {})
artifact = data.get("artifact", {})
if not HEX64.match(str(source.get("source_sha256", ""))):
    errors.append("invalid source_sha256")
if not HEX64.match(str(artifact.get("sha256", ""))):
    errors.append("invalid artifact sha256")
if not isinstance(artifact.get("size_bytes"), int) or artifact.get("size_bytes", -1) < 0:
    errors.append("invalid size_bytes")

for error in errors:
    print("ERROR", error)

sys.exit(1 if errors else 0)
