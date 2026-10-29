"""Synthetic extension manifest inventory tests; no execution or extraction."""
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from extension_inventory import scan, main


class ManifestInventoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "bundle.zip"

    def make(self, items):
        with zipfile.ZipFile(self.path, "w") as z:
            for name, payload in items:
                z.writestr(name, payload if isinstance(payload, (str, bytes)) else json.dumps(payload))
        return scan(self.path)

    def test_mv3(self):
        r = self.make([("firefox/manifest.json", {"manifest_version": 3, "name": "Test", "version": "1.2.3"})])
        self.assertEqual((r["status"], r["manifest_count"]), ("PASS", 1))
        self.assertEqual(r["manifests"][0]["browser_hint"], "firefox")

    def test_nested(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("chrome/manifest.json", json.dumps({"manifest_version": 3, "name": "Chrome", "version": "1.0"}))
        self.assertEqual(self.make([("extension.zip", buf.getvalue())])["manifest_count"], 1)

    def test_non_manifest_source_document_ignored(self):
        self.assertEqual(self.make([("SOURCE_MANIFEST.json", "{}")])["manifest_count"], 0)

    def test_wrong_mv(self):
        self.assertEqual(self.make([("manifest.json", {"manifest_version": 2, "name": "x", "version": "1"})])["status"], "FAIL")

    def test_bad_version(self):
        self.assertEqual(self.make([("manifest.json", {"manifest_version": 3, "name": "x", "version": "v1"})])["status"], "FAIL")

    def test_missing_name(self):
        self.assertEqual(self.make([("manifest.json", {"manifest_version": 3, "version": "1"})])["status"], "FAIL")

    def test_firefox_version_name(self):
        x = {"manifest_version": 3, "name": "x", "version": "1", "version_name": "test"}
        self.assertEqual(self.make([("firefox/manifest.json", x)])["status"], "FAIL")

    def test_chrome_version_name_allowed(self):
        x = {"manifest_version": 3, "name": "x", "version": "1", "version_name": "test"}
        self.assertEqual(self.make([("chrome/manifest.json", x)])["status"], "PASS")

    def test_bad_json(self):
        self.assertEqual(self.make([("manifest.json", "{invalid")])["status"], "FAIL")

    def test_bad_perms(self):
        x = {"manifest_version": 3, "name": "x", "version": "1", "permissions": ["tabs", 3]}
        self.assertEqual(self.make([("manifest.json", x)])["status"], "FAIL")

    def test_bad_nested_zip(self):
        self.assertEqual(self.make([("extension.zip", b"broken")])["status"], "FAIL")

    def test_oversize_nested_fails_closed(self):
        with patch("extension_inventory.MAX_NESTED_ZIP", 5):
            self.assertEqual(self.make([("extension.zip", b"123456")])["status"], "FAIL")

    def test_oversize_manifest_fails_closed(self):
        with patch("extension_inventory.MAX_MANIFEST", 5):
            self.assertEqual(self.make([("manifest.json", "{}123456")])["status"], "FAIL")

    def test_missing_archive(self):
        self.assertEqual(scan(self.path)["status"], "FAIL")

    def test_cli(self):
        self.make([("manifest.json", {"manifest_version": 3, "name": "x", "version": "1"})])
        with patch("builtins.print"):
            self.assertEqual(main([str(self.path), "--json"]), 0)


if __name__ == "__main__":
    unittest.main()
