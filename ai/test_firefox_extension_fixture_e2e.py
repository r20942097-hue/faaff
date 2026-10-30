import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ai.firefox_extension_fixture_e2e import MANIFEST, write_fixture, run

class FirefoxExtensionFixtureTests(unittest.TestCase):
    def test_manifest_uses_event_page_and_restricted_host(self):
        self.assertEqual(MANIFEST["manifest_version"], 3)
        self.assertEqual(MANIFEST["background"]["scripts"], ["background.js"])
        self.assertNotIn("service_worker", MANIFEST["background"])
        self.assertEqual(MANIFEST["host_permissions"], ["http://127.0.0.1/*"])

    def test_fixture_files_present(self):
        with tempfile.TemporaryDirectory() as t:
            root = write_fixture(t)
            self.assertEqual(json.loads((root / "manifest.json").read_text())["manifest_version"], 3)
            self.assertTrue((root / "content.js").exists())
            self.assertTrue((root / "background.js").exists())

    @patch("ai.firefox_extension_fixture_e2e.probe", return_value={"status": "PASS"})
    def test_fixture_success_does_not_claim_product(self, ignored):
        result = run()
        self.assertEqual(result["fixture_e2e"]["status"], "PASS")
        self.assertEqual(result["product_e2e"], "NOT_RUN")
        self.assertEqual(result["release_readiness"], "NO_GO")

    @patch("ai.firefox_extension_fixture_e2e.probe", side_effect=RuntimeError("/private/path"))
    def test_error_redacted(self, ignored):
        result = run()
        self.assertEqual(result["fixture_e2e"]["status"], "FAIL")
        self.assertNotIn("/private/path", json.dumps(result))

if __name__ == "__main__":
    unittest.main()
