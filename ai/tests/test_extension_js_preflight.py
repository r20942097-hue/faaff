"""No untrusted JS is executed; tests use small synthetic archives only."""
from __future__ import annotations
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import extension_js_preflight as gate


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'pkg.zip'
        self.root = 'addon/'
        self.files = {
            'addon/manifest.json': json.dumps({'manifest_version': 3,'name':'x','version':'1.0.0',
                'background': {'service_worker': 'worker.js'},'action':{'default_popup':'popup.html'}}),
            'addon/worker.js': "importScripts('dep.js');chrome.runtime.onMessage.addListener(()=>{});",
            'addon/dep.js': 'const x = 1;',
            'addon/popup.html': '<html><script src="popup.js"></script></html>',
            'addon/popup.js': 'const y = 2;',
        }

    def write(self, **changes):
        self.files.update(changes)
        with zipfile.ZipFile(self.path, 'w') as z:
            for name, value in self.files.items():
                z.writestr(name, value)
        return gate._sha256(self.path)

    def run_gate(self, *, baseline=None, node=None, digest=None, root=None):
        import sys
        fake = types.ModuleType('extension_source_preflight')
        fake.inspect = lambda *_: baseline or {'status': 'PASS', 'extensions': [{'root': self.root, 'status':'PASS'}]}
        with patch.dict(sys.modules, {'extension_source_preflight': fake}):
            return gate.inspect(self.path, digest or gate._sha256(self.path), root or self.root, node=node)

    def test_valid_candidate(self):
        self.write()
        r = self.run_gate()
        if shutil.which('node') is None:
            self.assertEqual(r['status'], 'PARTIAL')
        else:
            self.assertEqual(r['status'], 'PASS_SYNTAX_REFS_ONLY')
        self.assertEqual(r['worker_imports'], ['dep.js'])
        self.assertEqual(r['release_decision'], 'CANDIDATE_NO_GO')
        self.assertEqual(r['browser_e2e'], 'NOT_RUN')

    def test_existing_real_gate_integration(self):
        try:
            import artifact_gate  # noqa: F401
        except ImportError:
            self.skipTest('artifact_gate present only in integration repo')
        self.write()
        result = gate.inspect(self.path, gate._sha256(self.path), self.root)
        self.assertEqual(result['status'], 'PASS_SYNTAX_REFS_ONLY')
        self.assertEqual(result['scripts_checked'], 3)

    def test_real_gate_rejects_invalid_import(self):
        try:
            import artifact_gate  # noqa: F401
        except ImportError:
            self.skipTest('artifact_gate present only in integration repo')
        self.files.pop('addon/dep.js')
        self.write()
        result = gate.inspect(self.path, gate._sha256(self.path), self.root)
        self.assertEqual(result['status'], 'FAIL')
        self.assertIn('MISSING_WORKER_IMPORT', result['issues'])

    def test_wrong_expected_sha(self):
        self.write()
        self.assertEqual(self.run_gate(digest='0'*64)['issues'], ['SHA256_MISMATCH'])

    def test_invalid_digest(self):
        self.write()
        self.assertEqual(self.run_gate(digest='xyz')['issues'], ['INVALID_TRUSTED_SHA256'])

    def test_invalid_zip(self):
        self.path.write_bytes(b'bad zip')
        self.assertEqual(self.run_gate(baseline={'status':'FAIL'})['status'], 'FAIL')

    def test_original_static_gate_failure_blocks(self):
        self.write()
        r=self.run_gate(baseline={'status':'FAIL'})
        self.assertIn('EXISTING_ARCHIVE_OR_MANIFEST_GATE_NOT_PASS',r['issues'])

    def test_wrong_selected_root(self):
        self.write()
        self.assertIn('ROOT_NOT_VERIFIED_EXTENSION', self.run_gate(root='wrong/')['issues'])

    def test_missing_import_is_detected(self):
        self.files.pop('addon/dep.js')
        self.write()
        self.assertIn('MISSING_WORKER_IMPORT', self.run_gate()['issues'])

    def test_remote_worker_import_rejected(self):
        self.write(**{'addon/worker.js': 'importScripts("https://evil.example/x.js");'})
        self.assertIn('UNSAFE_OR_REMOTE_WORKER_IMPORT', self.run_gate()['issues'])

    def test_dynamic_import_unknown_not_pass(self):
        self.write(**{'addon/worker.js': "importScripts(somePath);"})
        self.assertEqual(self.run_gate()['status'], 'PARTIAL')

    def test_missing_node_partial(self):
        self.write()
        with patch.object(gate.shutil, 'which', return_value=None):
            r=self.run_gate()
        self.assertEqual(r['status'], 'PARTIAL')
        self.assertEqual(r['scripts_checked'], 0)

    @unittest.skipUnless(shutil.which('node'), 'Node is required for syntax checks')
    def test_invalid_js_syntax(self):
        self.write(**{'addon/dep.js': 'const broken = ;'})
        self.assertIn('dep.js',self.run_gate()['syntax_failures'])

    def test_non_literal_worker_import_is_partial(self):
        self.write(**{'addon/worker.js': "const name='dep.js';importScripts(name);"})
        self.assertEqual(self.run_gate()['status'], 'PARTIAL')

    def test_no_worker_is_partial(self):
        self.files['addon/manifest.json'] = json.dumps({'manifest_version':3,'name':'x','version':'1'})
        self.write()
        self.assertEqual(self.run_gate()['status'],'PARTIAL')

    def test_module_syntax_nonexecuting(self):
        if not shutil.which('node'): self.skipTest('Node missing')
        self.files['addon/manifest.json']=json.dumps({'manifest_version':3,'name':'x','version':'1',
                            'background':{'service_worker':'worker.js','type':'module'}})
        self.write(**{'addon/worker.js':"import {a} from './dep.js';",'addon/dep.js':'export const a = 1;'})
        self.assertEqual(self.run_gate()['status'],'PASS_SYNTAX_REFS_ONLY')

    def test_parser_does_not_execute_js(self):
        self.write(**{'addon/dep.js': "process.exit(99); console.log('this is never executed');"})
        self.assertEqual(self.run_gate()['status'],'PASS_SYNTAX_REFS_ONLY' if shutil.which('node') else 'PARTIAL')

    def test_node_check_timeout_not_pass(self):
        self.assertEqual(gate._node_syntax(b'const a = 1;', False, '/not-a-node'), 'UNAVAILABLE')

    def test_invalid_import_literal_list(self):
        a,b=gate._parse_imports("importScripts('a.js', unknown);")
        self.assertEqual(a,[])
        self.assertTrue(b)

    def test_dynamic_import_notice(self):
        a,b=gate._parse_imports('import(\'dep.js\')')
        self.assertEqual(a,[])
        self.assertIn('POSSIBLE_UNSUPPORTED_DYNAMIC_IMPORT_REQUIRES_REVIEW',b)

    def test_safe_ref(self):
        for ref in ('../escape.js','/root.js','https://x/y.js','c:\\test.js','bad?foo'):
            self.assertFalse(gate._safe_local_ref(ref))
        self.assertTrue(gate._safe_local_ref('lib/worker.js'))

if __name__ == '__main__': unittest.main()