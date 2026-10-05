#!/usr/bin/env python3
from pathlib import Path
import argparse, base64, gzip, hashlib, subprocess, sys, tempfile

ENCODED_SHA256 = "a608b9365dd57881cab1009cabfe24c1af0b7c59ec944e053a85c2c7d6f4251c"
BOOTSTRAP_SHA256 = "b20979eaf275754addfa573c29ac684bf04579c68bbe96c006363ae84cab28cc"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    root = Path(__file__).resolve().parent
    encoded_path = root / "source" / "control-plane-v9.1-bootstrap.py.gz.b64"
    encoded_bytes = encoded_path.read_bytes()
    if sha256(encoded_bytes) != ENCODED_SHA256:
        raise SystemExit("encoded payload SHA-256 mismatch")
    compressed = base64.b64decode(b"".join(encoded_bytes.split()), validate=True)
    bootstrap = gzip.decompress(compressed)
    if sha256(bootstrap) != BOOTSTRAP_SHA256:
        raise SystemExit("bootstrap SHA-256 mismatch")
    with tempfile.TemporaryDirectory(prefix="control-plane-v9-bootstrap-") as td:
        script = Path(td) / "bootstrap.py"
        script.write_bytes(bootstrap)
        subprocess.run([sys.executable, str(script), "--extract", args.out], check=True)
    print("PASS: extracted verified Production Control Plane v9.1 source")


if __name__ == "__main__":
    main()
