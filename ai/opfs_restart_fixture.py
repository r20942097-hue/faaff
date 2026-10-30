#!/usr/bin/env python3
"""Real browser synthetic OPFS journal restart probe. Not product acceptance."""
import argparse
import hashlib
import json
import sys
import tempfile
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SOURCE_A = [3, 7, 31, 63, 127, 251] * 64
SOURCE_B = [2, 5, 11, 17, 37, 101] * 64
HASH_A = hashlib.sha256(bytes(SOURCE_A)).hexdigest()
HASH_B = hashlib.sha256(bytes(SOURCE_B)).hexdigest()
DIRECTORY = 'synthetic_journal_recovery_v7'
INITIALIZE = r"""async ({directory,bytes,digest}) => {
 const root=await navigator.storage.getDirectory();
 const dir=await root.getDirectoryHandle(directory,{create:true});
 async function write(name,content) {
   const file=await dir.getFileHandle(name,{create:true});
   const writer=await file.createWritable();
   await writer.write(content); await writer.close();
 }
 await write('blob-0001.bin',Uint8Array.from(bytes));
 await write('state.json',JSON.stringify({generation:1,active:'blob-0001.bin',sha256:digest}));
 return true;
}"""
STAGE_THEN_ABORT_MANIFEST = r"""async ({directory,bytes,digest}) => {
 const root=await navigator.storage.getDirectory();
 const dir=await root.getDirectoryHandle(directory);
 const blob=await dir.getFileHandle('blob-0002.bin',{create:true});
 const bw=await blob.createWritable();
 await bw.write(Uint8Array.from(bytes));
 await bw.close();
 const state=await dir.getFileHandle('state.json');
 const manifestWriter=await state.createWritable();
 await manifestWriter.write(JSON.stringify({generation:2,active:'blob-0002.bin',sha256:digest}));
 await manifestWriter.abort();
 return true;
}"""
INSPECT = r"""async directory => {
 const root=await navigator.storage.getDirectory();
 const dir=await root.getDirectoryHandle(directory);
 const manifest=JSON.parse(await(await dir.getFileHandle('state.json')).getFile().then(f=>f.text()));
 const blob=new Uint8Array(await(await dir.getFileHandle(manifest.active)).getFile().then(f=>f.arrayBuffer()));
 const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',blob)))
     .map(x=>x.toString(16).padStart(2,'0')).join('');
 const names=[];
 for await(const [name] of dir.entries()) names.push(name);
 return {generation:manifest.generation,active:manifest.active,declared:manifest.sha256,
         calculated:digest,bytes:Array.from(blob),names:names.sort()};
}"""
RECOVER_AND_COMMIT = r"""async ({directory,bytes,digest}) => {
 const root=await navigator.storage.getDirectory();
 const dir=await root.getDirectoryHandle(directory);
 const stateHandle=await dir.getFileHandle('state.json');
 const before=JSON.parse(await(await stateHandle.getFile()).text());
 const removed=[];
 for await(const [name] of dir.entries()) {
   if(name.startsWith('blob-') && name!==before.active){
     await dir.removeEntry(name); removed.push(name);
   }
 }
 const blob=await dir.getFileHandle('blob-0002.bin',{create:true});
 const writer=await blob.createWritable();
 await writer.write(Uint8Array.from(bytes));
 await writer.close();
 const manifestWriter=await stateHandle.createWritable();
 await manifestWriter.write(JSON.stringify({generation:2,active:'blob-0002.bin',sha256:digest}));
 await manifestWriter.close();
 return {removed,previousGeneration:before.generation};
}"""
ISOLATION = r"""async directory => {
 const root=await navigator.storage.getDirectory();
 try { await root.getDirectoryHandle(directory); return {isolated:false}; }
 catch(error) {
   if(error.name!=='NotFoundError') throw error;
   return {isolated:true};
 }
}"""

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != '/fixture':
            self.send_error(404)
            return
        body=b'<!doctype html><html><body><main id="fixture">Synthetic OPFS journal</main></body></html>'
        self.send_response(200)
        self.send_header('Content-Type','text/html; charset=utf-8')
        self.send_header('Content-Length',str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self,*args):
        pass

def report_template(browser):
    return {
        'schema':'opfs-journal-restart-fixture/v1',
        'generated_at_utc':datetime.now(timezone.utc).isoformat(),
        'browser':browser, 'source':'synthetic_fixture_only',
        'initial_commit':'NOT_RUN','injected_manifest_abort':'NOT_RUN',
        'restart_old_generation':'NOT_RUN','orphan_cleanup':'NOT_RUN',
        'new_generation_commit':'NOT_RUN','restart_new_generation':'NOT_RUN',
        'cross_origin_isolation':'NOT_RUN','expected_a_sha256':HASH_A,
        'expected_b_sha256':HASH_B,'actual_process_crash':'NOT_RUN',
        'actual_storage_quota':'NOT_RUN','product_e2e':'NOT_RUN',
        'release_readiness':'NO_GO','status':'BLOCKED',
    }

