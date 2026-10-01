from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from phase3_security.external_source_evidence import validate_external_evidence


class ExternalSourceEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        path = Path(__file__).parents[1] / "phase3_security" / "external-source-evidence.json"
        self.document = json.loads(path.read_text(encoding="utf-8"))

    def test_current_seven_of_seven_evidence_preserves_scan_unknown(self) -> None:
        result = validate_external_evidence(self.document)
        self.assertEqual(result["current_retrievable_verified"], 7)
        self.assertFalse(result["github_scan_ready"])
        self.assertEqual(result["vulnerability_posture"], "UNKNOWN")

    def test_external_evidence_cannot_claim_github_ready(self) -> None:
        document = copy.deepcopy(self.document)
        document["github_scan_ready"] = True
        with self.assertRaisesRegex(ValueError, "cannot establish GitHub scan readiness"):
            validate_external_evidence(document)

    def test_verified_watcher_digest_must_match_expected(self) -> None:
        document = copy.deepcopy(self.document)
        watcher = next(x for x in document["products"] if x["product_id"] == "universal-live-watcher")
        watcher["actual_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            validate_external_evidence(document)

    def test_evidence_count_must_match_individual_records(self) -> None:
        document = copy.deepcopy(self.document)
        document["current_retrievable_verified"] = 6
        with self.assertRaisesRegex(ValueError, "does not match"):
            validate_external_evidence(document)

    def test_malformed_dependency_declaration_is_rejected(self) -> None:
        document = copy.deepcopy(self.document)
        watcher = next(x for x in document["products"] if x["product_id"] == "universal-live-watcher")
        watcher["manifests"][0]["declarations"][0]["raw"] = None
        with self.assertRaisesRegex(ValueError, "invalid dependency declaration"):
            validate_external_evidence(document)


if __name__ == "__main__":
    unittest.main()
