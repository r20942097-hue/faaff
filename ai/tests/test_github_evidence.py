"""Offline adversarial tests for live GitHub check/ruleset evidence."""
from __future__ import annotations

from copy import deepcopy
import unittest
from unittest.mock import patch

from ai.github_evidence import review_evidence
from ai.inspect_pr import CollectionError, collect_pages, inspect

HEAD = "a" * 40
BASE = "b" * 40
REPO = "r20942097-hue/faaff"
CONTEXTS = ("validate", "pinned-import (3.11)")


def fixture():
    pr = {
        "state": "open", "draft": False, "merged": False, "mergeable": True,
        "head": {"sha": HEAD},
        "base": {"sha": BASE, "ref": "main", "repo": {"full_name": REPO}},
        "changed_files": 1,
    }
    ruleset = {
        "id": 26005483, "target": "branch", "enforcement": "active",
        "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
        "rules": [{"type": "required_status_checks", "parameters": {
            "required_status_checks": [
                {"context": name, "integration_id": 15368} for name in CONTEXTS
            ]
        }}],
    }
    checks = [
        {
            "name": name, "head_sha": HEAD, "status": "completed",
            "conclusion": "success", "app": {"id": 15368},
        }
        for name in CONTEXTS
    ]
    return pr, ruleset, {"total_count": len(checks), "check_runs": checks}


def assess(*, files=None, alter=None):
    pr, rules, checks = fixture()
    if alter is not None:
        alter(pr, rules, checks)
    return review_evidence(
        repository=REPO, pull=pr,
        paths=["ai/HANDOFF.md"] if files is None else files,
        ruleset=rules, check_runs=checks,
    )


class EvidenceContractTests(unittest.TestCase):
    def test_successful_evidence_is_not_merge_permission(self):
        r = assess()
        self.assertEqual(r["status"], "AWAITING_OWNER_APPROVAL")
        self.assertEqual(r["risk"], "documentation")
        self.assertEqual(r["required_checks"], list(CONTEXTS))

    def test_publication_hold_wins_even_with_green_checks(self):
        r = assess(files=["browser_filter_lists/stable.txt"])
        self.assertEqual(r["status"], "BLOCKED")
        self.assertIn("publication_hold", r["reasons"])

    def test_wrong_publisher_is_blocked(self):
        r = assess(alter=lambda p, s, c: c["check_runs"][0]["app"].update(id=999))
        self.assertIn("check_publisher_mismatch:validate", r["reasons"])

    def test_wrong_head_is_blocked(self):
        r = assess(alter=lambda p, s, c: c["check_runs"][0].update(head_sha=BASE))
        self.assertIn("check_head_mismatch:validate", r["reasons"])

    def test_duplicate_context_is_ambiguous(self):
        def alter(p, s, c):
            c["check_runs"].append(deepcopy(c["check_runs"][0]))
            c["total_count"] += 1
        r = assess(alter=alter)
        self.assertIn("missing_or_ambiguous_check:validate", r["reasons"])

    def test_missing_context_is_blocked(self):
        def alter(p, s, c):
            c["check_runs"].pop()
            c["total_count"] -= 1
        r = assess(alter=alter)
        self.assertIn("missing_or_ambiguous_check:pinned-import (3.11)", r["reasons"])

    def test_skipped_check_is_not_success(self):
        r = assess(alter=lambda p, s, c: c["check_runs"][0].update(conclusion="skipped"))
        self.assertEqual(r["status"], "BLOCKED")
        self.assertIn("missing_or_nonpassing_check:validate", r["reasons"])

    def test_pending_check_is_not_success(self):
        r = assess(alter=lambda p, s, c: c["check_runs"][0].update(status="in_progress"))
        self.assertIn("missing_or_nonpassing_check:validate", r["reasons"])

    def test_partial_check_collection_is_blocked(self):
        r = assess(alter=lambda p, s, c: c.update(total_count=3))
        self.assertIn("incomplete_check_runs_collection", r["reasons"])

    def test_rule_on_different_branch_is_blocked(self):
        r = assess(alter=lambda p, s, c: s["conditions"]["ref_name"].update(include=["refs/heads/develop"]))
        self.assertIn("unverified_ruleset_scope", r["reasons"])

    def test_ruleset_excludes_are_not_assumed_safe(self):
        r = assess(alter=lambda p, s, c: s["conditions"]["ref_name"].update(exclude=["refs/heads/*"]))
        self.assertIn("unverified_ruleset_scope", r["reasons"])

    def test_base_not_main_is_blocked(self):
        r = assess(alter=lambda p, s, c: p["base"].update(ref="develop"))
        self.assertIn("unexpected_base_branch", r["reasons"])

    def test_draft_pr_is_blocked(self):
        r = assess(alter=lambda p, s, c: p.update(draft=True))
        self.assertIn("not_open_ready_pr", r["reasons"])

    def test_merge_conflicts_are_blocked(self):
        r = assess(alter=lambda p, s, c: p.update(mergeable=False))
        self.assertIn("not_confirmed_mergeable", r["reasons"])

    def test_wrong_repo_is_blocked(self):
        r = review_evidence(repository="unrelated/repo", pull=fixture()[0],
                            paths=["README.md"], ruleset=fixture()[1], check_runs=fixture()[2])
        self.assertIn("repository_mismatch", r["reasons"])

    def test_missing_required_checks_is_blocked(self):
        r = assess(alter=lambda p, s, c: s["rules"][0]["parameters"].update(required_status_checks=[]))
        self.assertIn("no_required_checks_in_ruleset", r["reasons"])

    def test_untrusted_json_shape_is_blocked(self):
        r = review_evidence(repository=REPO, pull=[], paths=[], ruleset={}, check_runs={})
        self.assertEqual(r["status"], "BLOCKED")


