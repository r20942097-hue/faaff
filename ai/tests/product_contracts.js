'use strict';
// This file intentionally imports the *actual* RPLAY pure modules by path.
// It makes no network requests, writes no files, and uses only synthetic metadata.
const assert = require('node:assert/strict');
const path = require('node:path');
const directory = process.env.GPT1_PURE_MODULE_DIR;
if (!directory || !path.isAbsolute(directory)) throw Error('MODULE_DIR_REQUIRED');
const W = require(path.join(directory, 'hls_window.js'));
const H = require(path.join(directory, 'http_resume.js'));
const L = require(path.join(directory, 'hls_ledger.js'));
global.RspHlsWindow = W;
let tests = 0;
function check(name, fn) { fn(); tests++; }
function fails(name, fn, code) { check(name, () => assert.throws(fn, new RegExp(code))); }
const fs = require('node:fs');
const cp = require('node:child_process');
check('node-is-not-root',()=>assert.notEqual(process.getuid(),0));
check('out-of-scope-file-read-denied',()=>assert.throws(()=>fs.readFileSync('/etc/passwd'),{code:'ERR_ACCESS_DENIED'}));
check('child-process-permission-denied',()=>assert.throws(()=>cp.execFileSync('/bin/true'),{code:'ERR_ACCESS_DENIED'}));

