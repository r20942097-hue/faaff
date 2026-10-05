#!/usr/bin/env python3
import argparse,sqlite3,json,datetime
from state_v9 import state_sha256
from eventlog_v9 import append_event

def main():
    ap=argparse.ArgumentParser();ap.add_argument('db');ap.add_argument('plan_id');ap.add_argument('--actor',required=True);ap.add_argument('--role',required=True);ap.add_argument('--confirm',default='');a=ap.parse_args()
    if a.confirm!='APPLY_LOCAL_ONLY':raise SystemExit('confirmation token required')
    con=sqlite3.connect(a.db);con.execute('PRAGMA foreign_keys=ON');con.row_factory=sqlite3.Row
    con.execute('BEGIN IMMEDIATE')
    try:
        plan=con.execute('SELECT * FROM promotion_plans WHERE plan_id=?',(a.plan_id,)).fetchone()
        if not plan:raise RuntimeError('plan not found')
        if plan['status']!='READY_FOR_APPROVAL':raise RuntimeError('plan not ready')
        if plan['input_state_sha256']!=state_sha256(con):raise RuntimeError('authoritative state drift')
        roles=json.loads(plan['required_approvals_json'])
        if a.role not in roles:raise RuntimeError('role not required by plan')
        con.execute("""INSERT OR IGNORE INTO promotion_plan_approvals(plan_id,role,actor,approved_at,note) VALUES(?,?,?,?,?)""",
                    (a.plan_id,a.role,a.actor,datetime.datetime.now(datetime.timezone.utc).isoformat(),'explicit local-only approval'))
        have={x[0] for x in con.execute('SELECT role FROM promotion_plan_approvals WHERE plan_id=?',(a.plan_id,))}
        if not set(roles).issubset(have):
            con.commit();print('APPROVAL_RECORDED_WAITING',sorted(set(roles)-have));return
        release=con.execute('SELECT * FROM releases WHERE release_id=?',(plan['release_id'],)).fetchone()
        con.execute('UPDATE releases SET stage=? WHERE release_id=?',(plan['target_stage'],plan['release_id']))
        if plan['target_stage']=='STABLE':
            con.execute('UPDATE project_heads SET stable_release_id=? WHERE project_id=?',(plan['release_id'],release['project_id']))
        con.execute("UPDATE promotion_plans SET status='LOCAL_COMMITTED' WHERE plan_id=?",(a.plan_id,))
        append_event(con,'LOCAL_PROMOTION_COMMITTED','release',plan['release_id'],{'plan_id':a.plan_id,'target_stage':plan['target_stage'],'external_publish':False})
        con.commit();print('LOCAL_COMMITTED',plan['release_id'],plan['target_stage'],'external_publish=False')
    except:
        con.rollback();raise
if __name__=='__main__':main()
