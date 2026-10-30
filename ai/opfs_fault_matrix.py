#!/usr/bin/env python3
"""Cross-browser synthetic OPFS fault matrix; never product or physical-quota acceptance."""
import argparse
import hashlib
import json
import sys
import tempfile
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

A=[11,22,33,44]*64
B=[71,82,93,104]*64
C=[9,19,29,39]*64
SHA={key:hashlib.sha256(bytes(value)).hexdigest() for key,value in (('A',A),('B',B),('C',C))}
FAULTS=('simulated_quota_before_blob','abort_binary_writer','interrupt_after_binary_close',
        'abort_manifest_writer','interrupt_after_manifest_close','reject_same_id_conflict')
DIRECTORY='opfs-v8-'

FAULT_JS=r"""async ({folder,scenario,a,b}) => {
 const root=await navigator.storage.getDirectory();
 const d=await root.getDirectoryHandle(folder,{create:true});
 async function digest(bytes){return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))).map(x=>x.toString(16).padStart(2,'0')).join('');}
 async function put(name,value){const file=await d.getFileHandle(name,{create:true});const w=await file.createWritable();await w.write(Uint8Array.from(value));await w.close();}
 async function manifest(){return JSON.parse(await(await d.getFileHandle('state.json')).getFile().then(f=>f.text()));}
 async function commit(state){const file=await d.getFileHandle('state.json',{create:true});const w=await file.createWritable();await w.write(JSON.stringify(state));await w.close();}
 async function read(state){const f=await d.getFileHandle(state.active);const bytes=new Uint8Array(await(await f.getFile()).arrayBuffer());return {sha:await digest(bytes),bytes:Array.from(bytes)};}
 const shaA=await digest(Uint8Array.from(a)),shaB=await digest(Uint8Array.from(b));
 await put('blob-a.bin',a);await commit({generation:1,active:'blob-a.bin',sha256:shaA});
 let fault='NOT_THROWN';
 try{
  if(scenario==='simulated_quota_before_blob')throw new DOMException('synthetic injected quota','QuotaExceededError');
  if(scenario==='reject_same_id_conflict'){
    const old=await manifest();
    if(old.active==='blob-a.bin'&&old.sha256!==shaB)throw Error('CONTENT_ID_CONFLICT');
  }
  const f=await d.getFileHandle('blob-b.bin',{create:true});
  const writer=await f.createWritable();
  await writer.write(Uint8Array.from(b));
  if(scenario==='abort_binary_writer'){await writer.abort();throw Error('SYNTHETIC_BINARY_ABORT');}
  await writer.close();
  if(scenario==='interrupt_after_binary_close')throw Error('SYNTHETIC_PRECOMMIT_INTERRUPTION');
  const state=await d.getFileHandle('state.json');
  const mw=await state.createWritable();
  await mw.write(JSON.stringify({generation:2,active:'blob-b.bin',sha256:shaB}));
  if(scenario==='abort_manifest_writer'){await mw.abort();throw Error('SYNTHETIC_MANIFEST_ABORT');}
  await mw.close();
  if(scenario==='interrupt_after_manifest_close')throw Error('SYNTHETIC_POSTCOMMIT_INTERRUPTION');
 }catch(error){fault=error.name==='QuotaExceededError'?'SIMULATED_QUOTA':error.message;}
 const expected={
  simulated_quota_before_blob:'SIMULATED_QUOTA',
  abort_binary_writer:'SYNTHETIC_BINARY_ABORT',
  interrupt_after_binary_close:'SYNTHETIC_PRECOMMIT_INTERRUPTION',
  abort_manifest_writer:'SYNTHETIC_MANIFEST_ABORT',
  interrupt_after_manifest_close:'SYNTHETIC_POSTCOMMIT_INTERRUPTION',
  reject_same_id_conflict:'CONTENT_ID_CONFLICT'
 }[scenario];
 if(fault!==expected)throw Error('FAULT_INJECTION_DID_NOT_FIRE');
 const state=await manifest(),current=await read(state);
 if(state.sha256!==current.sha||(state.generation===1?current.sha!==shaA:current.sha!==shaB))throw Error('LIVE_DATA_INTEGRITY_FAILURE');
 const names=[];for await(const [name] of d.entries())names.push(name);
 return {scenario,fault,generation:state.generation,active:state.active,sha256:current.sha,names:names.sort(),committed:state.generation===2};
}"""
INSPECT_JS=r"""async folder=>{
 const root=await navigator.storage.getDirectory(),d=await root.getDirectoryHandle(folder);
 const manifest=JSON.parse(await(await d.getFileHandle('state.json')).getFile().then(f=>f.text()));
 const bytes=new Uint8Array(await(await d.getFileHandle(manifest.active)).getFile().then(f=>f.arrayBuffer()));
 const sha=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))).map(x=>x.toString(16).padStart(2,'0')).join('');
 const names=[];for await(const [name] of d.entries())names.push(name);
 return {generation:manifest.generation,sha256:sha,declared:manifest.sha256,names:names.sort()};
}"""
CLEAN_JS=r"""async folder=>{
 const root=await navigator.storage.getDirectory(),d=await root.getDirectoryHandle(folder);
 const state=JSON.parse(await(await d.getFileHandle('state.json')).getFile().then(f=>f.text()));
 const removed=[];for await(const [name] of d.entries()){
  if(name.startsWith('blob-')&&name!==state.active){await d.removeEntry(name);removed.push(name);}
 }
 return removed.sort();
}"""
CONCURRENT_JS=r"""({folder,bytes,delayMs})=>{
 window.__v8txn={state:'RUNNING'};
 (async()=>{
  const root=await navigator.storage.getDirectory(),d=await root.getDirectoryHandle(folder,{create:true});
  const outcome=await navigator.locks.request('opfs-v8-'+folder,{mode:'exclusive'},async()=>{
   const sf=await d.getFileHandle('state.json'),state=JSON.parse(await(await sf.getFile()).text());
   await new Promise(resolve=>setTimeout(resolve,delayMs));
   const generation=state.generation+1,name='blob-g'+generation+'.bin';
   const bin=await d.getFileHandle(name,{create:true});
   const bw=await bin.createWritable();await bw.write(Uint8Array.from(bytes));await bw.close();
   const sha=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',Uint8Array.from(bytes)))).map(x=>x.toString(16).padStart(2,'0')).join('');
   const mw=await sf.createWritable();await mw.write(JSON.stringify({generation,active:name,sha256:sha}));await mw.close();
   return {generation,sha};
  });
  window.__v8txn={state:'DONE',...outcome};
 })().catch(e=>{window.__v8txn={state:'FAILED',errorType:e.name};});
 return true;
}"""
INITIAL_CONCURRENT_JS=r"""async ({folder,bytes})=>{
 const root=await navigator.storage.getDirectory(),d=await root.getDirectoryHandle(folder,{create:true});
 const b=await d.getFileHandle('blob-g1.bin',{create:true}),w=await b.createWritable();
 await w.write(Uint8Array.from(bytes));await w.close();
 const sha=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',Uint8Array.from(bytes)))).map(x=>x.toString(16).padStart(2,'0')).join('');
 const s=await d.getFileHandle('state.json',{create:true}),writer=await s.createWritable();
 await writer.write(JSON.stringify({generation:1,active:'blob-g1.bin',sha256:sha}));
 await writer.close();return sha;
}"""

