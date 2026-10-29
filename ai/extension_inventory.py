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

VERSION = re.compile(r"[0-9]+(?:\.[0-9]+){0,3}\Z")
MAX_MANIFEST = 256 * 1024
MAX_NESTED_ZIP = 24 * 1024 * 1024
MAX_DEPTH = 2
MAX_MANIFESTS = 150


def read_bounded(zf: zipfile.ZipFile, info: zipfile.ZipInfo, limit: int) -> bytes:
    with zf.open(info) as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("uncompressed entry exceeds inspection limit")
    return data


def scan(path: Path) -> dict:
    records: list[dict] = []
    issues: list[str] = []

    def walk(zf: zipfile.ZipFile, prefix: str, depth: int) -> None:
        if len(records) > MAX_MANIFESTS:
            issues.append("too many extension manifests")
            return
        for info in zf.infolist():
            name = info.filename
            location = prefix + name
            if name.rsplit("/", 1)[-1].lower() == "manifest.json":
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
                browser = "firefox" if "firefox" in location.lower() else "chrome" if "chrome" in location.lower() else "unspecified"
                if value.get("manifest_version") != 3:
                    issues.append(location + ": manifest_version is not MV3")
                v = value.get("version")
                if not isinstance(v, str) or VERSION.fullmatch(v) is None:
                    issues.append(location + ": invalid extension version")
                if not isinstance(value.get("name"), str) or not value["name"].strip():
                    issues.append(location + ": missing extension name")
                perms = value.get("permissions", [])
                if not isinstance(perms, list) or any(not isinstance(p, str) for p in perms):
                    issues.append(location + ": malformed permissions")
                    perms = []
                if browser == "firefox" and "version_name" in value:
                    issues.append(location + ": Firefox manifest includes Chrome-only version_name")
                records.append({"location": location, "browser_hint": browser,
                                "name": value.get("name") if isinstance(value.get("name"), str) else None,
                                "version": v if isinstance(v, str) else None,
                                "manifest_version": value.get("manifest_version"),
                                "version_name": value.get("version_name"),
                                "permission_count": len(perms),
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
    if path.is_symlink() or not path.is_file():
        issues.append("missing/linked archive")
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
