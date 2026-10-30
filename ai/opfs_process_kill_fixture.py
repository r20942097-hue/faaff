#!/usr/bin/env python3
"""Linux-only isolated browser-process group SIGKILL OPFS test; never product GO."""
import argparse
import json
import os
import select
import signal
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path

from ai.opfs_restart_fixture import (
    Handler, INITIALIZE, INSPECT, DIRECTORY, SOURCE_A, SOURCE_B, HASH_A, HASH_B,
)
from ai.chromium_renderer_crash_fixture import STAGE_UNCOMMITTED, CLEAN, verify_old

MARKER = "READY_STAGED_UNCOMMITTED"
BROWSER_COMM = {
    "chromium": ("chrome", "chromium", "headless_shell"),
    "firefox": ("firefox",),
}

def parse_group_processes(raw, group_id, browser_name):
    """Accept only processes belonging to the dedicated child session."""
    result=[]
    expected=BROWSER_COMM[browser_name]
    for line in raw.splitlines():
        fields=line.split(None,3)
        if len(fields)!=4:
            continue
        pid,group,state,command=fields
        if group!=str(group_id) or state.startswith("Z") or not pid.isdecimal():
            continue
        if any(token in command.lower() for token in expected):
            result.append(int(pid))
    return result

def browser_members(group_id, browser_name):
    p=subprocess.run(["ps","-e","-o","pid=,pgid=,stat=,comm="],
                     capture_output=True,text=True,timeout=8,check=True)
    return parse_group_processes(p.stdout,group_id,browser_name)

def await_marker(proc, seconds=75):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        if proc.poll() is not None:
            raise RuntimeError("ISOLATED_CHILD_EXITED_EARLY")
        ready,_,_=select.select([proc.stdout],[],[],min(0.4,max(0,deadline-time.monotonic())))
        if ready:
            line=proc.stdout.readline().strip()
            if line==MARKER:
                return
            if line:
                raise RuntimeError("ISOLATED_CHILD_UNEXPECTED_OUTPUT")
    raise TimeoutError("ISOLATED_CHILD_DID_NOT_STAGE")

def child(profile, url, browser_name):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        context=getattr(p,browser_name).launch_persistent_context(
            profile,headless=True,timeout=45000)
        page=context.new_page()
        page.goto(url,wait_until="load",timeout=15000)
        page.evaluate(INITIALIZE,{
            "directory":DIRECTORY,"bytes":SOURCE_A,"digest":HASH_A})
        verify_old(page.evaluate(INSPECT,DIRECTORY))
        stage=page.evaluate(STAGE_UNCOMMITTED,{
            "directory":DIRECTORY,"bytes":SOURCE_B,"digest":HASH_B})
        if not stage.get("manifestWriterUnclosed"):
            raise AssertionError("UNCOMMITTED_STAGE_NOT_ESTABLISHED")
        print(MARKER,flush=True)
        # Deliberately do not close context, browser, or the pending manifest writer.
        # Parent verifies a real browser process in the isolated process group, then SIGKILLs it.
        threading.Event().wait(180)

def template(browser_name):
    return {
        "schema":"isolated-browser-process-kill-opfs/v1",
        "generated_at_utc":datetime.now(timezone.utc).isoformat(),
        "browser":browser_name,
        "data_source":"synthetic_only",
        "committed_sha256":HASH_A,"staged_sha256":HASH_B,
        "child_browser_process_detected":"NOT_RUN",
        "browser_group_sigkill":"NOT_RUN",
        "relaunch_same_profile":"NOT_RUN",
        "old_committed_bytes_sha256":"NOT_RUN",
        "orphan_cleanup":"NOT_RUN",
        "physical_power_failure":"NOT_RUN",
        "os_kernel_crash":"NOT_RUN",
        "product_e2e":"NOT_RUN",
        "release_readiness":"NO_GO",
        "status":"BLOCKED",
    }

def stop_group(proc):
    if proc is None:
        return
    if proc.poll() is None:
        try:os.killpg(proc.pid,signal.SIGKILL)
        except ProcessLookupError:pass
    try:proc.wait(timeout=12)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
    if proc.stdout:
        proc.stdout.close()

