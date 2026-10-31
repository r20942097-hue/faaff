'use strict';
// Offline known-P0 proof against an explicitly supplied source with verified SHA-256.
// Uses a synthetic in-memory OPFS adapter: NOT real-browser/product release evidence.
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const EXPECTED = '3f1a00b89207f8cb783f59152db6ff230c300569f79b1e1eb691353b70218b9e';
const target = process.argv[2];
if (!target) throw Error('SOURCE_PATH_REQUIRED');
const sha = crypto.createHash('sha256').update(fs.readFileSync(target)).digest('hex');
if (sha !== EXPECTED) throw Error('SOURCE_SHA256_MISMATCH');
const source = require(path.resolve(target));
const missing = () => Object.assign(Error('not found'), {name: 'NotFoundError'});

class Dir {
  constructor(){this.files=new Map();this.children=new Map();this.failNextBinaryWrite=false;}
  async getDirectoryHandle(n,{create=false}={}){
    if(!this.children.has(n)){if(!create)throw missing();this.children.set(n,new Dir());}
    return this.children.get(n);
  }
  async getFileHandle(n,{create=false}={}){
    if(!this.files.has(n)){if(!create)throw missing();this.files.set(n,Buffer.alloc(0));}
    const folder=this;
    return {
      kind:'file',
      async getFile(){
        if(!folder.files.has(n))throw missing();
        const b=Buffer.from(folder.files.get(n));
        return {size:b.length,async text(){return b.toString('utf8')},
          async arrayBuffer(){return Uint8Array.from(b).buffer}};
      },
      async createWritable(){
        let parts=[],closed=false;
        return {
          async write(bytes){
            if(n.endsWith('.bin')&&folder.failNextBinaryWrite){
              folder.failNextBinaryWrite=false;
              throw Object.assign(Error('synthetic quota'),{name:'QuotaExceededError'});
            }
            parts.push(Buffer.from(bytes));
          },
          async close(){if(closed)throw Error('closed');closed=true;folder.files.set(n,Buffer.concat(parts))},
          async abort(){closed=true},
        };
      }
    };
  }
  async *entries(){for(const name of this.files.keys())yield [name,{kind:'file'}];}
  async removeEntry(n){if(!this.files.delete(n))throw missing();}
}

async function main(){
  const root=new Dir();
  const store=source.create({storage:{getDirectory:async()=>root},namespace:'repro',
    now:(()=>{let t=1;return()=>t++;})(),maxBytes:4,maxCount:3});
  const A='aaaaaaaa',B='bbbbbbbb';
  await store.put(A,Uint8Array.from([1,2,3]));
  assert.equal(await store.has(A),true);
  const folder=await(await root.getDirectoryHandle('rsp_seg')).getDirectoryHandle('repro');
  folder.failNextBinaryWrite=true;
  let caught=null;
  try{await store.put(B,Uint8Array.from([3,4,5]));}catch(e){caught=e.message;}
  const retained=await store.has(A);
  const reproduced=caught==='SEGMENT_QUOTA_EXCEEDED'&&!retained;
  console.log(JSON.stringify({schema:'rplay-source-p0-reproducer/v1',
    source_sha256:sha,injected_fault:'QuotaExceededError_on_B_bin_write',
    B_error:caught,old_A_survives:retained,known_bad_reproduced:reproduced,
    environment:'in_memory_opfs_mock_only',real_browser:'NOT_RUN',
    real_recording:'NOT_RUN',release_decision:'NO_GO'}));
  assert.equal(reproduced,true,'expected a known-bad defect reproduction');
}
main().catch(e=>{console.error(e.stack);process.exitCode=1});
