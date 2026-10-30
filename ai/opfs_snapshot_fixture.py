#!/usr/bin/env python3
"""Disposable real-browser OPFS snapshot/restore; NEVER product runtime acceptance."""
import argparse
import hashlib
import json
import sys
import threading
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path

from ai.extension_fixture_e2e import Handler

DATA = [7, 31, 151, 2, 0, 255]
DIGEST = hashlib.sha256(bytes(DATA)).hexdigest()
DIRECTORY = "dev_env_synthetic_opfs_snapshot_v6"
WRITE = r"""async ({directory,data}) => {
  if (!isSecureContext || !navigator.storage?.getDirectory || !crypto?.subtle) {
    throw Error('OPFS_SECURE_CONTEXT_REQUIRED');
  }
  const root = await navigator.storage.getDirectory();
  const folder = await root.getDirectoryHandle(directory, {create:true});
  const file = await folder.getFileHandle('segment.bin',{create:true});
  const writer = await file.createWritable();
  await writer.write(Uint8Array.from(data));
  await writer.close();
  // Synthetic interruption after writing an uncommitted replacement.
  const uncommitted = await file.createWritable();
  await uncommitted.write(Uint8Array.of(99,88,77));
  await uncommitted.abort();
  const stored = new Uint8Array(await (await file.getFile()).arrayBuffer());
  const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', stored)))
    .map(b => b.toString(16).padStart(2,'0')).join('');
  return {bytes:Array.from(stored), sha256:digest, abortedReplacement:true};
}"""
READ = r"""async (directory) => {
  const root = await navigator.storage.getDirectory();
  const folder = await root.getDirectoryHandle(directory);
  const file = await folder.getFileHandle('segment.bin');
  const stored = new Uint8Array(await (await file.getFile()).arrayBuffer());
  const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', stored)))
    .map(b=>b.toString(16).padStart(2,'0')).join('');
  return {bytes:Array.from(stored), sha256:digest};
}"""
LOCK1 = r"""() => {
 window.__held=false; window.__releaseLock=null;
 window.__lockJob=navigator.locks.request('synthetic-opfs-v6-lock', {mode:'exclusive'}, () => {
   window.__held=true;
   return new Promise(resolve => {window.__releaseLock=resolve;});
 });
}"""
LOCK2 = r"""() => {
 window.__acquired=false;
 window.__secondJob=navigator.locks.request('synthetic-opfs-v6-lock',
   {mode:'exclusive'}, () => {window.__acquired=true;});
}"""

def base_report(browser_name):
    return {"schema":"opfs-snapshot-fixture/v1", "browser":browser_name,
            "generated_at_utc":datetime.now(timezone.utc).isoformat(),
            "source_fixture":"synthetic_bytes", "expected_sha256":DIGEST,
            "write_close":"NOT_RUN", "abort_preserves":"NOT_RUN",
            "reload_read":"NOT_RUN", "snapshot_export":"NOT_RUN",
            "snapshot_import":"NOT_RUN", "cross_tab_lock":"NOT_RUN",
            "real_product_e2e":"NOT_RUN", "real_quota":"NOT_RUN",
            "real_power_loss":"NOT_RUN", "release_readiness":"NO_GO",
            "status":"BLOCKED"}

def require_equal(observed):
    if observed.get("bytes") != DATA or observed.get("sha256") != DIGEST:
        raise AssertionError("SYNTHETIC_OPFS_DATA_OR_HASH_MISMATCH")

def probe(browser_name):
    from playwright.sync_api import sync_playwright
    with ThreadingHTTPServer(('127.0.0.1', 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}/fixture"
        report = base_report(browser_name)
        try:
            with sync_playwright() as playwright:
                browser = getattr(playwright, browser_name).launch(headless=True, timeout=45000)
                try:
                    context = browser.new_context()
                    try:
                        first = context.new_page()
                        first.goto(url, wait_until="load")
                        initial = first.evaluate(WRITE, {"directory":DIRECTORY,"data":DATA})
                        require_equal(initial)
                        report["write_close"] = "PASS"
                        report["abort_preserves"] = "PASS"
                        first.reload(wait_until="load")
                        require_equal(first.evaluate(READ, DIRECTORY))
                        report["reload_read"] = "PASS"
                        second = context.new_page()
                        second.goto(url, wait_until="load")
                        first.evaluate(LOCK1)
                        first.wait_for_function("window.__held === true", timeout=7000)
                        second.evaluate(LOCK2)
                        second.wait_for_timeout(150)
                        if second.evaluate("window.__acquired"):
                            raise AssertionError("CROSS_TAB_EXCLUSIVE_LOCK_VIOLATION")
                        first.evaluate("window.__releaseLock()")
                        second.wait_for_function("window.__acquired === true", timeout=7000)
                        report["cross_tab_lock"] = "PASS"
                        snapshot = context.storage_state(opfs=True)
                        origins = snapshot.get("origins", [])
                        matching = [x for x in origins if x.get("origin") == first.evaluate("location.origin")]
                        if not matching or "opfs" not in matching[0]:
                            raise AssertionError("OPFS_NOT_EXPORTED_IN_STORAGE_STATE")
                        report["snapshot_export"] = "PASS"
                    finally:
                        context.close()
                    restored = browser.new_context(storage_state=snapshot)
                    try:
                        page = restored.new_page()
                        page.goto(url, wait_until="load")
                        require_equal(page.evaluate(READ,DIRECTORY))
                        report["snapshot_import"] = "PASS"
                    finally:
                        restored.close()
                finally:
                    browser.close()
        finally:
            server.shutdown()
            thread.join(timeout=5)
        if all(report[key] == "PASS" for key in ("write_close","abort_preserves",
                "reload_read","snapshot_export","snapshot_import","cross_tab_lock")):
            report["status"] = "PASS_DISPOSABLE_BROWSER_OPFS"
        return report

def run(browser_name):
    try:
        return probe(browser_name)
    except Exception as error:
        report = base_report(browser_name)
        report["failure_type"] = type(error).__name__
        # Environment paths, URLs and browser diagnostics are not written into evidence.
        return report

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", choices=("chromium","firefox"), required=True)
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    report = run(args.browser)
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(payload, encoding="utf-8")
    print(payload)
    return 0 if report["status"] == "PASS_DISPOSABLE_BROWSER_OPFS" else 2

if __name__ == "__main__":
    sys.exit(main())
