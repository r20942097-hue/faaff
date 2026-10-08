#!/usr/bin/env python3
"""Verify the committed runtime sources, then copy into a fresh directory."""
from pathlib import Path, PurePosixPath
import argparse, hashlib, json, os, stat

MANIFEST_SHA256 = "d1781cea9c28b9f7905329f126a1e183627ae42bb7d26b1393dd2c98499041a1"

def sha256(data):
    return hashlib.sha256(data).hexdigest()

def regular_file(path):
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError("source must be a regular file: " + str(path))
    return path.read_bytes()

def extract(root, out):
    manifest_bytes = regular_file(root / "runtime-manifest.json")
    if sha256(manifest_bytes) != MANIFEST_SHA256:
        raise ValueError("runtime manifest SHA-256 mismatch")
    manifest = json.loads(manifest_bytes)
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported manifest schema")
    sources = root / "runtime"
    if not stat.S_ISDIR(sources.lstat().st_mode):
        raise ValueError("runtime must be a real directory")
    expected = manifest["files"]
    actual = set()
    for current, dirs, files in os.walk(sources, followlinks=False):
        for name in dirs:
            if not stat.S_ISDIR((Path(current) / name).lstat().st_mode):
                raise ValueError("linked runtime directory")
        for name in files:
            actual.add((Path(current) / name).relative_to(sources).as_posix())
    if actual != set(expected):
        raise ValueError("runtime file set mismatch")
    checked = {}
    for name, identity in expected.items():
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or "\\" in name:
            raise ValueError("unsafe manifest path")
        data = regular_file(sources / name)
        if len(data) != identity["bytes"] or sha256(data) != identity["sha256"]:
            raise ValueError("runtime source identity mismatch: " + name)
        checked[name] = data
    # Validate everything before creating output; existing destinations fail closed.
    out.mkdir(parents=True, exist_ok=False)
    for name, data in checked.items():
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(data)
    print("PASS: extracted verified Production Control Plane v9.1 runtime (15 files)")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    extract(Path(__file__).resolve().parent, args.out)

if __name__ == "__main__":
    main()
