import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai.opfs_postcommit_kill_fixture import (
    MARKER,COMMIT_B_KEEP_A,template,verify_committed,run,main
)
from ai.opfs_restart_fixture import SOURCE_B,HASH_B

class PostcommitKillTests(unittest.TestCase):
    def test_baseline_pass_claims_are_never_preset(self):
        r=template("firefox")
        self.assertEqual(r["status"],"BLOCKED")
        self.assertEqual(r["release_readiness"],"NO_GO")
        self.assertEqual(r["product_e2e"],"NOT_RUN")
        self.assertEqual(r["power_failure"],"NOT_RUN")
        self.assertEqual(r["physical_disk_failure"],"NOT_RUN")

    def test_browser_phase_requires_closed_manifest(self):
        self.assertIn("manifestWriter.close()",COMMIT_B_KEEP_A)
        self.assertIn("writer.close()",COMMIT_B_KEEP_A)
        self.assertIn("blob-0001.bin",COMMIT_B_KEEP_A)
        self.assertEqual(MARKER,"READY_COMMITTED_B_WITH_OLD_A")

    def test_new_generation_verified_with_previous_orphan(self):
        observed={"generation":2,"active":"blob-0002.bin",
                  "declared":HASH_B,"calculated":HASH_B,"bytes":SOURCE_B,
                  "names":["blob-0001.bin","blob-0002.bin","state.json"]}
        verify_committed(observed,True)
        with self.assertRaisesRegex(AssertionError,"POSTCOMMIT_INVENTORY_MISMATCH"):
            verify_committed(observed,False)

    def test_corrupted_bytes_are_rejected(self):
        observed={"generation":2,"active":"blob-0002.bin",
                  "declared":HASH_B,"calculated":HASH_B,"bytes":[0],
                  "names":["blob-0002.bin","state.json"]}
        with self.assertRaisesRegex(AssertionError,"GENERATION_SHA256_OR_BYTES_MISMATCH"):
            verify_committed(observed,False)

    def test_unexpected_files_are_rejected(self):
        observed={"generation":2,"active":"blob-0002.bin",
                  "declared":HASH_B,"calculated":HASH_B,"bytes":SOURCE_B,
                  "names":["blob-0002.bin","state.json","unexpected"]}
        with self.assertRaisesRegex(AssertionError,"POSTCOMMIT_INVENTORY_MISMATCH"):
            verify_committed(observed,False)

    @patch("ai.opfs_postcommit_kill_fixture.probe",
           side_effect=RuntimeError("secret /home/private"))
    def test_error_report_redacts_private_paths(self, _unused):
        report=run("chromium")
        self.assertEqual(report["status"],"BLOCKED")
        self.assertEqual(report["failure_code"],"UNCLASSIFIED")
        self.assertNotIn("/home/private",json.dumps(report))

    @patch("ai.opfs_postcommit_kill_fixture.probe",
           side_effect=RuntimeError("OLD_GENERATION_CLEANUP_MISMATCH"))
    def test_known_error_uses_bounded_code(self, _unused):
        self.assertEqual(run("firefox")["failure_code"],"OLD_GENERATION_CLEANUP_MISMATCH")

    @patch("ai.opfs_postcommit_kill_fixture.probe",
           side_effect=RuntimeError("unavailable"))
    def test_cli_blocks_and_reports_no_go(self,_unused):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"result.json"
            with patch("builtins.print"):
                code=main(["--browser","chromium","--output",str(path)])
            self.assertEqual(code,2)
            self.assertEqual(json.loads(path.read_text())["release_readiness"],"NO_GO")

if __name__=="__main__":
    unittest.main()
