"""Synthetic extension-only Chromium OPFS/Web Locks probe. Never load product data."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import tempfile

DATA=[7,31,151,2,0,255]
DIGEST=hashlib.sha256(bytes(DATA)).hexdigest()
SCHEMA='gpt1-synthetic-opfs-browser/v1'
FLAGS=('worker','popup_identity','write_close','abort_preserves','second_page',
       'lock_exclusion','lock_released_on_restart','persisted_after_restart')

def evidence_ok(record):
    return (record.get('schema')==SCHEMA and record.get('product_executed') is False
            and record.get('external_network')=='DISABLED'
            and record.get('release_decision')=='CANDIDATE_NO_GO'
            and record.get('sha256')==DIGEST
            and all(record.get(x)=='PASS' for x in FLAGS))

def make_fixture(folder):
    folder.mkdir()
    (folder/'manifest.json').write_text(json.dumps({
        'manifest_version':3,'name':'GPT1 synthetic OPFS probe','version':'1.0',
        'background':{'service_worker':'worker.js'},
        'action':{'default_popup':'popup.html'},'permissions':['storage']}))
    (folder/'worker.js').write_text(
        "chrome.runtime.onMessage.addListener((x,s,r)=>{if(x==='ping')r('pong')});")
    (folder/'popup.html').write_text(
        '<!doctype html><meta charset="utf-8"><title>GPT1 synthetic</title>')

def get_id(context):
    for _ in range(2):
        ids=[]
        for worker in context.service_workers:
            found=re.fullmatch(r'chrome-extension://([a-p]{32})/worker\.js',worker.url)
            if found: ids.append(found.group(1))
        if len(ids)==1:return ids[0]
        if len(ids)>1:raise RuntimeError('MULTIPLE_EXTENSION_WORKERS')
        try:context.wait_for_event('serviceworker',timeout=12000)
        except Exception:pass
    raise RuntimeError('SYNTHETIC_EXTENSION_WORKER_MISSING')

JS_WRITE=r"""async bytes => {
  if(!navigator.storage?.getDirectory || !navigator.locks?.request || !crypto?.subtle)
    throw Error('OPFS_OR_LOCKS_UNAVAILABLE');
  const dir=await (await navigator.storage.getDirectory()).getDirectoryHandle('gpt1_v41',{create:true});
  const file=await dir.getFileHandle('segment.bin',{create:true});
  const writer=await file.createWritable();await writer.write(Uint8Array.from(bytes));await writer.close();
  const read=Array.from(new Uint8Array(await (await file.getFile()).arrayBuffer()));
  const w=await file.createWritable();await w.write(Uint8Array.of(1,1,1));await w.abort();
  const after=Array.from(new Uint8Array(await (await file.getFile()).arrayBuffer()));
  return {read,after};
}"""
JS_READ=r"""async () => {
  const dir=await (await navigator.storage.getDirectory()).getDirectoryHandle('gpt1_v41');
  const file=await dir.getFileHandle('segment.bin');
  const bytes=new Uint8Array(await (await file.getFile()).arrayBuffer());
  const digest=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))]
    .map(x=>x.toString(16).padStart(2,'0')).join('');
  return {bytes:Array.from(bytes),digest};
}"""

def open_page(context,extension_id):
    page=context.new_page()
    page.goto('chrome-extension://'+extension_id+'/popup.html',
              wait_until='domcontentloaded',timeout=10000)
    ident=page.evaluate('() => ({id:chrome.runtime.id,origin:location.origin})')
    if ident!={'id':extension_id,'origin':'chrome-extension://'+extension_id}:
        raise RuntimeError('EXTENSION_IDENTITY_MISMATCH')
    return page

def run(browser,parent_netns):
    result={'schema':SCHEMA,'status':'BLOCKED','release_decision':'CANDIDATE_NO_GO',
            'product_executed':False,'external_network':'DISABLED',
            'real_power_loss':'NOT_TESTED','rplay_product':'NOT_TESTED','sha256':None}
    from isolated_extension_e2e import isolation_check
    faults=isolation_check(parent_netns)
    if faults:
        result.update(reason='ISOLATION_PRECONDITION_FAILED',isolation_faults=faults)
        return result
    try:
        from playwright.sync_api import sync_playwright
        with tempfile.TemporaryDirectory(prefix='gpt1-opfs-only-') as tmp:
            root=Path(tmp); ext=root/'extension';make_fixture(ext)
            profile=root/'profile'
            opts=dict(headless=True,channel='chromium',chromium_sandbox=True,timeout=20000,args=[
                '--disable-extensions-except='+str(ext),'--load-extension='+str(ext),
                '--disable-background-networking','--disable-sync',
                '--no-first-run','--disable-component-update'])
            if browser:opts['executable_path']=browser
            with sync_playwright() as pw:
                ctx=pw.chromium.launch_persistent_context(str(profile),**opts)
                try:
                    eid=get_id(ctx);result['worker']='PASS'
                    a=open_page(ctx,eid);b=open_page(ctx,eid)
                    result['popup_identity']='PASS'
                    written=a.evaluate(JS_WRITE,DATA)
                    if written['read']!=DATA:raise RuntimeError('WRITE_CLOSE_NOT_READABLE')
                    result['write_close']='PASS'
                    if written['after']!=DATA:raise RuntimeError('ABORT_DID_NOT_PRESERVE_DATA')
                    result['abort_preserves']='PASS'
                    other=b.evaluate(JS_READ)
                    if other!={'bytes':DATA,'digest':DIGEST}:
                        raise RuntimeError('SECOND_PAGE_OPFS_DID_NOT_MATCH')
                    result['second_page']='PASS'
                    a.evaluate("""() => {window.gpt1_release=null;window.gpt1_lock=navigator.locks.request(
                      'gpt1_opfs_cross_page',()=>new Promise(resolve=>window.gpt1_release=resolve));}""")
                    a.wait_for_function('() => typeof window.gpt1_release === "function"',timeout=6000)
                    b.evaluate("""() => {window.gpt1_entered=false;window.gpt1_wait=navigator.locks.request(
                      'gpt1_opfs_cross_page',()=>{window.gpt1_entered=true;});}""")
                    b.wait_for_timeout(250)
                    if b.evaluate('() => window.gpt1_entered'):
                        raise RuntimeError('WEB_LOCKS_FAILED_MUTUAL_EXCLUSION')
                    a.evaluate('() => window.gpt1_release()')
                    b.wait_for_function('() => window.gpt1_entered === true',timeout=6000)
                    result['lock_exclusion']='PASS'
                    b.evaluate("""() => {window.gpt1_held=null;window.gpt1_restart_lock=navigator.locks.request(
                      'gpt1_opfs_restart',()=>new Promise(resolve=>window.gpt1_held=resolve));}""")
                    b.wait_for_function('() => typeof window.gpt1_held === "function"',timeout=6000)
                finally:
                    ctx.close()
                ctx=pw.chromium.launch_persistent_context(str(profile),**opts)
                try:
                    new_eid=get_id(ctx)
                    if new_eid!=eid:raise RuntimeError('EXTENSION_ID_CHANGED_AFTER_RESTART')
                    page=open_page(ctx,eid)
                    if page.evaluate(JS_READ)!={'bytes':DATA,'digest':DIGEST}:
                        raise RuntimeError('OPFS_BYTES_NOT_PERSISTENT_AFTER_RESTART')
                    result['persisted_after_restart']='PASS'
                    available=page.evaluate("""async () => navigator.locks.request(
                      'gpt1_opfs_restart',{ifAvailable:true},lock=>Boolean(lock))""")
                    if available is not True:raise RuntimeError('WEB_LOCK_NOT_RELEASED_AFTER_RESTART')
                    result['lock_released_on_restart']='PASS'
                finally:
                    ctx.close()
    except Exception as error:
        result['reason']=(type(error).__name__+': '+str(error))[:180]
        return result
    result['sha256']=DIGEST
    result['status']='PASS_SYNTHETIC_BROWSER_OPFS' if evidence_ok(result) else 'BLOCKED'
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--parent-netns',required=True)
    p.add_argument('--browser-executable',default=None)
    args=p.parse_args()
    result=run(args.browser_executable,args.parent_netns)
    print(json.dumps(result,sort_keys=True))
    return 0 if result['status']=='PASS_SYNTHETIC_BROWSER_OPFS' else 2

if __name__=='__main__':raise SystemExit(main())
