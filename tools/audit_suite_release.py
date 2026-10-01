#!/usr/bin/env python3
"""Offline, fail-closed audit of Universal Control Suite release archives.

The auditor never extracts or executes archive content.  It is intentionally
usable before a candidate workspace is trusted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import tempfile
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath
from typing import Iterable
from zipfile import BadZipFile, ZipFile, ZipInfo

DEFAULT_MEMBER_LIMIT = 128 * 1024 * 1024
DEFAULT_TOTAL_LIMIT = 1024 * 1024 * 1024
DEFAULT_ARCHIVE_LIMIT = 1024 * 1024 * 1024
DEFAULT_ENTRY_LIMIT = 10_000
DEFAULT_COMPRESSION_RATIO_LIMIT = 200
EXECUTABLE_SUFFIXES = {".bat", ".cmd", ".com", ".exe", ".msi", ".ps1", ".scr"}
WINDOWS_RESERVED_NAMES = {
    "con", "prn", "aux", "nul", "clock$",
    *(f"com{number}" for number in range(1, 10)),
    *(f"lpt{number}" for number in range(1, 10)),
}


@dataclass(frozen=True)
class Candidate:
    product: str
    version: str
    filename: str
    sha256: str
    executable_allowlist: tuple[str, ...] = ()


@dataclass
class AuditResult:
    product: str
    version: str
    filename: str
    status: str
    expected_sha256: str
    actual_sha256: str | None = None
    archive_size: int | None = None
    file_count: int | None = None
    extracted_size: int | None = None
    findings: list[str] = field(default_factory=list)


def _unsafe_name(name: str, *, directory: bool = False) -> str | None:
    if "\x00" in name:
        return "NUL byte in archive path"
    if "\\" in name:
        return "backslash in archive path"
    raw = name[:-1] if directory and name.endswith("/") else name
    parts = raw.split("/")
    path = PurePosixPath(raw)
    if path.is_absolute() or name.startswith("/"):
        return "absolute archive path"
    if path.parts and path.parts[0].endswith(":"):
        return "drive-qualified archive path"
    if any(part in {"", ".", ".."} for part in parts):
        return "non-canonical or traversing archive path"
    for part in parts:
        if part.rstrip(" .") != part:
            return "Windows-ambiguous trailing dot or space in archive path"
        stem = part.split(".", 1)[0].casefold()
        if stem in WINDOWS_RESERVED_NAMES:
            return "Windows reserved device name in archive path"
    return None


def _portable_name(name: str) -> str:
    """Return the cross-platform collision key used by release validation."""
    return unicodedata.normalize("NFC", name.rstrip("/")).casefold()


def _is_symlink(info: ZipInfo) -> bool:
    return stat.S_ISLNK((info.external_attr >> 16) & 0xFFFF)


def _unix_mode(info: ZipInfo) -> int:
    return (info.external_attr >> 16) & 0xFFFF if info.create_system == 3 else 0


def _sha256(stream) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def _open_candidate(path: Path):
    """Open once for hash+parse, refusing final-component symlinks where supported."""
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise OSError("candidate is not a regular file")
        return os.fdopen(descriptor, "rb"), metadata.st_size
    except BaseException:
        os.close(descriptor)
        raise


def _verify_crc_bounded(
    bundle: ZipFile, infos: list[ZipInfo], byte_limit: int
) -> str | None:
    """Stream every member with a hard actual-byte ceiling; never retain payloads."""
    consumed = 0
    try:
        for info in infos:
            if info.is_dir():
                continue
            member_size = 0
            with bundle.open(info, "r") as member:
                while chunk := member.read(min(1024 * 1024, byte_limit - consumed + 1)):
                    consumed += len(chunk)
                    member_size += len(chunk)
                    if consumed > byte_limit or member_size > info.file_size:
                        return f"{info.filename!r}: actual extracted size limit exceeded"
            if member_size != info.file_size:
                return f"{info.filename!r}: extracted size disagrees with ZIP metadata"
    except (BadZipFile, OSError, RuntimeError, EOFError) as exc:
        return f"CRC/content validation error: {type(exc).__name__}: {exc}"
    return None


def audit_candidate(
    root: Path,
    candidate: Candidate,
    *,
    member_limit: int = DEFAULT_MEMBER_LIMIT,
    total_limit: int = DEFAULT_TOTAL_LIMIT,
    entry_limit: int = DEFAULT_ENTRY_LIMIT,
    compression_ratio_limit: int = DEFAULT_COMPRESSION_RATIO_LIMIT,
    archive_limit: int = DEFAULT_ARCHIVE_LIMIT,
) -> AuditResult:
    result = AuditResult(
        candidate.product,
        candidate.version,
        candidate.filename,
        "NOT RUN",
        candidate.sha256.lower(),
    )
    archive = root / candidate.filename
    if archive.is_symlink():
        result.status = "FAIL"
        result.findings.append("candidate archive is not a regular, non-symlink file")
        return result
    if not archive.exists():
        result.findings.append("candidate archive is not present")
        return result
    if not archive.is_file():
        result.status = "FAIL"
        result.findings.append("candidate archive is not a regular, non-symlink file")
        return result
    try:
        # One no-follow handle eliminates hash-to-parse and stat-to-open path
        # replacement windows on platforms that expose O_NOFOLLOW.
        stream, result.archive_size = _open_candidate(archive)
        with stream:
            if result.archive_size > archive_limit:
                result.status = "FAIL"
                result.findings.append("archive size limit exceeded")
                return result
            result.actual_sha256 = _sha256(stream)
            if result.actual_sha256 != result.expected_sha256:
                result.status = "FAIL"
                result.findings.append("SHA-256 mismatch")
                return result
            stream.seek(0)
            with ZipFile(stream) as bundle:
                _inspect_bundle(
                    bundle,
                    result,
                    candidate,
                    member_limit,
                    total_limit,
                    entry_limit,
                    compression_ratio_limit,
                )
    except (BadZipFile, OSError, RuntimeError, EOFError) as exc:
        result.findings.append(f"ZIP validation error: {type(exc).__name__}: {exc}")

    result.status = "FAIL" if result.findings else "PASS"
    return result


def _inspect_bundle(
    bundle: ZipFile,
    result: AuditResult,
    candidate: Candidate,
    member_limit: int,
    total_limit: int,
    entry_limit: int,
    compression_ratio_limit: int,
) -> None:
    infos = bundle.infolist()
    result.file_count = len(infos)
    result.extracted_size = sum(info.file_size for info in infos)
    names: set[str] = set()
    portable_names: dict[str, str] = {}
    allowed = set(candidate.executable_allowlist)
    if len(infos) > entry_limit:
        result.findings.append("ZIP entry count limit exceeded")
    for info in infos:
        reason = _unsafe_name(info.filename, directory=info.is_dir())
        if reason:
            result.findings.append(f"{info.filename!r}: {reason}")
        if info.filename in names:
            result.findings.append(f"{info.filename!r}: duplicate ZIP entry")
        names.add(info.filename)
        portable = _portable_name(info.filename)
        prior = portable_names.get(portable)
        if prior is not None and prior != info.filename:
            result.findings.append(
                f"{info.filename!r}: portable path collision with {prior!r}"
            )
        portable_names[portable] = info.filename
        if _is_symlink(info):
            result.findings.append(f"{info.filename!r}: symbolic link entry")
        mode = _unix_mode(info)
        if mode & (stat.S_ISUID | stat.S_ISGID | stat.S_ISVTX):
            result.findings.append(f"{info.filename!r}: unsafe special permission bits")
        if mode & 0o111 and not info.is_dir() and info.filename not in allowed:
            result.findings.append(
                f"{info.filename!r}: unexpected executable permission"
            )
        if info.flag_bits & 0x1:
            result.findings.append(f"{info.filename!r}: encrypted entry")
        if info.file_size > member_limit:
            result.findings.append(
                f"{info.filename!r}: extracted member size limit exceeded"
            )
        if info.file_size and (
            info.compress_size == 0
            or info.file_size / info.compress_size > compression_ratio_limit
        ):
            result.findings.append(f"{info.filename!r}: compression ratio limit exceeded")
        if (
            not info.is_dir()
            and PurePosixPath(info.filename).suffix.lower() in EXECUTABLE_SUFFIXES
            and info.filename not in allowed
        ):
            result.findings.append(f"{info.filename!r}: unexpected executable")
    if result.extracted_size > total_limit:
        result.findings.append("total extracted size limit exceeded")
    # Do not decompress an archive after metadata has already identified
    # it as unsafe. This prevents CRC checking from becoming a bomb path.
    if not result.findings:
        crc_finding = _verify_crc_bounded(bundle, infos, total_limit)
        if crc_finding:
            result.findings.append(crc_finding)


def load_candidates(path: Path) -> list[Candidate]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("unsupported inventory schema_version")
    raw_candidates = data.get("candidates")
    if not isinstance(raw_candidates, list) or not raw_candidates:
        raise ValueError("inventory candidates must be a non-empty list")
    candidates = []
    filenames: set[str] = set()
    for raw in raw_candidates:
        if not isinstance(raw, dict):
            raise ValueError("inventory candidate must be an object")
        for field_name in ("product", "version", "filename", "sha256"):
            if not isinstance(raw.get(field_name), str) or not raw[field_name]:
                raise ValueError(f"candidate {field_name} must be a non-empty string")
        filename = raw["filename"]
        if _unsafe_name(filename) or len(PurePosixPath(filename).parts) != 1:
            raise ValueError(f"invalid candidate filename: {filename}")
        if not filename.casefold().endswith(".zip"):
            raise ValueError(f"candidate filename must end in .zip: {filename}")
        filename_key = _portable_name(filename)
        if filename_key in filenames:
            raise ValueError(f"duplicate candidate filename: {filename}")
        filenames.add(filename_key)
        digest = raw["sha256"].lower()
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError(f"invalid SHA-256 for {raw['filename']}")
        allowlist = raw.get("executable_allowlist", [])
        if not isinstance(allowlist, list) or not all(isinstance(item, str) for item in allowlist):
            raise ValueError(f"invalid executable_allowlist for {filename}")
        if len({_portable_name(item) for item in allowlist}) != len(allowlist):
            raise ValueError(f"duplicate executable_allowlist entry for {filename}")
        if any(_unsafe_name(item) for item in allowlist):
            raise ValueError(f"unsafe executable_allowlist entry for {filename}")
        candidates.append(
            Candidate(
                product=raw["product"],
                version=raw["version"],
                filename=filename,
                sha256=digest,
                executable_allowlist=tuple(allowlist),
            )
        )
    return candidates


def write_report(results: Iterable[AuditResult], output: Path) -> None:
    items = [asdict(result) for result in results]
    counts = {status: sum(item["status"] == status for item in items) for status in ("PASS", "FAIL", "NOT RUN")}
    overall = "FAIL" if counts["FAIL"] else ("NOT RUN" if counts["NOT RUN"] else "PASS")
    payload = {
        "schema_version": 2,
        "overall_status": overall,
        "summary": counts,
        "status_definitions": {
            "PASS": "verified by this invocation",
            "FAIL": "a check executed and failed",
            "NOT RUN": "artifact unavailable, so archive checks did not execute",
        },
        "results": items,
    }
    serialized = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", newline="\n", dir=output.parent, delete=False
        ) as temporary:
            temporary_name = temporary.name
            temporary.write(serialized)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, output)
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--allow-not-run",
        action="store_true",
        help="return success when candidates are absent (inspection only; never use for release gates)",
    )
    args = parser.parse_args(argv)
    candidates = load_candidates(args.inventory)
    results = [audit_candidate(args.artifact_dir, candidate) for candidate in candidates]
    write_report(results, args.output)
    print("\n".join(f"{item.status}: {item.filename}" for item in results))
    if any(item.status == "FAIL" for item in results):
        return 1
    if any(item.status == "NOT RUN" for item in results) and not args.allow_not_run:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
