import hashlib
import json
import unittest
from unittest.mock import patch
from ai.opfs_snapshot_fixture import DATA, DIGEST, WRITE, base_report, require_equal, run

class OpfsSnapshotFixtureTest(unittest.TestCase):
    def test_known_fixture_digest(self):
        self.assertEqual(hashlib.sha256(bytes(DATA)).hexdigest(), DIGEST)

    def test_no_go_by_default(self):
        report = base_report("chromium")
        self.assertEqual(report["release_readiness"], "NO_GO")
        self.assertEqual(report["real_product_e2e"], "NOT_RUN")
        self.assertEqual(report["snapshot_import"], "NOT_RUN")

    def test_write_has_abort_path(self):
        self.assertIn("await uncommitted.abort()", WRITE)
        self.assertIn("await writer.close()", WRITE)

    def test_mismatch_is_detected(self):
        with self.assertRaises(AssertionError):
            require_equal({"bytes":[1,2], "sha256":DIGEST})
        with self.assertRaises(AssertionError):
            require_equal({"bytes":DATA,"sha256":"bad"})

    @patch("ai.opfs_snapshot_fixture.probe", side_effect=RuntimeError("PRIVATE_SANDBOX_INFO"))
    def test_failure_cannot_emit_private_details_or_pass(self, ignored):
        report=run("firefox")
        self.assertEqual(report["status"], "BLOCKED")
        self.assertNotIn("PRIVATE_SANDBOX_INFO",json.dumps(report))
        self.assertEqual(report["snapshot_export"], "NOT_RUN")

    @patch("ai.opfs_snapshot_fixture.probe")
    def test_only_proven_fixture_pass_still_no_go_for_product(self, probe):
        fixture=base_report("chromium")
        fixture.update(status="PASS_DISPOSABLE_BROWSER_OPFS",
                       snapshot_export="PASS",snapshot_import="PASS")
        probe.return_value=fixture
        report=run("chromium")
        self.assertEqual(report["real_product_e2e"],"NOT_RUN")
        self.assertEqual(report["release_readiness"],"NO_GO")

if __name__ == "__main__":
    unittest.main()
