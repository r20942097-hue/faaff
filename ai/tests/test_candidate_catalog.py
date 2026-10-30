"""Offline candidate catalog tests; never extract or execute candidate code."""
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from candidate_catalog import MAX_INPUTS, build_catalog, main


class CandidateCatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.good = self.root / "candidate.zip"
        with zipfile.ZipFile(self.good, "w") as z:
            z.writestr("chrome/manifest.json", json.dumps({
                "manifest_version": 3, "name": "Example", "version": "1.0"}))

    def test_one_good_candidate(self):
        result = build_catalog([self.good])
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["decision"], "CANDIDATE_NO_GO")
        self.assertEqual(result["items"][0]["extension_manifest_count"], 1)
        self.assertEqual(len(result["items"][0]["sha256"]), 64)

    def test_real_browser_never_pass(self):
        result = build_catalog([self.good])
        self.assertEqual(result["items"][0]["real_browser"], "NOT_RUN")
        self.assertEqual(result["items"][0]["source_provenance"], "NOT_VERIFIED")

    def test_input_path_not_exposed(self):
        result = build_catalog([self.good])
        self.assertEqual(result["items"][0]["filename"], "candidate.zip")
        self.assertNotIn(str(self.root), json.dumps(result))

    def test_missing_archive(self):
        result = build_catalog([self.root / "missing.zip"])
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["items"][0]["extension_inventory"], "BLOCKED")

    def test_bad_zip(self):
        p = self.root / "bad.zip"
        p.write_bytes(b"not zip")
        result = build_catalog([p])
        self.assertEqual(result["status"], "FAIL")

    def test_no_paths(self):
        self.assertEqual(build_catalog([])["status"], "INVALID")

    def test_duplicate_input(self):
        self.assertEqual(build_catalog([self.good, self.good])["status"], "INVALID")

    def test_wrong_suffix(self):
        p = self.root / "candidate.txt"
        p.write_bytes(self.good.read_bytes())
        self.assertEqual(build_catalog([p])["status"], "INVALID")

    def test_too_many_files(self):
        self.assertEqual(build_catalog([self.good] * (MAX_INPUTS + 1))["status"], "INVALID")

    def test_two_valid_files(self):
        p = self.root / "copy.zip"
        p.write_bytes(self.good.read_bytes())
        result = build_catalog([self.good, p])
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(len(result["items"]), 2)

    def test_cli_json(self):
        with patch("builtins.print"):
            self.assertEqual(main([str(self.good), "--json"]), 0)

    def test_cli_missing(self):
        with patch("builtins.print"):
            self.assertEqual(main([str(self.root / "missing.zip")]), 1)


if __name__ == "__main__":
    unittest.main()
