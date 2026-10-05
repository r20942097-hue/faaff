#!/usr/bin/env python3
from pathlib import Path
import argparse,sqlite3,hashlib,datetime

def q(s): return "'" + s.replace("'","''") + "'"

def main():
    ap=argparse.ArgumentParser();ap.add_argument("db");ap.add_argument("--migration",required=True);a=ap.parse_args()
    raw=Path(a.migration).read_text(encoding="utf-8")
    lines=[ln for ln in raw.splitlines() if ln.strip().upper()!="PRAGMA FOREIGN_KEYS = ON;"]
    sql="\n".join(lines)
    digest=hashlib.sha256(raw.encode()).hexdigest()
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    trailer=f"""
INSERT OR IGNORE INTO schema_migrations(version,name,applied_at,migration_sha256)
VALUES(9,{q(Path(a.migration).name)},{q(now)},{q(digest)});
INSERT OR REPLACE INTO metadata(key,value) VALUES('control_plane_model_version','9');
INSERT OR REPLACE INTO metadata(key,value) VALUES('schema_revision','9.0');
"""
    con=sqlite3.connect(a.db);con.execute("PRAGMA foreign_keys=ON")
    script="BEGIN IMMEDIATE;\n"+sql+"\n"+trailer+"\nCOMMIT;\n"
    try:
        con.executescript(script)
    except:
        try: con.execute("ROLLBACK")
        except: pass
        raise
    finally: con.close()
    print("migration=9",digest)
if __name__=="__main__":main()
