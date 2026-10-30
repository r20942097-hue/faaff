#!/usr/bin/env python3
"""Chromium renderer crash durability probe in a disposable profile; NOT power-loss."""
import argparse
import json
import sys
import tempfile
import threading
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path

from ai.opfs_restart_fixture import Handler, INITIALIZE, INSPECT, SOURCE_A, SOURCE_B, HASH_A, HASH_B, DIRECTORY

STAGE_UNCOMMITTED=r"""async ({directory,bytes,digest}) => {
 const root=await navigator.storage.getDirectory();
 const d=await root.getDirectoryHandle(directory);
 const candidate=await d.getFileHandle('blob-0002.bin',{create:true});
 const writable=await candidate.createWritable();
 await writable.write(Uint8Array.from(bytes));await writable.close();
 const state=await d.getFileHandle('state.json');
 window.__pendingManifest=await state.createWritable();
 await window.__pendingManifest.write(JSON.stringify({
   generation:2,active:'blob-0002.bin',sha256:digest
 }));
 return {stagedCandidate:true,manifestWriterUnclosed:true};
}"""
CLEAN=r"""async directory=>{
 const root=await navigator.storage.getDirectory();
 const dir=await root.getDirectoryHandle(directory);
 const state=JSON.parse(await(await dir.getFileHandle('state.json')).getFile().then(f=>f.text()));
 const removed=[];
 for await(const [name] of dir.entries()) {
   if(name.startsWith('blob-') && name!==state.active) {
     await dir.removeEntry(name);removed.push(name);
   }
 }
 return removed.sort();
}"""

def template():
    return {'schema':'chromium-renderer-crash-opfs/v1',
            'generated_at_utc':datetime.now(timezone.utc).isoformat(),
            'browser':'chromium',
            'fixture':'localhost_synthetic_bytes',
            'baseline_sha256':HASH_A, 'staged_candidate_sha256':HASH_B,
            'baseline_commit':'NOT_RUN',
            'staged_manifest_unclosed':'NOT_RUN',
            'cdp_renderer_crash':'NOT_RUN',
            'post_crash_browser_relaunch':'NOT_RUN',
            'committed_baseline_survives':'NOT_RUN',
            'orphan_cleanup':'NOT_RUN',
            'os_process_termination':'NOT_RUN',
            'sudden_power_loss':'NOT_RUN',
            'product_e2e':'NOT_RUN',
            'release_readiness':'NO_GO',
            'status':'BLOCKED'}

def verify_old(item):
    if (item.get('generation')!=1 or
        item.get('active')!='blob-0001.bin' or
        item.get('declared')!=HASH_A or
        item.get('calculated')!=HASH_A or
        item.get('bytes')!=SOURCE_A):
        raise AssertionError('CRASH_RECOVERY_A_SHA256_MISMATCH')

def probe():
    from playwright.sync_api import sync_playwright, Error, TimeoutError
    result=template()
    with tempfile.TemporaryDirectory(prefix='chromium-renderer-crash-') as tmp:
        profile=Path(tmp)/'profile'
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        url=f'http://127.0.0.1:{server.server_port}/fixture'
        try:
            with sync_playwright() as playwright:
                ctx=playwright.chromium.launch_persistent_context(
                    str(profile),headless=True,timeout=45000)
                try:
                    page=ctx.new_page()
                    page.goto(url,wait_until='load')
                    page.evaluate(INITIALIZE,
                        {'directory':DIRECTORY,'bytes':SOURCE_A,'digest':HASH_A})
                    verify_old(page.evaluate(INSPECT,DIRECTORY))
                    result['baseline_commit']='PASS'
                    stage=page.evaluate(STAGE_UNCOMMITTED,
                        {'directory':DIRECTORY,'bytes':SOURCE_B,'digest':HASH_B})
                    if not (stage.get('stagedCandidate') and stage.get('manifestWriterUnclosed')):
                        raise AssertionError('CANDIDATE_STAGE_NOT_COMPLETE')
                    result['staged_manifest_unclosed']='PASS'
                    crashes=[]
                    page.on('crash',lambda _: crashes.append(True))
                    session=ctx.new_cdp_session(page)
                    try:
                        session.send('Page.crash')
                    except Error:
                        # The debugger command itself may fail when the target dies.
                        pass
                    if not crashes:
                        try:
                            page.wait_for_event('crash',timeout=5000)
                            crashes.append(True)
                        except (Error,TimeoutError):
                            pass
                    if not crashes:
                        raise AssertionError('CDP_RENDERER_CRASH_NOT_OBSERVED')
                    result['cdp_renderer_crash']='PASS'
                finally:
                    try:ctx.close()
                    except Error:pass
                ctx=playwright.chromium.launch_persistent_context(
                    str(profile),headless=True,timeout=45000)
                try:
                    page=ctx.new_page()
                    page.goto(url,wait_until='load')
                    result['post_crash_browser_relaunch']='PASS'
                    state=page.evaluate(INSPECT,DIRECTORY)
                    verify_old(state)
                    result['committed_baseline_survives']='PASS'
                    if 'blob-0002.bin' not in state['names']:
                        raise AssertionError('EXPECTED_UNCOMMITTED_ORPHAN_ABSENT')
                    removed=page.evaluate(CLEAN,DIRECTORY)
                    if removed!=['blob-0002.bin']:
                        raise AssertionError('ORPHAN_CLEANUP_MISMATCH')
                    verify_old(page.evaluate(INSPECT,DIRECTORY))
                    result['orphan_cleanup']='PASS'
                finally:ctx.close()
        finally:
            server.shutdown();server.server_close();thread.join(timeout=5)
    if all(result[x]=='PASS' for x in (
        'baseline_commit','staged_manifest_unclosed','cdp_renderer_crash',
        'post_crash_browser_relaunch','committed_baseline_survives','orphan_cleanup')):
        result['status']='PASS_DISPOSABLE_RENDERER_CRASH_OPFS'
    return result

def run():
    try:return probe()
    except Exception as exc:
        result=template()
        result['error_type']=type(exc).__name__
        return result

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output')
    args=parser.parse_args(argv)
    report=run()
    payload=json.dumps(report,ensure_ascii=False,indent=2)+'\n'
    if args.output:
        path=Path(args.output)
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(payload,encoding='utf-8')
    print(payload)
    return 0 if report['status']=='PASS_DISPOSABLE_RENDERER_CRASH_OPFS' else 2

if __name__=='__main__':sys.exit(main())
