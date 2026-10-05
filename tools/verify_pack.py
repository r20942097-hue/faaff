#!/usr/bin/env python3
import argparse
from governance import *
def verify(root):
    root=Path(root)
    manifest=load(root/'CONTENT_MANIFEST_SHA256.json')
    if type(manifest) is not dict or not manifest: raise Invalid('empty content manifest')
    actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='CONTENT_MANIFEST_SHA256.json'}
    if actual!=set(manifest): raise Invalid('content manifest inventory mismatch')
    for name,sha in manifest.items():
        if type(sha) is not str or not re.fullmatch('[0-9a-f]{64}',sha): raise Invalid('invalid content digest')
        if digest(safe_file(root,name))!=sha: raise Invalid('content SHA mismatch: '+name)
    return len(actual)
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory',type=Path);a=parser.parse_args()
    try: print('OK: '+str(verify(a.directory))+' content hashes')
    except Invalid as e: raise SystemExit('ERROR: '+str(e))
