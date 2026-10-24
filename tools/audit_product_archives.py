#!/usr/bin/env python3
"""Read-only integrity audit for saved ZIPs and their companion SHA256 lists."""
import argparse,json,zipfile
from pathlib import Path,PurePosixPath
from governance import digest as sha, Invalid, zip_check

def require(ok,message):
    if not ok: raise Invalid(message)

def audit(root):
    root=Path(root).resolve(); records=[]; expected={}
    for p in sorted(root.glob('*sha256*')):
        for line in p.read_text().splitlines():
            if not line.strip(): continue
            digest,name=line.split(None,1); name=name.strip().lstrip('*')
            if name in expected: require(expected[name]==digest,'conflicting companion hash: '+name)
            expected[name]=digest
    for p in sorted(root.glob('*.zip')):
        zip_check(p)
        digest=sha(p); require(p.name in expected,'missing companion SHA: '+p.name)
        require(digest==expected[p.name],'companion SHA mismatch: '+p.name)
        with zipfile.ZipFile(p) as z:
            names=z.namelist(); require(len(set(names))==len(names),'duplicate ZIP entries')
            for n in names:
                q=PurePosixPath(n); require(not q.is_absolute() and '..' not in q.parts and '\\' not in n,'unsafe ZIP member')
                require((z.getinfo(n).external_attr>>16)&0o170000!=0o120000,'ZIP symlink')
            require(z.testzip() is None,'CRC failure')
            count=0; coverage=None
            candidates=[n for n in names if PurePosixPath(n).name in ('SOURCE_MANIFEST.json','MANIFEST.json','SHA256SUMS','SHA256SUMS.txt')]
            for n in candidates:
                base=PurePosixPath(n).parent.as_posix(); prefix='' if base=='.' else base+'/'
                if n.endswith('.json'):
                    m=json.loads(z.read(n)); entries=m['files']; pairs=[(r['path'],r['sha256']) for r in entries]
                else:
                    pairs=[]
                    for line in z.read(n).decode().splitlines():
                        if line.strip(): h,name=line.split(None,1); pairs.append((name.strip().lstrip('*'),h))
                require(len(pairs)==len(set(x[0] for x in pairs)),'duplicate internal hash refs')
                for name,h in pairs:
                    require(prefix+name in names,'missing internal member: '+name)
                    import hashlib
                    require(hashlib.sha256(z.read(prefix+name)).hexdigest()==h,'internal SHA mismatch: '+name)
                count+=len(pairs)
                scope={x for x in names if x.startswith(prefix) and not x.endswith('/') and x!=n}
                coverage={prefix+name for name,_ in pairs}==scope
                require(coverage,'incomplete internal manifest: '+n)
        records.append({'filename':p.name,'size_bytes':p.stat().st_size,'sha256':digest,'companion_sha':'PASS','crc':'PASS','internal_hashes_verified':count,'internal_coverage':coverage})
    return {'mode':'read_only','archives':records,'product_tests':'separate','signature_verification':'NOT_RUN'}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory');a=p.parse_args()
    print(json.dumps(audit(a.directory),indent=2))
