"""Offline tests of independent Git-tree-to-manifest comparison."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from compare_pinned_tree import compare  # noqa: E402

SHA = "a" * 40
TREE = "b" * 40
BLOB = "c" * 40


class CompareTreeTest(unittest.TestCase):
    def setUp(self):
        self.manifest = {"source_commit": SHA, "source_tree_sha": TREE,
                         "excluded_paths": ["AGENTS.md"],
                         "files": [{"path": "ad.txt", "git_blob_sha": BLOB, "size": 4}]}
        self.commit = {"sha": SHA, "tree": {"sha": TREE}}
        self.tree = {"sha": TREE, "truncated": False, "tree": [
            {"path": "ad.txt", "type": "blob", "sha": BLOB, "size": 4, "mode": "100644"},
            {"path": "AGENTS.md", "type": "blob", "sha": BLOB, "size": 4, "mode": "100644"},
        ]}

    def test_exact_parity(self):
        self.assertEqual(compare(self.manifest, self.commit, self.tree), [])

    def test_wrong_commit(self):
        self.commit["sha"] = BLOB
        self.assertIn("commit SHA", " ".join(compare(self.manifest, self.commit, self.tree)))

    def test_mismatched_blob_sha(self):
        self.manifest["files"][0]["git_blob_sha"] = SHA
        self.assertIn("Git blob SHA", " ".join(compare(self.manifest, self.commit, self.tree)))

    def test_missing_file(self):
        self.manifest["files"] = []
        self.assertIn("file set differs", " ".join(compare(self.manifest, self.commit, self.tree)))

    def test_truncated_tree(self):
        self.tree["truncated"] = True
        self.assertIn("truncated", " ".join(compare(self.manifest, self.commit, self.tree)))

    def test_unexcluded_symlink(self):
        self.tree["tree"][0]["mode"] = "120000"
        self.assertIn("symbolic link", " ".join(compare(self.manifest, self.commit, self.tree)))

    def test_missing_excluded(self):
        self.tree["tree"].pop()
        self.assertIn("excluded upstream", " ".join(compare(self.manifest, self.commit, self.tree)))

    def test_malformed_record_does_not_crash(self):
        self.tree["tree"].append(None)
        self.assertIn("malformed upstream", " ".join(compare(self.manifest, self.commit, self.tree)))


if __name__ == "__main__":
    unittest.main()
