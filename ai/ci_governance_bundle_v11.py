#!/usr/bin/env python3
"""Deterministic audit-only ZIP with SHA-256 inventory. No executable product assets."""
import argparse
import hashlib
import json
import stat
import sys
import zipfile
from pathlib import Path

from ai.ci_workflow_audit import audit

FIXED_DATE=(2020,1,1,0,0,0)
CORE=(
    "ai/ci_workflow_audit.py",
    "ai/test_ci_workflow_audit.py",
    "ai/requirements-ci-audit.txt",
    "ai/CI_GOVERNANCE_V11.md",
)
README="""# CI Governance v11 — workflow audit source package

GitHub Actionsの重複実行制御、SHA固定、最小権限、YAML解析を検査します。
これは製品配布版ではありません。監査対象のworkflow原本と検証コードを収録します。
実製品の録画動作・障害復旧はNOT_RUN。製品リリースはNO_GO。
"""

def sha(data):
    return hashlib.sha256(data).hexdigest()

def collect(root):
    root=Path(root).resolve(strict=True)
    status=audit(root)
    if status["status"]!="PASS":
        raise ValueError("WORKFLOW_AUDIT_MUST_PASS")
    paths=list(CORE)
    paths.extend(str(x.relative_to(root)).replace("\\","/")
                 for x in sorted((root/".github"/"workflows").iterdir())
                 if x.suffix in (".yml",".yaml"))
    entries={}
    for name in sorted(set(paths)):
        target=root/name
        if target.is_symlink() or not target.is_file() or target.stat().st_size>128_000:
            raise ValueError("UNSAFE_SOURCE")
        entries[name]=target.read_bytes()
    entries["README_JA.md"]=README.encode("utf-8")
    entries["evidence/ci-governance-v11.json"]=(
        json.dumps(status,sort_keys=True,indent=2,ensure_ascii=False)+"\n").encode()
    return entries

def build(root,output,evidence_path=None):
    entries=collect(root)
    manifest={
        "schema":"ci-governance-v11-package/v1",
        "release_readiness":"NO_GO",
        "product_e2e":"NOT_RUN",
        "files":[{"path":p,"bytes":len(b),"sha256":sha(b)}
                 for p,b in sorted(entries.items())],
    }
    entries["MANIFEST_SHA256.json"]=(
        json.dumps(manifest,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode()
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,"w",compression=zipfile.ZIP_DEFLATED) as z:
        for name,payload in sorted(entries.items()):
            item=zipfile.ZipInfo(name,date_time=FIXED_DATE)
            item.compress_type=zipfile.ZIP_DEFLATED
            item.external_attr=(stat.S_IFREG|0o644)<<16
            z.writestr(item,payload,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    with zipfile.ZipFile(output) as z:
        if z.testzip() is not None:
            raise RuntimeError("ZIP_CRC_FAILURE")
        if sorted(z.namelist())!=sorted(entries):
            raise RuntimeError("ZIP_INVENTORY_MISMATCH")
        for row in manifest["files"]:
            if sha(z.read(row["path"]))!=row["sha256"]:
                raise RuntimeError("ZIP_SHA256_MISMATCH")
    result={
        "schema":"ci-governance-v11-bundle-evidence/v1",
        "sha256":sha(output.read_bytes()),
        "members":len(entries),
        "verified_sha256":len(manifest["files"]),
        "crc":"PASS",
        "release_readiness":"NO_GO",
        "product_e2e":"NOT_RUN",
    }
    if evidence_path:
        target=Path(evidence_path)
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return result

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root",default=".")
    p.add_argument("--output",required=True)
    p.add_argument("--evidence")
    args=p.parse_args(argv)
    print(json.dumps(build(args.root,args.output,args.evidence),indent=2))
    return 0

if __name__=="__main__":
    sys.exit(main())
