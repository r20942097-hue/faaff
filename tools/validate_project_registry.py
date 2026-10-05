#!/usr/bin/env python3
import json
import sys
from pathlib import Path

path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/project_registry.json")
data = json.loads(path.read_text(encoding="utf-8"))
errors = []
seen = set()

if data.get("schema_version") != 3:
    errors.append("schema_version must be 3")

for project in data.get("projects", []):
    project_id = project.get("id")
    if not project_id:
        errors.append("project missing id")
        continue
    if project_id in seen:
        errors.append(f"duplicate project id: {project_id}")
    seen.add(project_id)

    if project.get("state") == "STABLE" and not project.get("stable"):
        errors.append(f"{project_id}: STABLE without stable version")
    if str(project.get("decision", "")).startswith("NO_GO") and project.get("state") == "STABLE":
        errors.append(f"{project_id}: STABLE contradicts NO_GO")

for error in errors:
    print("ERROR", error)

print(f"projects={len(data.get('projects', []))}")
sys.exit(1 if errors else 0)
