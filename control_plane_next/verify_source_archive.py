#!/usr/bin/env python3
"""Verify and test the Phase 2 source archive before accepting a PR."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent
ARCHIVE = ROOT / "ucs-control-plane-phase2-source.zip"
ARCHIVE_NAME = ARCHIVE.name
MAX_UNCOMPRESSED = 10 * 1024 * 1024
EVIDENCE_NAME = "evidence/phase2-local-verification.json"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_manifest(data: bytes) -> dict[str, str]:
    result: dict[str, str] = {}
    for line_number, raw in enumerate(data.decode("utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        match = re.fullmatch(r"([0-9a-f]{64})  ([^\r\n]+)", raw)
        if not match:
            raise ValueError(f"invalid SHA256SUMS line {line_number}")
        sha, name = match.groups()
        if name in result:
            raise ValueError(f"duplicate SHA256SUMS path: {name}")
        result[name] = sha
    return result


def main() -> int:
    declared = (ROOT / "SOURCE-ARCHIVE-SHA256.txt").read_text(encoding="utf-8").strip()
    match = re.fullmatch(r"([0-9a-f]{64})  " + re.escape(ARCHIVE_NAME), declared)
    if not match:
        raise ValueError("invalid SOURCE-ARCHIVE-SHA256.txt")
    archive_bytes = ARCHIVE.read_bytes()
    if digest(archive_bytes) != match.group(1):
        raise ValueError("source ZIP SHA-256 mismatch")

    with zipfile.ZipFile(ARCHIVE) as archive:
        infos = archive.infolist()
        if not infos:
            raise ValueError("source ZIP is empty")
        names: list[str] = []
        seen: set[str] = set()
        total_size = 0
        for info in infos:
            name = info.filename
            path = PurePosixPath(name)
            mode = info.external_attr >> 16
            if path.is_absolute() or ".." in path.parts or "\\" in name or "\x00" in name or re.match(r"^[A-Za-z]:", name):
                raise ValueError(f"unsafe ZIP path: {name!r}")
            if not name or name.endswith("/") or name in seen or name.casefold() in {x.casefold() for x in seen}:
                raise ValueError(f"duplicate or unsupported ZIP entry: {name!r}")
            if stat.S_ISLNK(mode):
                raise ValueError(f"symlink ZIP entry: {name!r}")
            seen.add(name)
            names.append(name)
            total_size += info.file_size
            if total_size > MAX_UNCOMPRESSED:
                raise ValueError("source ZIP exceeds uncompressed size limit")
        bad_entry = archive.testzip()
        if bad_entry:
            raise ValueError(f"ZIP CRC failure: {bad_entry}")
        if ARCHIVE_NAME in seen or "SOURCE-ARCHIVE-SHA256.txt" in seen:
            raise ValueError("recursive source archive checksum entry")
        required = {"README.md", "SHA256SUMS.txt", "pyproject.toml", EVIDENCE_NAME}
        if not required.issubset(seen):
            raise ValueError(f"missing required ZIP entries: {sorted(required - seen)}")

        contents = {name: archive.read(name) for name in names}
        sums = parse_manifest(contents["SHA256SUMS.txt"])
        if EVIDENCE_NAME not in sums:
            raise ValueError("SHA256SUMS.txt must checksum verification evidence")
        if set(sums) != seen - {"SHA256SUMS.txt"}:
            raise ValueError("SHA256SUMS.txt does not cover every other ZIP entry")
        for name, expected in sums.items():
            if digest(contents[name]) != expected:
                raise ValueError(f"internal SHA-256 mismatch: {name}")

        evidence = json.loads(contents[EVIDENCE_NAME])
        records = evidence.get("files")
        if not isinstance(records, list):
            raise ValueError("evidence files inventory must be an array")
        evidence_paths: set[str] = set()
        for record in records:
            name = record.get("path")
            if not isinstance(name, str) or name == EVIDENCE_NAME or name in evidence_paths:
                raise ValueError(f"invalid or self-referencing evidence path: {name!r}")
            if name not in contents:
                raise ValueError(f"evidence inventory path missing from ZIP: {name}")
            body = contents[name]
            if record.get("size") != len(body) or record.get("sha256") != digest(body):
                raise ValueError(f"evidence inventory mismatch: {name}")
            evidence_paths.add(name)
        expected_paths = {"README.md", "baseline/verified-candidate-baseline.json", "pyproject.toml"}
        expected_paths.update(name for name in names if name.startswith("tests/") and name.endswith(".py"))
        expected_paths.update(name for name in names if name.startswith("ucs_control_plane/") and name.endswith(".py"))
        if evidence_paths != expected_paths:
            raise ValueError("evidence inventory is incomplete")

        with tempfile.TemporaryDirectory(prefix="ucs-phase2-verify-") as temp_dir:
            source_root = Path(temp_dir) / "source"
            source_root.mkdir()
            archive.extractall(source_root)
            rebuilt = Path(temp_dir) / ARCHIVE_NAME
            rebuilt_sum = Path(temp_dir) / "SOURCE-ARCHIVE-SHA256.txt"
            subprocess.run([
                sys.executable, str(ROOT / "build_source_archive.py"),
                "--source-dir", str(source_root), "--archive", str(rebuilt), "--checksum", str(rebuilt_sum),
            ], check=True, stdout=subprocess.DEVNULL)
            if rebuilt.read_bytes() != archive_bytes:
                raise ValueError("deterministic rebuild differs from committed source ZIP")
            subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], cwd=source_root, check=True, stdout=subprocess.DEVNULL)
            subprocess.run([sys.executable, "-m", "compileall", "-q", "ucs_control_plane", "tests"], cwd=source_root, check=True)
    print(f"PASS: ZIP SHA-256, {len(infos)} entries, CRC, safe paths, both checksum inventories, tests, compileall")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError, zipfile.BadZipFile, subprocess.CalledProcessError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
