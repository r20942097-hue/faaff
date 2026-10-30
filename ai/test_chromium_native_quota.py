import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ai.chromium_native_quota import PAYLOAD,DIGEST,READ,TRY_BIG,report_template,verify_baseline,run,main

class NativeQuotaUnitTests(unittest.TestCase):
 def test_checksum(self):self.assertEqual(hashlib.sha256(bytes(PAYLOAD)).hexdigest(),DIGEST)
 def test_valid_baseline(self):verify_baseline({'digest':DIGEST,'generation':1,'size':len(PAYLOAD)})
 def test_data_loss_detected(self):
  with self.assertRaises(AssertionError):
   verify_baseline({'digest':'bad','generation':1,'size':len(PAYLOAD)})
 def test_product_remains_no_go(self):
  report=report_template()
  self.assertEqual(report['native_quota_error'],'NOT_RUN')
  self.assertEqual(report['firefox_native_quota'],'NOT_RUN')
  self.assertEqual(report['release_readiness'],'NO_GO')
 def test_large_candidate(self):
  self.assertIn('new Uint8Array(8*1024*1024)',TRY_BIG)
  self.assertIn("getFileHandle('manifest.json')",READ)
 @patch('ai.chromium_native_quota.probe',side_effect=RuntimeError('SECRET_PATH'))
 def test_secret_diagnostics_redacted(self,ignored):
  report=run();self.assertEqual(report['status'],'BLOCKED')
  self.assertNotIn('SECRET_PATH',json.dumps(report))
 @patch('ai.chromium_native_quota.probe',side_effect=RuntimeError('failure'))
 def test_error_exits_nonzero(self,ignored):
  with tempfile.TemporaryDirectory() as d:
   out=Path(d)/'result.json'
   with patch('builtins.print'):
    rc=main(['--output',str(out)])
   self.assertEqual(rc,2)
   self.assertEqual(json.loads(out.read_text())['release_readiness'],'NO_GO')
if __name__=='__main__':unittest.main()
