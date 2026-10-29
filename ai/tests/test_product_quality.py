"""Failure-mode coverage for evidence claims and the no-auto-GO contract."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from product_quality import GATES, PRODUCTS, main, run, validate


def fixture():
    return {"schema": "gpt1-product-quality/v1", "release_gate": "PUBLICATION_HOLD",
            "products": [{"id": p, "decision": "CANDIDATE_NO_GO",
                          "source_commit": None, "artifact_sha256": None,
                          "gates": {g: {"status": "NOT_RUN", "evidence": None} for g in GATES}}
                         for p in PRODUCTS]}


class QualityTests(unittest.TestCase):
    def setUp(self):
        self.data = fixture()

    def claim(self, gate, state="PASS", evidence="ai/verification/synthetic.log"):
        self.data["products"][0]["gates"][gate] = {"status": state, "evidence": evidence}

    def invalid(self):
        self.assertEqual(validate(self.data)["status"], "INVALID")

    def test_baseline_passes_without_go(self):
        v = validate(self.data)
        self.assertEqual(v["status"], "PASS")
        self.assertEqual(v["decision"], "CANDIDATE_NO_GO")
        self.assertEqual(v["counts"]["NOT_RUN"], 18)

    def test_root_type(self):
        self.assertEqual(validate([])["status"], "INVALID")

    def test_wrong_schema(self):
        self.data["schema"] = "v2"
        self.invalid()

    def test_removed_publication_hold(self):
        self.data["release_gate"] = "active_publication"
        self.invalid()

    def test_missing_product(self):
        self.data["products"].pop()
        self.invalid()

    def test_duplicate_product(self):
        self.data["products"][1]["id"] = "rplay"
        self.invalid()

    def test_unknown_product(self):
        self.data["products"][0]["id"] = "unknown"
        self.invalid()

    def test_product_not_dict(self):
        self.data["products"][0] = ["bad"]
        self.invalid()

    def test_go_override_rejected(self):
        self.data["products"][0]["decision"] = "GO"
        self.invalid()

    def test_missing_gate(self):
        self.data["products"][0]["gates"].pop("real_site_e2e")
        self.invalid()

    def test_unknown_gate(self):
        self.data["products"][0]["gates"]["unapproved"] = {"status": "PASS", "evidence": None}
        self.invalid()

    def test_missing_status(self):
        self.data["products"][0]["gates"]["unit_tests"] = {"evidence": None}
        self.invalid()

    def test_invalid_status(self):
        self.claim("unit_tests", "COMPLETED")
        self.invalid()

    def test_pass_without_evidence(self):
        self.claim("unit_tests", "PASS", None)
        self.invalid()

    def test_fail_with_success_evidence(self):
        self.claim("unit_tests", "FAIL")
        self.invalid()

    def test_browser_pass_claim_does_not_make_release_go(self):
        self.claim("real_site_e2e")
        a = validate(self.data)
        self.assertEqual(a["status"], "PASS")
        self.assertEqual(a["decision"], "CANDIDATE_NO_GO")

    def test_url_with_query_or_credentials_rejected(self):
        self.claim("unit_tests", evidence="https://github.com/a/b/actions/runs/1?token=secret")
        self.invalid()

    def test_url_run_reference_allowed_but_not_attested(self):
        self.claim("unit_tests", evidence="https://github.com/a/b/actions/runs/12345")
        self.assertEqual(validate(self.data)["decision"], "CANDIDATE_NO_GO")

    def test_relative_path_traversal_rejected(self):
        self.claim("unit_tests", evidence="ai/../../secrets.txt")
        self.invalid()

    def test_source_integrity_needs_commit(self):
        self.claim("source_integrity")
        self.invalid()

    def test_archive_integrity_needs_digest(self):
        self.claim("archive_integrity")
        self.invalid()

    def test_source_integrity_hash_recorded(self):
        self.data["products"][0]["source_commit"] = "a" * 40
        self.claim("source_integrity")
        self.assertEqual(validate(self.data)["status"], "PASS")

    def test_bad_sha256(self):
        self.data["products"][0]["artifact_sha256"] = "NOT-A-SHA"
        self.invalid()

    def test_sha256_with_archive_claim(self):
        self.data["products"][0]["artifact_sha256"] = "b" * 64
        self.claim("archive_integrity")
        self.assertEqual(validate(self.data)["status"], "PASS")

    def test_local_file_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "qa.json"
            p.write_text(json.dumps(self.data), encoding="utf-8")
            self.assertEqual(run(p)["status"], "PASS")
            with patch("builtins.print"):
                self.assertEqual(main(["--registry", str(p), "--json"]), 0)

    def test_corrupt_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "qa.json"
            p.write_text("{broken", encoding="utf-8")
            self.assertEqual(run(p)["status"], "INVALID")
            with patch("builtins.print"):
                self.assertEqual(main(["--registry", str(p)]), 1)

    def test_unavailable_registry(self):
        self.assertEqual(run(Path("/__nonexistent__/qa.json"))["status"], "INVALID")


if __name__ == "__main__":
    unittest.main()
