import argparse,json,sys
from pathlib import Path
from governance import *
def main(mode):
    parser=argparse.ArgumentParser()
    parser.add_argument('file',type=Path,nargs='?',default=REGISTRY)
    parser.add_argument('--policy',type=Path,default=ROOT/'policies/promotion-policy.json')
    parser.add_argument('--json',action='store_true')
    a=parser.parse_args()
    try:
        d=load(a.file)
        if mode=='registry': validate_registry(d); print('OK: '+str(len(d['projects']))+' projects')
        elif mode=='manifest': validate_manifest(d);print('OK: manifest structure (artifact/evidence verification is separate)')
        elif mode=='retention': print(json.dumps(retention(d),indent=2))
        elif mode=='index': print(render_index(d),end='')
        else:
            result=promotion(d,a.file.parent,load(a.policy))
            print(json.dumps(result,indent=2) if a.json or mode=='verify' else result['decision'])
            if mode=='verify' and result['decision']=='DEV_OR_NO_GO':return 1
        return 0
    except (Invalid,OSError,zipfile.BadZipFile) as e:print('ERROR: '+str(e),file=sys.stderr);return 2
