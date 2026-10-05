#!/usr/bin/env python3
"""Deterministic ZIP; never updates source files or release identities."""
import argparse,zipfile
from governance import *
from verify_pack import verify
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory',type=Path);parser.add_argument('output',type=Path);a=parser.parse_args()
    try:
        verify(a.directory)
        if a.output.resolve().is_relative_to(a.directory.resolve()): raise Invalid('output must be outside pack root')
        with zipfile.ZipFile(a.output,'w',compression=zipfile.ZIP_STORED) as z:
            for p in sorted(a.directory.rglob('*')):
                if p.is_file() and '__pycache__' not in p.parts:
                    safe_file(a.directory,p.relative_to(a.directory).as_posix())
                    i=zipfile.ZipInfo(p.relative_to(a.directory).as_posix(),date_time=(2026,1,1,0,0,0));i.external_attr=0o100644<<16
                    z.writestr(i,p.read_bytes())
        zip_check(a.output);print(digest(a.output))
    except (Invalid,OSError) as e:raise SystemExit('ERROR: '+str(e))
