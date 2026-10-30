import tempfile
import unittest
from pathlib import Path
from ai.audit_environment import inspect

class AuditEnvironmentTest(unittest.TestCase):
    def test_missing_source_never_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = inspect(tmp)
            self.assertEqual(result["products"]["watcher"]["status"], "SOURCE_MISSING")
            self.assertEqual(result["release_readiness"], "NO_GO")
            self.assertEqual(result["browser_e2e"], "NOT_RUN")

    def test_source_is_not_equivalent_to_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "rplay_watcher").mkdir()
            (root / "rplay_watcher" / "__init__.py").write_text("")
            (root / "pyproject.toml").write_text("")
            (root / "extension").mkdir()
            (root / "extension" / "manifest.json").write_text("{}")
            result = inspect(root)
            self.assertTrue(all(v["status"] == "SOURCE_PRESENT_UNTESTED" for v in result["products"].values()))
            self.assertEqual(result["release_readiness"], "NO_GO")

if __name__ == "__main__":
    unittest.main()
