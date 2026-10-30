"""Offline regression cases for the pinned import validator."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_hub import blob_sha, safe_path, verify  # noqa: E402

SHA = "a" * 40


class CheckHubTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "ai/imports").mkdir(parents=True)
        self.src = self.root / "integrations/browser-filters/source/s"
        self.src.mkdir(parents=True)
        self.data = b"stable content\n"
        (self.src / "ad.txt").write_bytes(self.data)
        self.projects = {"schema": "ai-hub-registry/v1", "hub": "r20942097-hue/faaff",
                         "repositories": [{"id": "faaff", "observed_head": SHA},
                                          {"id": "s", "observed_head": SHA}],
                         "workstreams": [{"id": "import", "state": "pinned_snapshot"}]}
        self.manifest = {"schema": "pinned-source-import/v1", "source_repository": "r20942097-hue/s",
                         "source_commit": SHA, "source_tree_sha": SHA,
                         "target_prefix": "integrations/browser-filters/source/s/",
                         "excluded_paths": ["AGENTS.md"],
                         "files": [{"path": "ad.txt", "size": len(self.data), "git_blob_sha": blob_sha(self.data)}]}
        self.persist()

    def persist(self):
        (self.root / "ai/projects.json").write_text(json.dumps(self.projects), encoding="utf-8")
        (self.root / "ai/imports/s.json").write_text(json.dumps(self.manifest), encoding="utf-8")

    def check(self, fragment):
        self.persist()
        self.assertIn(fragment, "\n".join(verify(self.root)))

    def test_valid(self):
        self.assertEqual(verify(self.root), [])

    def test_invalid_metadata_root(self):
        (self.root / "ai/projects.json").write_text("[]", encoding="utf-8")
        self.assertIn("metadata root", " ".join(verify(self.root)))

    def test_invalid_repositories_do_not_crash(self):
        self.projects["repositories"] = [None, {"id": "s", "observed_head": SHA}]
        self.check("expected unique")

    def test_invalid_workstream_type_does_not_crash(self):
        self.projects["workstreams"] = {"name": "oops"}
        self.check("bad workstream")

    def test_invalid_manifest_entry_does_not_crash(self):
        self.manifest["files"] = [None]
        self.check("invalid file entry")

    def test_malformed_excluded_paths_do_not_crash(self):
        self.manifest["excluded_paths"] = [None]
        self.check("invalid excluded")

    def test_invalid_tree_sha(self):
        self.manifest["source_tree_sha"] = "unknown"
        self.check("invalid source_tree_sha")

    def test_corrupt_file(self):
        (self.src / "ad.txt").write_bytes(b"changed")
        self.assertIn("source blob mismatch", " ".join(verify(self.root)))

    def test_extra_file(self):
        (self.src / "unexpected.txt").write_text("extra")
        self.assertIn("import file set drift", " ".join(verify(self.root)))

    def test_import_excluded_collision(self):
        self.manifest["excluded_paths"] = ["ad.txt"]
        self.check("also excluded")

    def test_windows_case_collision(self):
        (self.src / "AD.txt").write_bytes(b"z")
        self.manifest["files"].append({"path": "AD.txt", "size": 1, "git_blob_sha": blob_sha(b"z")})
        self.check("case-insensitive path collision")

    def test_windows_unsafe_names(self):
        for path in ("CON.txt", "foo:bar", "trailing. ", "../other", "x\\y", "a//b", "NUL", "foo\x00bar"):
            with self.subTest(path=path):
                self.assertFalse(safe_path(path))

    def test_symlink_root_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            (self.src / "ad.txt").unlink()
            self.src.rmdir()
            self.src.symlink_to(Path(outside), target_is_directory=True)
            self.assertIn("unsafe import directory", " ".join(verify(self.root)))

    def test_symlink_file_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / "outside"
            target.write_bytes(self.data)
            (self.src / "ad.txt").unlink()
            (self.src / "ad.txt").symlink_to(target)
            self.assertIn("unsafe source", " ".join(verify(self.root)))

    def test_symlink_parent_rejected(self):
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "ad.txt").write_bytes(self.data)
        (self.src / "ad.txt").unlink()
        (self.src / "folder").symlink_to(outside, target_is_directory=True)
        self.manifest["files"][0]["path"] = "folder/ad.txt"
        self.assertIn("unsafe source", " ".join(verify(self.root)))


if __name__ == "__main__":
    unittest.main()
