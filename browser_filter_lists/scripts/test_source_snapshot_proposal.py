from copy import deepcopy
from pathlib import Path
import json
import unittest

import refresh_source_snapshot_proposal as refresh


class SnapshotProposalTests(unittest.TestCase):
    def setUp(self):
        self.inventory = refresh.json.loads(refresh.DEFAULT_INVENTORY.read_text(encoding="utf-8"))
        self.calls = []

    def fake_api(self, url, token=None):
        self.calls.append(url)
        if "/commits?" in url:
            repository = url.split("/repos/", 1)[1].split("/commits?", 1)[0]
            sha = {
                "easylist/easylist": "a" * 40,
                "uBlockOrigin/uAssets": "b" * 40,
                "AdguardTeam/AdguardFilters": "c" * 40,
            }[repository]
            return [{"sha": sha, "commit": {"committer": {"date": "2026-10-02T00:00:00Z"}}}]
        if "/contents/" in url:
            return {"type": "file", "sha": "d" * 40, "size": 123}
        raise AssertionError(f"Unexpected API URL: {url}")

    def test_proposal_refreshes_verified_sources_without_mutating_inventory(self):
        original = deepcopy(self.inventory)
        proposal = refresh.build_proposal(
            self.inventory,
            generated_at="2026-10-02T00:00:00Z",
            fetch_json=self.fake_api,
        )
        self.assertEqual(self.inventory, original)
        self.assertTrue(proposal["manual_review_required"])
        self.assertFalse(proposal["active_rules_changed"])
        self.assertEqual(proposal["inventory_proposal"]["retrieved_at"], "2026-10-02")
        by_family = {item["source_family"]: item for item in proposal["inventory_proposal"]["snapshots"]}
        self.assertEqual(by_family["easylist"]["commit"], "a" * 40)
        self.assertEqual(by_family["adguard"]["files"][0]["blob_sha"], "d" * 40)
        self.assertEqual(by_family["peter_lowe"]["mirror"]["commit"], "b" * 40)
        self.assertEqual(by_family["easylist_japan"]["status"], "stale_excluded")
        self.assertEqual(len([call for call in self.calls if "/commits?" in call]), 3)

    def test_file_paths_are_encoded_and_pinned_to_commit(self):
        result = refresh.fetch_blob_metadata(
            "example/repo", "a" * 40, "folder/file name.txt", fetch_json=self.fake_api
        )
        self.assertEqual(result["size_bytes"], 123)
        self.assertIn("folder/file%20name.txt", self.calls[-1])
        self.assertIn("ref=" + "a" * 40, self.calls[-1])

    def test_invalid_or_empty_upstream_file_fails_closed(self):
        def empty_file(url, token=None):
            if "/commits?" in url:
                return [{"sha": "a" * 40, "commit": {"committer": {"date": "2026-10-02T00:00:00Z"}}}]
            return {"type": "file", "sha": "d" * 40, "size": 0}

        with self.assertRaises(refresh.GitHubApiError):
            refresh.fetch_blob_metadata("example/repo", "a" * 40, "list.txt", fetch_json=empty_file)

    def test_invalid_inventory_is_rejected_before_network_access(self):
        with self.assertRaises(ValueError):
            refresh.build_proposal([], fetch_json=self.fake_api)
        self.assertEqual(self.calls, [])

    def test_proposal_contains_base_inventory_digest(self):
        proposal = refresh.build_proposal(
            self.inventory,
            generated_at="2026-10-02T00:00:00Z",
            fetch_json=self.fake_api,
        )
        self.assertEqual(len(proposal["base_inventory_sha256"]), 64)
        self.assertEqual(proposal["schema"], "browser-filter-snapshot-proposal/v1")


if __name__ == "__main__":
    unittest.main()
