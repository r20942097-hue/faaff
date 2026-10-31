"""Fetch immutable EasyPrivacy source fragments for an ISOLATED test run.

Downloads are hash-checked against Git blob IDs and sizes; no source files,
network traffic, credentials or raw rules are committed. Not the full published
EasyPrivacy subscription, and not the user's active filter configuration.
"""
import argparse
from hashlib import sha1, sha256
import json
from pathlib import Path
import re
import sys
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
LOCK = HERE / "verification/stock-source-lock.json"
PATHS = (
    "easyprivacy/easyprivacy_thirdparty.txt",
    "easyprivacy/easyprivacy_trackingservers_thirdparty.txt",
    "easyprivacy/easyprivacy_general.txt",
    "easyprivacy/easyprivacy_specific.txt",
    "easyprivacy/easyprivacy_allowlist.txt",
)


def blob_sha(content):
    return sha1(b"blob " + str(len(content)).encode("ascii") + b"\0" + content).hexdigest()


def verify_lock(lock):
    if (lock.get("schema") != "upc-stock-source-lock/v1"
            or lock.get("source_repository") != "easylist/easylist"
            or lock.get("scope") != "SELECTED_EASYPRIVACY_SOURCE_COMPONENTS_ONLY_NOT_COMPLETE_COMPILED_LIST"
            or not re.fullmatch(r"[a-f0-9]{40}", lock.get("upstream_commit", ""))
            or not isinstance(lock.get("files"), list)
            or [entry.get("path") for entry in lock["files"]] != list(PATHS)):
        raise ValueError("stock manifest invalid or scope enlarged without review")
    for entry in lock["files"]:
        if (type(entry.get("size")) is not int
                or not 100 <= entry["size"] <= 500_000
                or not re.fullmatch(r"[0-9a-f]{40}", entry.get("git_blob_sha", ""))):
            raise ValueError("invalid immutable stock source record")
    return True


def validate_bytes(content, record):
    if len(content) != record["size"] or blob_sha(content) != record["git_blob_sha"]:
        raise ValueError("upstream data size or Git blob hash mismatch: " + record["path"])
    return sha256(content).hexdigest()


def fetch(lock, read):
    verify_lock(lock)
    blobs = {}
    manifest = []
    commit = lock["upstream_commit"]
    for rec in lock["files"]:
        path = rec["path"]
        url = "https://raw.githubusercontent.com/easylist/easylist/" + commit + "/" + path
        data = read(url, rec["size"] + 1)
        checksum = validate_bytes(data, rec)
        blobs[path] = data
        manifest.append({"path": path, "git_blob_sha": rec["git_blob_sha"],
                         "sha256": checksum, "bytes": len(data)})
    return blobs, manifest


def download(url, limit):
    request = Request(url, headers={"User-Agent": "UPC-pinned-source-CI/1.0"})
    with urlopen(request, timeout=25) as response:
        content = response.read(limit)
    if len(content) >= limit:
        raise ValueError("upstream source exceeded pinned size")
    return content


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        target = args.output_dir.resolve()
        if target == REPO.resolve() or target.is_relative_to(REPO.resolve()):
            raise ValueError("read-only repository: output must be outside checkout")
        if target.exists() and any(target.iterdir()):
            raise ValueError("refusing reuse of non-empty output directory")
        lock = json.loads(LOCK.read_text(encoding="utf-8"))
        blobs, observed = fetch(lock, download)
        target.mkdir(parents=True, exist_ok=True)
        for path, data in blobs.items():
            location = target / path
            location.parent.mkdir(parents=True, exist_ok=True)
            location.write_bytes(data)
        (target / "verified-sources.json").write_text(
            json.dumps({"schema": "upc-verified-stock-sources/v1",
                        "source_repository": lock["source_repository"],
                        "upstream_commit": lock["upstream_commit"],
                        "scope": lock["scope"], "files": observed,
                        "real_enabled_stock_lists": "NOT_VERIFIED",
                        "publication": "NO_GO"}, indent=2) + "\n",
            encoding="utf-8")
        print("UPC STOCK SOURCE: PASS", len(blobs),
              "immutable selected components,",
              sum(len(value) for value in blobs.values()), "bytes; no publication")
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print("UPC STOCK SOURCE: FAIL:", error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
