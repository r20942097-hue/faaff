#!/usr/bin/env python3
from pathlib import Path
import sqlite3, tempfile, subprocess, json, hashlib, shutil, sys

ROOT=Path(__file__).resolve().parents[1]
PY=sys.executable

def run(*args, check=True):
    r=subprocess.run([PY,*map(str,args)],capture_output=True,text=True)
    if check and r.returncode:
        raise RuntimeError(f"failed: {args}\n{r.stdout}\n{r.stderr}")
    return r

def add_gate(con,rid,gate,status='PASS'):
    payload=json.dumps({'release_id':rid,'gate':gate,'status':status},sort_keys=True)
    h=hashlib.sha256(payload.encode()).hexdigest()
    eid='ev:'+h
    con.execute("""INSERT OR IGNORE INTO evidence(evidence_id,subject_type,subject_id,evidence_type,status,collected_at,issuer,environment_json,payload_sha256,source_ref,valid_until,supersedes_evidence_id)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (eid,'release',rid,'gate:'+gate,status,'2026-10-05T00:00:00Z','ci-selftest','{}',h,'synthetic-ci',None,None))
    gid='gr:'+h
    con.execute("""INSERT OR IGNORE INTO gate_results(gate_result_id,release_id,gate_id,status,evidence_id,environment_fingerprint,assessed_at,valid_until)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (gid,rid,gate,status,eid,'ci','2026-10-05T00:00:00Z',None))

def main():
    tmp=Path(tempfile.mkdtemp(prefix='control-plane-v9-ci-'))
    try:
        db=tmp/'cp.db'
        con=sqlite3.connect(db)
        con.executescript((ROOT/'schemas/control-plane.sql').read_text(encoding='utf-8'))
        con.close()
        run(ROOT/'tools/migrate_v8_to_v9.py',db,'--migration',ROOT/'migrations/009_control_plane_v9.sql')
        run(ROOT/'tools/apply_sql_migration.py',db,'--migration',ROOT/'migrations/010_policy_documents.sql','--version','10','--revision','9.1')
        run(ROOT/'tools/load_promotion_policy.py',db,'--policy',ROOT/'policies/promotion-policy-v9.json')

        con=sqlite3.connect(db);con.execute('PRAGMA foreign_keys=ON')
        rid='universal-live-watcher:main:6.49.12';tid='universal-live-watcher:main'
        con.execute("INSERT INTO projects VALUES(?,?,?,?,?,?,?)",('universal-live-watcher','Universal Live Watcher',1,'CANDIDATE','service_runtime','service_runtime','2026-10-05T00:00:00Z'))
        con.execute("INSERT INTO tracks VALUES(?,?,?,?)",(tid,'universal-live-watcher','main','ci fixture'))
        con.execute("INSERT INTO releases VALUES(?,?,?,?,?,?,?)",(rid,'universal-live-watcher',tid,'6.49.12','DEV','HOLD','2026-10-05T00:00:00Z'))
        con.execute("INSERT INTO project_heads VALUES(?,?,?,?,?)",('universal-live-watcher',rid,rid,rid,None))
        ah='a'*64;aid='sha256:'+ah
        con.execute("INSERT INTO artifacts VALUES(?,?,?,?,?)",(aid,ah,123,'application/zip','2026-10-05T00:00:00Z'))
        con.execute("INSERT INTO release_artifacts VALUES(?,?,?)",(rid,aid,'distribution'))
        srid='universal-control-suite:main:0.51.0';stid='universal-control-suite:main'
        con.execute("INSERT INTO projects VALUES(?,?,?,?,?,?,?)",('universal-control-suite','Universal Control Suite',2,'DEV','integration_runtime','integration_runtime','2026-10-05T00:00:00Z'))
        con.execute("INSERT INTO tracks VALUES(?,?,?,?)",(stid,'universal-control-suite','main','ci fixture'))
        con.execute("INSERT INTO releases VALUES(?,?,?,?,?,?,?)",(srid,'universal-control-suite',stid,'0.51.0','DEV','NO_GO','2026-10-05T00:00:00Z'))
        con.execute("INSERT INTO project_heads VALUES(?,?,?,?,?)",('universal-control-suite',srid,srid,srid,None))
        for g in ['unit_integration','package_integrity']: add_gate(con,rid,g)
        con.commit();con.close()

        out=tmp/'elig1.json'
        run(ROOT/'tools/evaluate_promotion_eligibility.py',db,'--policy',ROOT/'policies/promotion-policy-v9.json','--out',out)
        doc=json.loads(out.read_text())
        row=next(x for x in doc['releases'] if x['release_id']==rid)
        assert row['candidate_status']=='ELIGIBLE',row
        assert row['stable_status']=='NOT_ELIGIBLE',row

        plan=tmp/'candidate.json'
        run(ROOT/'tools/plan_promotion.py',db,rid,'--target','CANDIDATE','--policy',ROOT/'policies/promotion-policy-v9.json','--out',plan)
        p=json.loads(plan.read_text());assert p['status']=='READY_FOR_APPROVAL',p
        run(ROOT/'tools/apply_local_promotion.py',db,p['plan_id'],'--actor','ci','--role','operator','--confirm','APPLY_LOCAL_ONLY')
        con=sqlite3.connect(db);assert con.execute('SELECT stage FROM releases WHERE release_id=?',(rid,)).fetchone()[0]=='CANDIDATE';con.close()

        con=sqlite3.connect(db)
        for g in ['real_windows','authenticated_service','process_cleanup','soak','sbom','provenance','attestation_verified','rollback']:
            add_gate(con,rid,g)
        con.commit();con.close()
        out=tmp/'elig2.json'
        run(ROOT/'tools/evaluate_promotion_eligibility.py',db,'--policy',ROOT/'policies/promotion-policy-v9.json','--out',out)
        doc=json.loads(out.read_text());row=next(x for x in doc['releases'] if x['release_id']==rid)
        assert row['stable_status']=='ELIGIBLE',row

        plan=tmp/'stable.json'
        run(ROOT/'tools/plan_promotion.py',db,rid,'--target','STABLE','--policy',ROOT/'policies/promotion-policy-v9.json','--out',plan)
        p=json.loads(plan.read_text());assert p['status']=='READY_FOR_APPROVAL',p
        a=run(ROOT/'tools/apply_local_promotion.py',db,p['plan_id'],'--actor','ci-op','--role','operator','--confirm','APPLY_LOCAL_ONLY')
        assert 'WAITING' in a.stdout,a.stdout
        b=run(ROOT/'tools/apply_local_promotion.py',db,p['plan_id'],'--actor','ci-owner','--role','release_owner','--confirm','APPLY_LOCAL_ONLY')
        assert 'LOCAL_COMMITTED' in b.stdout,b.stdout
        con=sqlite3.connect(db)
        assert con.execute('SELECT stage FROM releases WHERE release_id=?',(rid,)).fetchone()[0]=='STABLE'
        assert con.execute("SELECT stable_release_id FROM project_heads WHERE project_id='universal-live-watcher'").fetchone()[0]==rid
        con.close()

        run(ROOT/'tools/verify_v9.py',db)
        run(ROOT/'tools/static_safety_check.py',ROOT)
        print('PASS: control-plane v9.1 CI selftest')
    finally:
        shutil.rmtree(tmp,ignore_errors=True)

if __name__=='__main__': main()
