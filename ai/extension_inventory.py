"""Read-only manifest inventory for candidate ZIPs, including nested ZIPs.

This is metadata inspection, not browser installation or permission safety review.
Run artifact_gate.py on the input ZIP first for structure/CRC/resource bounds.
"""
from __future__ import annotations
import argparse
import io
import json
import re
import sys
import zipfile
from pathlib import Path
from artifact_gate import inspect as inspect_archive

VERSION = re.compile(r"[0-9]+(?:\.[0-9]+){0,3}\Z")
MAX_MANIFEST = 256 * 1024
MAX_NESTED_ZIP = 24 * 1024 * 1024
MAX_DEPTH = 2
MAX_MANIFESTS = 150
MAX_ARCHIVES = 100
MAX_TOTAL_ENTRIES = 50000


def valid_store_version(value: object) -> bool:
    """Conservative cross-browser dotted numeric version policy."""
    if not isinstance(value, str) or VERSION.fullmatch(value) is None:
        return False
    parts = value.split(".")
    return all((part == "0" or not part.startswith("0")) and int(part) <= 65535
               for part in parts)


def browser_hint(location: str) -> str:
    """Match whole path components, avoiding accidental name substrings."""
    parts = {p for p in re.split(r"[/!_.-]+", location.casefold()) if p}
    if "firefox" in parts or "mozilla" in parts:
        return "firefox"
    if "chrome" in parts or "chromium" in parts:
        return "chrome"
    return "unspecified"


def read_bounded(zf: zipfile.ZipFile, info: zipfile.ZipInfo, limit: int) -> bytes:
    with zf.open(info) as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("uncompressed entry exceeds inspection limit")
    return data


def scan(path: Path) -> dict:
    records: list[dict] = []
    issues: list[str] = []
    warnings: list[str] = []
    budget = {"archives": 0, "entries": 0}

    def walk(zf: zipfile.ZipFile, prefix: str, depth: int) -> None:
        infos = zf.infolist()
        budget["archives"] += 1
        budget["entries"] += len(infos)
        if budget["archives"] > MAX_ARCHIVES or budget["entries"] > MAX_TOTAL_ENTRIES:
            issues.append(prefix + ": global ZIP archive/entry count limit exceeded")
            return
        if len(records) >= MAX_MANIFESTS:
            issues.append("manifest count limit exceeded")
            return
        for info in infos:
            name = info.filename
            location = prefix + name
            if name.rsplit("/", 1)[-1].lower() == "manifest.json":
                if len(records) >= MAX_MANIFESTS:
                    issues.append(location + ": manifest count limit exceeded")
                    break
                if info.file_size > MAX_MANIFEST:
                    issues.append(location + ": oversized manifest")
                    continue
                try:
                    value = json.loads(read_bounded(zf, info, MAX_MANIFEST).decode("utf-8"))
                    if not isinstance(value, dict):
                        raise ValueError("manifest must be JSON object")
                except (UnicodeError, ValueError, OSError, RuntimeError, zipfile.BadZipFile) as exc:
                    issues.append(location + ": invalid manifest (" + type(exc).__name__ + ")")
                    continue
                browser = browser_hint(location)
                if value.get("manifest_version") != 3:
                    issues.append(location + ": manifest_version is not MV3")
                v = value.get("version")
                if not valid_store_version(v):
                    issues.append(location + ": invalid extension version")
                if not isinstance(value.get("name"), str) or not value["name"].strip():
                    issues.append(location + ": missing extension name")
                perms = value.get("permissions", [])
                if not isinstance(perms, list) or any(not isinstance(p, str) for p in perms):
                    issues.append(location + ": malformed permissions")
                    perms = []
                for key in ("host_permissions", "optional_permissions", "optional_host_permissions"):
                    extra = value.get(key, [])
                    if not isinstance(extra, list) or any(not isinstance(p, str) for p in extra):
                        issues.append(location + ": malformed " + key)
                hosts = value.get("host_permissions", [])
                if isinstance(hosts, list) and any(h in ("<all_urls>", "*://*/*", "http://*/*", "https://*/*") for h in hosts if isinstance(h, str)):
                    warnings.append(location + ": broad host access requires manual permission review")
                if browser == "firefox" and "version_name" in value:
                    warnings.append(location + ": version_name compatibility should be checked in target Firefox")
                settings = value.get("browser_specific_settings")
                if settings is not None and not isinstance(settings, dict):
                    issues.append(location + ": malformed browser_specific_settings")
                if browser == "firefox":
                    gecko = settings.get("gecko", {}) if isinstance(settings, dict) else {}
                    if not isinstance(gecko, dict):
                        issues.append(location + ": malformed gecko settings")
                    elif "data_collection_permissions" not in gecko:
                        warnings.append(location + ": AMO data_collection_permissions review required")
                    if not isinstance(gecko, dict) or not isinstance(gecko.get("id"), str) or not gecko.get("id"):
                        warnings.append(location + ": Firefox signing/extension ID review required")
                records.append({"location": location, "browser_hint": browser,
                                "name": value.get("name") if isinstance(value.get("name"), str) else None,
                                "version": v if isinstance(v, str) else None,
                                "manifest_version": value.get("manifest_version"),
                                "version_name": value.get("version_name"),
                                "permission_count": len(perms),
                                "host_permission_count": len(hosts) if isinstance(hosts, list) else 0,
                                "has_browser_specific_settings": "browser_specific_settings" in value})
            elif name.lower().endswith(".zip"):
                if depth >= MAX_DEPTH or info.file_size > MAX_NESTED_ZIP:
                    issues.append(location + ": nested archive inspection limit exceeded")
                    continue
                try:
                    with zipfile.ZipFile(io.BytesIO(read_bounded(zf, info, MAX_NESTED_ZIP))) as nested:
                        walk(nested, location + "!/", depth + 1)
                except (ValueError, RuntimeError, OSError, zipfile.BadZipFile, EOFError):
                    issues.append(location + ": corrupt nested ZIP")
            if len(records) > MAX_MANIFESTS:
                issues.append("manifest count limit exceeded")
                break

    path = Path(path)
    # Enforce standalone structural safety; do not rely on callers running a prior command.
    structural = inspect_archive(path)
    if structural["status"] != "PASS":
        issues.append("ZIP structural preflight failed: " + "; ".join(structural["issues"][:5]))
    else:
        try:
            with zipfile.ZipFile(path) as zf:
                walk(zf, "", 0)
        except (ValueError, RuntimeError, OSError, zipfile.BadZipFile, EOFError):
            issues.append("unreadable archive")
    return {"schema": "gpt1-extension-inventory/v1",
            "status": "FAIL" if issues else "PASS",
            "scope": "manifest metadata only; no executable/browser validation",
            "manifest_count": len(records), "manifests": records, "issues": issues,
            "warnings": warnings, "zip_preflight": structural["status"],
            "scan_budget": budget,
            "real_browser": "NOT_RUN", "release_approval": "NOT_RUN"}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("zip_path", type=Path)
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    result = scan(args.zip_path)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result["status"], result["manifest_count"], "manifest(s)")
        for issue in result["issues"]:
            print("ERROR:", issue)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
