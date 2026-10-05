#!/usr/bin/env python3
from pathlib import Path
import argparse,sqlite3,json,hashlib,datetime
from state_v9 import state_sha256

def profile_for(con,pol,rid):
    row=con.execute("""SELECT r.project_id,r.track_id,p.policy_profile FROM releases r JOIN projects p ON p.project_id=r.project_id WHERE r.release_id=?""",(rid,)).fetchone()
    if not row:return 'context_only'
    return pol.get('track_policy',{}).get(row[1]) or pol.get('project_policy',{}).get(row[0]) or row[2] or 'context_only'
def gate_status(con,rid,gate):
    row=con.execute("""SELECT status,evidence_id FROM gate_results WHERE release_id=? AND gate_id=? ORDER BY assessed_at DESC,gate_result_id DESC LIMIT 1""",(rid,gate)).fetchone()
    return row if row else ('NOT_RUN',None)
def reasons_for(con,rid,gates):
    out=[]
    for g in gates:
        s,e=gate_status(con,rid,g)
        if s!='PASS':out.append({'gate':g,'status':s,'evidence_id':e})
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument('db');ap.add_argument('--policy',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    raw=Path(a.policy).read_bytes();pol=json.loads(raw);policy_sha=hashlib.sha256(raw).hexdigest()
    con=sqlite3.connect(a.db);con.execute('PRAGMA foreign_keys=ON');con.row_factory=sqlite3.Row
    active=con.execute("SELECT policy_sha256 FROM policy_documents WHERE policy_kind='promotion' AND active=1").fetchone()
    if not active or active[0]!=policy_sha:raise SystemExit('active promotion policy does not match supplied policy')
    state=state_sha256(con);now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    report=[]
    for r in con.execute('SELECT * FROM releases ORDER BY project_id,track_id,version'):
        profile=profile_for(con,pol,r['release_id'])
        cfg=pol['profiles'].get(profile,{'candidate_gates':[],'stable_gates':[]})
        if profile=='context_only':
            cand=stable='CONTEXT_ONLY';creasons=[];sreasons=[]
        else:
            creasons=reasons_for(con,r['release_id'],cfg['candidate_gates'])
            cand='ELIGIBLE' if not creasons else 'NOT_ELIGIBLE'
            sreasons=reasons_for(con,r['release_id'],cfg['candidate_gates']+cfg['stable_gates']+pol['global_stable_gates'])
            for d in con.execute("""SELECT dr.status,dr.reason,de.propagation_mode FROM dependency_results dr
                                    JOIN dependency_edges de ON de.edge_id=dr.edge_id
                                    WHERE dr.consumer_release_id=? AND dr.input_state_sha256=? ORDER BY dr.edge_id""",(r['release_id'],state)):
                if d['status']=='BLOCKED_CANDIDATE' and d['propagation_mode'] in ('BLOCK_CANDIDATE','BLOCK_STABLE'):
                    if d['propagation_mode']=='BLOCK_CANDIDATE':
                        creasons.append({'gate':'dependency_graph','status':d['status'],'detail':d['reason']});cand='NOT_ELIGIBLE'
                    sreasons.append({'gate':'dependency_graph','status':d['status'],'detail':d['reason']})
                elif d['status']=='CANDIDATE_OK_STABLE_BLOCKED' and d['propagation_mode']=='BLOCK_STABLE':
                    sreasons.append({'gate':'dependency_graph','status':d['status'],'detail':d['reason']})
            blockers=[x[0] for x in con.execute("SELECT code FROM blockers WHERE release_id=? AND status='ACTIVE'",(r['release_id'],))]
            if blockers:sreasons.append({'gate':'active_blockers','status':'BLOCKED','detail':blockers})
            stable='ELIGIBLE' if not sreasons else 'NOT_ELIGIBLE'
        payload={'release_id':r['release_id'],'profile':profile,'policy_sha256':policy_sha,'candidate_status':cand,'stable_status':stable,
                 'candidate_reasons':creasons,'stable_reasons':sreasons,'state':state}
        eid='elig:'+hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        dep_status='BLOCKED' if any(x.get('gate')=='dependency_graph' for x in sreasons) else 'CLEAR'
        con.execute("""INSERT OR IGNORE INTO promotion_eligibility(eligibility_id,release_id,evaluated_at,input_state_sha256,candidate_status,stable_status,
                       candidate_reasons_json,stable_reasons_json,dependency_status)
                       VALUES(?,?,?,?,?,?,?,?,?)""",
                    (eid,r['release_id'],now,state,cand,stable,json.dumps(creasons,sort_keys=True),json.dumps(sreasons,sort_keys=True),dep_status))
        report.append(payload)
    con.commit()
    Path(a.out).write_text(json.dumps({'schema_version':1,'policy_sha256':policy_sha,'input_state_sha256':state,'releases':report},indent=2),encoding='utf-8')
    print('evaluated',len(report),'candidate_eligible',sum(x['candidate_status']=='ELIGIBLE' for x in report),'stable_eligible',sum(x['stable_status']=='ELIGIBLE' for x in report))
if __name__=='__main__':main()
