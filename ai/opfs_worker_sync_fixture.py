#!/usr/bin/env python3
"""Real Dedicated Worker OPFS synchronous handle fixture; synthetic data only."""
import argparse
import hashlib
import json
import sys
import tempfile
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BYTES = [17, 0, 34, 255, 98, 76, 54, 32] * 128
SHA256 = hashlib.sha256(bytes(BYTES)).hexdigest()
DIRECTORY = "dev-environment-worker-sync-v9"
WORKER_JS = r"""'use strict';
let held = null;
async function handleMessage(message) {
  const root = await navigator.storage.getDirectory();
  const folder = await root.getDirectoryHandle(message.folder, {create:true});
  const file = await folder.getFileHandle('segment.bin', {create:true});
  if (message.cmd === 'release') {
    if (!held) throw new Error('NO_HELD_HANDLE');
    held.close(); held = null;
    return {phase:'released'};
  }
  if (message.cmd === 'hold') {
    if (held) throw new Error('ALREADY_HELD');
    held = await file.createSyncAccessHandle();
    return {phase:'held'};
  }
  if (message.cmd === 'probe') {
    const probe = await file.createSyncAccessHandle();
    probe.close();
    return {phase:'acquired'};
  }
  const handle = await file.createSyncAccessHandle();
  try {
    if (message.cmd === 'write') {
      const bytes = Uint8Array.from(message.bytes);
      handle.truncate(0);
      const written = handle.write(bytes, {at:0});
      if (written !== bytes.byteLength) throw new Error('SHORT_WRITE');
      handle.flush();
    }
    const size = handle.getSize();
    const bytes = new Uint8Array(size);
    const read = handle.read(bytes, {at:0});
    if (read !== size) throw new Error('SHORT_READ');
    const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)))
      .map(x=>x.toString(16).padStart(2,'0')).join('');
    return {phase:'done', bytes:Array.from(bytes),sha256:digest,flushed:message.cmd==='write'};
  } finally {handle.close();}
}
self.onmessage = async e => {
  try { self.postMessage(await handleMessage(e.data)); }
  catch (err) {self.postMessage({phase:'error',errorType:err.name});}
};
"""
SINGLE_WORKER = r"""async ({folder, cmd, bytes}) => {
  const w = new Worker('/worker.js');
  try {
    return await new Promise((resolve, reject) => {
      const timer=setTimeout(()=>reject(new Error('WORKER_TIMEOUT')),12000);
      w.onmessage=e=>{clearTimeout(timer);resolve(e.data);};
      w.onerror=()=>{clearTimeout(timer);reject(new Error('WORKER_EXCEPTION'));};
      w.postMessage({folder,cmd,bytes});
    });
  } finally {w.terminate();}
}"""
START_HOLD = r"""folder => {
 window.__workerOwner = new Worker('/worker.js');
 window.__ownerEvents = [];
 window.__workerOwner.onmessage=e=>window.__ownerEvents.push(e.data);
 window.__workerOwner.postMessage({folder,cmd:'hold'});
}"""
START_COMPETITOR = r"""folder => {
 window.__workerCompetitor = new Worker('/worker.js');
 window.__competitorEvents = [];
 window.__workerCompetitor.onmessage=e=>window.__competitorEvents.push(e.data);
 window.__workerCompetitor.postMessage({folder,cmd:'probe'});
}"""

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/worker.js':
            body=WORKER_JS.encode('utf-8')
            typ='application/javascript; charset=utf-8'
        elif self.path == '/fixture':
            body=b'<!doctype html><html><body>Dedicated Worker OPFS</body></html>'
            typ='text/html; charset=utf-8'
        else:
            self.send_error(404);return
        self.send_response(200)
        self.send_header('Content-Type',typ)
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store')
        self.end_headers()
        self.wfile.write(body)
    def log_message(self,*unused):pass

def template(browser_name):
    return {
        'schema':'opfs-worker-sync-fixture/v1',
        'generated_at_utc':datetime.now(timezone.utc).isoformat(),
        'browser':browser_name,'source':'deterministic_synthetic_bytes',
        'expected_sha256':SHA256,'worker_flush':'NOT_RUN',
        'worker_readback':'NOT_RUN','exclusive_handle_lock':'NOT_RUN',
        'restart_readback':'NOT_RUN','real_product_e2e':'NOT_RUN',
        'real_disk_power_loss':'NOT_RUN','release_readiness':'NO_GO',
        'status':'BLOCKED',
    }

