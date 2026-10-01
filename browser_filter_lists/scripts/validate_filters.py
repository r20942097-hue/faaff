from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
FILTER_DIR = ROOT / "filters"
FILES = sorted(FILTER_DIR.glob("*.txt"))

errors = []
warnings = []

if not FILES:
    errors.append("No filter files found.")

hostname_rule = re.compile(r"^\|\|([A-Za-z0-9.-]+)\^\$third-party$")
dangerous_all = re.compile(r"\$(?:all|document)(?:,|$)", re.I)

for path in FILES:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    if not lines or lines[0].strip() != "[Adblock Plus 2.0]":
        errors.append(f"{path}: missing [Adblock Plus 2.0] header")

    required_headers = ["! Title:", "! Version:", "! Expires:", "! Description:"]
    for header in required_headers:
        if not any(line.startswith(header) for line in lines[:20]):
            errors.append(f"{path}: missing header {header}")

    active = []
    for n, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("!") or line.startswith("["):
            continue

        if line in active:
            errors.append(f"{path}:{n}: duplicate rule: {line}")
        active.append(line)

        if dangerous_all.search(line):
            errors.append(f"{path}:{n}: broad $all/$document rule requires manual review: {line}")

        if not hostname_rule.fullmatch(line):
            errors.append(f"{path}:{n}: rule outside current conservative policy: {line}")

    if not active:
        warnings.append(f"{path}: contains no active rules")

if errors:
    print("VALIDATION FAILED")
    for e in errors:
        print("ERROR:", e)
    for w in warnings:
        print("WARNING:", w)
    sys.exit(1)

print(f"VALIDATION PASSED: {len(FILES)} file(s)")
for path in FILES:
    count = sum(
        1 for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith(("!", "["))
    )
    print(f"- {path.relative_to(ROOT)}: {count} active rules")
for w in warnings:
    print("WARNING:", w)
