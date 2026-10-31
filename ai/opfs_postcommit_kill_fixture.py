#!/usr/bin/env python3
"""Synthetic OPFS post-commit process SIGKILL and idempotent recovery; never product GO."""
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
    Handler, INITIALIZE, INSPECT, DIRECTORY, SOURCE_A, SOURCE_B,
    HASH_A, HASH_B, require_generation,
)
from ai.chromium_renderer_crash_fixture import CLEAN
from ai.opfs_process_kill_fixture import BROWSER_COMM, stop_group

MARKER = "READY_COMMITTED_B_WITH_OLD_A"
COMMIT_B_KEEP_A = r"""async ({directory,bytes,digest}) => {
 const root=await navigator.storage.getDirectory();
 const dir=await root.getDirectoryHandle(directory);
 const candidate=await dir.getFileHandle('blob-0002.bin',{create:true});
 const writer=await candidate.createWritable();
 await writer.write(Uint8Array.from(bytes));
 await writer.close();
 const state=await dir.getFileHandle('state.json');
 const manifestWriter=await state.createWritable();
 await manifestWriter.write(JSON.stringify({
   generation:2,active:'blob-0002.bin',sha256:digest
 }));
 await manifestWriter.close();
 // Do not delete the previous generation before the deliberate crash.
 await dir.getFileHandle('blob-0001.bin');
 return {manifestClosed:true,oldGenerationRetained:true};
}"""


def template(browser):
    return {
        "schema":"opfs-postcommit-process-kill/v1",
        "generated_at_utc":datetime.now(timezone.utc).isoformat(),
        "browser":browser,
        "fixture":"deterministic_synthetic_bytes_only",
        "baseline_sha256":HASH_A,
        "committed_sha256":HASH_B,
        "postcommit_before_cleanup":"NOT_RUN",
        "owned_browser_process_detected":"NOT_RUN",
        "process_tree_sigkill":"NOT_RUN",
        "restart_new_generation_sha256":"NOT_RUN",
        "old_generation_cleanup":"NOT_RUN",
        "cleanup_idempotency":"NOT_RUN",
        "second_restart_sha256":"NOT_RUN",
        "power_failure":"NOT_RUN",
        "physical_disk_failure":"NOT_RUN",
        "product_e2e":"NOT_RUN",
        "release_readiness":"NO_GO",
        "status":"BLOCKED",
    }


def verify_committed(observed, expect_old):
    require_generation(observed,2,HASH_B,SOURCE_B)
    expected={"state.json","blob-0002.bin"}
    if expect_old:
        expected.add("blob-0001.bin")
    if set(observed["names"]) != expected:
        raise AssertionError("POSTCOMMIT_INVENTORY_MISMATCH")


def await_ready(proc, seconds=75):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        if proc.poll() is not None:
            raise RuntimeError("CHILD_EXITED_BEFORE_COMMIT")
        readable,_,_=select.select(
            [proc.stdout],[],[],min(0.4,max(0,deadline-time.monotonic())))
        if readable:
            line=proc.stdout.readline().strip()
            if line==MARKER:
                return
            raise RuntimeError("CHILD_UNEXPECTED_OUTPUT")
    raise TimeoutError("COMMIT_MARKER_TIMEOUT")


def child(profile, url, browser):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        context=getattr(p,browser).launch_persistent_context(
            profile,headless=True,timeout=45000)
        page=context.new_page()
        page.goto(url,wait_until="load",timeout=15000)
        page.evaluate(INITIALIZE,{"directory":DIRECTORY,"bytes":SOURCE_A,"digest":HASH_A})
        require_generation(page.evaluate(INSPECT,DIRECTORY),1,HASH_A,SOURCE_A)
        confirmation=page.evaluate(
            COMMIT_B_KEEP_A,{"directory":DIRECTORY,"bytes":SOURCE_B,"digest":HASH_B})
        if confirmation != {"manifestClosed":True,"oldGenerationRetained":True}:
            raise AssertionError("B_MANIFEST_NOT_CLOSED")
        verify_committed(page.evaluate(INSPECT,DIRECTORY),expect_old=True)
        print(MARKER,flush=True)
        # Process dies by OS SIGKILL, never a graceful Playwright close.
        threading.Event().wait(180)


