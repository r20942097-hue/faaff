"""Evidence/approval decision contract: deterministic examples, not LLM E2E."""
import unittest

from ai.decision_contract import assess_change, classify_path, classify_paths

HEAD = "a" * 40
REQUIRED = ["Source synchronization check", "pinned-import (3.11)", "analyze-python"]
GOOD = {check: "success" for check in REQUIRED}


def assess(paths, **overrides):
    data = dict(
        paths=paths,
        head_sha=HEAD,
        checked_sha=HEAD,
        checks=GOOD,
        required_checks=REQUIRED,
        owner_approved=False,
        product_verified=False,
    )
    data.update(overrides)
    return assess_change(**data)


class ClassifierTests(unittest.TestCase):
    def test_documentation_only(self):
        self.assertEqual(classify_paths(["README.md", "ai/HANDOFF.md"]), "documentation")

    def test_metadata_is_not_plain_documentation(self):
        self.assertEqual(classify_path("ai/PROJECT_STATE.json"), "metadata")
        self.assertEqual(classify_path("AGENTS.md"), "metadata")

    def test_workflow_changes_are_infrastructure(self):
        self.assertEqual(classify_paths([".github/workflows/ci.yml", "ai/check_hub.py"]), "infrastructure")

    def test_product_code_requires_product_evidence(self):
        self.assertEqual(classify_path("extension/content.js"), "implementation")
        self.assertEqual(classify_path("integrations/browser-filters/source/s/ad.txt"), "implementation")

    def test_published_filters_are_high_risk(self):
        self.assertEqual(classify_path("browser_filter_lists/filters/universal-web-ad.txt"), "publication")

    def test_mixed_scope_uses_maximum_risk(self):
        self.assertEqual(classify_paths(["README.md", "browser_filter_lists/foo.txt"]), "publication")

    def test_invalid_paths_and_archives_never_downgrade(self):
        for path in ("", "../outside", "/root/secrets", r"foo\\\\bar", "releases/data.zip", "secret.pem", ".env", "config/.env.local", ".ssh/id_rsa", "private/secrets/key", "api.token", "bad\u000achar"):
            with self.subTest(path=path):
                self.assertEqual(classify_path(path), "prohibited")

    def test_empty_change_set_is_not_low_risk(self):
        self.assertEqual(classify_paths([]), "prohibited")


class ApprovalTests(unittest.TestCase):
    def test_documentation_still_needs_owner_approval(self):
        a = assess(["ai/HANDOFF.md"])
        self.assertEqual(a.status, "AWAITING_OWNER_APPROVAL")
        self.assertIn("approval_required_by_repo_policy", a.reasons)

    def test_explicit_approval_is_only_review_eligibility(self):
        a = assess(["ai/HANDOFF.md"], owner_approved=True)
        self.assertEqual(a.status, "ELIGIBLE_FOR_REVIEW")
        self.assertIn("github_ruleset_and_release_gates_still_apply", a.reasons)

    def test_stale_ci_is_not_reused(self):
        a = assess(["ai/HANDOFF.md"], checked_sha="b" * 40, owner_approved=True)
        self.assertEqual(a.status, "BLOCKED")
        self.assertIn("stale_or_invalid_check_sha", a.reasons)

    def test_short_sha_is_invalid(self):
        a = assess(["ai/HANDOFF.md"], head_sha="abc", checked_sha="abc")
        self.assertIn("stale_or_invalid_check_sha", a.reasons)

    def test_required_checks_cannot_be_empty(self):
        a = assess(["README.md"], required_checks=[])
        self.assertIn("invalid_required_checks", a.reasons)

    def test_missing_check_is_blocking(self):
        a = assess(["README.md"], checks={"Source synchronization check": "success"})
        self.assertIn("missing_or_nonpassing_check:pinned-import (3.11)", a.reasons)

    def test_skipped_check_cannot_count_as_success(self):
        checks = dict(GOOD)
        checks[REQUIRED[0]] = "skipped"
        a = assess(["README.md"], checks=checks)
        self.assertIn("missing_or_nonpassing_check:" + REQUIRED[0], a.reasons)

    def test_pending_check_cannot_count_as_success(self):
        checks = dict(GOOD)
        checks[REQUIRED[1]] = "in_progress"
        a = assess(["README.md"], checks=checks)
        self.assertIn("missing_or_nonpassing_check:" + REQUIRED[1], a.reasons)

    def test_duplicate_required_contexts_are_invalid(self):
        a = assess(["README.md"], required_checks=[REQUIRED[0], REQUIRED[0]])
        self.assertIn("invalid_required_checks", a.reasons)

    def test_infrastructure_does_not_claim_product_e2e(self):
        a = assess([".github/workflows/ci.yml"], owner_approved=True)
        self.assertEqual(a.status, "ELIGIBLE_FOR_REVIEW")
        self.assertEqual(a.risk, "infrastructure")

    def test_runtime_change_is_blocked_without_product_evidence(self):
        a = assess(["extension/popup.js"], owner_approved=True)
        self.assertIn("implementation_verification_not_supplied", a.reasons)

    def test_runtime_change_requires_all_gates(self):
        a = assess(["extension/popup.js"], owner_approved=True, product_verified=True)
        self.assertEqual(a.status, "ELIGIBLE_FOR_REVIEW")
        self.assertEqual(a.risk, "implementation")

    def test_publication_hold_even_when_other_checks_pass(self):
        a = assess(["browser_filter_lists/stable.txt"], owner_approved=True, product_verified=True)
        self.assertEqual(a.status, "BLOCKED")
        self.assertIn("publication_hold", a.reasons)

    def test_archives_never_eligible(self):
        a = assess(["release.zip"], owner_approved=True, product_verified=True)
        self.assertEqual(a.status, "BLOCKED")
        self.assertIn("prohibited_or_invalid_path", a.reasons)


if __name__ == "__main__":
    unittest.main()
