#!/usr/bin/env python3
"""Native Chromium OPFS quota override on isolated loopback origin; NOT product acceptance."""
import argparse
import hashlib
import json
import sys
import tempfile
import threading
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path

PAYLOAD=[17,29,47,71]*8192
DIGEST=hashlib.sha256(bytes(PAYLOAD)).hexdigest()
FOLDER='isolated-native-quota-v8'
INITIAL=r"""async ({folder,payload})=>{
 const root=await navigator.storage.getDirectory(),d=await root.getDirectoryHandle(folder,{create:true});
 const f=await d.getFileHandle('baseline.bin',{create:true}),w=await f.createWritable();
 await w.write(Uint8Array.from(payload));await w.close();
 const s=await d.getFileHandle('manifest.json',{create:true}),sw=await s.createWritable();
 await sw.write(JSON.stringify({active:'baseline.bin',generation:1}));await sw.close();
 return true;
}"""
TRY_BIG=r"""async folder=>{
 const root=await navigator.storage.getDirectory(),d=await root.getDirectoryHandle(folder);
 const f=await d.getFileHandle('large-candidate.bin',{create:true}),w=await f.createWritable();
 let stage='write',exceptionName='NONE';
 try{await w.write(new Uint8Array(8*1024*1024));stage='close';await w.close();}
 catch(e){exceptionName=e.name;try{await w.abort();}catch(e){}}
 return {stage,exceptionName};
}"""
READ=r"""async folder=>{
 const root=await navigator.storage.getDirectory(),d=await root.getDirectoryHandle(folder);
 const s=JSON.parse(await(await d.getFileHandle('manifest.json')).getFile().then(f=>f.text()));
 const data=new Uint8Array(await(await d.getFileHandle(s.active)).getFile().then(f=>f.arrayBuffer()));
 const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',data))).map(x=>x.toString(16).padStart(2,'0')).join('');
 return {digest,generation:s.generation,size:data.byteLength};
}"""

class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  if self.path!='/fixture':self.send_error(404);return
  data=b'<!doctype html><html><body>Isolated Chromium quota fixture</body></html>'
  self.send_response(200);self.send_header('Content-Length',str(len(data)))
  self.send_header('Content-Type','text/html; charset=utf-8')
  self.end_headers();self.wfile.write(data)
 def log_message(self,*args):pass

def report_template():
 return {'schema':'chromium-native-quota/v1',
  'generated_at_utc':datetime.now(timezone.utc).isoformat(),
  'browser':'chromium','mode':'cdp_storage_override_on_ephemeral_origin',
  'baseline_sha256':DIGEST,'native_quota_override':'NOT_RUN',
  'native_quota_error':'NOT_RUN','baseline_after_failure':'NOT_RUN',
  'restart_integrity':'NOT_RUN','firefox_native_quota':'NOT_RUN',
  'power_loss':'NOT_RUN','product_e2e':'NOT_RUN',
  'release_readiness':'NO_GO','status':'BLOCKED'}

def verify_baseline(item):
 if(item.get('digest')!=DIGEST or item.get('generation')!=1 or
    item.get('size')!=len(PAYLOAD)):
  raise AssertionError('COMMITTED_BASELINE_LOST')

def probe():
 from playwright.sync_api import sync_playwright
 report=report_template()
 with tempfile.TemporaryDirectory(prefix='native-quota-v8-') as tmp:
  profile=Path(tmp)/'profile'
  server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
  thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  url=f'http://127.0.0.1:{server.server_port}/fixture'
  try:
   with sync_playwright() as p:
    ctx=p.chromium.launch_persistent_context(str(profile),headless=True,timeout=45000)
    try:
     page=ctx.new_page();page.goto(url,wait_until='load')
     page.evaluate(INITIAL,{'folder':FOLDER,'payload':PAYLOAD})
     verify_baseline(page.evaluate(READ,FOLDER))
     origin=page.evaluate('location.origin')
     session=ctx.new_cdp_session(page)
     observed=session.send('Storage.getUsageAndQuota',{'origin':origin})
     ceiling=int(observed['usage'])+256*1024
     try:
      session.send('Storage.overrideQuotaForOrigin',{'origin':origin,'quotaSize':ceiling})
      active=session.send('Storage.getUsageAndQuota',{'origin':origin})
      if not active.get('overrideActive'):
       raise AssertionError('NATIVE_QUOTA_OVERRIDE_NOT_ACTIVE')
      report['native_quota_override']='PASS'
      attempt=page.evaluate(TRY_BIG,FOLDER)
      report['native_quota_error']=attempt['exceptionName']
      if attempt['exceptionName']!='QuotaExceededError':
       raise AssertionError('NATIVE_QUOTA_EXCEPTION_NOT_OBSERVED')
      verify_baseline(page.evaluate(READ,FOLDER))
      report['baseline_after_failure']='PASS'
     finally:
      session.send('Storage.overrideQuotaForOrigin',{'origin':origin})
    finally:ctx.close()
    ctx=p.chromium.launch_persistent_context(str(profile),headless=True,timeout=45000)
    try:
     page=ctx.new_page();page.goto(url,wait_until='load')
     verify_baseline(page.evaluate(READ,FOLDER))
     report['restart_integrity']='PASS'
    finally:ctx.close()
  finally:
   server.shutdown();server.server_close();thread.join(timeout=5)
 if(report['native_quota_override']=='PASS' and report['native_quota_error']=='QuotaExceededError'
     and report['baseline_after_failure']=='PASS' and report['restart_integrity']=='PASS'):
  report['status']='PASS_CHROMIUM_NATIVE_QUOTA'
 return report

def run():
 try:return probe()
 except Exception as error:
  report=report_template()
  report['error_type']=type(error).__name__
  return report

def main(argv=None):
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--output')
 args=parser.parse_args(argv)
 report=run();payload=json.dumps(report,ensure_ascii=False,indent=2)+'\n'
 if args.output:
  target=Path(args.output);target.parent.mkdir(parents=True,exist_ok=True)
  target.write_text(payload,encoding='utf-8')
 print(payload)
 return 0 if report['status']=='PASS_CHROMIUM_NATIVE_QUOTA' else 2
if __name__=='__main__':sys.exit(main())
