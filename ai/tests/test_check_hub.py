"""Isolated regression tests for the AI hub's state/import consistency guard."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ai.check_hub import blob_sha, verify


class HubStateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "ai/imports").mkdir(parents=True)
        imported = self.root / "integrations/browser-filters/source/s"
        imported.mkdir(parents=True)
        data = b"safe-fixture\n"
        (imported / "fixture.txt").write_bytes(data)

        self.projects = {
            "schema": "ai-hub-registry/v1",
            "hub": "r20942097-hue/faaff",
            "repositories": [
                {"id": "faaff", "observed_head": "a" * 40},
                {"id": "s", "observed_head": "b" * 40},
            ],
            "workstreams": [],
        }
        self.source = {
            "schema": "pinned-source-import/v1",
            "source_repository": "r20942097-hue/s",
            "source_commit": "b" * 40,
            "target_prefix": "integrations/browser-filters/source/s/",
            "files": [
                {"path": "fixture.txt", "git_blob_sha": blob_sha(data), "size": len(data)}
            ],
        }
        self.state = {
            "schema": "project-state/v1",
            "repository": "r20942097-hue/faaff",
            "pinned_import": {
                "manifest": "ai/imports/s.json",
                "source_commit": "b" * 40,
            },
        }
        self.write_metadata()

    def write_metadata(self) -> None:
        for path, value in (
            ("ai/projects.json", self.projects),
            ("ai/imports/s.json", self.source),
            ("ai/PROJECT_STATE.json", self.state),
        ):
            target = self.root / path
            target.write_text(json.dumps(value), encoding="utf-8")

    def test_consistent_pinned_state_passes(self) -> None:
        self.assertEqual(verify(self.root), [])

    def test_unsafe_windows_and_control_character_manifest_paths(self) -> None:
        for unsafe in ("fixture.txt:altstream", "fixture\n.txt"):
            with self.subTest(path=unsafe):
                self.source["files"][0]["path"] = unsafe
                self.write_metadata()
                errors = verify(self.root)
                self.assertTrue(any("invalid or duplicate file entry" in e for e in errors), errors)

    def test_pinned_commit_drift_fails(self) -> None:
        self.state["pinned_import"]["source_commit"] = "c" * 40
        self.write_metadata()
        self.assertIn("project state / pinned import mismatch", verify(self.root))

    def test_missing_project_state_fails(self) -> None:
        (self.root / "ai/PROJECT_STATE.json").unlink()
        self.assertTrue(any(e.startswith("unreadable project state:") for e in verify(self.root)))

    def test_broken_schema_fails(self) -> None:
        self.state["schema"] = "unexpected"
        self.write_metadata()
        self.assertIn("bad project state schema/repository", verify(self.root))

    def test_reject_nonobject_registry(self) -> None:
        (self.root / "ai/projects.json").write_text("[]", encoding="utf-8")
        self.assertIn("invalid metadata structure: expected JSON objects", verify(self.root))

    def test_reject_nonobject_import_manifest(self) -> None:
        (self.root / "ai/imports/s.json").write_text("[]", encoding="utf-8")
        self.assertIn("invalid metadata structure: expected JSON objects", verify(self.root))

    def test_extra_symlink_is_rejected(self) -> None:
        imported = self.root / "integrations/browser-filters/source/s"
        try:
            (imported / "hidden.txt").symlink_to(imported / "fixture.txt")
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation unavailable on this runner")
        self.assertIn("linked extra source: hidden.txt", verify(self.root))

    def test_linked_parent_cannot_escape_manifest(self) -> None:
        imported = self.root / "integrations/browser-filters/source/s"
        try:
            (imported / "alias").symlink_to(imported, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("directory symlinks unavailable on this runner")
        self.source["files"].append(self.source["files"][0] | {"path": "alias/fixture.txt"})
        self.write_metadata()
        self.assertIn("missing or linked source: alias/fixture.txt", verify(self.root))



if __name__ == "__main__":
    unittest.main()
