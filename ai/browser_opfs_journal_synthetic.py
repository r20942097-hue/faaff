"""SYNTHETIC extension-only OPFS journal replay in real Chromium; NO product ZIP."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import tempfile
from browser_opfs_runtime_probe import make_extension, extension_worker_id
from isolated_extension_e2e import isolation_check

FLAGS=('prepare_replay','orphan_rollback','commit_replay','corrupt_fail_closed','cross_page_lock','restart_persistence')

def accepted(r):
    return (r.get('scope')=='SYNTHETIC_BROWSER_JOURNAL_ONLY' and
            r.get('product_executed') is False and
            r.get('external_network')=='DISABLED' and
            r.get('release_decision')=='CANDIDATE_NO_GO' and
            all(r.get(k)=='PASS' for k in FLAGS))

def open_page(ctx,eid):
    p=ctx.new_page()
    p.goto('chrome-extension://'+eid+'/popup.html',wait_until='load',timeout=12000)
    actual=p.evaluate('() => ({id:chrome.runtime.id,origin:location.origin,ready:!!window.GPT1_JOURNAL})')
    if actual!={'id':eid,'origin':'chrome-extension://'+eid,'ready':True}:
        raise RuntimeError('SYNTHETIC_EXTENSION_ORIGIN_MISMATCH')
    return p

def worker_id(ctx):
    eid=extension_worker_id(ctx.service_workers)
    if eid:return eid
    try:ctx.wait_for_event('serviceworker',timeout=12000)
    except Exception:pass
    eid=extension_worker_id(ctx.service_workers)
    if not eid:raise RuntimeError('WORKER_NOT_OBSERVED')
    return eid

def run(parent_ns,browser=None):
    result={k:'NOT_RUN' for k in FLAGS}
    result.update(scope='SYNTHETIC_BROWSER_JOURNAL_ONLY',status='BLOCKED',
                  release_decision='CANDIDATE_NO_GO',external_network='DISABLED',
                  product_executed=False,real_process_kill='NOT_TESTED',power_loss='NOT_TESTED')
    faults=isolation_check(parent_ns)
    if faults:
        result['reason']='ISOLATION_PRECONDITION_FAILED:'+','.join(faults)
        return result
    try:
        from playwright.sync_api import sync_playwright
        with tempfile.TemporaryDirectory(prefix='gpt1-journal-only-') as temp:
            home=Path(temp);ext=home/'extension'
            make_extension(ext)
            (ext/'journal_synthetic.js').write_bytes(Path(__file__).with_name('journal_synthetic.js').read_bytes())
            (ext/'popup.html').write_text('<!doctype html><meta charset="utf-8"><script src="journal_synthetic.js"></script>',encoding='utf-8')
            opts=dict(headless=True,channel='chromium',chromium_sandbox=True,timeout=20000,args=[
                '--disable-extensions-except='+str(ext),'--load-extension='+str(ext),
                '--disable-background-networking','--disable-sync','--no-first-run','--disable-component-update'])
            if browser:opts['executable_path']=browser
            profile=str(home/'profile')
            with sync_playwright() as pw:
                # PREPARED journal survives clean browser context teardown.
                ctx=pw.chromium.launch_persistent_context(profile,**opts)
                try:
                    eid=worker_id(ctx)
                    if open_page(ctx,eid).evaluate('() => window.GPT1_JOURNAL.prepare()')!='PREPARED':
                        raise RuntimeError('PREPARE_FAILED')
                finally:ctx.close()
                ctx=pw.chromium.launch_persistent_context(profile,**opts)
                try:
                    if worker_id(ctx)!=eid:raise RuntimeError('EXTENSION_ID_CHANGED')
                    page=open_page(ctx,eid)
                    if page.evaluate('() => window.GPT1_JOURNAL.recover()')!='ROLLED_BACK':
                        raise RuntimeError('PREPARED_ROLLBACK_FAILED')
                    expected={'old':[1,2,3],'fresh':None,'journal':False}
                    if page.evaluate('() => window.GPT1_JOURNAL.state()')!=expected:
                        raise RuntimeError('OLD_DATA_NOT_PRESERVED')
                    result['prepare_replay']='PASS'
                    page.evaluate('() => window.GPT1_JOURNAL.prepareWithOrphan()')
                    if page.evaluate('() => window.GPT1_JOURNAL.recover()')!='ROLLED_BACK':
                        raise RuntimeError('ORPHAN_ROLLBACK_FAILED')
                    if page.evaluate('() => window.GPT1_JOURNAL.state()')!=expected:
                        raise RuntimeError('ORPHAN_DATA_CHANGED')
                    result['orphan_rollback']='PASS'
                    if page.evaluate('() => window.GPT1_JOURNAL.commit()')!='COMMITTED':
                        raise RuntimeError('POSTCOMMIT_PREPARATION_FAILED')
                finally:ctx.close()
                ctx=pw.chromium.launch_persistent_context(profile,**opts)
                try:
                    if worker_id(ctx)!=eid:raise RuntimeError('EXTENSION_ID_CHANGED')
                    page=open_page(ctx,eid)
                    if page.evaluate('() => window.GPT1_JOURNAL.recover()')!='COMMIT_REPLAYED':
                        raise RuntimeError('POSTCOMMIT_REPLAY_FAILED')
                    if page.evaluate('() => window.GPT1_JOURNAL.state()')!={
                        'old':None,'fresh':[4,5,6],'journal':False}:
                        raise RuntimeError('COMMITTED_DATA_NOT_PERSISTENT')
                    result['commit_replay']='PASS'
                    result['restart_persistence']='PASS'
                    page.evaluate('() => window.GPT1_JOURNAL.corrupt()')
                    error=page.evaluate("""async () => {
                      try {await window.GPT1_JOURNAL.recover();return 'UNSAFE_SUCCESS';}
                      catch(e){return e.message;}}""")
                    if error!='JOURNAL_CORRUPT':raise RuntimeError('CORRUPT_JOURNAL_ACCEPTED')
                    if page.evaluate('() => window.GPT1_JOURNAL.state()')['fresh']!=[4,5,6]:
                        raise RuntimeError('CORRUPT_JOURNAL_CHANGED_DATA')
                    result['corrupt_fail_closed']='PASS'
                    b=open_page(ctx,eid)
                    page.evaluate("""() => {
                      window.gpt1Release=null;
                      window.gpt1Hold=navigator.locks.request('gpt1_v42_journal',
                        {mode:'exclusive'},()=>new Promise(resolve=>window.gpt1Release=resolve));}""")
                    page.wait_for_function('() => typeof window.gpt1Release === "function"',timeout=5000)
                    request="""async () => navigator.locks.request('gpt1_v42_journal',
                      {mode:'exclusive',ifAvailable:true},lock=>Boolean(lock))"""
                    if b.evaluate(request):raise RuntimeError('WEB_LOCKS_MUTUAL_EXCLUSION_FAILED')
                    page.evaluate('() => window.gpt1Release()')
                    page.evaluate('() => window.gpt1Hold')
                    if not b.evaluate(request):raise RuntimeError('WEB_LOCK_RELEASE_FAILED')
                    result['cross_page_lock']='PASS'
                finally:ctx.close()
    except Exception as exc:
        result['reason']=(type(exc).__name__+': '+str(exc))[:240]
        return result
    if accepted(result):result['status']='PASS_SYNTHETIC_JOURNAL_BROWSER'
    return result

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--parent-netns',required=True)
    parser.add_argument('--browser-executable')
    args=parser.parse_args()
    result=run(args.parent_netns,args.browser_executable)
    print(json.dumps(result,sort_keys=True))
    return 0 if accepted(result) else 2

if __name__=='__main__':raise SystemExit(main())
