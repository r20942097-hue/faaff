#!/usr/bin/env python3
"""Deterministic, allowlisted source ZIP for isolated OPFS v10 tools; no product GO."""
import argparse
import hashlib
import json
import stat
import sys
import zipfile
from pathlib import Path

FILES=(
    "ai/DEV_ENV_V10.md",
    "ai/requirements-browser.txt",
    "ai/requirements-process.txt",
    "ai/opfs_restart_fixture.py",
    "ai/chromium_renderer_crash_fixture.py",
    "ai/test_chromium_renderer_crash_fixture.py",
    "ai/opfs_process_kill_fixture.py",
    "ai/test_opfs_process_kill_fixture.py",
    "ai/opfs_worker_sync_fixture.py",
    "ai/test_opfs_worker_sync_fixture.py",
    "ai/package_dev_env_v10.py",
    "ai/test_package_dev_env_v10.py",
    ".github/workflows/opfs-process-kill.yml",
    ".github/workflows/opfs-worker-sync-fixture.yml",
    ".github/workflows/chromium-renderer-crash.yml",
    ".github/workflows/package-dev-environment-v10.yml",
)
README="""# 開発環境 v10 — 再現可能な合成OPFS検証

対象：Chromium / Firefox。
Dedicated Worker / 同期OPFS / flush / プロセス強制終了と復旧を検証します。
ユーザーの実ブラウザープロファイルや本番製品は使いません。

導入と実行手順: ai/DEV_ENV_V10.md
配布元の検証ファイル: MANIFEST_SHA256.json
ZIPソースはすべて許可リストから収録し、CRC / SHA-256で検証しました。
実製品E2E、停電・OSクラッシュ、RPLAY保存修正はNOT_RUN。
製品リリース判定: NO_GO
"""
FIXED_DATE=(2020,1,1,0,0,0)

def digest(data):
    return hashlib.sha256(data).hexdigest()

def collect(root):
    root=Path(root).resolve(strict=True)
    entries={}
    for name in FILES:
        file=root/name
        if file.is_symlink() or not file.is_file():
            raise ValueError("MISSING_OR_UNSAFE_SOURCE")
        source=file.read_bytes()
        if not source or len(source)>2_000_000:
            raise ValueError("INVALID_SOURCE_SIZE")
        entries[name]=source
    return entries

def build(root, output, evidence=None):
    entries=collect(root)
    entries["README_JA.md"]=README.encode("utf-8")
    manifest={
        "schema":"development-environment-v10-package/v1",
        "product_e2e":"NOT_RUN",
        "release_readiness":"NO_GO",
        "files":[{"path":name,"sha256":digest(data),"bytes":len(data)}
                 for name,data in sorted(entries.items())],
    }
    entries["MANIFEST_SHA256.json"]=(json.dumps(
        manifest,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode("utf-8")
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,"w",compression=zipfile.ZIP_DEFLATED) as archive:
        for name,data in sorted(entries.items()):
            info=zipfile.ZipInfo(name,date_time=FIXED_DATE)
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=(stat.S_IFREG|0o644)<<16
            archive.writestr(info,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("CRC_FAILURE")
        if sorted(archive.namelist())!=sorted(entries):
            raise RuntimeError("ZIP_MEMBER_LIST_MISMATCH")
        for file in manifest["files"]:
            if digest(archive.read(file["path"]))!=file["sha256"]:
                raise RuntimeError("SHA256_MISMATCH")
    record={
        "schema":"development-environment-v10-evidence/v1",
        "archive_sha256":digest(output.read_bytes()),
        "members":len(entries),
        "sha256_verified":len(manifest["files"]),
        "zip_crc":"PASS",
        "sha256_integrity":"PASS",
        "product_e2e":"NOT_RUN",
        "release_readiness":"NO_GO",
    }
    if evidence is not None:
        dest=Path(evidence)
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n",
                        encoding="utf-8")
    return record

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root",default=".")
    p.add_argument("--output",required=True)
    p.add_argument("--evidence")
    args=p.parse_args(argv)
    print(json.dumps(build(args.root,args.output,args.evidence),ensure_ascii=False,indent=2))
    return 0

if __name__=="__main__":
    sys.exit(main())
