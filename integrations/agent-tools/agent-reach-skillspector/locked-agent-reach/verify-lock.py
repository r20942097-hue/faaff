#!/usr/bin/env python3
"""Review checked-in uv lock provenance and confirm resolved runtime matches it."""
from __future__ import annotations
import importlib.metadata as metadata
import re
from pathlib import Path
import tomllib
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
COMMIT = "beabda7486e9a666360b18cdb5c0e759c2c4d20f"
ALLOWED_PACKAGE_HOSTS = {"files.pythonhosted.org"}
EXPECTED = {"agent-reach": "1.6.0", "yt-dlp": "2026.8.19"}
SHA = re.compile(r"sha256:[0-9a-f]{64}\Z")

project = tomllib.loads((HERE / "pyproject.toml").read_text(encoding="utf-8"))
lock = tomllib.loads((HERE / "uv.lock").read_text(encoding="utf-8"))
assert project["project"]["requires-python"] == ">=3.12,<3.13"
assert project["project"]["dependencies"] == ["agent-reach==1.6.0"]
source = project["tool"]["uv"]["sources"]["agent-reach"]
assert source["rev"] == COMMIT
packages = lock["package"]
names = {p["name"]: p for p in packages}
assert len(names) == len(packages) and len(packages) >= 15
assert lock["requires-python"] == "==3.12.*"
for name, version in EXPECTED.items():
    assert names[name]["version"] == version, name
    assert metadata.version(name) == version, f"Installed {name} differs from locked version"

git_source = names["agent-reach"]["source"]
assert git_source["git"].startswith("https://github.com/Panniantong/Agent-Reach.git?rev=" + COMMIT + "#")
assert git_source["git"].endswith(COMMIT)
hash_count = 0
for package in packages:
    if package["name"] in ("agent-reach", "faaff-agent-reach-validation"):
        continue
    assert package["source"] == {"registry": "https://pypi.org/simple"}, package["name"]
    files = ([package["sdist"]] if "sdist" in package else []) + package.get("wheels", [])
    assert files, f"No locked distribution for {package['name']}"
    for dist in files:
        assert SHA.fullmatch(dist["hash"]), package["name"]
        assert urlparse(dist["url"]).hostname in ALLOWED_PACKAGE_HOSTS
        hash_count += 1
assert hash_count >= 100, "Checksum coverage unexpectedly shrank"
print(f"PASS: immutable Agent-Reach Git SHA, {len(packages)} locked packages, "
      f"{hash_count} distribution SHA256 hashes, installed versions match")
