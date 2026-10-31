"""Immutable EasyPrivacy source acquisition and provenance checks."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_stock import LOCK, PATHS, blob_sha, fetch, validate_bytes, verify_lock
import json


class StockSourceVerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lock = json.loads(LOCK.read_text(encoding="utf-8"))

    def test_pin_contains_only_expected_upstream_fragments(self):
        self.assertTrue(verify_lock(self.lock))
        self.assertEqual(len(self.lock["files"]), 5)
        self.assertEqual(
            [e["path"] for e in self.lock["files"]], list(PATHS))
        self.assertEqual(sum(e["size"] for e in self.lock["files"]), 359254)
        self.assertIn("NOT_COMPLETE", self.lock["scope"])

    def test_commit_pin_must_be_full_sha(self):
        wrong = copy.deepcopy(self.lock)
        wrong["upstream_commit"] = "master"
        with self.assertRaisesRegex(ValueError, "manifest invalid"):
            verify_lock(wrong)

    def test_reordered_or_added_sources_rejected(self):
        for change in ("drop", "reorder", "add"):
            bad = copy.deepcopy(self.lock)
            if change == "drop":
                bad["files"].pop()
            if change == "reorder":
                bad["files"].reverse()
            if change == "add":
                bad["files"].append(dict(bad["files"][0]))
            with self.subTest(change=change), self.assertRaises(ValueError):
                verify_lock(bad)

    def test_size_or_sha_tampering_is_rejected(self):
        entry = {"path": "easyprivacy/easyprivacy_general.txt",
                 "size": 6, "git_blob_sha": blob_sha(b"hello\n")}
        self.assertEqual(len(validate_bytes(b"hello\n", entry)), 64)
        for content in (b"hello", b"HELLO\n", b"hello\r\n"):
            with self.subTest(content=content), self.assertRaises(ValueError):
                validate_bytes(content, entry)

    def test_fetch_aborts_without_leaking_invalid_source(self):
        fake = copy.deepcopy(self.lock)
        for entry in fake["files"]:
            entry["size"] = 100
            entry["git_blob_sha"] = blob_sha(b"hello\n" * 16 + b"hiya")
        requested = []
        def reader(url, limit):
            requested.append((url, limit))
            return b"hello\n" * 16 + b"hiya"
        files, manifest = fetch(fake, reader)
        self.assertEqual(len(files), 5)
        self.assertEqual(len(manifest), 5)
        self.assertTrue(all(fake["upstream_commit"] in url for url, _ in requested))
        def tamper(url, limit):
            if "general" in url:
                return b"fake!!"
            return b"hello\n" * 16 + b"hiya"
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            fetch(fake, tamper)

    def test_paths_reject_unpinned_replacement(self):
        incorrect = copy.deepcopy(self.lock)
        incorrect["files"][0]["path"] = "../secret"
        with self.assertRaises(ValueError):
            verify_lock(incorrect)

    def test_size_guards_and_missing_hash_rejected(self):
        for size in (0, 500001, True):
            bad = copy.deepcopy(self.lock)
            bad["files"][0]["size"] = size
            with self.subTest(size=size), self.assertRaises(ValueError):
                verify_lock(bad)
        bad = copy.deepcopy(self.lock)
        bad["files"][0].pop("git_blob_sha")
        with self.assertRaises(ValueError):
            verify_lock(bad)


if __name__ == "__main__":
    unittest.main()
