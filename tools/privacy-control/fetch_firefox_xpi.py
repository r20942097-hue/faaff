"""Download and verify official signed uBlock Origin XPI for isolated Firefox CI."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
LOCKFILE = HERE / "verification/firefox-ubo-xpi-lock.json"


def verify_lock(lock):
    if (lock.get("schema") != "upc-firefox-ubo-xpi-lock/v1"
            or lock.get("repository") != "gorhill/uBlock"
            or lock.get("tag") != "1.75.0"
            or lock.get("asset") != "uBlock0_1.75.0.firefox.signed.xpi"
            or lock.get("url") !=
            "https://github.com/gorhill/uBlock/releases/download/1.75.0/uBlock0_1.75.0.firefox.signed.xpi"
            or lock.get("size") != 4650100
            or not re.fullmatch(r"[0-9a-f]{64}", lock.get("sha256", ""))
            or lock.get("publication") != "NO_GO"):
        raise ValueError("unapproved XPI source or digest")
    return True


def verify_bytes(data, lock):
    verify_lock(lock)
    if len(data) != lock["size"] or sha256(data).hexdigest() != lock["sha256"]:
        raise ValueError("official signed XPI size/SHA-256 mismatch")
    return True


def download(lock):
    verify_lock(lock)
    with urlopen(Request(lock["url"], headers={
            "User-Agent": "UPC-isolated-Firefox-lab/1.0"}), timeout=45) as response:
        return response.read(lock["size"] + 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        path = args.output.resolve()
        if path.is_relative_to(REPO.resolve()) or path.suffix != ".xpi":
            raise ValueError("write XPI only outside checkout")
        if path.exists():
            raise ValueError("refuse to overwrite existing XPI")
        lock = json.loads(LOCKFILE.read_text(encoding="utf-8"))
        content = download(lock)
        verify_bytes(content, lock)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        print("UPC FIREFOX XPI PIN PASS:", lock["tag"], lock["sha256"])
        return 0
    except (OSError, ValueError, TypeError, KeyError) as err:
        print("UPC FIREFOX XPI PIN FAIL:", err, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
