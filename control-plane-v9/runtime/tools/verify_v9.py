#!/usr/bin/env python3
import argparse,sqlite3,json,hashlib,sys
from state_v9 import state_sha256
def main():
    ap=argparse.ArgumentParser();ap.add_argument('db');a=ap.parse_args()
    con=sqlite3.connect(a.db);con.execute('PRAGMA foreign_keys=ON');con.row_factory=sqlite3.Row
    errs=[]
    if con.execute('PRAGMA integrity_check').fetchone()[0]!='ok':errs.append('integrity_check')
    fk=con.execute('PRAGMA foreign_key_check').fetchall()
    if fk:errs.append(f'foreign_key_errors={len(fk)}')
    mv=con.execute("SELECT value FROM metadata WHERE key='control_plane_model_version'").fetchone()
    if not mv or mv[0]!='9':errs.append('model_version_not_9')
    prev=''
    for r in con.execute('SELECT * FROM events ORDER BY seq'):
        payload=json.loads(r['payload_json'])
        body=json.dumps({'event_id':r['event_id'],'event_type':r['event_type'],'object_type':r['object_type'],'object_id':r['object_id'],
                         'created_at':r['created_at'],'payload':payload,'previous_event_hash':prev},sort_keys=True,separators=(',',':'))
        if (r['previous_event_hash'] or '')!=prev or hashlib.sha256(body.encode()).hexdigest()!=r['event_hash']:
            errs.append('event_chain');break
        prev=r['event_hash']
    graph={}
    for e in con.execute("SELECT consumer_release_id,provider_project_id FROM dependency_edges WHERE provider_kind='PROJECT' AND optional=0"):
        consumer_project=con.execute('SELECT project_id FROM releases WHERE release_id=?',(e['consumer_release_id'],)).fetchone()[0]
        graph.setdefault(consumer_project,set()).add(e['provider_project_id'])
    visiting=set();done=set()
    def dfs(n):
        if n in visiting:return True
        if n in done:return False
        visiting.add(n)
        for m in graph.get(n,()):
            if dfs(m):return True
        visiting.remove(n);done.add(n);return False
    if any(dfs(n) for n in list(graph)):errs.append('dependency_cycle')
    row=con.execute("""SELECT r.version FROM project_heads h JOIN releases r ON r.release_id=h.observed_release_id
                       WHERE h.project_id='universal-control-suite'""").fetchone()
    if not row or row[0]!='0.51.0':errs.append('suite_not_reconciled_to_0.51.0')
    if con.execute("SELECT COUNT(*) FROM adapter_plans WHERE status!='DRY_RUN_ONLY'").fetchone()[0]:
        errs.append('adapter_not_dry_run')
    print('PASS' if not errs else 'FAIL')
    for e in errs:print('-',e)
    print('state_sha256',state_sha256(con))
    for t in ['projects','releases','artifacts','remote_observations','dependency_edges','dependency_results','promotion_eligibility','promotion_plans','adapter_plans','events']:
        print(t,con.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0])
    sys.exit(1 if errs else 0)
if __name__=='__main__':main()
