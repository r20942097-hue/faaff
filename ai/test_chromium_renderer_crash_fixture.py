import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai.chromium_renderer_crash_fixture import (
    STAGE_UNCOMMITTED, CLEAN, template, verify_old, run, main)
from ai.opfs_restart_fixture import SOURCE_A, HASH_A

class RendererCrashFixtureTests(unittest.TestCase):
    def test_unclosed_manifest_is_explicit(self):
        self.assertIn('window.__pendingManifest=await state.createWritable()',STAGE_UNCOMMITTED)
        self.assertNotIn('window.__pendingManifest.close()',STAGE_UNCOMMITTED)
        self.assertIn('await writable.close()',STAGE_UNCOMMITTED)

    def test_valid_committed_state(self):
        verify_old({'generation':1,'active':'blob-0001.bin',
                    'sha256':HASH_A,'declared':HASH_A,
                    'calculated':HASH_A,'bytes':SOURCE_A})

    def test_corrupted_sha_is_rejected(self):
        with self.assertRaises(AssertionError):
            verify_old({'generation':1,'active':'blob-0001.bin',
                        'sha256':'wrong','declared':HASH_A,
                        'calculated':HASH_A,'bytes':SOURCE_A})

    def test_cleanup_does_not_remove_active_blob(self):
        self.assertIn("name!==state.active",CLEAN)

    def test_report_is_scoped(self):
        report=template()
        self.assertEqual(report['os_process_termination'],'NOT_RUN')
        self.assertEqual(report['sudden_power_loss'],'NOT_RUN')
        self.assertEqual(report['product_e2e'],'NOT_RUN')
        self.assertEqual(report['release_readiness'],'NO_GO')

    @patch('ai.chromium_renderer_crash_fixture.probe',
           side_effect=RuntimeError('private-profile-path'))
    def test_error_is_redacted(self,unused):
        result=run()
        self.assertEqual(result['status'],'BLOCKED')
        self.assertNotIn('private-profile-path',json.dumps(result))

    @patch('ai.chromium_renderer_crash_fixture.probe',
           side_effect=RuntimeError('failure'))
    def test_cli_failure_exits_nonzero(self,unused):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'result.json'
            with patch('builtins.print'):
                code=main(['--output',str(path)])
            self.assertEqual(code,2)
            self.assertEqual(json.loads(path.read_text())['release_readiness'],'NO_GO')

if __name__=='__main__':
    unittest.main()
