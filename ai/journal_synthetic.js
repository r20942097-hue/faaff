/* Synthetic browser test only. Does not import RPLAY code. No network. */
'use strict';
const ROOT='gpt1_synthetic_journal_v42';
const bytesA=[1,2,3],bytesB=[4,5,6];
const hash=async x=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',Uint8Array.from(x)))).map(b=>b.toString(16).padStart(2,'0')).join('');
async function dir(){return (await navigator.storage.getDirectory()).getDirectoryHandle(ROOT,{create:true});}
async function put(name,bytes){const d=await dir(),f=await d.getFileHandle(name,{create:true}),w=await f.createWritable();await w.write(Uint8Array.from(bytes));await w.close();}
async function read(name){try{const f=await(await dir()).getFileHandle(name);return Array.from(new Uint8Array(await(await f.getFile()).arrayBuffer()));}catch(e){if(e?.name==='NotFoundError')return null;throw e;}}
async function remove(name){try{await(await dir()).removeEntry(name);}catch(e){if(e?.name!=='NotFoundError')throw e;}}
async function prepare(){await put('old.bin',bytesA);await put('txn.json',Array.from(new TextEncoder().encode(JSON.stringify({state:'PREPARED',old:'old.bin',fresh:'new.bin',digest:await hash(bytesB)}))));return 'PREPARED';}
async function prepareWithOrphan(){await prepare();await put('new.bin',[99]);return 'STAGED_ORPHAN';}
async function commit(){await put('new.bin',bytesB);await put('txn.json',Array.from(new TextEncoder().encode(JSON.stringify({state:'COMMITTED',old:'old.bin',fresh:'new.bin',digest:await hash(bytesB)}))));return 'COMMITTED';}
async function recover(){
 const payload=await read('txn.json');if(!payload)return 'NO_JOURNAL';
 let j;try{j=JSON.parse(new TextDecoder().decode(Uint8Array.from(payload)));}catch(e){throw Error('JOURNAL_CORRUPT');}
 if(j.old!=='old.bin'||j.fresh!=='new.bin'||typeof j.digest!=='string'||!/^[a-f0-9]{64}$/.test(j.digest))throw Error('JOURNAL_CORRUPT');
 const old=await read('old.bin'),fresh=await read('new.bin');
 if(j.state==='PREPARED'){
   if(JSON.stringify(old)!==JSON.stringify(bytesA))throw Error('OLD_DATA_UNVERIFIED');
   await remove('new.bin');await remove('txn.json');return 'ROLLED_BACK';
 }
 if(j.state==='COMMITTED'){
   if(!fresh||(await hash(fresh))!==j.digest)throw Error('NEW_DATA_UNVERIFIED');
   await remove('old.bin');await remove('txn.json');return 'COMMIT_REPLAYED';
 }
 throw Error('JOURNAL_UNKNOWN_STATE');
}
async function corrupt(){await put('txn.json',Array.from(new TextEncoder().encode('{corrupt')));return true;}
async function state(){return {old:await read('old.bin'),fresh:await read('new.bin'),journal:await read('txn.json')!==null};}
window.GPT1_JOURNAL={prepare,prepareWithOrphan,commit,recover,corrupt,state};