def probe(browser):
    if sys.platform!="linux" or not hasattr(os,"killpg"):
        raise RuntimeError("LINUX_PROCESS_ISOLATION_REQUIRED")
    from playwright.sync_api import sync_playwright
    import psutil
    report=template(browser)
    with tempfile.TemporaryDirectory(prefix="opfs-postcommit-kill-") as tmp:
        profile=str(Path(tmp)/"browser-profile")
        with ThreadingHTTPServer(("127.0.0.1",0),Handler) as server:
            thread=threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            url=f"http://127.0.0.1:{server.server_port}/fixture"
            proc=None
            try:
                proc=subprocess.Popen(
                    [sys.executable,"-m","ai.opfs_postcommit_kill_fixture",
                     "--child","--browser",browser,"--profile",profile,"--url",url],
                    cwd=str(Path(__file__).resolve().parents[1]),
                    start_new_session=True,stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,text=True,bufsize=1)
                await_ready(proc)
                report["postcommit_before_cleanup"]="PASS"
                if os.getpgid(proc.pid)!=proc.pid:
                    raise AssertionError("NOT_ISOLATED_SESSION")
                owned=psutil.Process(proc.pid).children(recursive=True)
                candidates=[]
                for process in owned:
                    try:
                        if any(x in process.name().lower() for x in BROWSER_COMM[browser]):
                            candidates.append(process)
                    except (psutil.NoSuchProcess,psutil.ZombieProcess):
                        pass
                if not candidates:
                    raise AssertionError("OWNED_BROWSER_PROCESS_NOT_FOUND")
                report["owned_browser_process_detected"]="PASS"
                stop_group(proc,owned)
                if proc.returncode!=-signal.SIGKILL:
                    raise AssertionError("SESSION_LEADER_NOT_SIGKILLED")
                _,survivors=psutil.wait_procs(candidates,timeout=8)
                if survivors:
                    raise AssertionError("BROWSER_DESCENDANTS_SURVIVED")
                report["process_tree_sigkill"]="PASS"
                with sync_playwright() as p:
                    launcher=getattr(p,browser)
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
                stop_group(proc)
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
    required=("postcommit_before_cleanup","owned_browser_process_detected",
              "process_tree_sigkill","restart_new_generation_sha256",
              "old_generation_cleanup","cleanup_idempotency","second_restart_sha256")
    if all(report[k]=="PASS" for k in required):
        report["status"]="PASS_SYNTHETIC_POSTCOMMIT_SIGKILL"
    return report


KNOWN_CODES=frozenset({
    "CHILD_EXITED_BEFORE_COMMIT","CHILD_UNEXPECTED_OUTPUT","COMMIT_MARKER_TIMEOUT",
    "B_MANIFEST_NOT_CLOSED","POSTCOMMIT_INVENTORY_MISMATCH","NOT_ISOLATED_SESSION",
    "OWNED_BROWSER_PROCESS_NOT_FOUND","SESSION_LEADER_NOT_SIGKILLED",
    "BROWSER_DESCENDANTS_SURVIVED","OLD_GENERATION_CLEANUP_MISMATCH",
    "CLEANUP_NOT_IDEMPOTENT","GENERATION_SHA256_OR_BYTES_MISMATCH",
})


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
    parser.add_argument("--browser",required=True,choices=("chromium","firefox"))
    parser.add_argument("--output")
    parser.add_argument("--child",action="store_true",help=argparse.SUPPRESS)
    parser.add_argument("--profile",help=argparse.SUPPRESS)
    parser.add_argument("--url",help=argparse.SUPPRESS)
    args=parser.parse_args(argv)
    if args.child:
        if not args.profile or not args.url or not args.url.startswith("http://127.0.0.1:"):
            raise ValueError("INVALID_DISPOSABLE_CHILD_ARGUMENTS")
        child(args.profile,args.url,args.browser)
        return 0
    report=run(args.browser)
    payload=json.dumps(report,ensure_ascii=False,indent=2)+"\n"
    if args.output:
        target=Path(args.output)
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(payload,encoding="utf-8")
    print(payload)
    return 0 if report["status"]=="PASS_SYNTHETIC_POSTCOMMIT_SIGKILL" else 2


if __name__=="__main__":
    sys.exit(main())
