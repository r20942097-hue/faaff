#!/usr/bin/env python3
"""Read-only GitHub Actions governance audit. Never product acceptance."""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
import yaml

EXPECTED_GROUP = "${{ github.workflow }}-${{ github.event.pull_request.number || github.run_id }}"
EXPECTED_CANCEL = "${{ github.event_name == 'pull_request' }}"
ACTION_PIN = re.compile(r"^(?:[A-Za-z0-9_.-]+/){1,3}[A-Za-z0-9_.-]+@[0-9a-f]{40}$")
MAX_WORKFLOW_BYTES = 128_000

def validate_document(path, document):
    errors=[]
    if not isinstance(document, dict):
        return ["INVALID_DOCUMENT"]
    events=document.get("on",document.get(True))
    if not events:
        errors.append("MISSING_TRIGGER")
    elif isinstance(events,dict) and ({"pull_request_target","workflow_run"} & set(events)):
        errors.append("PRIVILEGED_TRIGGER")
    allowed={"contents":"read"}
    if Path(path).name=="codeql.yml":
        allowed["security-events"]="write"
    if document.get("permissions")!=allowed:
        errors.append("ROOT_PERMISSIONS_NOT_MINIMAL")
    concurrency=document.get("concurrency")
    if not isinstance(concurrency,dict):
        errors.append("NO_WORKFLOW_CONCURRENCY")
    else:
        if concurrency.get("group")!=EXPECTED_GROUP:
            errors.append("UNSAFE_CONCURRENCY_GROUP")
        if concurrency.get("cancel-in-progress")!=EXPECTED_CANCEL:
            errors.append("UNSAFE_CANCEL_POLICY")
    jobs=document.get("jobs")
    if not isinstance(jobs,dict) or not jobs:
        errors.append("MISSING_JOBS")
    else:
        for job in jobs.values():
            if not isinstance(job,dict):
                errors.append("INVALID_JOB")
                continue
            if "permissions" in job and job["permissions"]!=allowed:
                errors.append("JOB_PERMISSIONS_NOT_MINIMAL")
            if "runs-on" not in job and "uses" not in job:
                errors.append("MISSING_RUNNER")
            for step in job.get("steps",[]):
                if not isinstance(step,dict):
                    errors.append("INVALID_STEP")
                    continue
                action=step.get("uses")
                if action and not (isinstance(action,str) and
                                  (ACTION_PIN.fullmatch(action) or action.startswith("./"))):
                    errors.append("UNPINNED_ACTION")
    if isinstance(events,dict) and isinstance(events.get("pull_request"),dict):
        paths=events["pull_request"].get("paths")
        if paths and not any(str(x) in (path,".github/workflows/**",".github/workflows/*")
                             for x in paths):
            errors.append("WORKFLOW_FILE_NOT_IN_PR_PATHS")
    return sorted(set(errors))

def audit(root):
    directory=Path(root)/".github"/"workflows"
    records=[]
    if not directory.is_dir():
        return {"schema":"ci-governance-audit/v1","status":"BLOCKED",
                "release_readiness":"NO_GO","checked":0,"passed":0,
                "failed":1,"workflows":[],"failure":"MISSING_WORKFLOW_DIRECTORY"}
    for file in sorted(directory.iterdir()):
        if file.suffix not in (".yml",".yaml"):
            continue
        if file.is_symlink() or not file.is_file() or file.stat().st_size>MAX_WORKFLOW_BYTES:
            records.append({"file":file.name,"issues":["UNSAFE_WORKFLOW_FILE"]})
            continue
        data=file.read_bytes()
        try:
            document=yaml.safe_load(data)
            issues=validate_document(".github/workflows/"+file.name,document)
        except (yaml.YAMLError,UnicodeDecodeError,ValueError):
            issues=["INVALID_YAML"]
        records.append({"file":file.name,"sha256":hashlib.sha256(data).hexdigest(),
                        "issues":issues})
    failed=sum(bool(item["issues"]) for item in records)
    return {"schema":"ci-governance-audit/v1",
            "status":"PASS" if records and failed==0 else "BLOCKED",
            "checked":len(records),"passed":len(records)-failed,"failed":failed,
            "workflows":records,"product_e2e":"NOT_RUN",
            "release_readiness":"NO_GO"}

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",default=".")
    parser.add_argument("--output")
    args=parser.parse_args(argv)
    report=audit(args.root)
    payload=json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n"
    if args.output:
        path=Path(args.output)
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(payload,encoding="utf-8")
    print(payload)
    return 0 if report["status"]=="PASS" else 2

if __name__=="__main__":
    sys.exit(main())
