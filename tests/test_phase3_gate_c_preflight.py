from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from phase3_security.gate_c_preflight import evaluate_gate_c, validate_gate_c_evidence


ROOT = Path(__file__).parents[1]


class GateCPreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = json.loads((ROOT / "phase3_security" / "product-source-inputs.json").read_text(encoding="utf-8"))
        self.evidence = json.loads((ROOT / "phase3_security" / "gate-c-evidence.json").read_text(encoding="utf-8"))

    def test_missing_scanner_sources_keep_gate_c_not_run(self) -> None:
        report = evaluate_gate_c(self.registry, self.evidence, ROOT)
        self.assertEqual(report["gate_c_status"], "NOT_RUN")
        self.assertEqual(report["verified_product_count"], 0)
        self.assertEqual(report["vulnerability_posture"], "UNKNOWN")
        self.assertTrue(any("0/7 VERIFIED" in item for item in report["blockers"]))

    def test_gate_c_preflight_rejects_pass_claim(self) -> None:
        evidence = copy.deepcopy(self.evidence)
        evidence["gate_c_status"] = "PASS"
        with self.assertRaisesRegex(ValueError, "PASS is not a valid preflight status"):
            validate_gate_c_evidence(evidence, {x["product_id"] for x in self.registry["baseline"]})

    def test_complete_evidence_requires_all_seven_scanner_results(self) -> None:
        evidence = copy.deepcopy(self.evidence)
        evidence["gate_c_status"] = "READY_FOR_REVIEW"
        with self.assertRaisesRegex(ValueError, "verified dependency resolution"):
            validate_gate_c_evidence(evidence, {x["product_id"] for x in self.registry["baseline"]})

    def test_gate_c_requires_exact_candidate_baseline(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["baseline"].pop()
        with self.assertRaisesRegex(ValueError, "exact seven-product"):
            evaluate_gate_c(registry, self.evidence, ROOT)

    def test_registry_hashes_do_not_replace_missing_source_bytes(self) -> None:
        registry = copy.deepcopy(self.registry)
        for item in registry["baseline"]:
            item.update({"source_status": "VERIFIED", "immutable_source": f"missing/{item['product_id']}.zip", "sha256": "a" * 64, "size": 1})
        report = evaluate_gate_c(registry, self.evidence, ROOT)
        self.assertEqual(report["gate_c_status"], "NOT_RUN")
        self.assertTrue(any("source file is missing" in item for item in report["blockers"]))


if __name__ == "__main__":
    unittest.main()
