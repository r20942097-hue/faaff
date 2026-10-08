#!/usr/bin/env python3
from pathlib import Path
import argparse,sqlite3,json,hashlib,datetime
def main():
    ap=argparse.ArgumentParser();ap.add_argument("db");ap.add_argument("--policy",required=True);a=ap.parse_args()
    raw=Path(a.policy).read_bytes()
    doc=json.loads(raw)
    digest=hashlib.sha256(raw).hexdigest()
    con=sqlite3.connect(a.db);con.execute("PRAGMA foreign_keys=ON")
    con.execute("BEGIN IMMEDIATE")
    try:
        con.execute("UPDATE policy_documents SET active=0 WHERE policy_kind='promotion'")
        con.execute("""INSERT OR REPLACE INTO policy_documents(policy_id,policy_kind,policy_sha256,content_json,active,loaded_at)
                       VALUES(?,?,?,?,1,?)""",("promotion:"+digest,"promotion",digest,json.dumps(doc,sort_keys=True),
                       datetime.datetime.now(datetime.timezone.utc).isoformat()))
        con.commit()
    except:
        con.rollback();raise
    print("promotion_policy_sha256",digest)
if __name__=="__main__":main()
