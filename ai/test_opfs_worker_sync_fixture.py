import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ai.opfs_worker_sync_fixture import (
    BYTES, SHA256, WORKER_JS, SINGLE_WORKER, START_HOLD,
    START_COMPETITOR, template, require_bytes, run, main,
)

class WorkerSyncFixtureTests(unittest.TestCase):
    def test_fixture_bytes_sha256(self):
        self.assertEqual(hashlib.sha256(bytes(BYTES)).hexdigest(), SHA256)

    def test_real_sync_calls_and_flush(self):
        for part in ('createSyncAccessHandle()', 'handle.truncate(0)',
                     'handle.write(bytes, {at:0})', 'handle.flush()',
                     'handle.read(bytes, {at:0})', 'handle.close()'):
            self.assertIn(part, WORKER_JS)

    def test_worker_handles_do_not_expose_source_paths(self):
        self.assertIn("new Worker('/worker.js')", SINGLE_WORKER)
        self.assertIn("new Worker('/worker.js')", START_HOLD)
        self.assertIn("new Worker('/worker.js')", START_COMPETITOR)

    def test_valid_read(self):
        require_bytes({'phase':'done','bytes':BYTES,'sha256':SHA256,'flushed':True},
                      should_flush=True)

    def test_changed_data_rejected(self):
        with self.assertRaises(AssertionError):
            require_bytes({'phase':'done','bytes':BYTES[:-1],
                           'sha256':SHA256,'flushed':True})

    def test_flush_must_be_explicit(self):
        with self.assertRaises(AssertionError):
            require_bytes({'phase':'done','bytes':BYTES,'sha256':SHA256,'flushed':False},
                          should_flush=True)

    def test_release_remains_no_go(self):
        evidence=template('chromium')
        self.assertEqual(evidence['real_product_e2e'],'NOT_RUN')
        self.assertEqual(evidence['real_disk_power_loss'],'NOT_RUN')
        self.assertEqual(evidence['release_readiness'],'NO_GO')

    @patch('ai.opfs_worker_sync_fixture.probe',
           side_effect=RuntimeError('private-secret-stack'))
    def test_redacted_errors(self, unused):
        evidence=run('firefox')
        self.assertEqual(evidence['status'],'BLOCKED')
        self.assertEqual(evidence['error_type'],'RuntimeError')
        self.assertNotIn('private-secret-stack',json.dumps(evidence))

    @patch('ai.opfs_worker_sync_fixture.probe',
           side_effect=RuntimeError('failure'))
    def test_cli_failure_nonzero_and_json(self, unused):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'result.json'
            with patch('builtins.print'):
                exit_code=main(['--browser','chromium','--output',str(path)])
            self.assertEqual(exit_code,2)
            self.assertEqual(json.loads(path.read_text())['release_readiness'],'NO_GO')

if __name__=='__main__':unittest.main()
