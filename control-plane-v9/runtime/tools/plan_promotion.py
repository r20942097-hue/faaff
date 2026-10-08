#!/usr/bin/env python3
from pathlib import Path
import argparse,sqlite3,json,hashlib,datetime
from state_v9 import state_sha256
from evaluate_promotion_eligibility import active_policy, eligibility_for

def main():
    ap=argparse.ArgumentParser();ap.add_argument('db');ap.add_argument('release_id');ap.add_argument('--target',choices=['CANDIDATE','STABLE'],required=True);ap.add_argument('--policy',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    raw=Path(a.policy).read_bytes()
    con=sqlite3.connect(a.db);con.execute('PRAGMA foreign_keys=ON');con.row_factory=sqlite3.Row
    pol=active_policy(con,raw)
    state=state_sha256(con)
    e=con.execute("""SELECT * FROM promotion_eligibility WHERE release_id=? AND input_state_sha256=? ORDER BY evaluated_at DESC LIMIT 1""",(a.release_id,state)).fetchone()
    r=con.execute('SELECT * FROM releases WHERE release_id=?',(a.release_id,)).fetchone()
    if not r:raise SystemExit('release not found')
    required_roles=pol['approval_policy'][a.target]
    eligibility=(e['candidate_status'] if a.target=='CANDIDATE' else e['stable_status']) if e else 'NOT_EVALUATED'
    reasons=json.loads(e['candidate_reasons_json'] if a.target=='CANDIDATE' else e['stable_reasons_json']) if e else [{'status':'NOT_EVALUATED'}]
    current=eligibility_for(con,pol,a.release_id)
    fresh=current['candidate_status'] if a.target=='CANDIDATE' else current['stable_status']
    if fresh!='ELIGIBLE':
        eligibility=fresh
        reasons=current['candidate_reasons'] if a.target=='CANDIDATE' else current['stable_reasons']
    status='READY_FOR_APPROVAL' if eligibility=='ELIGIBLE' else 'BLOCKED'
    artifacts=[dict(x) for x in con.execute("""SELECT a.sha256,a.size_bytes,ra.role FROM release_artifacts ra JOIN artifacts a ON a.artifact_id=ra.artifact_id WHERE ra.release_id=? ORDER BY ra.role,a.sha256""",(a.release_id,))]
    pre={'input_state_sha256':state,'release_stage':r['stage'],'release_decision':r['decision'],'artifact_identities':artifacts,'eligibility':eligibility}
    actions=[
      {'type':'LOCAL_STAGE_TRANSITION','from':r['stage'],'to':a.target},
      {'type':'GENERATE_ADAPTER_PLANS','targets':['LIBRARY','GITHUB']},
      {'type':'NO_AUTO_PUBLISH','value':True}
    ]
    core={'release_id':a.release_id,'target_stage':a.target,'status':status,'required_approvals':required_roles,'preconditions':pre,'actions':actions,'reasons':reasons}
    ph=hashlib.sha256(json.dumps(core,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    plan_id='promote:'+ph[:32]
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    con.execute("""INSERT OR REPLACE INTO promotion_plans(plan_id,release_id,target_stage,status,created_at,input_state_sha256,input_eligibility_id,
                   required_approvals_json,preconditions_json,actions_json,plan_sha256)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (plan_id,a.release_id,a.target,status,now,state,e['eligibility_id'] if e else None,json.dumps(required_roles),json.dumps(pre,sort_keys=True),json.dumps(actions,sort_keys=True),ph))
    con.commit()
    out={'schema_version':1,'plan_id':plan_id,**core,'plan_sha256':ph}
    Path(a.out).write_text(json.dumps(out,indent=2),encoding='utf-8')
    print(status,plan_id)
if __name__=='__main__':main()
