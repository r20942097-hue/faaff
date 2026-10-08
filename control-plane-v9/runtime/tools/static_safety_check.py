#!/usr/bin/env python3
from pathlib import Path
import argparse,ast,json
FORBIDDEN={"requests","httpx","urllib.request","boto3"}
TOKENS=["delete_"+"file(","manage_"+"library(","update_"+"file(","create_"+"file("]
SELF="static_safety_check.py"
def main():
    ap=argparse.ArgumentParser();ap.add_argument("root");a=ap.parse_args()
    root=Path(a.root);findings=[];files=[]
    for p in sorted((root/"tools").glob("*.py")):
        if p.name==SELF: continue
        files.append(p)
        text=p.read_text(encoding="utf-8")
        try: tree=ast.parse(text)
        except SyntaxError as e:
            findings.append({"file":p.name,"type":"syntax","detail":str(e)});continue
        for n in ast.walk(tree):
            if isinstance(n,ast.Import):
                for x in n.names:
                    if x.name in FORBIDDEN: findings.append({"file":p.name,"type":"forbidden_import","detail":x.name})
            if isinstance(n,ast.ImportFrom) and n.module in FORBIDDEN:
                findings.append({"file":p.name,"type":"forbidden_import","detail":n.module})
        for token in TOKENS:
            if token in text: findings.append({"file":p.name,"type":"external_mutation_token","detail":token})
    result={"files_scanned":len(files),"findings":findings,"pass":not findings}
    print(json.dumps(result,indent=2))
    if findings: raise SystemExit(1)
if __name__=="__main__":main()
