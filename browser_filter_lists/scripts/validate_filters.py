from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
FILTER_DIR = ROOT / "filters"
FILES = sorted(FILTER_DIR.glob("*.txt"))

HOMEPAGE = "https://github.com/r20942097-hue/faaff/tree/main/browser_filter_lists"
RAW_BASE = "https://raw.githubusercontent.com/r20942097-hue/faaff/main/browser_filter_lists/filters"

errors = []
warnings = []

if not FILES:
    errors.append("No filter files found.")

hostname_rule = re.compile(r"^\|\|([A-Za-z0-9.-]+)\^\$third-party$")
dangerous_all = re.compile(r"\$(?:all|document)(?:,|$)", re.I)
version_re = re.compile(r"^\d{8}\.\d+$")
expires_re = re.compile(r"^\d+\s+days?$", re.I)
all_hosts = {}

for path in FILES:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    if not lines or lines[0].strip() != "[Adblock Plus 2.0]":
        errors.append(f"{path}: missing [Adblock Plus 2.0] header")

    header_values = {}
    required_headers = [
        "! Title:",
        "! Version:",
        "! Expires:",
        "! Homepage:",
        "! Subscription:",
        "! Description:",
        "! License:",
    ]
    for header in required_headers:
        matches = [line for line in lines[:25] if line.startswith(header)]
        if len(matches) != 1:
            errors.append(f"{path}: expected exactly one header {header}")
        else:
            header_values[header] = matches[0][len(header):].strip()

    if header_values.get("! Homepage:") not in (None, HOMEPAGE):
        errors.append(f"{path}: Homepage does not match published repository path")

    expected_subscription = f"{RAW_BASE}/{path.name}"
    if header_values.get("! Subscription:") not in (None, expected_subscription):
        errors.append(f"{path}: Subscription does not match stable raw URL")

    version = header_values.get("! Version:")
    if version is not None and not version_re.fullmatch(version):
        errors.append(f"{path}: Version must use YYYYMMDD.N format")

    expires = header_values.get("! Expires:")
    if expires is not None and not expires_re.fullmatch(expires):
        errors.append(f"{path}: Expires must use '<number> day(s)' format")

    active = []
    seen_hosts = set()
    for n, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("!") or line.startswith("["):
            continue

        if line in active:
            errors.append(f"{path}:{n}: duplicate rule: {line}")
        active.append(line)

        if dangerous_all.search(line):
            errors.append(f"{path}:{n}: broad $all/$document rule requires manual review: {line}")

        match = hostname_rule.fullmatch(line)
        if not match:
            errors.append(f"{path}:{n}: rule outside current conservative policy: {line}")
            continue

        host = match.group(1).lower()
        if host in seen_hosts:
            errors.append(f"{path}:{n}: duplicate hostname: {host}")
        seen_hosts.add(host)

        if host in all_hosts:
            errors.append(f"{path}:{n}: hostname also appears in {all_hosts[host]}: {host}")
        else:
            all_hosts[host] = path.name

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