class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  if self.path!='/fixture':
   self.send_error(404);return
  body=b'<!doctype html><html><body>OPFS fault injection fixture</body></html>'
  self.send_response(200)
  self.send_header('Content-Type','text/html; charset=utf-8')
  self.send_header('Content-Length',str(len(body)))
  self.end_headers();self.wfile.write(body)
 def log_message(self,*args):pass

def verify_item(scenario,item):
 generation=2 if scenario=='interrupt_after_manifest_close' else 1
 digest=SHA['B'] if generation==2 else SHA['A']
 if(item.get('generation')!=generation or item.get('sha256')!=digest or
    item.get('declared',digest)!=digest):
  raise AssertionError('FAULT_MATRIX_DATA_CORRUPTION_'+scenario)

def template(browser):
 return {'schema':'opfs-fault-matrix/v1',
  'generated_at_utc':datetime.now(timezone.utc).isoformat(),
  'browser':browser,'fixture':'synthetic_bytes_only','scenarios':{},
  'clean_restart':'NOT_RUN','orphan_recovery':'NOT_RUN',
  'web_locks_concurrency':'NOT_RUN','actual_quota_fault':'NOT_RUN',
  'forced_process_kill':'NOT_RUN','product_e2e':'NOT_RUN',
  'release_readiness':'NO_GO','status':'BLOCKED'}

