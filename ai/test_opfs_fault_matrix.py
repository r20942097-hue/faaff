import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ai.opfs_fault_matrix import (
 A, B, C, SHA, FAULTS, FAULT_JS, CONCURRENT_JS, template, verify_item, run, main
)

class FaultMatrixUnitTests(unittest.TestCase):
 def test_hashes(self):
  for key,data in [('A',A),('B',B),('C',C)]:
   self.assertEqual(hashlib.sha256(bytes(data)).hexdigest(),SHA[key])
  self.assertEqual(len(set(SHA.values())),3)

 def test_six_distinct_faults(self):
  self.assertEqual(len(FAULTS),6)
  self.assertEqual(len(set(FAULTS)),6)

 def test_precommit_a_survives(self):
  for fault in FAULTS:
   if fault!='interrupt_after_manifest_close':
    verify_item(fault,{'generation':1,'sha256':SHA['A']})

 def test_postcommit_b_survives(self):
  verify_item('interrupt_after_manifest_close',{'generation':2,'sha256':SHA['B']})

 def test_wrong_sha_fails(self):
  with self.assertRaises(AssertionError):
   verify_item('abort_manifest_writer',{'generation':1,'sha256':SHA['B']})

 def test_quota_and_process_kill_explicitly_not_run(self):
  report=template('chromium')
  self.assertEqual(report['actual_quota_fault'],'NOT_RUN')
  self.assertEqual(report['forced_process_kill'],'NOT_RUN')
  self.assertEqual(report['product_e2e'],'NOT_RUN')
  self.assertEqual(report['release_readiness'],'NO_GO')

 def test_js_writer_abort_close_contract(self):
  self.assertIn('await writer.abort()',FAULT_JS)
  self.assertIn('await mw.abort()',FAULT_JS)
  self.assertIn('await mw.close()',FAULT_JS)

 def test_lock_is_exclusive(self):
  self.assertIn("mode:'exclusive'",CONCURRENT_JS)
  self.assertIn('navigator.locks.request',CONCURRENT_JS)

 @patch('ai.opfs_fault_matrix.probe',side_effect=RuntimeError('PRIVATE_PATH'))
 def test_redacted_failure(self,ignored):
  result=run('firefox')
  self.assertEqual(result['status'],'BLOCKED')
  self.assertNotIn('PRIVATE_PATH',json.dumps(result))

 @patch('ai.opfs_fault_matrix.probe',side_effect=RuntimeError('error'))
 def test_cli_nonzero(self,ignored):
  with tempfile.TemporaryDirectory() as temp:
   output=Path(temp)/'data.json'
   with patch('builtins.print'):
    code=main(['--browser','chromium','--output',str(output)])
   self.assertEqual(code,2)
   self.assertEqual(json.loads(output.read_text())['release_readiness'],'NO_GO')

if __name__=='__main__':
 unittest.main()
