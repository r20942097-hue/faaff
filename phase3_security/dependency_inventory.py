#!/usr/bin/env python3
"""Deterministically inventory declared dependencies from the verified Phase 2 source ZIP.

This tool does not resolve packages, query registries, or claim vulnerability coverage.
It emits a declaration-level inventory and a minimal CycloneDX document whose scope is
explicitly limited to dependency declarations present in the supplied archive.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import zipfile

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 is unsupported by CI
    tomllib = None

MAX_UNCOMPRESSED = 10 * 1024 * 1024
SUPPORTED_TEXT_MANIFESTS = {
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "requirements-test.txt",
    "package.json",
}
LOCKFILE_NAMES = {
    "poetry.lock",
    "Pipfile.lock",
    "requirements.lock",
    "package-lock.json",
    "npm-shrinkwrap.json",
    "yarn.lock",
    "pnpm-lock.yaml",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_declared_checksum(path: Path, archive_name: str) -> str:
    text = path.read_text(encoding="utf-8").strip()
    match = re.fullmatch(r"([0-9a-f]{64})  " + re.escape(archive_name), text)
    if not match:
        raise ValueError("invalid detached archive checksum")
    return match.group(1)


def validate_zip(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    infos = archive.infolist()
    if not infos:
        raise ValueError("source ZIP is empty")
    seen: set[str] = set()
    casefolded: set[str] = set()
    total = 0
    for info in infos:
        name = info.filename
        path = PurePosixPath(name)
        mode = info.external_attr >> 16
        folded = name.casefold()
        if (
            not name
            or name.endswith("/")
            or path.is_absolute()
            or ".." in path.parts
            or "\\" in name
            or "\x00" in name
            or re.match(r"^[A-Za-z]:", name)
        ):
            raise ValueError(f"unsafe ZIP path: {name!r}")
        if name in seen or folded in casefolded:
            raise ValueError(f"duplicate ZIP path: {name!r}")
        if stat.S_ISLNK(mode):
            raise ValueError(f"symlink ZIP entry: {name!r}")
        seen.add(name)
        casefolded.add(folded)
        total += info.file_size
        if total > MAX_UNCOMPRESSED:
            raise ValueError("source ZIP exceeds uncompressed size limit")
    bad = archive.testzip()
    if bad:
        raise ValueError(f"ZIP CRC failure: {bad}")
    return infos


def _dep_name(spec: str) -> str:
    value = spec.strip()
    if not value:
        return "unknown"
    if value.startswith(("-r ", "--requirement ", "-c ", "--constraint ")):
        return value.split(maxsplit=1)[-1]
    match = re.match(r"([A-Za-z0-9][A-Za-z0-9._-]*)", value)
    return match.group(1) if match else value[:120]


def _record(group: str, spec: str) -> dict[str, str]:
    return {"group": group, "name": _dep_name(spec), "raw": spec}


def parse_pyproject(data: bytes) -> list[dict[str, str]]:
    if tomllib is None:
        raise ValueError("tomllib unavailable")
    doc = tomllib.loads(data.decode("utf-8"))
    out: list[dict[str, str]] = []
    project = doc.get("project", {})
    for spec in project.get("dependencies", []) or []:
        if not isinstance(spec, str):
            raise ValueError("project.dependencies contains non-string value")
        out.append(_record("project", spec))
    optional = project.get("optional-dependencies", {}) or {}
    if not isinstance(optional, dict):
        raise ValueError("project.optional-dependencies must be a table")
    for group, values in sorted(optional.items()):
        if not isinstance(values, list):
            raise ValueError(f"optional dependency group {group!r} must be an array")
        for spec in values:
            if not isinstance(spec, str):
                raise ValueError(f"optional dependency group {group!r} contains non-string value")
            out.append(_record(f"optional:{group}", spec))
    build = doc.get("build-system", {}) or {}
    for spec in build.get("requires", []) or []:
        if not isinstance(spec, str):
            raise ValueError("build-system.requires contains non-string value")
        out.append(_record("build-system", spec))
    poetry = ((doc.get("tool", {}) or {}).get("poetry", {}) or {})
    poetry_deps = poetry.get("dependencies", {}) or {}
    if isinstance(poetry_deps, dict):
        for name, spec in sorted(poetry_deps.items()):
            if str(name).lower() == "python":
                continue
            out.append(_record("poetry", f"{name} {json.dumps(spec, sort_keys=True) if isinstance(spec, dict) else spec}"))
    groups = poetry.get("group", {}) or {}
    if isinstance(groups, dict):
        for group, group_doc in sorted(groups.items()):
            deps = (group_doc or {}).get("dependencies", {}) if isinstance(group_doc, dict) else {}
            if isinstance(deps, dict):
                for name, spec in sorted(deps.items()):
                    out.append(_record(f"poetry:{group}", f"{name} {json.dumps(spec, sort_keys=True) if isinstance(spec, dict) else spec}"))
    return out


def parse_requirements(data: bytes) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for raw in data.decode("utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        out.append(_record("requirements", line))
    return out


def parse_package_json(data: bytes) -> list[dict[str, str]]:
    doc = json.loads(data.decode("utf-8"))
    if not isinstance(doc, dict):
        raise ValueError("package.json root must be an object")
    out: list[dict[str, str]] = []
    for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        table = doc.get(key, {}) or {}
        if not isinstance(table, dict):
            raise ValueError(f"package.json {key} must be an object")
        for name, spec in sorted(table.items()):
            if not isinstance(spec, str):
                raise ValueError(f"package.json {key}.{name} must be a string")
            out.append({"group": key, "name": name, "raw": f"{name}@{spec}"})
    return out


def scan_archive(archive_path: Path, checksum_path: Path) -> tuple[dict, dict]:
    archive_bytes = archive_path.read_bytes()
    actual = sha256(archive_bytes)
    declared = parse_declared_checksum(checksum_path, archive_path.name)
    if actual != declared:
        raise ValueError("source ZIP SHA-256 mismatch")

    manifests: list[dict] = []
    lockfiles: list[dict] = []
    with zipfile.ZipFile(archive_path) as archive:
        infos = validate_zip(archive)
        names = [info.filename for info in infos]
        for name in sorted(names):
            base = PurePosixPath(name).name
            if base in LOCKFILE_NAMES:
                body = archive.read(name)
                lockfiles.append({"path": name, "sha256": sha256(body), "size": len(body)})
                continue
            is_requirements = base.startswith("requirements") and base.endswith(".txt")
            if base not in SUPPORTED_TEXT_MANIFESTS and not is_requirements:
                continue
            body = archive.read(name)
            try:
                if base == "pyproject.toml":
                    deps = parse_pyproject(body)
                    kind = "python-pyproject"
                elif base == "package.json":
                    deps = parse_package_json(body)
                    kind = "node-package-json"
                else:
                    deps = parse_requirements(body)
                    kind = "python-requirements"
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                raise ValueError(f"cannot parse dependency manifest {name}: {exc}") from exc
            manifests.append(
                {
                    "path": name,
                    "kind": kind,
                    "sha256": sha256(body),
                    "size": len(body),
                    "dependencies": deps,
                }
            )

    dependency_count = sum(len(item["dependencies"]) for item in manifests)
    inventory_status = "PASS" if manifests else "UNKNOWN"
    report = {
        "schema_version": 1,
        "source_archive": {
            "path": archive_path.as_posix(),
            "sha256": actual,
            "declared_sha256": declared,
            "integrity": "PASS",
        },
        "scope": {
            "coverage": "PARTIAL",
            "reason": "Only the committed Phase 2 control-plane source archive is inventoried; complete dependency-bearing product source trees are not present in this repository scope.",
        },
        "inventory": {
            "status": inventory_status,
            "manifest_count": len(manifests),
            "dependency_declaration_count": dependency_count,
            "lockfile_count": len(lockfiles),
            "manifests": manifests,
            "lockfiles": lockfiles,
        },
        "security_posture": {
            "dependency_review": "NOT_RUN",
            "codeql": "NOT_RUN",
            "vulnerability_scan": "NOT_RUN",
            "vulnerability_posture": "UNKNOWN",
        },
        "sbom": {
            "status": "DECLARATION_ONLY",
            "standard": "CycloneDX 1.6",
            "limitations": "Declared direct dependencies only; no package resolution, transitive dependency graph, installed-version verification, registry lookup, or vulnerability matching.",
        },
    }

    components: list[dict] = []
    seen_components: set[tuple[str, str]] = set()
    for manifest in manifests:
        for dep in manifest["dependencies"]:
            key = (dep["name"].lower(), dep["raw"])
            if key in seen_components:
                continue
            seen_components.add(key)
            components.append(
                {
                    "type": "library",
                    "name": dep["name"],
                    "properties": [
                        {"name": "ucs:declaration", "value": dep["raw"]},
                        {"name": "ucs:group", "value": dep["group"]},
                        {"name": "ucs:source-manifest", "value": manifest["path"]},
                    ],
                }
            )
    components.sort(key=lambda item: (item["name"].lower(), item["properties"][0]["value"]))
    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "version": 1,
        "metadata": {
            "properties": [
                {"name": "ucs:scope", "value": "phase2-control-plane-source-archive-only"},
                {"name": "ucs:resolution", "value": "declaration-only"},
                {"name": "ucs:vulnerability-posture", "value": "UNKNOWN"},
                {"name": "ucs:source-archive-sha256", "value": actual},
            ]
        },
        "components": components,
    }
    return report, sbom


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--declared-checksum", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--sbom-output", required=True, type=Path)
    args = parser.parse_args()
    report, sbom = scan_archive(args.archive, args.declared_checksum)
    write_json(args.output, report)
    write_json(args.sbom_output, sbom)
    print("PASS: declaration inventory generated; scope=PARTIAL; SBOM=DECLARATION_ONLY; vulnerability_posture=UNKNOWN")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
