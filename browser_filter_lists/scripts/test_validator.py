import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import validate_filters as vf


class ValidatorTests(unittest.TestCase):
    def test_non_string_candidate_enums_report_validation_errors(self):
        real_load = vf.load_json
        manifest = real_load(vf.MANIFEST_PATH)
        queue_path = vf.ROOT / manifest['candidate_queue']
        original = real_load(queue_path)
        for field in ['category', 'state', 'risk']:
            for value in [{}, [], [{}], {'nested': []}, None, True]:
                with self.subTest(field=field, value=value):
                    queue = json.loads(json.dumps(original))
                    queue['candidates'][0][field] = value
                    def load_fixture(path):
                        return queue if path == queue_path else real_load(path)
                    with patch.object(vf, 'load_json', side_effect=load_fixture):
                        errors, _warnings = vf.validate()
                    self.assertTrue(any(field in error for error in errors), errors)

    def test_repository_state_is_valid(self):
        errors, _warnings = vf.validate()
        self.assertEqual(errors, [])

    def test_valid_hostname(self):
        for host in ["example.com", "sub.example.co.jp", "xn--bcher-kva.example"]:
            with self.subTest(host=host):
                self.assertTrue(vf.valid_hostname(host))

    def test_invalid_hostname(self):
        for host in [
            "localhost",
            "127.0.0.1",
            "example",
            ".example.com",
            "example.com.",
            "example..com",
            "-example.com",
            "example-.com",
            "exa_mple.com",
        ]:
            with self.subTest(host=host):
                self.assertFalse(vf.valid_hostname(host))

    def test_safe_repo_path_rejects_parent_escape(self):
        self.assertIsNone(vf.safe_repo_path("../outside.txt"))

    def test_safe_repo_path_rejects_in_tree_symlinks(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "target.txt").write_text("data")
            (root / "alias.txt").symlink_to("target.txt")
            (root / "real").mkdir()
            (root / "real" / "child.txt").write_text("data")
            (root / "alias-dir").symlink_to("real", target_is_directory=True)
            with patch.object(vf, "ROOT", root):
                self.assertIsNone(vf.safe_repo_path("alias.txt"))
                self.assertIsNone(vf.safe_repo_path("alias-dir/child.txt"))
                self.assertEqual(vf.safe_repo_path("target.txt"), root / "target.txt")

    def test_non_object_manifest_reports_error(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text("[]")
            with patch.object(vf, "MANIFEST_PATH", path):
                errors, _ = vf.validate()
            self.assertIn("root must be an object", errors[0])

    def test_non_string_list_path_reports_error(self):
        manifest = vf.load_json(vf.MANIFEST_PATH)
        manifest["stable_lists"][0]["path"] = {"invalid": "path"}
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text(json.dumps(manifest))
            with patch.object(vf, "MANIFEST_PATH", path):
                errors, _ = vf.validate()
            self.assertTrue(any("unsafe or invalid stable list path" in e for e in errors))

    def test_conservative_rule_shape(self):
        self.assertIsNotNone(vf.hostname_rule.fullmatch("||example.com^$third-party"))
        self.assertIsNone(vf.hostname_rule.fullmatch("||example.com^"))
        self.assertIsNone(vf.hostname_rule.fullmatch("example.com"))
        self.assertIsNone(vf.hostname_rule.fullmatch("||example.com^$document"))


if __name__ == "__main__":
    unittest.main()
