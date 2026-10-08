#!/usr/bin/env python3
"""Regression tests with synthetic evidence; never real-environment acceptance."""
import contextlib, datetime, hashlib, io, json, pathlib, sqlite3, sys, tempfile, unittest
from unittest.mock import patch
import evaluate_promotion_eligibility as ev
import plan_promotion
import apply_local_promotion

ROOT = pathlib.Path(__file__).resolve().parents[1]
NOW = datetime.datetime(2026, 10, 8, 12, tzinfo=datetime.timezone.utc)
LATER = NOW + datetime.timedelta(hours=2)

class PromotionSafety(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = pathlib.Path(self.tmp.name)/'test.db'
        self.con = sqlite3.connect(self.db); self.con.execute('PRAGMA foreign_keys=ON')
        for name in ('schemas/control-plane.sql', 'migrations/009_control_plane_v9.sql', 'migrations/010_policy_documents.sql'):
            self.con.executescript((ROOT/name).read_text())
        self.raw = (ROOT/'policies/promotion-policy-v9.json').read_bytes()
        self.pol = json.loads(self.raw)
        self.con.execute('INSERT INTO policy_documents VALUES(?,?,?,?,?,?)', ('p','promotion',hashlib.sha256(self.raw).hexdigest(),self.raw.decode(),1,NOW.isoformat()))
        self.con.execute('INSERT INTO projects VALUES(?,?,?,?,?,?,?)', ('fixture','Fixture',1,'DEV','service_runtime','service_runtime',NOW.isoformat()))
        self.con.execute('INSERT INTO tracks VALUES(?,?,?,?)', ('t','fixture','main','synthetic'))
        self.con.execute('INSERT INTO releases VALUES(?,?,?,?,?,?,?)', ('r','fixture','t','1','DEV','HOLD',NOW.isoformat()))
        self.con.commit()
        self.clock = patch.object(ev, 'utc_now', return_value=NOW); self.clock.start()
    def tearDown(self):
        self.clock.stop(); self.con.close(); self.tmp.cleanup()
    def gate(self, gate, status='PASS', evidence=True, evidence_status='PASS', subject='r', evidence_type=None, until=None, evidence_until=None):
        eid = 'ev:'+gate
        if evidence:
            self.con.execute('INSERT INTO evidence VALUES(?,?,?,?,?,?,?,?,?,?,?,?)', (eid,'release',subject,evidence_type or 'gate:'+gate,evidence_status,NOW.isoformat(),'synthetic-test','{}','a'*64,'synthetic',evidence_until,None))
        self.con.execute('INSERT INTO gate_results VALUES(?,?,?,?,?,?,?,?)', ('g:'+gate,'r',gate,status,eid if evidence else None,'synthetic',NOW.isoformat(),until))
        self.con.commit()
    def candidate_gates(self, until=None):
        for gate in ('unit_integration','package_integrity'): self.gate(gate, until=until)
    def call(self, module, args):
        with patch.object(sys,'argv',[str(module.__file__),str(self.db),*map(str,args)]), contextlib.redirect_stdout(io.StringIO()): module.main()
    def evaluate(self):
        policy=pathlib.Path(self.tmp.name)/'policy.json'; policy.write_bytes(self.raw)
        self.call(ev,['--policy',policy,'--out',pathlib.Path(self.tmp.name)/'elig.json'])
        return policy
    def plan(self, policy):
        out=pathlib.Path(self.tmp.name)/'plan.json'
        self.call(plan_promotion,['r','--target','CANDIDATE','--policy',policy,'--out',out])
        return json.loads(out.read_text())
    def test_unknown_profile_blocks_both_stages(self):
        self.con.execute("UPDATE projects SET policy_profile='typo'"); self.con.commit()
        x=ev.eligibility_for(self.con,self.pol,'r'); self.assertEqual(x['candidate_status'],'NOT_ELIGIBLE'); self.assertEqual(x['stable_status'],'NOT_ELIGIBLE')
    def test_empty_candidate_gate_list_blocks(self):
        self.pol['profiles']['service_runtime']['candidate_gates']=[]
        self.assertEqual(ev.eligibility_for(self.con,self.pol,'r')['candidate_status'],'NOT_ELIGIBLE')
    def test_context_only_never_eligible(self):
        self.con.execute("UPDATE projects SET policy_profile='context_only'"); self.con.commit()
        self.assertEqual(ev.eligibility_for(self.con,self.pol,'r')['stable_status'],'CONTEXT_ONLY')
    def test_missing_gate_blocks(self):
        self.assertEqual(ev.eligibility_for(self.con,self.pol,'r')['candidate_status'],'NOT_ELIGIBLE')
    def test_valid_candidate_retains_stable_block(self):
        self.candidate_gates(); x=ev.eligibility_for(self.con,self.pol,'r')
        self.assertEqual(x['candidate_status'],'ELIGIBLE'); self.assertEqual(x['stable_status'],'NOT_ELIGIBLE')
    def test_missing_evidence_blocks(self):
        self.gate('unit_integration',evidence=False)
        self.assertEqual(ev.gate_status(self.con,'r','unit_integration')[0],'INVALID_EVIDENCE')
    def test_failed_evidence_cannot_support_pass(self):
        self.gate('unit_integration',evidence_status='FAIL')
        self.assertEqual(ev.gate_status(self.con,'r','unit_integration')[0],'INVALID_EVIDENCE')
    def test_other_release_evidence_blocks(self):
        self.gate('unit_integration',subject='other')
        self.assertEqual(ev.gate_status(self.con,'r','unit_integration')[0],'INVALID_EVIDENCE')
    def test_other_gate_evidence_blocks(self):
        self.gate('unit_integration',evidence_type='gate:other')
        self.assertEqual(ev.gate_status(self.con,'r','unit_integration')[0],'INVALID_EVIDENCE')
    def test_expired_gate_blocks(self):
        self.gate('unit_integration',until=NOW.isoformat())
        self.assertEqual(ev.gate_status(self.con,'r','unit_integration')[0],'EXPIRED')
    def test_expired_evidence_blocks(self):
        self.gate('unit_integration',evidence_until=NOW.isoformat())
        self.assertEqual(ev.gate_status(self.con,'r','unit_integration')[0],'EXPIRED')
    def test_invalid_expiry_blocks(self):
        self.gate('unit_integration',until='bad-time')
        self.assertEqual(ev.gate_status(self.con,'r','unit_integration')[0],'INVALID_EXPIRY')
    def test_naive_expiry_blocks(self):
        self.gate('unit_integration',until='2027-01-01T00:00:00')
        self.assertEqual(ev.gate_status(self.con,'r','unit_integration')[0],'INVALID_EXPIRY')
    def test_changed_policy_cannot_weaken_approval(self):
        self.candidate_gates(); policy=self.evaluate()
        bad=json.loads(self.raw); bad['approval_policy']['CANDIDATE']=[]; policy.write_text(json.dumps(bad))
        with self.assertRaisesRegex(ValueError,'active promotion policy'): self.plan(policy)
    def test_empty_active_roles_rejected(self):
        self.pol['approval_policy']['STABLE']=[]
        self.con.execute('UPDATE policy_documents SET content_json=?',(json.dumps(self.pol),)); self.con.commit()
        with self.assertRaisesRegex(ValueError,'invalid approval policy'): ev.active_policy(self.con)
    def test_plan_rechecks_expiry_without_database_drift(self):
        self.candidate_gates(until=(NOW+datetime.timedelta(hours=1)).isoformat()); policy=self.evaluate()
        with patch.object(ev,'utc_now',return_value=LATER): plan=self.plan(policy)
        self.assertEqual(plan['status'],'BLOCKED')
    def test_apply_rechecks_expiry_and_rolls_back(self):
        self.candidate_gates(until=(NOW+datetime.timedelta(hours=1)).isoformat()); policy=self.evaluate(); plan=self.plan(policy)
        self.assertEqual(plan['status'],'READY_FOR_APPROVAL')
        with patch.object(ev,'utc_now',return_value=LATER), self.assertRaisesRegex(RuntimeError,'no longer eligible'):
            self.call(apply_local_promotion,[plan['plan_id'],'--actor','fixture','--role','operator','--confirm','APPLY_LOCAL_ONLY'])
        self.assertEqual(self.con.execute("SELECT stage FROM releases WHERE release_id='r'").fetchone()[0],'DEV')
        self.assertEqual(self.con.execute('SELECT COUNT(*) FROM promotion_plan_approvals').fetchone()[0],0)
    def test_valid_candidate_apply(self):
        self.candidate_gates(); policy=self.evaluate(); plan=self.plan(policy)
        self.call(apply_local_promotion,[plan['plan_id'],'--actor','fixture','--role','operator','--confirm','APPLY_LOCAL_ONLY'])
        self.assertEqual(self.con.execute("SELECT stage FROM releases WHERE release_id='r'").fetchone()[0],'CANDIDATE')

if __name__=='__main__': unittest.main(verbosity=2)
