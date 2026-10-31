"""Reject fabricated, incomplete or overstated stock-subset evidence."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_stock_report import audit, summary, CASES
from render_stock_html import render_stock


ROOT = Path(__file__).resolve().parents[2]


class StockVerdictTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lock = json.loads((ROOT / "tools/privacy-control/verification/stock-source-lock.json").read_text())
        cls.source = json.loads((ROOT / "ai/imports/s.json").read_text())

    def setUp(self):
        source_entry = next(x for x in self.source["files"]
                            if x["path"] == "v2/tracking.txt")
        observed = [dict(row, sha256="a" * 64, bytes=row["size"])
                    for row in self.lock["files"]]
        rows = []
        groups = []
        for n in range(38):
            host = "synthetic" + str(n) + ".example"
            for scenario in CASES:
                rows.append({
                    "host":host, "scenario":scenario,
                    "stock_fragment_matches":{"ubo":False,"ghostery":False},
                    "candidate_plus_stock_matches":{"ubo":False,"ghostery":False},
                    "actual_browser_stock_profile":"NOT_VERIFIED",
                    "real_site_incremental_efficacy":"NOT_ESTABLISHED"})
            groups.append({
                "host":host,
                "selected_fragment_coverage":{"ubo":[],"ghostery":[]},
                "additional_synthetic_cases":{"ubo":[],"ghostery":[]},
                "active_browser_stock_coverage":"NOT_VERIFIED",
                "incremental_real_world_privacy":"NOT_ESTABLISHED",
                "proposed_auto_adoption":False})
        self.document = {
            "schema":"upc-stock-fragment-comparison/v1", "result":"PASS",
            "synthetic_only":True,
            "selected_upstream_fragments_not_full_list":True,
            "actual_browser_enabled_lists":"NOT_VERIFIED",
            "production_browser_site_e2e":"NOT_RUN",
            "adopted_rules":0,"publication":"NO_GO",
            "source":{"repository":"easylist/easylist",
                      "commit":self.lock["upstream_commit"],
                      "scope":self.lock["scope"],"files":observed},
            "candidate_source":{"repository":"r20942097-hue/s",
                                "commit":self.source["source_commit"],
                                "path":"v2/tracking.txt",
                                "git_blob_sha":source_entry["git_blob_sha"]},
            "counts":{"source_components":5,"candidates":38,
                      "cases":266,"engine_observations":1064,
                      "selected_source_baseline_blocked":{"ubo":0,"ghostery":0},
                      "additional_synthetic_blocks":{"ubo":0,"ghostery":0},
                      "baseline_regressions":{"ubo":0,"ghostery":0},
                      "engine_disagreements":{"baseline":0,"combined":0}},
            "findings":rows,"per_host":groups,
        }

    def check(self):
        return audit(self.document, self.lock, self.source)

    def test_complete_synthetic_only_report(self):
        self.assertEqual(self.check(), [])
        self.assertIn("NO_GO", summary(self.document))
        self.assertIn("NOT full EasyPrivacy", summary(self.document))

    def test_summary_surfaces_incremental_candidate_hosts_without_safety_claim(self):
        host = self.document["per_host"][0]["host"]
        self.document["per_host"][0]["additional_synthetic_cases"]["ubo"] = ["third-party-script"]
        rendered = summary(self.document)
        self.assertIn(host, rendered)
        self.assertIn("fixture cases", rendered)
        self.assertIn("NO_GO", rendered)

    def test_static_html_report_has_all_hosts_and_no_script(self):
        page = render_stock(self.document)
        self.assertIn('lang="ja"', page)
        self.assertIn("script-src 'none'", page)
        self.assertNotIn("<script", page)
        self.assertEqual(page.count("<tr>"), 39)
        self.assertIn("NO_GO", page)

    def test_static_html_escapes_all_hostnames(self):
        self.document["per_host"][0]["host"] = "<script>alert(1)</script>"
        page = render_stock(self.document)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", page)
        self.assertNotIn("<script>alert", page)

    def test_fake_publication_and_user_stock_claim_rejected(self):
        for key, wrong in (("publication","GO"),
                           ("actual_browser_enabled_lists","VERIFIED"),
                           ("production_browser_site_e2e","PASS"),
                           ("adopted_rules",1)):
            with self.subTest(key=key):
                original = self.document[key]
                self.document[key] = wrong
                self.assertTrue(self.check())
                self.document[key] = original

    def test_removed_or_duplicate_case_rejected(self):
        self.document["findings"].pop()
        self.assertTrue(self.check())

    def test_changed_negative_control_rejected(self):
        item = next(x for x in self.document["findings"]
                    if x["scenario"] == "first-party-script")
        item["candidate_plus_stock_matches"]["ubo"] = True
        self.assertTrue(self.check())

    def test_fake_aggregation_and_per_host_rejected(self):
        self.document["counts"]["additional_synthetic_blocks"]["ubo"] = 1
        self.assertTrue(self.check())
        self.document["counts"]["additional_synthetic_blocks"]["ubo"] = 0
        self.document["per_host"][0]["proposed_auto_adoption"] = True
        self.assertTrue(self.check())

    def test_changed_source_provenance_rejected(self):
        self.document["source"]["files"][0]["git_blob_sha"] = "0" * 40
        self.assertTrue(self.check())

if __name__ == "__main__":
    unittest.main()