def require_generation(observed, generation, digest, data):
    if (observed.get('generation') != generation or
            observed.get('active') != f'blob-{generation:04d}.bin' or
            observed.get('declared') != digest or
            observed.get('calculated') != digest or
            observed.get('bytes') != data):
        raise AssertionError('GENERATION_SHA256_OR_BYTES_MISMATCH')

def probe(browser_name):
    from playwright.sync_api import sync_playwright
    report=report_template(browser_name)
    with tempfile.TemporaryDirectory(prefix='synthetic-opfs-journal-') as temp:
        profile=Path(temp)/'profile'
        servers=[ThreadingHTTPServer(('127.0.0.1',0),Handler) for _ in range(2)]
        threads=[threading.Thread(target=s.serve_forever,daemon=True) for s in servers]
        for t in threads: t.start()
        origin_a=f'http://127.0.0.1:{servers[0].server_port}/fixture'
        origin_b=f'http://127.0.0.1:{servers[1].server_port}/fixture'
        try:
            with sync_playwright() as p:
                browser=getattr(p,browser_name)
                ctx=browser.launch_persistent_context(str(profile),headless=True,timeout=45000)
                try:
                    page=ctx.new_page()
                    page.goto(origin_a,wait_until='load')
                    page.evaluate(INITIALIZE,{'directory':DIRECTORY,'bytes':SOURCE_A,'digest':HASH_A})
                    require_generation(page.evaluate(INSPECT,DIRECTORY),1,HASH_A,SOURCE_A)
                    report['initial_commit']='PASS'
                    page.evaluate(STAGE_THEN_ABORT_MANIFEST,
                        {'directory':DIRECTORY,'bytes':SOURCE_B,'digest':HASH_B})
                    observed=page.evaluate(INSPECT,DIRECTORY)
                    require_generation(observed,1,HASH_A,SOURCE_A)
                    if 'blob-0002.bin' not in observed['names']:
                        raise AssertionError('INTERRUPTED_STAGE_NOT_PRESENT')
                    report['injected_manifest_abort']='PASS'
                    foreign=ctx.new_page()
                    foreign.goto(origin_b,wait_until='load')
                    if not foreign.evaluate(ISOLATION,DIRECTORY)['isolated']:
                        raise AssertionError('OPFS_CROSS_ORIGIN_LEAK')
                    report['cross_origin_isolation']='PASS'
                finally:
                    ctx.close()
                ctx=browser.launch_persistent_context(str(profile),headless=True,timeout=45000)
                try:
                    page=ctx.new_page()
                    page.goto(origin_a,wait_until='load')
                    observed=page.evaluate(INSPECT,DIRECTORY)
                    require_generation(observed,1,HASH_A,SOURCE_A)
                    if 'blob-0002.bin' not in observed['names']:
                        raise AssertionError('ORPHAN_MISSING_AFTER_RESTART')
                    report['restart_old_generation']='PASS'
                    result=page.evaluate(RECOVER_AND_COMMIT,
                        {'directory':DIRECTORY,'bytes':SOURCE_B,'digest':HASH_B})
                    if result.get('previousGeneration')!=1 or result.get('removed')!=['blob-0002.bin']:
                        raise AssertionError('ORPHAN_CLEANUP_FAILED')
                    report['orphan_cleanup']='PASS'
                    require_generation(page.evaluate(INSPECT,DIRECTORY),2,HASH_B,SOURCE_B)
                    report['new_generation_commit']='PASS'
                finally:
                    ctx.close()
                ctx=browser.launch_persistent_context(str(profile),headless=True,timeout=45000)
                try:
                    page=ctx.new_page()
                    page.goto(origin_a,wait_until='load')
                    require_generation(page.evaluate(INSPECT,DIRECTORY),2,HASH_B,SOURCE_B)
                    report['restart_new_generation']='PASS'
                finally:
                    ctx.close()
        finally:
            for server in servers:
                server.shutdown()
                server.server_close()
            for thread in threads:
                thread.join(timeout=5)
    steps=('initial_commit','injected_manifest_abort','restart_old_generation',
           'orphan_cleanup','new_generation_commit','restart_new_generation',
           'cross_origin_isolation')
    if all(report[x]=='PASS' for x in steps):
        report['status']='PASS_REAL_BROWSER_SYNTHETIC_JOURNAL'
    return report

def run(browser_name):
    try:
        return probe(browser_name)
    except Exception as error:
        report=report_template(browser_name)
        report['failure_type']=type(error).__name__
        return report

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser',choices=('chromium','firefox'),required=True)
    parser.add_argument('--output')
    args=parser.parse_args(argv)
    report=run(args.browser)
    payload=json.dumps(report,indent=2,ensure_ascii=False)+'\n'
    if args.output:
        output=Path(args.output)
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(payload,encoding='utf-8')
    print(payload)
    return 0 if report['status']=='PASS_REAL_BROWSER_SYNTHETIC_JOURNAL' else 2

if __name__=='__main__':
    sys.exit(main())
