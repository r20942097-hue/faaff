#!/usr/bin/env python3
"""Fail-closed, read-only ZIP fingerprint of four RPLAY OPFS store copies."""
import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

from ai.archive_intake import scan

PATHS=(
 "rplay-stable-player-extension/segment_store.js",
 "rplay-stable-player-extension-firefox/segment_store.js",
 "segment_store.js",
 "src/segment_store.js",
)
KNOWN_BAD="3f1a00b89207f8cb783f59152db6ff230c300569f79b1e1eb691353b70218b9e"

def ordering_hint(data):
    """Advisory only: absence of a match is not evidence of a fix."""
    value=data.decode("utf-8","replace")
    evict=value.find("const evicted=await evict(")
    write=value.find("w=await fh.createWritable()")
    return ("EVICT_BEFORE_NEW_WRITE" if evict>=0 and write>evict
            else "UNRESOLVED_MANUAL_REVIEW")

def audit(path):
    path=Path(path)
    intake=scan(path)
    report={
      "schema":"rplay-source-zip-fingerprint/v1",
      "archive_name":path.name,"archive_sha256":intake["sha256"],
      "archive_members":intake["members"],"archive_crc_and_safety":intake["status"],
      "intake_issues":intake["issues"],
      "source_copies":[],"source_consistency":"NOT_RUN",
      "risk":"BLOCKED_UNVERIFIED","source_provenance":"UNVERIFIED",
      "product_e2e":"NOT_RUN","release_readiness":"NO_GO",
      "status":"BLOCKED",
    }
    if intake["status"]!="PASSED_INTAKE_ONLY":
        report["risk"]="UNSAFE_OR_BROKEN_ARCHIVE"
        return report
    try:
        with zipfile.ZipFile(path) as archive:
            for name in PATHS:
                try:
                    info=archive.getinfo(name)
                except KeyError:
                    report["risk"]="REQUIRED_SOURCE_MISSING"
                    return report
                if info.is_dir() or info.file_size>256*1024:
                    report["risk"]="INVALID_SOURCE_MEMBER"
                    return report
                raw=archive.read(info)
                report["source_copies"].append({
                    "path":name,"bytes":len(raw),
                    "sha256":hashlib.sha256(raw).hexdigest(),
                    "ordering_hint":ordering_hint(raw),
                })
    except (OSError,RuntimeError,ValueError,zipfile.BadZipFile):
        report["risk"]="SOURCE_READ_FAILED"
        return report
    digests={entry["sha256"] for entry in report["source_copies"]}
    report["source_consistency"]="MATCH" if len(digests)==1 else "DIVERGENT"
    if len(digests)>1:
        report["risk"]="DIVERGENT_SOURCES_MANUAL_REVIEW"
    elif KNOWN_BAD in digests:
        report["risk"]="KNOWN_BAD_PRECOMMIT_EVICTION"
    else:
        report["risk"]="CHANGED_BUT_UNREVIEWED_SOURCE"
    report["status"]="AUDIT_COMPLETED_NO_GO"
    return report

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives",nargs="+")
    parser.add_argument("--output")
    args=parser.parse_args(argv)
    reports=[audit(x) for x in args.archives]
    payload=json.dumps({"reports":reports},ensure_ascii=False,sort_keys=True,indent=2)+"\n"
    if args.output:
        output=Path(args.output)
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(payload,encoding="utf-8")
    print(payload)
    return 2 if all(x["status"]=="AUDIT_COMPLETED_NO_GO" for x in reports) else 3

if __name__=="__main__":
    sys.exit(main())
