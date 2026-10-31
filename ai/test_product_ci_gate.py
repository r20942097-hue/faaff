"""Positive, negative and contradictory evidence cases for product CI status."""
from __future__ import annotations

import unittest
from contextlib import redirect_stdout, redirect_stderr
import io
import os
from pathlib import Path
import tempfile
from unittest.mock import patch

try:
    from ai.product_ci_gate import evaluate, report, main
except ModuleNotFoundError:
    from product_ci_gate import evaluate, report, main


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


    def test_cli_records_bootstrap_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            summary = Path(directory) / "summary.md"
            outputs = Path(directory) / "outputs.txt"
            env = {
                "SOURCE_CHECK_RESULT": "success", "SOURCE_PRESENT": "false",
                "RUNTIME_TEST_RESULT": "skipped", "GITHUB_STEP_SUMMARY": str(summary),
                "GITHUB_OUTPUT": str(outputs),
            }
            with patch.dict(os.environ, env, clear=True), redirect_stdout(io.StringIO()):
                code = main()
            self.assertEqual(code, 0)
            self.assertIn("**NOT_RUN**", summary.read_text(encoding="utf-8"))
            self.assertIn("product_ci=NOT_RUN", outputs.read_text(encoding="utf-8"))
            self.assertIn("release_gate=NO_GO", outputs.read_text(encoding="utf-8"))

    def test_cli_rejects_inconsistent_job_result(self):
        env = {
            "SOURCE_CHECK_RESULT": "success", "SOURCE_PRESENT": "true",
            "RUNTIME_TEST_RESULT": "skipped",
        }
        with patch.dict(os.environ, env, clear=True), redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
            self.assertEqual(main(), 1)


if __name__ == "__main__":
    unittest.main()
