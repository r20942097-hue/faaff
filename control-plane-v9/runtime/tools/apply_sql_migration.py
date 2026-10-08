#!/usr/bin/env python3
from pathlib import Path
import argparse,sqlite3,hashlib,datetime

def q(s): return "'" + s.replace("'","''") + "'"

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("db");ap.add_argument("--migration",required=True);ap.add_argument("--version",type=int,required=True);ap.add_argument("--revision",required=True)
    a=ap.parse_args()
    raw=Path(a.migration).read_text(encoding="utf-8")
    digest=hashlib.sha256(raw.encode()).hexdigest()
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    trailer=f"""
INSERT OR IGNORE INTO schema_migrations(version,name,applied_at,migration_sha256)
VALUES({a.version},{q(Path(a.migration).name)},{q(now)},{q(digest)});
INSERT OR REPLACE INTO metadata(key,value) VALUES('schema_revision',{q(a.revision)});
"""
    con=sqlite3.connect(a.db);con.execute("PRAGMA foreign_keys=ON")
    try:
        con.executescript("BEGIN IMMEDIATE;\n"+raw+"\n"+trailer+"\nCOMMIT;\n")
    except:
        try:con.execute("ROLLBACK")
        except:pass
        raise
    finally:con.close()
    print("migration",a.version,digest)
if __name__=="__main__":main()