def probe(browser_name):
    if sys.platform!="linux" or not hasattr(os,"killpg"):
        raise RuntimeError("LINUX_ISOLATION_REQUIRED")
    from playwright.sync_api import sync_playwright
    result=template(browser_name)
    with tempfile.TemporaryDirectory(prefix="isolated-opfs-sigkill-") as tmp:
        profile=str(Path(tmp)/"profile")
        with ThreadingHTTPServer(("127.0.0.1",0),Handler) as server:
            worker=threading.Thread(target=server.serve_forever,daemon=True)
            worker.start()
            url=f"http://127.0.0.1:{server.server_port}/fixture"
            proc=None
            try:
                proc=subprocess.Popen(
                    [sys.executable,"-m","ai.opfs_process_kill_fixture",
                     "--child","--browser",browser_name,
                     "--profile",profile,"--url",url],
                    cwd=str(Path(__file__).resolve().parents[1]),
                    start_new_session=True,stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,text=True,bufsize=1,
                )
                await_marker(proc)
                if os.getpgid(proc.pid)!=proc.pid:
                    raise AssertionError("CHILD_NOT_IN_DEDICATED_PROCESS_GROUP")
                original=browser_members(proc.pid,browser_name)
                if not original:
                    raise AssertionError("NO_BROWSER_OS_PROCESS_IN_DEDICATED_GROUP")
                result["child_browser_process_detected"]="PASS"
                group_id=proc.pid
                stop_group(proc)
                if proc.returncode!=-signal.SIGKILL:
                    raise AssertionError("CHILD_NOT_SIGKILLED")
                result["browser_group_sigkill"]="PASS"
                for _ in range(50):
                    survivors=browser_members(group_id,browser_name)
                    if not survivors:
                        break
                    time.sleep(0.2)
                else:
                    raise AssertionError("BROWSER_PROCESS_SURVIVED_SIGKILL")
                with sync_playwright() as playwright:
                    context=getattr(playwright,browser_name).launch_persistent_context(
                        profile,headless=True,timeout=45000)
                    try:
                        page=context.new_page()
                        page.goto(url,wait_until="load",timeout=15000)
                        result["relaunch_same_profile"]="PASS"
                        state=page.evaluate(INSPECT,DIRECTORY)
                        verify_old(state)
                        result["old_committed_bytes_sha256"]="PASS"
                        if "blob-0002.bin" not in state["names"]:
                            raise AssertionError("STAGED_B_NOT_PRESENT_AFTER_KILL")
                        removed=page.evaluate(CLEAN,DIRECTORY)
                        if removed!=["blob-0002.bin"]:
                            raise AssertionError("ORPHAN_CLEANUP_MISMATCH")
                        verify_old(page.evaluate(INSPECT,DIRECTORY))
                        result["orphan_cleanup"]="PASS"
                    finally:
                        context.close()
            finally:
                stop_group(proc)
                server.shutdown()
                worker.join(timeout=5)
    required=("child_browser_process_detected","browser_group_sigkill",
              "relaunch_same_profile","old_committed_bytes_sha256","orphan_cleanup")
    if all(result[key]=="PASS" for key in required):
        result["status"]="PASS_ISOLATED_OS_BROWSER_KILL"
    return result

KNOWN_DIAGNOSTIC_CODES = frozenset((
    "ISOLATED_CHILD_EXITED_EARLY", "ISOLATED_CHILD_DID_NOT_STAGE",
    "ISOLATED_CHILD_UNEXPECTED_OUTPUT", "CHILD_NOT_IN_DEDICATED_PROCESS_GROUP",
    "NO_BROWSER_OS_PROCESS_IN_DEDICATED_GROUP", "CHILD_NOT_SIGKILLED",
    "BROWSER_PROCESS_SURVIVED_SIGKILL", "STAGED_B_NOT_PRESENT_AFTER_KILL",
    "ORPHAN_CLEANUP_MISMATCH", "UNCOMMITTED_STAGE_NOT_ESTABLISHED",
    "CRASH_RECOVERY_A_SHA256_MISMATCH",
))

def run(browser_name):
    try:return probe(browser_name)
    except Exception as error:
        result=template(browser_name)
        # Browser profiles, URLs and command-line arguments are deliberately redacted.
        result["error_type"]=type(error).__name__
        result["failure_code"]=(str(error) if str(error) in KNOWN_DIAGNOSTIC_CODES
                               else "UNCLASSIFIED")
        return result

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser",choices=("chromium","firefox"),required=True)
    parser.add_argument("--output")
    parser.add_argument("--child",action="store_true",help=argparse.SUPPRESS)
    parser.add_argument("--profile",help=argparse.SUPPRESS)
    parser.add_argument("--url",help=argparse.SUPPRESS)
    args=parser.parse_args(argv)
    if args.child:
        if not args.profile or not args.url or not args.url.startswith("http://127.0.0.1:"):
            raise ValueError("ISOLATED_CHILD_MISSING_LOCAL_PARAMETERS")
        child(args.profile,args.url,args.browser)
        return 0
    report=run(args.browser)
    payload=json.dumps(report,indent=2,ensure_ascii=False)+"\n"
    if args.output:
        target=Path(args.output)
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(payload,encoding="utf-8")
    print(payload)
    return 0 if report["status"]=="PASS_ISOLATED_OS_BROWSER_KILL" else 2

if __name__=="__main__":
    sys.exit(main())