def probe(browser_name):
 from playwright.sync_api import sync_playwright
 report=template(browser_name)
 with tempfile.TemporaryDirectory(prefix='opfs-v8-') as temp:
  profile=Path(temp)/'profile'
  server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
  thread=threading.Thread(target=server.serve_forever,daemon=True)
  thread.start()
  url=f'http://127.0.0.1:{server.server_port}/fixture'
  try:
   with sync_playwright() as p:
    browser=getattr(p,browser_name)
    context=browser.launch_persistent_context(str(profile),headless=True,timeout=45000)
    try:
     page=context.new_page();page.goto(url,wait_until='load')
     for fault in FAULTS:
      result=page.evaluate(FAULT_JS,{'folder':DIRECTORY+fault,'scenario':fault,'a':A,'b':B})
      verify_item(fault,result)
      report['scenarios'][fault]={'status':'PASS','fault':result['fault'],
         'committed':result['committed'],'sha256':result['sha256']}
     folder=DIRECTORY+'concurrent'
     page.evaluate(INITIAL_CONCURRENT_JS,{'folder':folder,'bytes':A})
     other=context.new_page();other.goto(url,wait_until='load')
     page.evaluate(CONCURRENT_JS,{'folder':folder,'bytes':B,'delayMs':250})
     other.evaluate(CONCURRENT_JS,{'folder':folder,'bytes':C,'delayMs':75})
     for ppage in (page,other):
      ppage.wait_for_function("window.__v8txn.state !== 'RUNNING'",timeout=15000)
     a=page.evaluate('window.__v8txn')
     b=other.evaluate('window.__v8txn')
     if({a.get('state'),b.get('state')}!={'DONE'} or
        sorted([a.get('generation'),b.get('generation')])!=[2,3]):
      raise AssertionError('WEB_LOCKS_WRITE_SERIALIZATION_FAILED')
     report['web_locks_concurrency']='PASS'
     final_sha=next(x['sha'] for x in (a,b) if x['generation']==3)
    finally:context.close()
    context=browser.launch_persistent_context(str(profile),headless=True,timeout=45000)
    try:
     page=context.new_page();page.goto(url,wait_until='load')
     for fault in FAULTS:
      folder=DIRECTORY+fault
      state=page.evaluate(INSPECT_JS,folder)
      verify_item(fault,state)
      removed=page.evaluate(CLEAN_JS,folder)
      state2=page.evaluate(INSPECT_JS,folder)
      verify_item(fault,state2)
      expected_orphans=(
       ['blob-b.bin'] if fault in ('abort_binary_writer',
        'interrupt_after_binary_close','abort_manifest_writer')
       else ['blob-a.bin'] if fault=='interrupt_after_manifest_close' else [])
      if removed!=expected_orphans:raise AssertionError('ORPHAN_RECOVERY_UNEXPECTED')
      expected_files=['state.json', 'blob-b.bin' if fault=='interrupt_after_manifest_close' else 'blob-a.bin']
      if sorted(state2['names'])!=sorted(expected_files):
       raise AssertionError('RECOVERY_LEFT_ORPHAN')
     report['clean_restart']='PASS'
     report['orphan_recovery']='PASS'
     state=page.evaluate(INSPECT_JS,DIRECTORY+'concurrent')
     if state['generation']!=3 or state['sha256']!=final_sha or state['declared']!=final_sha:
      raise AssertionError('CONCURRENT_RESTART_HASH_MISMATCH')
    finally:context.close()
  finally:
   server.shutdown();server.server_close();thread.join(timeout=5)
 if(len(report['scenarios'])==len(FAULTS) and
    all(x['status']=='PASS' for x in report['scenarios'].values()) and
    all(report[x]=='PASS' for x in ('clean_restart','orphan_recovery','web_locks_concurrency'))):
  report['status']='PASS_SYNTHETIC_FAULT_MATRIX'
 return report

def run(browser_name):
 try:return probe(browser_name)
 except Exception as error:
  report=template(browser_name)
  report['error_type']=type(error).__name__
  return report

def main(argv=None):
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--browser',choices=('chromium','firefox'),required=True)
 parser.add_argument('--output')
 args=parser.parse_args(argv)
 report=run(args.browser)
 payload=json.dumps(report,ensure_ascii=False,indent=2)+'\n'
 if args.output:
  dest=Path(args.output)
  dest.parent.mkdir(parents=True,exist_ok=True)
  dest.write_text(payload,encoding='utf-8')
 print(payload)
 return 0 if report['status']=='PASS_SYNTHETIC_FAULT_MATRIX' else 2
if __name__=='__main__':sys.exit(main())
