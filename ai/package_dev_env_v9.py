#!/usr/bin/env python3
"""Build a deterministic allowlisted development environment ZIP. Never product GO."""
import argparse
import hashlib
import json
import stat
import sys
import zipfile
from pathlib import Path

FILES = (
    "ai/DEV_ENV_V9.md",
    "ai/requirements-browser.txt",
    "ai/opfs_worker_sync_fixture.py",
    "ai/test_opfs_worker_sync_fixture.py",
    "ai/chromium_renderer_crash_fixture.py",
    "ai/test_chromium_renderer_crash_fixture.py",
    "ai/opfs_restart_fixture.py",
    "ai/test_opfs_restart_fixture.py",
    ".github/workflows/opfs-worker-sync-fixture.yml",
    ".github/workflows/chromium-renderer-crash.yml",
)
README = """# 開発環境 v9｜合成OPFS検証パッケージ

- ブラウザー専用プロファイルのDedicated Worker同期OPFS / flush / 排他制御 / 再起動検証
- Chromiumレンダラークラッシュからの確定済みセグメント復旧検証
- GitHub Actions用2種類のワークフローと17件の単体テスト
- 収録ファイルのSHA-256をMANIFEST_SHA256.jsonで確認可能

実行手順と限界事項は ai/DEV_ENV_V9.md を参照してください。
このZIPには実製品のソース・録画・認証情報を含めていません。
実製品のE2E・停電・実ディスク耐障害はNOT_RUN、製品リリースNO_GOです。
"""
ZIP_DATE=(2020,1,1,0,0,0)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def read_inputs(root):
    root=Path(root).resolve(strict=True)
    entries={}
    for relative in FILES:
        p=root / relative
        if p.is_symlink() or not p.is_file():
            raise ValueError("MISSING_OR_UNSAFE_ALLOWLIST_FILE")
        content=p.read_bytes()
        if len(content)>2_000_000:
            raise ValueError("SOURCE_EXCEEDS_PACKAGE_BUDGET")
        entries[relative]=content
    return entries

def make_zip(root,destination,evidence_path=None):
    entries=read_inputs(root)
    manifest={
        "schema":"dev-env-v9-source-manifest/v1",
        "scope":"synthetic_browser_test_tools_only",
        "release_readiness":"NO_GO",
        "real_product_e2e":"NOT_RUN",
        "files":[{"path":name,"sha256":sha(data),"bytes":len(data)}
                 for name,data in sorted(entries.items())]
    }
    entries["README_JA.md"]=README.encode("utf-8")
    manifest["files"].append({"path":"README_JA.md",
                                "sha256":sha(entries["README_JA.md"]),
                                "bytes":len(entries["README_JA.md"])})
    entries["MANIFEST_SHA256.json"]=(json.dumps(
        manifest,ensure_ascii=False,indent=2,sort_keys=True)+"\n").encode("utf-8")
    destination=Path(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(destination,"w",compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9) as archive:
        for name,bytes_ in sorted(entries.items()):
            info=zipfile.ZipInfo(name,date_time=ZIP_DATE)
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=(stat.S_IFREG | 0o644)<<16
            archive.writestr(info,bytes_,compress_type=zipfile.ZIP_DEFLATED,
                             compresslevel=9)
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("CRC_FAILURE")
        if sorted(archive.namelist())!=sorted(entries):
            raise RuntimeError("PACKAGE_INVENTORY_MISMATCH")
        for entry in manifest["files"]:
            if sha(archive.read(entry["path"]))!=entry["sha256"]:
                raise RuntimeError("PACKAGE_SHA256_FAILURE")
    evidence={
        "schema":"dev-env-v9-package-evidence/v1",
        "archive_sha256":sha(destination.read_bytes()),
        "zip_member_count":len(entries),
        "verified_file_count":len(manifest["files"]),
        "crc":"PASS",
        "file_sha256":"PASS",
        "release_readiness":"NO_GO",
        "real_product_e2e":"NOT_RUN",
    }
    if evidence_path is not None:
        p=Path(evidence_path)
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+"\n",
                     encoding="utf-8")
    return evidence

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",default=".")
    parser.add_argument("--output",required=True)
    parser.add_argument("--evidence")
    args=parser.parse_args(argv)
    report=make_zip(args.root,args.output,args.evidence)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0

if __name__=="__main__":
    sys.exit(main())
