"""Fetch and extract a vendor SHA-256-pinned official uBO Lite Chromium build.

Only outside the checkout, to an empty ephemeral location. No dependency
scripts, arbitrary archive file paths or network forwarding. Never copy or
publish the unpacked vendor extension as a project artifact.
"""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import time
from urllib.request import Request, urlopen
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[2]
LOCK=Path(__file__).resolve().parent/"verification"/"ubol-official-release-lock.json"


def verify_lock(lock):
    if (lock.get("schema")!="upc-ubol-official-release-lock/v1"
            or lock.get("source")!="uBlockOrigin/uBOL-home"
            or lock.get("release_tag")!="2026.1026.1812"
            or lock.get("download_url")!=
              "https://github.com/uBlockOrigin/uBOL-home/releases/download/2026.1026.1812/uBOLite_2026.1026.1812.chromium.zip"
            or lock.get("size")!=9009606
            or lock.get("sha256")!="d3788eac9f0a44c67f3745a43c3fd446ef33d56b1121f469b19e0fa0a836c2b5"
            or lock.get("expected_manifest_version")!=lock.get("release_tag")
            or lock.get("expected_static_rulesets")!=
                ["ublock-filters","easylist","easyprivacy","pgl"]
            or lock.get("rules_published")!=0
            or lock.get("publication")!="NO_GO"):
        raise ValueError("official uBOL asset provenance is not pinned")
    return lock


def validate_bytes(data, lock):
    if len(data)!=lock["size"] or sha256(data).hexdigest()!=lock["sha256"]:
        raise ValueError("uBOL zip SHA-256 or byte size does not match GitHub release")
    return True


def safe_entries(archive):
    entries=archive.infolist()
    if not entries or len(entries)>5000:
        raise ValueError("unexpected number of vendor archive members")
    total=0
    seen=set()
    for info in entries:
        name=info.filename
        parts=PurePosixPath(name).parts
        if (not parts or len(name)>400 or len(parts)>18
                or name.startswith("/") or "\\" in name
                or ".." in parts or ":" in name or name.startswith("./")):
            raise ValueError("unsafe vendor archive member name")
        if name in seen:
            raise ValueError("duplicate vendor archive member")
        seen.add(name)
        mode=(info.external_attr>>16)&0o170000
        if mode not in (0,stat.S_IFREG,stat.S_IFDIR):
            raise ValueError("symlinks/special archive entries are forbidden")
        total+=info.file_size
        if total>160*1024*1024 or info.file_size>10*1024*1024:
            raise ValueError("archive expansion exceeds pinned safety envelope")
    return entries


def unpack_verified(data, parent, lock):
    from io import BytesIO
    if not parent.exists() or any(parent.iterdir()):
        raise ValueError("official package extraction must use an empty directory")
    with ZipFile(BytesIO(data)) as z:
        members=safe_entries(z)
        manifest_options=[
            p for p in members if p.filename.endswith("manifest.json")
            and len(PurePosixPath(p.filename).parts)<=3
        ]
        if len(manifest_options)!=1:
            raise ValueError("official package manifest root ambiguous")
        stem=PurePosixPath(manifest_options[0].filename).parent
        prefix="" if str(stem)=="." else str(stem)+"/"
        for member in members:
            if member.is_dir():
                continue
            if prefix and not member.filename.startswith(prefix):
                raise ValueError("mixed vendor archive roots")
            relative=member.filename[len(prefix):]
            if not relative:
                continue
            output=parent.joinpath(*PurePosixPath(relative).parts)
            output.parent.mkdir(parents=True,exist_ok=True)
            with output.open("xb") as stream:
                with z.open(member) as source:
                    import shutil
                    shutil.copyfileobj(source,stream)
    manifest=json.loads((parent/"manifest.json").read_text(encoding="utf-8"))
    if (manifest.get("manifest_version")!=3
            or manifest.get("version")!=lock["expected_manifest_version"]
            or "declarativeNetRequest" not in manifest.get("permissions",[])
            or manifest.get("background",{}).get("service_worker") not in
               ("/js/background.js","js/background.js")):
        raise ValueError("official package manifest identity or MV3 invalid")
    resources=manifest.get("declarative_net_request",{}).get("rule_resources",[])
    enabled={r.get("id") for r in resources if r.get("enabled") is True}
    if not set(lock["expected_static_rulesets"]).issubset(enabled):
        raise ValueError("official default DNR stock rulesets absent from manifest")
    for row in resources:
        name=row["path"].lstrip("/")
        if not (parent/name).is_file():
            raise ValueError("compiled official ruleset missing from vendor zip")
    return {"version":manifest["version"],"enabled_manifest_rulesets":sorted(enabled),
            "rule_resources":len(resources)}


def fetch(lock):
    last=None
    for _ in range(3):
        try:
            with urlopen(Request(lock["download_url"],headers={
                "User-Agent":"UPC-ci-official-asset-pinner/1.0",
                "Accept":"application/octet-stream"}),timeout=65) as r:
                data=r.read(lock["size"]+1)
            validate_bytes(data,lock)
            return data
        except (OSError,ValueError) as error:
            last=error
            time.sleep(2)
    raise ValueError("cannot fetch hashed upstream release asset: "+str(last))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir",type=Path,required=True)
    a=p.parse_args()
    try:
        dest=a.output_dir.resolve()
        if dest.is_relative_to(ROOT) or dest.exists():
            raise ValueError("never write vendor archive into repo/existing path")
        lock=verify_lock(json.loads(LOCK.read_text(encoding="utf-8")))
        dest.mkdir(parents=True)
        data=fetch(lock)
        info=unpack_verified(data,dest,lock)
        print("UPC OFFICIAL UBOL PIN PASS:",info["version"],
              lock["sha256"],"enabled",",".join(info["enabled_manifest_rulesets"]),
              "vendor package unpacked in CI temporary dir only")
        return 0
    except (OSError,ValueError,KeyError,TypeError) as error:
        print("UPC OFFICIAL UBOL PIN FAIL:",error,file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
