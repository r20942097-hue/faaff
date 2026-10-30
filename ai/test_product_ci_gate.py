"""Positive, negative and contradictory evidence cases for product CI status."""
from __future__ import annotations

import unittest

try:
    from ai.product_ci_gate import evaluate, report
except ModuleNotFoundError:
    from product_ci_gate import evaluate, report


class ProductCIGateTests(unittest.TestCase):
    def test_bootstrap_is_not_runtime_pass(self):
        result = evaluate("success", "false", "skipped")
        self.assertTrue(result.checks_consistent)
        self.assertEqual(result.engineering_ci, "PASS")
        self.assertEqual(result.product_ci, "NOT_RUN")
        self.assertEqual(result.release_gate, "NO_GO")

    def test_runtime_success_does_not_authorize_release(self):
        result = evaluate("success", "true", "success")
        self.assertTrue(result.checks_consistent)
        self.assertEqual(result.product_ci, "CI_PASS")
        self.assertEqual(result.release_gate, "NO_GO")

    def test_runtime_skipped_when_source_present_fails(self):
        result = evaluate("success", "true", "skipped")
        self.assertFalse(result.checks_consistent)

    def test_failed_runtime_fails(self):
        for state in ("failure", "cancelled", "", "skipped"):
            with self.subTest(state=state):
                result = evaluate("success", "true", state)
                self.assertEqual(result.engineering_ci, "FAIL")
                self.assertEqual(result.release_gate, "NO_GO")
                self.assertFalse(result.checks_consistent)

    def test_absent_source_non_skipped_job_fails(self):
        for state in ("success", "failure", "", "cancelled"):
            with self.subTest(state=state):
                self.assertFalse(evaluate("success", "false", state).checks_consistent)

    def test_source_check_failure_blocks_both(self):
        for state in ("failure", "cancelled", "skipped", ""):
            with self.subTest(state=state):
                self.assertFalse(evaluate(state, "false", "skipped").checks_consistent)

    def test_invalid_source_output_fails_closed(self):
        for state in ("", "unknown", "TRUE", "0"):
            with self.subTest(state=state):
                self.assertFalse(evaluate("success", state, "success").checks_consistent)

    def test_summary_labels_are_unambiguous(self):
        result = evaluate("success", "false", "skipped")
        summary = report(result, "success", "false", "skipped")
        self.assertIn("NOT_RUN", summary)
        self.assertIn("NO_GO", summary)
        self.assertNotIn("GO_CANDIDATE", summary)


if __name__ == "__main__":
    unittest.main()
