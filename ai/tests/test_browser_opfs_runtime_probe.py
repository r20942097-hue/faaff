"""Fail-closed offline tests; no browser launched and no product ZIP loaded."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import browser_opfs_runtime_probe as gate

class SyntheticBrowserOpfsTests(unittest.TestCase):
    def valid(self):
        result={'schema':gate.SCHEMA,'product_executed':False,
                'external_network':'DISABLED','release_decision':'CANDIDATE_NO_GO',
                'sha256':gate.DIGEST}
        result.update({key:'PASS' for key in gate.FLAGS})
        return result
    def test_positive_evidence(self):
        self.assertTrue(gate.evidence_ok(self.valid()))
    def test_missing_fields_all_block(self):
        for key in gate.FLAGS:
            with self.subTest(key=key):
                r=self.valid();r[key]='NOT_RUN'
                self.assertFalse(gate.evidence_ok(r))
    def test_wrong_identity_and_digest_block(self):
        for key,value in [('schema','bad'),('sha256','0'*64),('product_executed',True),
                          ('release_decision','GO'),('external_network','ALLOWED')]:
            with self.subTest(key=key):
                r=self.valid();r[key]=value
                self.assertFalse(gate.evidence_ok(r))
    def test_fixture_has_no_remote_permissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'extension';gate.make_fixture(path)
            manifest=json.loads((path/'manifest.json').read_text())
            self.assertEqual(manifest['permissions'],['storage'])
            self.assertNotIn('host_permissions',manifest)
            self.assertEqual(manifest['background']['service_worker'],'worker.js')
            self.assertNotIn('http://',(path/'popup.html').read_text())
    def test_synthetic_data_integrity(self):
        self.assertEqual(gate.DIGEST,hashlib.sha256(bytes(gate.DATA)).hexdigest())
    def test_worker_id_strict(self):
        class W:
            def __init__(self,url):self.url=url
        class C:
            def __init__(self,urls):self.service_workers=[W(url) for url in urls]
        ident='a'*32
        self.assertEqual(gate.get_id(C(['chrome-extension://'+ident+'/worker.js'])),ident)
        self.assertRaises(RuntimeError,gate.get_id,C(['chrome-extension://'+ident+'/worker.js',
                          'chrome-extension://'+ident+'/worker.js']))
    def test_invalid_isolation_refuses_execution(self):
        with patch.dict(sys.modules,{'isolated_extension_e2e':types.SimpleNamespace(
                isolation_check=lambda x:['DEFAULT_IPV4_ROUTE_PRESENT'])}):
            report=gate.run(None,'net:[123]')
        self.assertEqual(report['status'],'BLOCKED')
        self.assertEqual(report['reason'],'ISOLATION_PRECONDITION_FAILED')
        self.assertIs(report['product_executed'],False)
    def test_no_network_fetch_in_browser_script(self):
        for bad in ('fetch(', 'http://', 'https://', 'XMLHttpRequest','eval('):
            self.assertNotIn(bad,gate.JS_WRITE)
            self.assertNotIn(bad,gate.JS_READ)

if __name__=='__main__':unittest.main()
