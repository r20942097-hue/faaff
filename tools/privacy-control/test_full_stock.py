"""Regression coverage for an exactly pinned EasyPrivacy template source expansion."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_full_stock import LOCK_FILE, SOURCE_COUNT, TOTAL_BYTES, validate_lock
from verify_stock_report import audit, summary
from render_stock_html import render_stock


class OfficialTemplateSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lock = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
        cls.source = json.loads((Path(__file__).resolve().parents[2]
                                 / "ai/imports/s.json").read_text(encoding="utf-8"))

    def test_template_is_pinned_to_git_blob(self):
        self.assertTrue(validate_lock(self.lock))
        self.assertEqual(len(self.lock["files"]), SOURCE_COUNT)
        self.assertEqual(sum(x["size"] for x in self.lock["files"]), TOTAL_BYTES)
        self.assertEqual(self.lock["template"]["path"], "easyprivacy.template")
        self.assertEqual(self.lock["files"][0]["path"], "template_header.txt")

    def test_template_source_paths_no_duplicates(self):
        paths = [row["path"] for row in self.lock["files"]]
        self.assertEqual(len(paths), len(set(paths)))
        self.assertEqual(paths[-1],
                         "easyprivacy/easyprivacy_allowlist_international.txt")

    def test_invalid_commit_and_template_ref_rejected(self):
        for attr, bad_value in (("upstream_commit", "master"), ("upstream_commit", ""),
                                ("source_repository", "evil/other")):
            edited = copy.deepcopy(self.lock)
            edited[attr] = bad_value
            with self.subTest(attr=attr), self.assertRaises(ValueError):
                validate_lock(edited)
        edited = copy.deepcopy(self.lock)
        edited["template"]["git_blob_sha"] = "oops"
        with self.assertRaises(ValueError):
            validate_lock(edited)

    def test_added_or_removed_component_fails_closed(self):
        for kind in ("add", "remove", "reverse"):
            edited = copy.deepcopy(self.lock)
            if kind == "add":
                edited["files"].append(copy.deepcopy(edited["files"][0]))
            elif kind == "remove":
                edited["files"].pop()
            else:
                edited["files"].reverse()
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                validate_lock(edited)

    def test_manifest_path_escape_and_hash_tampering(self):
        edited = copy.deepcopy(self.lock)
        edited["files"][2]["path"] = "../../private"
        with self.assertRaises(ValueError):
            validate_lock(edited)
        edited = copy.deepcopy(self.lock)
        edited["files"][2]["git_blob_sha"] = "invalid"
        with self.assertRaises(ValueError):
            validate_lock(edited)

    def build_fixture(self):
        # Reuse the existing verified synthetic fixture without copying it
        # into the published source or representing it as actual browser traffic.
        from test_stock_report import StockVerdictTests
        StockVerdictTests.setUpClass()
        template_fixture = StockVerdictTests("test_complete_synthetic_only_report")
        template_fixture.setUp()
        record = copy.deepcopy(template_fixture.document)
        record["schema"] = "upc-full-template-source-comparison/v1"
        record["source"]["commit"] = self.lock["upstream_commit"]
        record["source"]["scope"] = self.lock["scope"]
        record["source"]["files"] = [
            {"path":e["path"], "git_blob_sha":e["git_blob_sha"],
             "bytes":e["size"], "sha256":"a" * 64}
            for e in self.lock["files"]]
        record["source"]["template"] = {
            "path":"easyprivacy.template",
            "git_blob_sha":self.lock["template"]["git_blob_sha"],
            "bytes":self.lock["template"]["size"], "verified":True,
        }
        record["counts"]["source_components"] = SOURCE_COUNT
        record["selected_upstream_fragments_not_full_list"] = False
        record["template_source_components_complete"] = True
        record["template_includes_verified"] = True
        record["published_easyprivacy_distribution_equivalence"] = "NOT_VERIFIED"
        return record

    def test_complete_template_fixture_audit_passes_without_live_claim(self):
        fixture = self.build_fixture()
        self.assertEqual(audit(fixture, self.lock, self.source, full_template=True), [])
        self.assertIn("published distribution", summary(fixture))
        self.assertIn("全39ソース", render_stock(fixture))
        self.assertIn("NO_GO", render_stock(fixture))

    def test_incomplete_template_or_false_publication_rejected(self):
        for field, wrong in [
            ("template_includes_verified", False),
            ("template_source_components_complete", False),
            ("published_easyprivacy_distribution_equivalence", "PASS"),
            ("actual_browser_enabled_lists", "VERIFIED"),
        ]:
            item = self.build_fixture()
            item[field] = wrong
            with self.subTest(field=field):
                self.assertTrue(audit(item, self.lock, self.source, full_template=True))
        item = self.build_fixture()
        item["source"]["template"]["git_blob_sha"] = "0" * 40
        self.assertTrue(audit(item, self.lock, self.source, full_template=True))


if __name__ == "__main__":
    unittest.main()