class CollectionTests(unittest.TestCase):
    def test_readonly_live_fixture(self):
        pr, rules, checks = fixture()
        file_records = [{"filename": "ai/HANDOFF.md", "status": "modified"}]

        def transport(url):
            if "/check-runs" in url:
                return checks
            if "/rules/branches/main?" in url:
                return [{"type": "required_status_checks", "ruleset_id": 26005483}]
            if url.endswith("/rulesets/26005483"):
                return rules
            if "/files?" in url:
                return file_records
            if url.endswith("/pulls/44"):
                return pr
            raise AssertionError("unexpected URL: " + url)

        with patch("ai.inspect_pr.get_json", side_effect=transport):
            r = inspect(REPO, 44, 26005483)
        self.assertEqual(r["status"], "AWAITING_OWNER_APPROVAL")

    def test_renamed_publication_path_is_never_downgraded(self):
        pr, rules, checks = fixture()
        row = [{"filename": "README.md", "previous_filename": "browser_filter_lists/stable.txt", "status": "renamed"}]

        def transport(url):
            if "/check-runs" in url:
                return checks
            if "/rules/branches/main?" in url:
                return [{"type": "required_status_checks", "ruleset_id": 26005483}]
            if url.endswith("/rulesets/26005483"):
                return rules
            if "/files?" in url:
                return row
            if url.endswith("/pulls/44"):
                return pr
            raise AssertionError(url)

        with patch("ai.inspect_pr.get_json", side_effect=transport):
            r = inspect(REPO, 44, 26005483)
        self.assertEqual(r["status"], "BLOCKED")
        self.assertIn("publication_hold", r["reasons"])

    def test_head_change_during_audit_is_blocked(self):
        pr, rules, checks = fixture()
        other = deepcopy(pr)
        other["head"]["sha"] = BASE
        calls = 0

        def transport(url):
            nonlocal calls
            if "/check-runs" in url:
                return checks
            if "/rules/branches/main?" in url:
                return [{"type": "required_status_checks", "ruleset_id": 26005483}]
            if url.endswith("/rulesets/26005483"):
                return rules
            if "/files?" in url:
                return [{"filename": "README.md", "status": "modified"}]
            if url.endswith("/pulls/44"):
                calls += 1
                return pr if calls == 1 else other
            raise AssertionError(url)

        with patch("ai.inspect_pr.get_json", side_effect=transport):
            with self.assertRaisesRegex(CollectionError, "changed during audit"):
                inspect(REPO, 44, 26005483)

    def test_incomplete_paginated_file_list_is_detected(self):
        with patch("ai.inspect_pr.get_json", return_value=[{"filename": "a"}] * 100):
            with self.assertRaisesRegex(CollectionError, "pagination limit"):
                collect_pages("/repo/files", key="files", max_pages=2)

    def test_changed_collection_count_is_rejected(self):
        def response(url):
            return {"total_count": 3, "check_runs": [{"name": "a"}]} if url.endswith("&page=1") else {"total_count": 3, "check_runs": []}
        with patch("ai.inspect_pr.get_json", side_effect=response):
            with self.assertRaisesRegex(CollectionError, "incomplete collection"):
                collect_pages("/check-runs", key="check_runs", max_pages=2)

    def test_additional_effective_ruleset_blocks_eligibility(self):
        pr, rules, checks = fixture()

        def transport(url):
            if "/rules/branches/main?" in url:
                return [{"type": "required_status_checks", "ruleset_id": 26005483},
                        {"type": "pull_request", "ruleset_id": 12345}]
            if "/check-runs" in url:
                return checks
            if url.endswith("/rulesets/26005483"):
                return rules
            if "/files?" in url:
                return [{"filename": "README.md", "status": "modified"}]
            if url.endswith("/pulls/44"):
                return pr
            raise AssertionError(url)

        with patch("ai.inspect_pr.get_json", side_effect=transport):
            with self.assertRaisesRegex(CollectionError, "other applicable"):
                inspect(REPO, 44, 26005483)

    def test_missing_effective_rules_are_blocked(self):
        pr, rules, checks = fixture()

        def transport(url):
            if "/rules/branches/main?" in url:
                return []
            if "/files?" in url:
                return [{"filename": "README.md", "status": "modified"}]
            if url.endswith("/pulls/44"):
                return pr
            raise AssertionError(url)

        with patch("ai.inspect_pr.get_json", side_effect=transport):
            with self.assertRaisesRegex(CollectionError, "effective branch rule collection is empty"):
                inspect(REPO, 44, 26005483)

    def test_invalid_repository_is_rejected_before_network(self):
        with self.assertRaisesRegex(CollectionError, "invalid repository"):
            inspect("owner/repo/extra", 44, 26005483)


if __name__ == "__main__":
    unittest.main()
