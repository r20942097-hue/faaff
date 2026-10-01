#!/usr/bin/env python3
"""Build a deterministic Phase 2 source ZIP and detached SHA-256 file."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path, PurePosixPath
import stat
import zipfile


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--archive", type=Path, default=Path(__file__).with_name("ucs-control-plane-phase2-source.zip"))
    parser.add_argument("--checksum", type=Path, default=Path(__file__).with_name("SOURCE-ARCHIVE-SHA256.txt"))
    args = parser.parse_args()
    source = args.source_dir.resolve(strict=True)
    archive_path = args.archive.resolve()
    checksum_path = args.checksum.resolve()
    candidates: list[tuple[str, Path]] = []
    for path in source.rglob("*"):
        if path.is_dir():
            continue
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"source entry is not a regular file: {path}")
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        name = path.relative_to(source).as_posix()
        pure = PurePosixPath(name)
        if pure.is_absolute() or ".." in pure.parts or "\\" in name:
            raise ValueError(f"unsafe source path: {name}")
        if name in {"SHA256SUMS.txt", "SOURCE-ARCHIVE-SHA256.txt", archive_path.name}:
            continue
        candidates.append((name, path))
    names = [name for name, _ in candidates]
    if len(names) != len(set(names)) or len({name.casefold() for name in names}) != len(names):
        raise ValueError("duplicate source path")
    if not candidates:
        raise ValueError("empty source tree")

    sums = [f"{sha256(path.read_bytes())}  {name}" for name, path in sorted(candidates)]
    sums_path = source / "SHA256SUMS.txt"
    sums_path.write_text("\n".join(sums) + "\n", encoding="utf-8", newline="\n")
    candidates.append(("SHA256SUMS.txt", sums_path))
    candidates.sort(key=lambda item: item[0])

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, path in candidates:
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.create_system = 3
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    checksum_path.parent.mkdir(parents=True, exist_ok=True)
    checksum_path.write_text(f"{sha256(archive_path.read_bytes())}  {archive_path.name}\n", encoding="utf-8", newline="\n")
    print(f"Built {archive_path} ({archive_path.stat().st_size} bytes, {len(candidates)} entries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
