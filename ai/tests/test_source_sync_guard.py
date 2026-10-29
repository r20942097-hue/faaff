"""Fixtures for the metadata-only, offline provenance observer."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from source_sync_guard import check, main, valid_sha

PIN = "a" * 40
NEXT = "b" * 40


class SyncGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = {"schema": "pinned-source-import/v1", "source_repository": "r20942097-hue/s",
                         "source_commit": PIN, "source_tree_sha": "c" * 40,
                         "target_prefix": "integrations/browser-filters/source/s/"}
        self.registry = {"schema": "ai-hub-registry/v1", "repositories": [
            {"id": "faaff", "observed_head": "d" * 40},
            {"id": "s", "observed_head": PIN, "url": "https://github.com/r20942097-hue/s"}]}
        self.state = {"schema": "project-state/v1", "repository": "r20942097-hue/faaff",
                      "pinned_import": {"source_commit": PIN}, "heads": {"s_main_pinned_import": PIN}}
        self.write()

    def write(self):
        for name, value in (("ai/imports/s.json", self.manifest), ("ai/projects.json", self.registry),
                            ("ai/PROJECT_STATE.json", self.state)):
            p = self.root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(value), encoding="utf-8")

    def test_matching_head(self):
        self.assertEqual(check(self.root, PIN)["status"], "IN_SYNC")

    def test_upstream_ahead(self):
        self.assertEqual(check(self.root, NEXT)["status"], "UPSTREAM_DRIFT")

    def test_invalid_head(self):
        self.assertEqual(check(self.root, "bad")["status"], "INVALID")

    def test_uppercase_sha_not_accepted(self):
        self.assertFalse(valid_sha("A" * 40))

    def test_wrong_source_authority(self):
        self.manifest["source_repository"] = "other/s"
        self.write()
        self.assertEqual(check(self.root, PIN)["status"], "INVALID")

    def test_wrong_import_prefix(self):
        self.manifest["target_prefix"] = "../outside/"
        self.write()
        self.assertEqual(check(self.root, PIN)["status"], "INVALID")

    def test_registry_drift(self):
        self.registry["repositories"][1]["observed_head"] = NEXT
        self.write()
        self.assertEqual(check(self.root, PIN)["status"], "INVALID")

    def test_duplicate_registry_entry(self):
        self.registry["repositories"].append(self.registry["repositories"][1].copy())
        self.write()
        self.assertEqual(check(self.root, PIN)["status"], "INVALID")

    def test_missing_state_reference(self):
        self.state["pinned_import"] = {}
        self.write()
        self.assertEqual(check(self.root, PIN)["status"], "INVALID")

    def test_missing_file(self):
        (self.root / "ai/imports/s.json").unlink()
        self.assertEqual(check(self.root, PIN)["status"], "INVALID")

    def test_malformed_json(self):
        (self.root / "ai/imports/s.json").write_text("[bad", encoding="utf-8")
        self.assertEqual(check(self.root, PIN)["status"], "INVALID")

    def test_json_array_not_accepted(self):
        (self.root / "ai/projects.json").write_text("[]", encoding="utf-8")
        self.assertEqual(check(self.root, PIN)["status"], "INVALID")

    def test_cli_in_sync(self):
        with patch("builtins.print"):
            self.assertEqual(main(["--root", str(self.root), "--upstream-head", PIN]), 0)

    def test_cli_drift(self):
        with patch("builtins.print"):
            self.assertEqual(main(["--root", str(self.root), "--upstream-head", NEXT]), 2)

    def test_cli_invalid(self):
        with patch("builtins.print"):
            self.assertEqual(main(["--root", str(self.root), "--upstream-head", "invalid"]), 1)


if __name__ == "__main__":
    unittest.main()
