"""Synthetic journal CI evidence and safety checks: no real browser launched."""
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import browser_opfs_journal_synthetic as gate

class JournalTests(unittest.TestCase):
    def valid(self):
        r=dict(scope='SYNTHETIC_BROWSER_JOURNAL_ONLY',product_executed=False,
               external_network='DISABLED',release_decision='CANDIDATE_NO_GO')
        r.update({key:'PASS' for key in gate.FLAGS})
        return r
    def test_all_required_evidence_pass(self):
        self.assertTrue(gate.accepted(self.valid()))
    def test_missing_result_rejected(self):
        for key in gate.FLAGS:
            with self.subTest(key=key):
                data=self.valid()
                data[key]='NOT_RUN'
                self.assertFalse(gate.accepted(data))
    def test_wrong_product_scope_rejected(self):
        for key,val in [('product_executed',True),('scope','PRODUCT'),
                        ('external_network','ALLOWED'),('release_decision','GO')]:
            with self.subTest(key=key):
                data=self.valid()
                data[key]=val
                self.assertFalse(gate.accepted(data))
    def test_synthetic_fixture_only(self):
        js=Path(gate.__file__).with_name('journal_synthetic.js').read_text()
        self.assertIn('crypto.subtle.digest',js)
        self.assertIn('createWritable()',js)
        self.assertIn('JOURNAL_CORRUPT',js)
        self.assertIn('COMMIT_REPLAYED',js)
        for forbidden in ('fetch(', 'XMLHttpRequest', 'https://', 'http://', 'importScripts('):
            self.assertNotIn(forbidden,js)
    def test_fails_closed_before_browser_if_not_isolated(self):
        with patch.object(gate,'isolation_check',return_value=['ROOT_RUNTIME_FORBIDDEN']):
            result=gate.run('net:[123]')
        self.assertEqual(result['status'],'BLOCKED')
        self.assertEqual(result['real_process_kill'],'NOT_TESTED')
        self.assertIn('ISOLATION_PRECONDITION_FAILED',result['reason'])
    def test_fixture_runner_has_no_product_loader(self):
        source=Path(gate.__file__).read_text()
        self.assertNotIn('product.zip',source.lower())
        self.assertNotIn('--no-sandbox',source)
        self.assertNotIn('load_user_profile',source)
    def test_ready_origin_strict(self):
        class FakePage:
            def __init__(self,actual):self.actual=actual
            def goto(self,*a,**kw):pass
            def evaluate(self,*a):return self.actual
        class FakeContext:
            def __init__(self,actual):self.actual=actual
            def new_page(self):return FakePage(self.actual)
        eid='a'*32
        with self.assertRaisesRegex(RuntimeError,'ORIGIN_MISMATCH'):
            gate.open_page(FakeContext({'id':eid,'origin':'https://example.invalid','ready':True}),eid)

if __name__=='__main__':unittest.main()