def require_bytes(observed, should_flush=False):
    if (observed.get('phase')!='done' or
            observed.get('bytes')!=BYTES or
            observed.get('sha256')!=SHA256 or
            (should_flush and observed.get('flushed') is not True)):
        raise AssertionError('WORKER_OPFS_DIGEST_OR_BYTE_MISMATCH')

def probe(browser_name):
    from playwright.sync_api import sync_playwright
    report=template(browser_name)
    with tempfile.TemporaryDirectory(prefix='dev-worker-opfs-v9-') as temporary:
        profile=Path(temporary)/'profile'
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        worker=threading.Thread(target=server.serve_forever,daemon=True)
        worker.start()
        url=f'http://127.0.0.1:{server.server_port}/fixture'
        try:
            with sync_playwright() as playwright:
                engine=getattr(playwright,browser_name)
                context=engine.launch_persistent_context(str(profile),headless=True,timeout=45000)
                try:
                    page=context.new_page()
                    page.goto(url,wait_until='load')
                    response=page.evaluate(SINGLE_WORKER,
                        {'folder':DIRECTORY,'cmd':'write','bytes':BYTES})
                    require_bytes(response,should_flush=True)
                    report['worker_flush']='PASS'
                    response=page.evaluate(SINGLE_WORKER,
                        {'folder':DIRECTORY,'cmd':'read','bytes':[]})
                    require_bytes(response)
                    report['worker_readback']='PASS'
                    competitor=context.new_page()
                    competitor.goto(url,wait_until='load')
                    page.evaluate(START_HOLD,DIRECTORY)
                    page.wait_for_function(
                        "window.__ownerEvents.some(e=>e.phase==='held')",timeout=10000)
                    competitor.evaluate(START_COMPETITOR,DIRECTORY)
                    competitor.wait_for_timeout(300)
                    events=competitor.evaluate('window.__competitorEvents')
                    if any(e.get('phase')=='acquired' for e in events):
                        raise AssertionError('EXCLUSIVE_OPFS_HANDLE_VIOLATED')
                    if any(e.get('phase')=='error' and e.get('errorType') not in
                           ('InvalidStateError','NoModificationAllowedError') for e in events):
                        raise AssertionError('UNEXPECTED_CONCURRENT_HANDLE_ERROR')
                    page.evaluate("""() => window.__workerOwner.postMessage(
                        {folder:'dev-environment-worker-sync-v9',cmd:'release'})""")
                    page.wait_for_function(
                        "window.__ownerEvents.some(e=>e.phase==='released')",timeout=10000)
                    if any(e.get('phase')=='error' for e in events):
                        competitor.evaluate("""folder =>
                          window.__workerCompetitor.postMessage({folder,cmd:'probe'})""",
                          DIRECTORY)
                    competitor.wait_for_function(
                        "window.__competitorEvents.some(e=>e.phase==='acquired')",timeout=10000)
                    page.evaluate("window.__workerOwner.terminate()")
                    competitor.evaluate("window.__workerCompetitor.terminate()")
                    report['exclusive_handle_lock']='PASS'
                finally:
                    context.close()
                context=engine.launch_persistent_context(str(profile),headless=True,timeout=45000)
                try:
                    page=context.new_page()
                    page.goto(url,wait_until='load')
                    response=page.evaluate(SINGLE_WORKER,
                        {'folder':DIRECTORY,'cmd':'read','bytes':[]})
                    require_bytes(response)
                    report['restart_readback']='PASS'
                finally:context.close()
        finally:
            server.shutdown();server.server_close();worker.join(timeout=5)
    if all(report[key]=='PASS' for key in
           ('worker_flush','worker_readback','exclusive_handle_lock','restart_readback')):
        report['status']='PASS_DISPOSABLE_WORKER_OPFS'
    return report

def run(browser_name):
    try:return probe(browser_name)
    except Exception as exc:
        report=template(browser_name)
        report['error_type']=type(exc).__name__
        return report

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser',choices=('chromium','firefox'),required=True)
    parser.add_argument('--output')
    args=parser.parse_args(argv)
    report=run(args.browser)
    payload=json.dumps(report,ensure_ascii=False,indent=2)+'\n'
    if args.output:
        path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(payload,encoding='utf-8')
    print(payload)
    return 0 if report['status']=='PASS_DISPOSABLE_WORKER_OPFS' else 2

if __name__=='__main__':sys.exit(main())
