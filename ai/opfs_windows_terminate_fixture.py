#!/usr/bin/env python3
"""Windows-only forced-termination OPFS postcommit test. Synthetic and disposable."""
import argparse
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path

from ai.opfs_postcommit_kill_fixture import (
    MARKER, child, verify_committed,
)
from ai.opfs_process_kill_fixture import BROWSER_COMM
from ai.opfs_restart_fixture import (
    Handler, INSPECT, DIRECTORY, HASH_A, HASH_B,
)
from ai.chromium_renderer_crash_fixture import CLEAN

def template(browser):
    return {
        "schema":"windows-opfs-postcommit-terminate/v1",
        "generated_at_utc":datetime.now(timezone.utc).isoformat(),
        "browser":browser,
        "runner":"windows-2025",
        "data_source":"synthetic_only",
        "baseline_sha256":HASH_A,
        "committed_sha256":HASH_B,
        "owned_browser_process_detected":"NOT_RUN",
        "windows_forced_process_tree_termination":"NOT_RUN",
        "restart_new_generation_sha256":"NOT_RUN",
        "old_generation_cleanup":"NOT_RUN",
        "cleanup_idempotency":"NOT_RUN",
        "second_restart_sha256":"NOT_RUN",
        "physical_power_failure":"NOT_RUN",
        "actual_product_source":"NOT_RUN",
        "product_e2e":"NOT_RUN",
        "release_readiness":"NO_GO",
        "status":"BLOCKED",
    }

def await_child_marker(proc,seconds=100):
    """A Windows stdout pipe is not selectable using select.select()."""
    messages=queue.Queue(maxsize=2)
    def reader():
        try:
            messages.put(proc.stdout.readline().strip())
        except Exception:
            messages.put("")
    threading.Thread(target=reader,daemon=True).start()
    try:
        received=messages.get(timeout=seconds)
    except queue.Empty:
        raise TimeoutError("ISOLATED_CHILD_READY_TIMEOUT") from None
    if proc.poll() is not None:
        raise RuntimeError("ISOLATED_CHILD_EXITED_EARLY")
    if received!=MARKER:
        raise RuntimeError("UNEXPECTED_CHILD_MARKER")

def owned_browser_processes(leader,browser):
    """Require browser descendants of the exact process object we created."""
    import psutil
    if leader is None or not leader.is_running():
        raise RuntimeError("ISOLATED_LEADER_NOT_RUNNING")
    descendants=leader.children(recursive=True)
    matched=[]
    for process in descendants:
        try:
            if any(token in process.name().lower() for token in BROWSER_COMM[browser]):
                matched.append(process)
        except (psutil.NoSuchProcess,psutil.ZombieProcess):
            pass
    if not matched:
        raise RuntimeError("OWNED_BROWSER_PROCESS_NOT_FOUND")
    return descendants,matched

def force_terminate_owned(proc,observed=None,required_browser=None):
    """Terminate only psutil-identified descendants and dedicated child leader."""
    if proc is None:
        return
    import psutil
    try:
        leader=psutil.Process(proc.pid)
        if observed is None:
            observed=leader.children(recursive=True)
    except (psutil.NoSuchProcess,psutil.ZombieProcess):
        observed=[]
        leader=None
    if required_browser is not None and not observed:
        raise RuntimeError("OWNED_DESCENDANTS_NOT_FOUND")
    for target in reversed(observed):
        try:
            target.kill()  # Windows TerminateProcess, not POSIX SIGKILL.
        except (psutil.NoSuchProcess,psutil.ZombieProcess):
            pass
        except psutil.AccessDenied as e:
            raise RuntimeError("OWNED_PROCESS_KILL_DENIED") from e
    if leader is not None:
        try:
            leader.kill()
        except (psutil.NoSuchProcess,psutil.ZombieProcess):
            pass
        except psutil.AccessDenied as e:
            raise RuntimeError("ISOLATED_LEADER_KILL_DENIED") from e
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired as e:
        raise RuntimeError("ISOLATED_LEADER_SURVIVED") from e
    if observed:
        _,survivors=psutil.wait_procs(observed,timeout=12)
        if survivors:
            raise RuntimeError("OWNED_DESCENDANTS_SURVIVED")
    if proc.stdout:
        proc.stdout.close()

