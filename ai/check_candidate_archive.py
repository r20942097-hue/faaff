#!/usr/bin/env python3
"""Read-only candidate ZIP intake: no extraction, network, execution, or user secrets."""
from __future__ import annotations
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import zipfile

MAX_ENTRIES = 10000
MAX_BYTES = 256 * 1024 * 1024
MAX_MEMBER = 100 * 1024 * 1024
MAX_JSON = 1024 * 1024


class IntakeError(ValueError):
    pass


def check_zip(z: zipfile.ZipFile) -> None:
    infos = z.infolist()
    if len(infos) > MAX_ENTRIES or sum(i.file_size for i in infos) > MAX_BYTES:
        raise IntakeError("ZIP_SIZE_LIMIT")
    seen = set()
    for i in infos:
        name = i.filename
        parts = name.split("/")
        if (not name or name.startswith(("/", "\\")) or
            "\\" in name or "\x00" in name or ":" in parts[0] or
            any(part in ("", ".", "..") for part in parts[:-1]) or
            ".." in parts or
            (stat.S_IFMT(i.external_attr >> 16) == stat.S_IFLNK) or
            i.file_size > MAX_MEMBER or
            (i.file_size > 2_000_000 and i.file_size > max(i.compress_size, 1) * 1000)):
            raise IntakeError("UNSAFE_ZIP_MEMBER")
        if name in seen:
            raise IntakeError("DUPLICATE_ZIP_MEMBER")
        seen.add(name)
    if z.testzip() is not None:
        raise IntakeError("CRC_MISMATCH")


def read_json(z: zipfile.ZipFile, name: str) -> dict:
    info = z.getinfo(name)
    if info.file_size > MAX_JSON:
        raise IntakeError("JSON_LIMIT")
    data = json.loads(z.read(name))
    if not isinstance(data, dict):
        raise IntakeError("INVALID_JSON_OBJECT")
    return data


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_addons(z: zipfile.ZipFile) -> dict:
    manifest = read_json(z, "PACKAGE_MANIFEST.json")
    if len(manifest) != 6:
        raise IntakeError("ADDON_PACKAGE_COUNT")
    sums = {}
    for line in z.read("SHA256SUMS.txt").decode("utf-8").splitlines():
        m = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if not m or m.group(2) in sums:
            raise IntakeError("BAD_SHA256SUMS")
        sums[m.group(2)] = m.group(1)
    if set(sums) != set(z.namelist()) - {"SHA256SUMS.txt"}:
        raise IntakeError("SHA256SUMS_COVERAGE")
    for name, digest in sums.items():
        if hash_bytes(z.read(name)) != digest:
            raise IntakeError("SHA256SUMS_MISMATCH")
    entries = []
    groups = {}
    for basename, rec in sorted(manifest.items()):
        if (not isinstance(rec, dict) or rec.get("browser") not in ("Firefox", "Chrome") or
            not isinstance(rec.get("product"), str) or not rec["product"]):
            raise IntakeError("MANIFEST_INVALID")
        browser = rec["browser"]
        path = f"Extensions/{browser}/{basename}"
        if (not re.fullmatch(r"[A-Za-z0-9_.-]+\.zip", basename) or
            not basename.endswith(f"_{browser}_MV3.zip")):
            raise IntakeError("BAD_NESTED_PATH")
        raw = z.read(path)
        if len(raw) != rec.get("bytes") or hash_bytes(raw) != rec.get("sha256"):
            raise IntakeError("NESTED_ARCHIVE_HASH")
        with zipfile.ZipFile(io.BytesIO(raw)) as inner:
            check_zip(inner)
            mm = read_json(inner, "manifest.json")
            if mm.get("manifest_version") != 3 or mm.get("version") != rec.get("version"):
                raise IntakeError("MANIFEST_VERSION_MISMATCH")
            if browser == "Firefox":
                gecko = (mm.get("browser_specific_settings") or {}).get("gecko") or {}
                if not gecko.get("id"):
                    raise IntakeError("FIREFOX_GECKO_ID_MISSING")
            entries.append({
                "product": rec["product"], "browser": browser,
                "version": mm["version"], "files": len(inner.infolist()),
                "manifest_v3": True, "sha256_verified": True, "crc_verified": True,
            })
            groups.setdefault(rec["product"], []).append((browser, mm["version"]))
    if len(groups) != 3 or any(sorted(k for k, _ in vals) != ["Chrome", "Firefox"]
                               or len({v for _, v in vals}) != 1 for vals in groups.values()):
        raise IntakeError("PRODUCT_BROWSER_PAIR_MISMATCH")
    return {"type": "three_addons", "package_count": len(entries),
            "checksum_file_entries": len(sums), "packages": entries,
            "qa_claim_only": read_json(z, "QA_REPORT.json").get("status"),
            "status": "CANDIDATE_NOT_RELEASED"}


def verify_rplay(z: zipfile.ZipFile) -> dict:
    head = z.read("DEVELOPMENT_HANDOFF_v2.68.0.md")[:2048].decode("utf-8")
    if "NO GO" not in head and "NO_GO" not in head:
        raise IntakeError("RPLAY_CANDIDATE_GATE_UNCONFIRMED")
    versions = []
    for path in ("rplay-stable-player-extension/manifest.json",
                 "rplay-stable-player-extension-firefox/manifest.json"):
        m = read_json(z, path)
        if m.get("manifest_version") != 3:
            raise IntakeError("RPLAY_MANIFEST_NOT_MV3")
        versions.append(m.get("version"))
    if versions != ["2.68.0", "2.68.0"]:
        raise IntakeError("RPLAY_VERSION_MISMATCH")
    names = z.namelist()
    return {"type": "rplay", "version": "2.68.0",
            "js_source_files": sum(n.startswith("src/") and n.endswith(".js") for n in names),
            "python_test_modules": sum(n.startswith("tests/") and n.endswith(".py") for n in names),
            "status": "NO_GO", "real_browser_test": "NOT_RUN"}


def inspect(path: Path, kind: str) -> dict:
    if not path.is_file() or path.suffix.lower() != ".zip":
        raise IntakeError("ZIP_INPUT_REQUIRED")
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            sha.update(chunk)
    with zipfile.ZipFile(path) as z:
        check_zip(z)
        names = set(z.namelist())
        if kind == "auto":
            kind = "three_addons" if "PACKAGE_MANIFEST.json" in names else "rplay"
        detail = verify_addons(z) if kind == "three_addons" else verify_rplay(z)
        return {"schema": "source-intake/v1", "sha256": sha.hexdigest(),
                "size_bytes": path.stat().st_size, "zip_crc": "PASS",
                "entry_count": len(z.infolist()), "read_only": True, **detail}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--kind", choices=["auto", "rplay", "three_addons"], default="auto")
    args = parser.parse_args()
    try:
        print(json.dumps(inspect(args.archive, args.kind), ensure_ascii=False, indent=2))
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, UnicodeError) as exc:
        # Never echo raw paths, archive data, credentials, or exception strings.
        code = str(exc) if isinstance(exc, IntakeError) else "INVALID_OR_CORRUPT_ARCHIVE"
        print(json.dumps({"schema": "source-intake/v1", "status": "REJECTED", "reason": code}))
        sys.exit(2)
