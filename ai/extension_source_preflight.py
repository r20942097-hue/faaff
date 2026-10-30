"""Offline, fail-closed preflight for extension source trees or source ZIP files.

The archive integrity check is delegated to the repository's artifact_gate.py.
Neither source checks nor archive integrity imply browser E2E, provenance or GO.
No extraction, network access, browser launch or credentials are needed.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
import sys
import unicodedata
import zipfile
from pathlib import Path, PurePosixPath

MANIFEST_LIMIT = 256 * 1024
MAX_FILES = 15000
MAX_DIR_BYTES = 768 * 1024 * 1024
MAX_REPORT_FINDINGS = 60
VALID_VERSION = re.compile(r"\d+(?:\.\d+){0,3}\Z")
INVALID_WINDOWS = set('<>"|*')
WIN_RESERVED = re.compile(r"(?:CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])(?:\..*)?\Z", re.I)


def _unique_json_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON manifest key")
        result[key] = value
    return result


def _path_key(path: str) -> str:
    return unicodedata.normalize("NFC", path).casefold()


def _relative_file(path: str) -> bool:
    # Manifest file references cannot be absolute, escape their root or contain
    # backslashes, NUL/control chars, drive prefixes or URL-like strings.
    if not isinstance(path, str) or not path or path.startswith("/") or "\\" in path:
        return False
    if any(ord(c) < 32 for c in path) or ":" in path or "?" in path or "#" in path:
        return False
    return all(part not in ("", ".", "..")
               and not part.endswith((" ", "."))
               and not WIN_RESERVED.fullmatch(part)
               and not any(char in INVALID_WINDOWS for char in part)
               for part in path.split("/"))


def _manifest_refs(manifest: dict) -> list[tuple[str, str]]:
    refs: list[tuple[str, str]] = []

    def add(label: str, value):
        if value is not None:
            refs.append((label, value))

    bg = manifest.get("background")
    if isinstance(bg, dict):
        add("background.service_worker", bg.get("service_worker"))
        if "scripts" in bg:
            items = bg["scripts"]
            if isinstance(items, list):
                for i, value in enumerate(items):
                    add(f"background.scripts[{i}]", value)
            else:
                add("background.scripts", items)
    for key in ("action", "browser_action", "page_action"):
        item = manifest.get(key)
        if isinstance(item, dict):
            add(f"{key}.default_popup", item.get("default_popup"))
    for key in ("options_page", "devtools_page", "side_panel"):
        item = manifest.get(key)
        if key == "side_panel":
            if isinstance(item, dict):
                add("side_panel.default_path", item.get("default_path"))
        else:
            add(key, item)
    options_ui = manifest.get("options_ui")
    if isinstance(options_ui, dict):
        add("options_ui.page", options_ui.get("page"))
    for k, item in (manifest.get("chrome_url_overrides") or {}).items() if isinstance(manifest.get("chrome_url_overrides"), dict) else []:
        add("chrome_url_overrides." + str(k), item)
    for k, value in (manifest.get("icons") or {}).items() if isinstance(manifest.get("icons"), dict) else []:
        add("icons." + str(k), value)
    for k in ("action", "browser_action", "page_action"):
        icons = manifest.get(k, {})
        if isinstance(icons, dict):
            icons = icons.get("default_icon")
            if isinstance(icons, str):
                add(k + ".default_icon", icons)
            if isinstance(icons, dict):
                for size, item in icons.items():
                    add(k + ".default_icon." + str(size), item)
    # DNR static rule files and sandbox pages are packaged local files too.
    dnr = manifest.get("declarative_net_request")
    if isinstance(dnr, dict) and isinstance(dnr.get("rule_resources"), list):
        for i, ruleset in enumerate(dnr["rule_resources"]):
            if isinstance(ruleset, dict):
                add(f"declarative_net_request.rule_resources[{i}].path", ruleset.get("path"))
    sandbox = manifest.get("sandbox")
    if isinstance(sandbox, dict) and isinstance(sandbox.get("pages"), list):
        for i, page in enumerate(sandbox["pages"]):
            add(f"sandbox.pages[{i}]", page)
    css = manifest.get("content_scripts")
    if isinstance(css, list):
        for i, content in enumerate(css):
            if not isinstance(content, dict):
                add(f"content_scripts[{i}]", content)
                continue
            for name in ("js", "css"):
                if name in content:
                    if isinstance(content[name], list):
                        for j, value in enumerate(content[name]):
                            add(f"content_scripts[{i}].{name}[{j}]", value)
                    else:
                        add(f"content_scripts[{i}].{name}", content[name])
    return refs


def _resource_reference(value, root: str, names: set[str]) -> tuple[str | None, str | None]:
    """Validate Web Accessible Resource path; allow only '*' glob syntax.

    A leading '/' is allowed for WAR per Chrome/Firefox documentation, unlike
    ordinary file references. Empty matches are warnings, not malformed paths.
    """
    if not isinstance(value, str) or not value:
        return "unsafe/non-string resource reference", None
    pattern = value[1:] if value.startswith("/") else value
    if not _relative_file(pattern.replace("*", "x")):
        return "unsafe resource reference", None
    if "*" in pattern:
        found = any(fnmatch.fnmatchcase(name, _path_key(root + pattern)) for name in names)
        return None, (None if found else "resource wildcard has no matching packaged file")
    if _path_key(root + pattern) not in names:
        return "resource file missing", None
    return None, None


def _validate_web_resources(obj: dict, mv, root: str, names: set[str],
                            errors: list[str], warnings: list[str]) -> None:
    resources = obj.get("web_accessible_resources")
    if resources is None:
        return
    if not isinstance(resources, list):
        errors.append("web_accessible_resources must be an array")
        return
    for i, entry in enumerate(resources):
        label = f"web_accessible_resources[{i}]"
        if mv == 2:
            values = [entry]
        else:
            if not isinstance(entry, dict):
                errors.append(label + ": MV3 resource entry must be an object")
                continue
            values = entry.get("resources")
            if not isinstance(values, list) or not values:
                errors.append(label + ": resources must be a nonempty array")
                continue
            targets = (entry.get("matches"), entry.get("extension_ids"))
            if not any(isinstance(t, list) and t for t in targets):
                errors.append(label + ": missing matches/extension_ids")
            for field, target in zip(("matches", "extension_ids"), targets):
                if target is not None and (not isinstance(target, list)
                                           or not target or any(not isinstance(t, str) or not t for t in target)):
                    errors.append(label + "." + field + ": expected nonempty string array")
        for j, resource in enumerate(values):
            err, warn = _resource_reference(resource, root, names)
            if err:
                errors.append(f"{label}.resources[{j}]: {err}")
            if warn:
                warnings.append(f"{label}.resources[{j}]: {warn}")


def _manifest_validate(data: bytes, root: str, names: set[str]) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    if len(data) > MANIFEST_LIMIT:
        errors.append("manifest exceeds 256 KiB limit")
        return {"root": root or ".", "status": "FAIL", "errors": errors, "warnings": warnings}
    try:
        obj = json.loads(data.decode("utf-8-sig"), object_pairs_hook=_unique_json_pairs)
    except (UnicodeError, json.JSONDecodeError, ValueError):
        errors.append("manifest is not valid UTF-8 JSON")
        return {"root": root or ".", "status": "FAIL", "errors": errors, "warnings": warnings}
    if not isinstance(obj, dict):
        errors.append("manifest root must be JSON object")
        return {"root": root or ".", "status": "FAIL", "errors": errors, "warnings": warnings}
    mv = obj.get("manifest_version")
    if type(mv) is not int or mv not in (2, 3):
        errors.append("unsupported/missing manifest_version (expected integer 2 or 3)")
    elif mv == 2:
        warnings.append("MV2 compatibility varies by browser; check independently")
    if not isinstance(obj.get("name"), str) or not obj["name"].strip():
        errors.append("missing/empty extension name")
    version = obj.get("version")
    if not isinstance(version, str) or VALID_VERSION.fullmatch(version) is None:
        errors.append("invalid/missing extension version")
    if "background" in obj and not isinstance(obj["background"], dict):
        errors.append("background must be an object")
    bg = obj.get("background")
    if isinstance(bg, dict) and "scripts" in bg and (
            not isinstance(bg["scripts"], list)
            or any(not isinstance(item, str) or not item for item in bg["scripts"])):
        errors.append("background.scripts must be an array of file paths")
    dnr = obj.get("declarative_net_request")
    if dnr is not None:
        if not isinstance(dnr, dict) or not isinstance(dnr.get("rule_resources"), list) or not dnr["rule_resources"]:
            errors.append("declarative_net_request.rule_resources must be a nonempty array")
        else:
            ids = set()
            for i, ruleset in enumerate(dnr["rule_resources"]):
                label = f"declarative_net_request.rule_resources[{i}]"
                if not isinstance(ruleset, dict):
                    errors.append(label + ": expected object")
                    continue
                identifier = ruleset.get("id")
                if not isinstance(identifier, str) or not identifier or identifier.startswith("_"):
                    errors.append(label + ": invalid/missing ruleset id")
                elif identifier in ids:
                    errors.append(label + ": duplicate ruleset id")
                else:
                    ids.add(identifier)
                if type(ruleset.get("enabled")) is not bool:
                    errors.append(label + ": enabled must be boolean")
                if not isinstance(ruleset.get("path"), str) or not ruleset["path"]:
                    errors.append(label + ": missing/invalid ruleset path")
    sandbox = obj.get("sandbox")
    if sandbox is not None and (not isinstance(sandbox, dict)
                                or not isinstance(sandbox.get("pages"), list)
                                or any(not isinstance(item, str) or not item for item in sandbox["pages"])):
        errors.append("sandbox.pages must be an array of file paths")
    _validate_web_resources(obj, mv, root, names, errors, warnings)
    for label, ref in _manifest_refs(obj):
        if not _relative_file(ref):
            errors.append(label + ": unsafe/non-string file reference")
            continue
        actual = root + ref
        if _path_key(actual) not in names:
            errors.append(label + ": referenced file missing")
    content_scripts = obj.get("content_scripts")
    if content_scripts is not None and not isinstance(content_scripts, list):
        errors.append("content_scripts must be an array")
    if isinstance(content_scripts, list):
        for i, item in enumerate(content_scripts):
            if (not isinstance(item, dict) or not isinstance(item.get("matches"), list)
                    or not item["matches"]
                    or any(not isinstance(match, str) or not match for match in item["matches"])):
                errors.append(f"content_scripts[{i}] missing/invalid matches array")
            if isinstance(item, dict):
                for key in ("js", "css"):
                    if key in item and (not isinstance(item[key], list)
                                        or any(not isinstance(v, str) or not v for v in item[key])):
                        errors.append(f"content_scripts[{i}].{key} must be an array of file paths")
    permissions = obj.get("host_permissions", [])
    if permissions is not None and not isinstance(permissions, list):
        errors.append("host_permissions must be an array")
    if isinstance(permissions, list) and any(p == "<all_urls>" for p in permissions):
        warnings.append("broad host permissions: manual review required")
    if obj.get("permissions") is not None and not isinstance(obj.get("permissions"), list):
        errors.append("permissions must be an array")
    return {"root": root or ".", "status": "FAIL" if errors else "PASS",
            "manifest_version": mv if type(mv) is int else None,
            "version": version if isinstance(version, str) else None,
            "errors": errors[:MAX_REPORT_FINDINGS], "warnings": warnings[:MAX_REPORT_FINDINGS]}


def _scan_zip(path: Path, expected_sha256: str | None) -> dict:
    # Import locally: this module already exists in faaff and remains the sole
    # authoritative implementation for ZIP CRC, traversal, nested ZIP and limits.
    from artifact_gate import inspect as inspect_archive
    archive = inspect_archive(path, expected_sha256=expected_sha256)
    if archive["status"] != "PASS":
        return {"status": "FAIL", "reason": "ARCHIVE_INTEGRITY_FAIL",
                "archive": archive, "extensions": [], "nested_zip_count": None}
    with zipfile.ZipFile(path, "r") as zf:
        names = {_path_key(i.filename) for i in zf.infolist() if not i.is_dir()}
        manifests = [i for i in zf.infolist() if not i.is_dir() and
                     PurePosixPath(i.filename).name == "manifest.json"]
        nested = sum(1 for i in zf.infolist() if not i.is_dir() and i.filename.lower().endswith(".zip"))
        extensions = []
        for item in sorted(manifests, key=lambda i: i.filename):
            root = item.filename[:-len("manifest.json")]
            with zf.open(item) as stream:
                data = stream.read(MANIFEST_LIMIT + 1)
            extensions.append(_manifest_validate(data, root, names))
    return {"status": "FAIL" if any(e["status"] == "FAIL" for e in extensions)
            else ("PARTIAL" if not extensions or nested else "PASS"),
            "archive": {"status": archive["status"], "sha256": archive["sha256"],
                        "summary": archive["summary"]},
            "reason": "UNINSPECTED_NESTED_ZIP" if nested else ("NO_EXTENSION_MANIFEST" if not extensions else None),
            "extensions": extensions, "nested_zip_count": nested}


def _scan_dir(path: Path, expected_sha256: str | None) -> dict:
    if expected_sha256 is not None:
        return {"status": "FAIL", "reason": "SHA256_ONLY_FOR_ZIP", "extensions": []}
    seen: set[str] = set()
    by_name: dict[str, Path] = {}
    files_count = 0
    total_bytes = 0
    for f in path.rglob("*"):
        if f.is_symlink():
            return {"status": "FAIL", "reason": "SYMLINK_IN_SOURCE_TREE", "extensions": []}
        if f.is_dir():
            continue
        if not f.is_file():
            return {"status": "FAIL", "reason": "NONREGULAR_SOURCE_ENTRY", "extensions": []}
        name = f.relative_to(path).as_posix()
        key = _path_key(name)
        if key in seen:
            return {"status": "FAIL", "reason": "CASE_OR_UNICODE_PATH_COLLISION", "extensions": []}
        if not _relative_file(name):
            return {"status": "FAIL", "reason": "UNSAFE_SOURCE_PATH", "extensions": []}
        seen.add(key)
        by_name[key] = f
        files_count += 1
        total_bytes += f.stat().st_size
        if files_count > MAX_FILES or total_bytes > MAX_DIR_BYTES:
            return {"status": "FAIL", "reason": "SOURCE_TREE_LIMIT_EXCEEDED", "extensions": []}
    manifests = sorted((name for name in by_name if name.endswith("manifest.json") and (name == "manifest.json" or name.endswith("/manifest.json"))))
    extensions = []
    for name in manifests:
        f = by_name[name]
        if f.stat().st_size > MANIFEST_LIMIT:
            data = b" " * (MANIFEST_LIMIT + 1)
        else:
            data = f.read_bytes()
        rel = f.relative_to(path).as_posix()
        root = rel[:-len("manifest.json")]
        extensions.append(_manifest_validate(data, root, seen))
    nested = sum(1 for n in by_name if n.endswith(".zip"))
    return {"status": "FAIL" if any(e["status"] == "FAIL" for e in extensions)
            else ("PARTIAL" if not extensions or nested else "PASS"),
            "reason": "UNINSPECTED_NESTED_ZIP" if nested else ("NO_EXTENSION_MANIFEST" if not extensions else None),
            "extensions": extensions, "nested_zip_count": nested,
            "directory_files": files_count}


def inspect(path: Path, expected_sha256: str | None = None) -> dict:
    path = Path(path)
    result = {"schema": "gpt1-extension-source-preflight/v1", "file": path.name,
              "scope": "offline extension manifest and referenced file layout ONLY",
              "browser_install": "NOT_RUN", "browser_e2e": "NOT_RUN",
              "real_site_e2e": "NOT_RUN", "windows_device": "NOT_RUN",
              "release_decision": "CANDIDATE_NO_GO"}
    if path.is_symlink() or not path.exists():
        report = {"status": "FAIL", "reason": "SOURCE_MISSING_OR_SYMLINK", "extensions": []}
    elif path.is_dir():
        report = _scan_dir(path, expected_sha256)
    elif path.is_file() and path.suffix.lower() == ".zip":
        report = _scan_zip(path, expected_sha256)
    else:
        report = {"status": "FAIL", "reason": "EXPECTED_SOURCE_DIRECTORY_OR_ZIP", "extensions": []}
    result.update(report)
    return result


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", type=Path)
    p.add_argument("--sha256", help="trusted, expected lowercase SHA-256 for source ZIP")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    result = inspect(args.source, args.sha256)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result["status"], result["file"], "manifest_count", len(result["extensions"]))
        for e in result["extensions"]:
            print("-", e["root"], e["status"], "; ".join(e["errors"]))
    return {"PASS": 0, "FAIL": 1, "PARTIAL": 2}[result["status"]]


if __name__ == "__main__":
    sys.exit(main())