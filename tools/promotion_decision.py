#!/usr/bin/env python3
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
e = data["evidence"]

candidate = all([
    e["tests_pass"],
    e["clean_extract_pass"],
    e["archive_integrity_pass"],
    e["reproducible_build_pass"],
    (not e["sbom_required"] or e["sbom_present"]),
    (not e["provenance_required"] or e["provenance_present"]),
])

stable = candidate
if e["real_environment_required"]:
    stable = stable and (e["real_environment_pass"] is True)
if e["rollback_required"]:
    stable = stable and (e["rollback_pass"] is True)

if stable:
    print("STABLE_ELIGIBLE")
elif candidate:
    print("CANDIDATE_ELIGIBLE")
else:
    print("DEV_OR_NO_GO")
