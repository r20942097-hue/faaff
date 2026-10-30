"""Regression tests: pinned data integrity, semantics, conservative outcomes."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core import (
    assess, build_report, extract_active, git_blob_sha, parse_list,
    parse_rule, pinned_lists, valid_host, verify_report,
)
from cli import summary


ROOT = Path(__file__).resolve().parents[2]


class RuleParserTests(unittest.TestCase):
    def test_domain_and_options_normalized(self):
        row = parse_rule("||Example.COM^$script,third-party")
        self.assertTrue(row.supported)
        self.assertEqual(row.canonical, "||example.com^$script,third-party")
        self.assertEqual(parse_rule("||example.com^$third-party,script").canonical,
                         row.canonical)

    def test_no_option_is_not_same_as_third_party(self):
        result = assess(
            [parse_rule("||example.com^")],
            [parse_rule("||example.com^$third-party")])
        self.assertEqual(
            result["findings"][0]["status"],
            "NO_EXACT_STABLE_OVERLAP_NOT_VERIFIED")

    def test_exact_overlap_and_no_exact_overlap_not_claimed_effectiveness(self):
        data = assess([parse_rule("||example.com^$third-party")], [
            parse_rule("||EXAMPLE.COM^$third-party"),
            parse_rule("||example.net^$third-party")])
        self.assertEqual(data["counts"]["EXACT_OVERLAP_WITH_PINNED_STABLE"], 1)
        self.assertEqual(data["counts"]["NO_EXACT_STABLE_OVERLAP_NOT_VERIFIED"], 1)
        self.assertTrue(all(
            x["real_world_incremental_blocking"] == "NOT_ESTABLISHED"
            and x["safe_to_publish"] is False for x in data["findings"]))

    def test_invalid_domains_fail_closed(self):
        for domain in ("localhost", "example..org", "-bad.example",
                       "bad-.example", "a" * 64 + ".example", "127.0.0.1"):
            with self.subTest(domain=domain):
                self.assertFalse(valid_host(domain))
                self.assertFalse(parse_rule("||" + domain + "^").supported)

    def test_complex_syntax_and_url_rewrites_not_misidentified(self):
        for line in ("*$removeparam=utm_source",
                     "@@||example.org^$third-party",
                     "example.org##.advert", "||site.org/path$script",
                     "||example.org^$domain=example.com",
                     "||example.org^$third-party,third-party"):
            with self.subTest(line=line):
                self.assertFalse(parse_rule(line).supported)

    def test_trailing_and_empty_options_are_not_accepted(self):
        for line in ("||site.org^$third-party,",
                     "||site.org^$,third-party",
                     "||site.org^$third-party,,script"):
            with self.subTest(line=line):
                self.assertFalse(parse_rule(line).supported)

    def test_unknown_bracket_metadata_is_not_silently_dropped(self):
        parsed = parse_list("[Untrusted Metadata]" + chr(10)
                            + "||site.org^$third-party" + chr(10), "suspicious")
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0].reason, "UNSUPPORTED_OR_COMPLEX_SYNTAX")

    def test_contradictory_first_third_scope_is_rejected(self):
        self.assertEqual(
            parse_rule("||site.org^$first-party,third-party").reason,
            "CONTRADICTORY_PARTY_SCOPE")

    def test_metadata_comments_are_excluded_without_dropping_unknown_rules(self):
        raw = "! title\n[Adblock Plus 2.0]\n\n||test.example^$third-party\n###ad\n"
        self.assertEqual(extract_active(raw),
                         ["||test.example^$third-party", "###ad"])
        self.assertEqual(len(parse_list(raw, "fixture")), 2)

    def test_same_semantic_rule_with_reordered_modifiers_rejected_as_duplicate(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            parse_list("||example.org^$script,third-party\n"
                       "||EXAMPLE.ORG^$third-party,script\n", "source")

    def test_duplicate_unknown_rule_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            parse_list("##.advert\n##.advert\n", "unsupported")


class PinnedSourceTests(unittest.TestCase):
    def test_blob_hash_matches_git_blob_semantics(self):
        self.assertEqual(
            git_blob_sha(b"hello\n"),
            "ce013625030ba8dba906f756967f9e9ca394464a")

    def test_import_snapshot_is_real_and_pinned(self):
        commit, files, entries = pinned_lists(ROOT)
        self.assertEqual(len(commit), 40)
        self.assertIn("tracking.txt", files)
        self.assertIn("v2/tracking.txt", files)
        self.assertEqual(entries["tracking.txt"]["bytes"],
                         len(files["tracking.txt"].encode()))
        self.assertEqual(entries["v2/tracking.txt"]["git_blob_sha"],
                         git_blob_sha(files["v2/tracking.txt"].encode()))

    def test_missing_or_modified_pinned_source_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "ai/imports").mkdir(parents=True)
            paths = root / "integrations/browser-filters/source/s/v2"
            paths.mkdir(parents=True)
            src = json.loads((ROOT / "ai/imports/s.json").read_text())
            (root / "ai/imports/s.json").write_text(json.dumps(src))
            (paths.parent / "tracking.txt").write_bytes(b"||evil.example^\n")
            (paths / "tracking.txt").write_bytes(b"||good.example^\n")
            with self.assertRaisesRegex(ValueError, "blob mismatch"):
                pinned_lists(root)


class ReleaseGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = build_report(ROOT)

    def test_current_pinned_baseline_9_38_and_9_exact_overlaps(self):
        report = self.report
        self.assertTrue(verify_report(report))
        self.assertEqual(report["stable_rules"], 9)
        self.assertEqual(report["candidate_rules"], 38)
        counts = report["coverage"]["counts"]
        self.assertEqual(counts.get("EXACT_OVERLAP_WITH_PINNED_STABLE"), 9)
        self.assertEqual(counts.get("NO_EXACT_STABLE_OVERLAP_NOT_VERIFIED"), 29)
        self.assertEqual(report["release"], "NO_GO")
        self.assertEqual(report["rules_published"], 0)

    def test_serialization_is_deterministic(self):
        self.assertEqual(json.dumps(self.report, sort_keys=True),
                         json.dumps(build_report(ROOT), sort_keys=True))

    def test_summary_never_claims_real_site_or_stock_coverage(self):
        doc = summary(self.report)
        self.assertIn("NOT_RUN", doc)
        self.assertIn("NO_GO", doc)
        self.assertIn("pinned stable", doc.lower())

    def test_fake_release_or_fake_efficacy_rejected(self):
        for field, value in (
                ("release", "GO"), ("rules_published", 1),
                ("browser_stock_coverage", "PASS"),
                ("real_engine_efficacy", "PASS"),
                ("live_site_compatibility", "PASS")):
            with self.subTest(field=field):
                altered = copy.deepcopy(self.report)
                altered[field] = value
                with self.assertRaisesRegex(ValueError, "gate invalid"):
                    verify_report(altered)

    def test_candidates_dropped_or_forged_safe_fail(self):
        bad = copy.deepcopy(self.report)
        bad["coverage"]["findings"].pop()
        with self.assertRaisesRegex(ValueError, "incomplete"):
            verify_report(bad)
        bad = copy.deepcopy(self.report)
        bad["coverage"]["findings"][0]["safe_to_publish"] = True
        with self.assertRaisesRegex(ValueError, "incomplete"):
            verify_report(bad)

    def test_revision_or_exact_overlap_count_requires_review(self):
        bad = copy.deepcopy(self.report)
        bad["candidate_rules"] = 37
        with self.assertRaisesRegex(ValueError, "baseline changed"):
            verify_report(bad)


if __name__ == "__main__":
    unittest.main()