def probe(browser):
    if sys.platform!="win32":
        raise RuntimeError("WINDOWS_NATIVE_RUNNER_REQUIRED")
    import psutil
    from playwright.sync_api import sync_playwright
    report=template(browser)
    with tempfile.TemporaryDirectory(prefix="win-postcommit-opfs-") as tmp:
        profile=str(Path(tmp)/"profile")
        with ThreadingHTTPServer(("127.0.0.1",0),Handler) as server:
            worker=threading.Thread(target=server.serve_forever,daemon=True)
            worker.start()
            url=f"http://127.0.0.1:{server.server_port}/fixture"
            proc=None
            observed=None
            try:
                proc=subprocess.Popen(
                    [sys.executable,"-m","ai.opfs_windows_terminate_fixture",
                     "--child","--browser",browser,"--profile",profile,"--url",url],
                    cwd=str(Path(__file__).resolve().parents[1]),
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                    stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                    text=True,bufsize=1)
                await_child_marker(proc)
                leader=psutil.Process(proc.pid)
                observed,matched=owned_browser_processes(leader,browser)
                report["owned_browser_process_detected"]="PASS"
                force_terminate_owned(proc,observed,required_browser=browser)
                if any(p.is_running() for p in matched):
                    raise RuntimeError("BROWSER_PROCESS_SURVIVED")
                report["windows_forced_process_tree_termination"]="PASS"
                with sync_playwright() as pw:
                    launcher=getattr(pw,browser)
                    context=launcher.launch_persistent_context(
                        profile,headless=True,timeout=45000)
                    try:
                        page=context.new_page()
                        page.goto(url,wait_until="load",timeout=15000)
                        verify_committed(page.evaluate(INSPECT,DIRECTORY),expect_old=True)
                        report["restart_new_generation_sha256"]="PASS"
                        removed=page.evaluate(CLEAN,DIRECTORY)
                        if removed!=["blob-0001.bin"]:
                            raise AssertionError("OLD_GENERATION_CLEANUP_MISMATCH")
                        verify_committed(page.evaluate(INSPECT,DIRECTORY),expect_old=False)
                        report["old_generation_cleanup"]="PASS"
                        if page.evaluate(CLEAN,DIRECTORY)!=[]:
                            raise AssertionError("CLEANUP_NOT_IDEMPOTENT")
                        verify_committed(page.evaluate(INSPECT,DIRECTORY),expect_old=False)
                        report["cleanup_idempotency"]="PASS"
                    finally:
                        context.close()
                    context=launcher.launch_persistent_context(
                        profile,headless=True,timeout=45000)
                    try:
                        page=context.new_page()
                        page.goto(url,wait_until="load",timeout=15000)
                        verify_committed(page.evaluate(INSPECT,DIRECTORY),expect_old=False)
                        report["second_restart_sha256"]="PASS"
                    finally:
                        context.close()
            finally:
                if proc is not None:
                    force_terminate_owned(proc)
                server.shutdown()
                server.server_close()
                worker.join(timeout=5)
    keys=("owned_browser_process_detected",
          "windows_forced_process_tree_termination","restart_new_generation_sha256",
          "old_generation_cleanup","cleanup_idempotency","second_restart_sha256")
    if all(report[k]=="PASS" for k in keys):
        report["status"]="PASS_WINDOWS_SYNTHETIC_POSTCOMMIT_TERMINATION"
    return report

KNOWN_CODES=frozenset((
    "WINDOWS_NATIVE_RUNNER_REQUIRED","ISOLATED_CHILD_READY_TIMEOUT",
    "ISOLATED_CHILD_EXITED_EARLY","UNEXPECTED_CHILD_MARKER",
    "ISOLATED_LEADER_NOT_RUNNING","OWNED_BROWSER_PROCESS_NOT_FOUND",
    "OWNED_DESCENDANTS_NOT_FOUND","OWNED_PROCESS_KILL_DENIED",
    "ISOLATED_LEADER_KILL_DENIED","ISOLATED_LEADER_SURVIVED",
    "OWNED_DESCENDANTS_SURVIVED","BROWSER_PROCESS_SURVIVED",
    "OLD_GENERATION_CLEANUP_MISMATCH","CLEANUP_NOT_IDEMPOTENT",
    "GENERATION_SHA256_OR_BYTES_MISMATCH","POSTCOMMIT_INVENTORY_MISMATCH",
))

def run(browser):
    try:
        return probe(browser)
    except Exception as error:
        report=template(browser)
        report["error_type"]=type(error).__name__
        report["failure_code"]=str(error) if str(error) in KNOWN_CODES else "UNCLASSIFIED"
        return report

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser",choices=("chromium","firefox"),required=True)
    parser.add_argument("--output")
    parser.add_argument("--child",action="store_true",help=argparse.SUPPRESS)
    parser.add_argument("--profile",help=argparse.SUPPRESS)
    parser.add_argument("--url",help=argparse.SUPPRESS)
    args=parser.parse_args(argv)
    if args.child:
        if sys.platform!="win32" or not args.profile or not args.url or not args.url.startswith("http://127.0.0.1:"):
            raise RuntimeError("INVALID_ISOLATED_CHILD")
        child(args.profile,args.url,args.browser)
        return 0
    report=run(args.browser)
    payload=json.dumps(report,ensure_ascii=False,indent=2)+"\n"
    if args.output:
        path=Path(args.output)
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(payload,encoding="utf-8")
    print(payload)
    return 0 if report["status"]=="PASS_WINDOWS_SYNTHETIC_POSTCOMMIT_TERMINATION" else 2

if __name__=="__main__":
    sys.exit(main())