function playlist(first, count, extra='') {
 return ['#EXTM3U', '#EXT-X-VERSION:3', `#EXT-X-MEDIA-SEQUENCE:${first}`,
  ...Array.from({length:count}, (_,i)=>`#EXTINF:4.0,\nseg-${i}.ts`), extra].join('\n');
}
check('snapshot',()=>assert.deepEqual(W.snapshot(playlist(100,3)).first,100));
check('snapshot-last',()=>assert.equal(W.snapshot(playlist(100,3)).lastExclusive,103));
check('sliding-no-gap',()=>assert.equal(W.compareWindows(W.snapshot(playlist(100,3)), W.snapshot(playlist(102,3))).state,'NO_DEFINITE_WINDOW_GAP'));
check('sliding-gap',()=>assert.equal(W.compareWindows(W.snapshot(playlist(100,3)), W.snapshot(playlist(106,3))).lostSegments,3));
check('sequence-rewind',()=>assert.equal(W.compareWindows(W.snapshot(playlist(106,3)), W.snapshot(playlist(100,3))).state,'SEQUENCE_REWIND'));
check('delta-rejected',()=>assert.equal(W.compareWindows(W.snapshot(playlist(100,3,'#EXT-X-SKIP:SKIPPED-SEGMENTS=3')),W.snapshot(playlist(106,3))).state,'UNSAFE_DELTA_PLAYLIST'));
check('parts-warning',()=>assert.equal(W.compareWindows(W.snapshot(playlist(100,3)),W.snapshot(playlist(101,3,'#EXT-X-PART:DURATION=1,URI="p0"'))).warning, 'PARTS_NOT_TRACKED'));
fails('master-rejected',()=>W.snapshot('#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=1000\nvariant.m3u8'),'NOT_MEDIA_PLAYLIST');
fails('missing-uri',()=>W.snapshot('#EXTM3U\n#EXTINF:3.0,'),'SEGMENT_URI_MISSING');
fails('invalid-sequence',()=>W.snapshot('#EXTM3U\n#EXT-X-MEDIA-SEQUENCE:-1'),'BAD_SEQUENCE');
check('range-append',()=>assert.equal(H.verifyTransfer({storedBytes:100,receivedBytes:50,rangeRequested:true,status:206,contentRangeHeader:'bytes 100-149/200'}).action,'APPEND'));
check('range-complete',()=>assert.equal(H.verifyTransfer({storedBytes:100,receivedBytes:50,rangeRequested:true,status:206,contentRangeHeader:'bytes 100-149/150'}).remaining,0));
check('200-no-append',()=>assert.equal(H.verifyTransfer({storedBytes:100,receivedBytes:200,rangeRequested:true,status:200}).action,'RESTART_FROM_ZERO'));
check('416-hash-gate',()=>assert.equal(H.verifyTransfer({storedBytes:100,receivedBytes:0,rangeRequested:true,status:416,contentRangeHeader:'bytes */100'}).action,'VERIFY_LOCAL_HASH'));
check('416-unknown',()=>assert.equal(H.verifyTransfer({storedBytes:101,receivedBytes:0,rangeRequested:true,status:416,contentRangeHeader:'bytes */100'}).action,'REJECT'));
check('weak-if-range',()=>assert.equal(H.verifyTransfer({storedBytes:100,receivedBytes:10,rangeRequested:true,status:206,ifRange:'W/"abc"',contentRangeHeader:'bytes 100-109/110'}).action,'RESTART_FROM_ZERO'));
check('etag-change',()=>assert.equal(H.verifyTransfer({storedBytes:100,receivedBytes:10,rangeRequested:true,status:206,previousETag:'"a"',responseETag:'"b"',contentRangeHeader:'bytes 100-109/110'}).action,'RESTART_FROM_ZERO'));
check('gzip-reject',()=>assert.equal(H.verifyTransfer({storedBytes:100,receivedBytes:10,rangeRequested:true,status:206,contentEncoding:'gzip',contentRangeHeader:'bytes 100-109/110'}).action,'REJECT'));
check('range-misaligned',()=>assert.equal(H.verifyTransfer({storedBytes:100,receivedBytes:50,rangeRequested:true,status:206,contentRangeHeader:'bytes 101-150/200'}).action,'REJECT'));
check('range-truncated',()=>assert.equal(H.verifyTransfer({storedBytes:100,receivedBytes:50,rangeRequested:true,status:206,contentRangeHeader:'bytes 100-145/200'}).action,'REJECT'));
check('range-overflow',()=>assert.equal(H.verifyTransfer({storedBytes:Number.MAX_SAFE_INTEGER,receivedBytes:100,rangeRequested:true,status:206,contentRangeHeader:`bytes ${Number.MAX_SAFE_INTEGER}-9007199254740992/*`}).action,'REJECT'));
check('ledger-schema',()=>assert.deepEqual(L.parseLedger(JSON.stringify({schema:'rsp-ledger/v1',sequences:[100,101,102]})),[100,101,102]));
fails('ledger-dup',()=>L.parseLedger(JSON.stringify({schema:'rsp-ledger/v1',sequences:[100,100]})),'LEDGER_SEQUENCE_DUPLICATE');
fails('ledger-unsorted',()=>L.parseLedger(JSON.stringify({schema:'rsp-ledger/v1',sequences:[101,100]})),'LEDGER_SEQUENCE_UNORDERED');
fails('ledger-invalid',()=>L.parseLedger(JSON.stringify({schema:'rsp-ledger/v1',sequences:[true]})),'LEDGER_SEQUENCE_INVALID');
fails('ledger-wrong-schema',()=>L.parseLedger(JSON.stringify({schema:'other',sequences:[]})),'LEDGER_SCHEMA_UNSUPPORTED');
check('ledger-missing-confirmed',()=>{
 const before=W.snapshot(playlist(100,3)),after=W.snapshot(playlist(106,3));
 const r=L.reconcile(before,after,[100,101,102,103,105,106]);
 assert.equal(r.reconciliation.confirmedMissing,1);
 assert.deepEqual(r.reconciliation.missingSequences,[104]);
 assert.equal(r.reconciliation.verdict,'LOSS_CONFIRMED');
});
check('ledger-unrelated',()=>{
 const r=L.reconcile(W.snapshot(playlist(100,3)),W.snapshot(playlist(106,3)),[10,11]);
 assert.equal(r.reconciliation.verdict,'LEDGER_UNRELATED');
});
check('ledger-no-loss',()=>{
 const r=L.reconcile(W.snapshot(playlist(100,3)),W.snapshot(playlist(106,3)),[100,101,102,103,104,105]);
 assert.equal(r.reconciliation.verdict,'NO_LOSS_EVIDENCE');
});
check('bounded-large-gap',()=>{
 const r=L.reconcile(W.snapshot(playlist(100,2)),W.snapshot(playlist(100000,2)),[100,101]);
 assert.equal(r.reconciliation.missingSequences.length, L.MISSING_LIST_CAP);
 assert.equal(r.reconciliation.missingTruncated, true);
});
// Deterministic adversarial consistency of HTTP range accounting.
for(let i=1;i<=256;i++){
 const stored = (i*997)%100000, received = (i*31)%4096 + 1, total=stored+received+((i*13)%500);
 const header=`bytes ${stored}-${stored+received-1}/${total}`;
 const ok=H.verifyTransfer({storedBytes:stored,receivedBytes:received,rangeRequested:true,status:206,contentRangeHeader:header});
 check('property-'+i,()=>{assert.equal(ok.action,'APPEND');assert.equal(ok.newLength,stored+received);assert.equal(ok.remaining,total-stored-received)});
}
// Sliding playlist and ledger property checks against an independent simple oracle.
for (let i=0; i<128; i++) {
 const base=10000+i*10, overlap=(i%4), gap=3+(i%7);
 const before=W.snapshot(playlist(base,3));
 const after=W.snapshot(playlist(base+3+gap,2));
 const inGap=Array.from({length:gap}, (_,k)=>base+3+k).filter((_,k)=>k%4===overlap);
 const present=[base,base+1,base+2,...inGap,base+3+gap];
 const observed=L.reconcile(before,after,present);
 check('gap-invariant-'+i,()=> {
   assert.equal(observed.reconciliation.confirmedMissing,gap-inGap.length);
   assert.equal(observed.reconciliation.missingSequences.length,gap-inGap.length);
   assert.equal(observed.reconciliation.suspected.count,gap);
   assert.equal(observed.reconciliation.verdict,
      gap-inGap.length ? 'LOSS_CONFIRMED' : 'NO_LOSS_EVIDENCE');
 });
}
process.stdout.write(JSON.stringify({status:'PASS', count:tests, test_scope:'RPLAY v2.67 actual pure HLS ledger/window/range JS; synthetic metadata; restricted Node permissions; not browser/recording E2E'})+'\n');
