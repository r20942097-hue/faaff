"""Fetch all 39 pinned source components included by official EasyPrivacy template.

Never retrieves an unpinned 'latest' list; this creates test inputs in an
isolated directory only. A byte change, include mismatch or failed download
prevents the entire candidate benchmark. No filters or binaries are published.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import sys

from fetch_stock import blob_sha, download, validate_bytes

HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[1]
LOCK_FILE = HERE / "verification/full-stock-source-lock.json"
TEMPLATE = "easyprivacy.template"
SOURCE_COUNT = 39
TOTAL_BYTES = 1_508_164


def validate_lock(lock):
    rows = lock.get("files")
    template = lock.get("template")
    if (lock.get("schema") != "upc-easyprivacy-template-lock/v1"
            or lock.get("source_repository") != "easylist/easylist"
            or lock.get("scope") !=
            "PINNED_OFFICIAL_EASYPRIVACY_TEMPLATE_COMPONENTS_NOT_VERIFIED_DISTRIBUTION_BUILD"
            or not re.fullmatch(r"[0-9a-f]{40}", lock.get("upstream_commit", ""))
            or not isinstance(template, dict)
            or template.get("path") != TEMPLATE
            or template.get("size") != 3557
            or not re.fullmatch(r"[0-9a-f]{40}", template.get("git_blob_sha", ""))
            or not isinstance(rows, list) or len(rows) != SOURCE_COUNT):
        raise ValueError("full template source lock invalid")
    paths = []
    for record in rows:
        path = record.get("path", "")
        if (not re.fullmatch(r"(template_header\.txt|easyprivacy/[a-z0-9_-]+\.txt)", path)
                or type(record.get("size")) is not int
                or not 100 <= record["size"] <= 500_000
                or not re.fullmatch(r"[0-9a-f]{40}", record.get("git_blob_sha", ""))):
            raise ValueError("unsafe or invalid upstream source record")
        paths.append(path)
    if (len(set(paths)) != SOURCE_COUNT or paths[0] != "template_header.txt"
            or not paths[-1].endswith("/easyprivacy_allowlist_international.txt")
            or sum(x["size"] for x in rows) != TOTAL_BYTES):
        raise ValueError("source set cardinality/order/size mismatch")
    return True


def fetch_all(lock, reader):
    validate_lock(lock)
    commit = lock["upstream_commit"]
    base = "https://raw.githubusercontent.com/easylist/easylist/" + commit + "/"
    template = lock["template"]
    template_bytes = reader(base + TEMPLATE, template["size"] + 1)
    validate_bytes(template_bytes, template)
    decoded = template_bytes.decode("utf-8", errors="strict")
    includes = re.findall(r"^%include easylist:([^%]+)%$", decoded, re.MULTILINE)
    expected = [row["path"] for row in lock["files"]]
    if includes != expected:
        raise ValueError("template include paths changed or unaccounted source added")
    if any(line.startswith("%include") and not
           re.fullmatch(r"%include easylist:[^%]+%", line)
           for line in decoded.splitlines()):
        raise ValueError("unknown template include directive")

    def get_one(entry):
        url = base + entry["path"]
        content = reader(url, entry["size"] + 1)
        digest = validate_bytes(content, entry)
        return (entry["path"], content, {
            "path": entry["path"], "git_blob_sha": entry["git_blob_sha"],
            "bytes": len(content), "sha256": digest})

    # Threads reduce CI latency; preserve template sequence in result collection.
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(get_one, lock["files"]))
    blobs = {name: content for name, content, _ in results}
    manifest = [record for _, _, record in results]
    return blobs, manifest, {
        "path": TEMPLATE, "git_blob_sha": template["git_blob_sha"],
        "bytes": len(template_bytes),
        "verified": True
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        target = args.output_dir.resolve()
        source_root = REPOSITORY.resolve()
        if target == source_root or target.is_relative_to(source_root):
            raise ValueError("source checkout must remain read-only")
        if target.exists() and any(target.iterdir()):
            raise ValueError("refusing to reuse a non-empty directory")
        lock = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
        blobs, records, template = fetch_all(lock, download)
        target.mkdir(parents=True, exist_ok=True)
        for name, content in blobs.items():
            path = target / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        (target / "verified-sources.json").write_text(
            json.dumps({
                "schema": "upc-verified-stock-sources/v1",
                "source_repository": lock["source_repository"],
                "upstream_commit": lock["upstream_commit"],
                "scope": lock["scope"], "template": template,
                "files": records,
                "source_components": len(records),
                "total_bytes": sum(x["bytes"] for x in records),
                "real_enabled_stock_lists": "NOT_VERIFIED",
                "publication": "NO_GO",
            }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("UPC FULL TEMPLATE SOURCE PASS:", len(records), "verified",
              sum(len(x) for x in blobs.values()),
              "bytes; actual distribution build NOT_VERIFIED")
        return 0
    except (OSError, ValueError, KeyError, TypeError, UnicodeError) as error:
        print("UPC FULL TEMPLATE SOURCE FAIL:", error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
