import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from ai.audit_environment import REQUIRED, inspect, main

class AuditEnvironmentTest(unittest.TestCase):
    def test_missing_source_never_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = inspect(tmp)
            self.assertEqual(report["products"]["watcher"]["status"], "SOURCE_MISSING")
            self.assertEqual(report["products"]["extension"]["status"], "SOURCE_MISSING")
            self.assertEqual(report["release_readiness"], "NO_GO")
            self.assertTrue(all(v == "NOT_RUN" for v in report["checks"].values()))

    def test_present_files_are_not_product_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for paths in REQUIRED.values():
                for path in paths:
                    file = root / path
                    file.parent.mkdir(parents=True, exist_ok=True)
                    file.write_text("fixture", encoding="utf-8")
            report = inspect(root)
            self.assertTrue(all(x["status"] == "SOURCE_PRESENT_UNTESTED"
                                for x in report["products"].values()))
            self.assertEqual(report["checks"]["firefox_extension_e2e"], "NOT_RUN")
            self.assertEqual(report["release_readiness"], "NO_GO")

    def test_sha256_uses_actual_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "pyproject.toml").write_bytes(b"hello\r\n")
            item = next(x for x in inspect(tmp)["products"]["watcher"]["sources"]
                        if x["path"] == "pyproject.toml")
            self.assertEqual(item["sha256"], hashlib.sha256(b"hello\r\n").hexdigest())
            self.assertEqual(item["size"], 7)

    def test_nonexistent_root_is_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(inspect(Path(tmp) / "missing")["workflows"], [])

    def test_symlink_outside_root_not_hashed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            outside = Path(tmp) / "outside"
            outside.write_text("sensitive")
            try:
                (root / "pyproject.toml").symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable")
            item = next(x for x in inspect(root)["products"]["watcher"]["sources"]
                        if x["path"] == "pyproject.toml")
            self.assertFalse(item["present"])
            self.assertNotIn("sha256", item)

    def test_non_strict_writes_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "reports" / "audit.json"
            self.assertEqual(main([tmp, "--output", str(out)]), 0)
            self.assertEqual(json.loads(out.read_text())["release_readiness"], "NO_GO")

    def test_strict_source_gate_fails_on_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(main([tmp, "--require-source", "watcher"]), 2)

    def test_strict_source_gate_does_not_claim_e2e_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            for path in REQUIRED["watcher"]:
                p = Path(tmp) / path
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(b"test")
            self.assertEqual(main([tmp, "--require-source", "watcher"]), 0)
            self.assertEqual(inspect(tmp)["release_readiness"], "NO_GO")

if __name__ == "__main__":
    unittest.main()
