import unittest
from unittest.mock import patch
from ai.browser_preflight import run

class BrowserPreflightTest(unittest.TestCase):
    @patch("ai.browser_preflight.check_browser", return_value={
        "status": "PASS", "version": "test", "scope": "in_memory_fixture_only"})
    def test_toolchain_success_does_not_claim_e2e(self, ignored):
        report = run("chromium")
        self.assertEqual(report["toolchain_smoke"]["status"], "PASS")
        self.assertEqual(report["extension_e2e"], "NOT_RUN")
        self.assertEqual(report["site_e2e"], "NOT_RUN")
        self.assertEqual(report["media_recording_e2e"], "NOT_RUN")

    @patch("ai.browser_preflight.check_browser", side_effect=RuntimeError("do not expose private path"))
    def test_toolchain_error_is_clear_without_sensitive_exception_text(self, ignored):
        report = run("firefox")
        self.assertEqual(report["toolchain_smoke"]["status"], "FAIL")
        self.assertEqual(report["toolchain_smoke"]["error_type"], "RuntimeError")
        self.assertNotIn("private path", str(report))

if __name__ == "__main__":
    unittest.main()
