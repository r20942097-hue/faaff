from pathlib import Path
import copy
from datetime import date
import unittest

import validate_delta_policy as delta


class DeltaPolicyTests(unittest.TestCase):
    def test_repository_delta_policy_is_valid(self):
        errors, _warnings = delta.validate()
        self.assertEqual(errors, [])

    def test_recommended_delta_is_unique_and_empty_initially(self):
        manifest = delta.load_json(delta.MANIFEST_PATH)
        recommended = [entry for entry in manifest["stable_lists"] if entry.get("recommended") is True]
        self.assertEqual(len(recommended), 1)
        self.assertEqual(recommended[0]["profile"], "ubo-default-delta")
        self.assertEqual(delta.active_hosts(delta.ROOT / recommended[0]["path"]), [])

    def test_legacy_rules_are_not_delta_approved(self):
        manifest = delta.load_json(delta.MANIFEST_PATH)
        audit = delta.load_json(delta.ROOT / manifest["upstream_audit"])
        self.assertTrue(audit["legacy_rules"])
        self.assertTrue(all(item["status"] in delta.ALLOWED_LEGACY_STATUSES for item in audit["legacy_rules"]))

    def test_canary_is_not_stable(self):
        manifest = delta.load_json(delta.MANIFEST_PATH)
        canary = delta.load_json(delta.ROOT / manifest["canary_manifest"])
        recommended = next(entry for entry in manifest["stable_lists"] if entry.get("recommended") is True)
        stable_hosts = set(delta.active_hosts(delta.ROOT / recommended["path"]))
        canary_hosts = {item["domain"] for item in canary["candidates"]}
        self.assertTrue(stable_hosts.isdisjoint(canary_hosts))

    def test_current_source_inventory_matches_audit_baseline(self):
        manifest = delta.load_json(delta.MANIFEST_PATH)
        audit = delta.load_json(delta.ROOT / manifest["upstream_audit"])
        inventory = delta.load_json(delta.ROOT / manifest["snapshot_inventory"])
        self.assertEqual(delta.validate_snapshot_inventory(inventory, audit["baseline"]), [])

    def test_source_inventory_rejects_invalid_blob_sha(self):
        manifest = delta.load_json(delta.MANIFEST_PATH)
        audit = delta.load_json(delta.ROOT / manifest["upstream_audit"])
        inventory = copy.deepcopy(delta.load_json(delta.ROOT / manifest["snapshot_inventory"]))
        inventory["snapshots"][0]["files"][0]["blob_sha"] = "bad-sha"
        errors = delta.validate_snapshot_inventory(inventory, audit["baseline"])
        self.assertTrue(any("blob_sha" in error for error in errors))

    def test_source_inventory_rejects_non_object_root(self):
        self.assertEqual(
            delta.validate_snapshot_inventory([], {}),
            ["snapshot inventory: root must be an object"],
        )

    def test_source_inventory_rejects_loose_commit_timestamp(self):
        manifest = delta.load_json(delta.MANIFEST_PATH)
        audit = delta.load_json(delta.ROOT / manifest["upstream_audit"])
        inventory = copy.deepcopy(delta.load_json(delta.ROOT / manifest["snapshot_inventory"]))
        inventory["snapshots"][0]["commit_date"] = "2026-10-01garbage"
        errors = delta.validate_snapshot_inventory(inventory, audit["baseline"])
        self.assertTrue(any("commit_date" in error for error in errors))

    def test_source_inventory_rejects_boolean_size(self):
        manifest = delta.load_json(delta.MANIFEST_PATH)
        audit = delta.load_json(delta.ROOT / manifest["upstream_audit"])
        inventory = copy.deepcopy(delta.load_json(delta.ROOT / manifest["snapshot_inventory"]))
        inventory["snapshots"][0]["files"][0]["size_bytes"] = True
        errors = delta.validate_snapshot_inventory(inventory, audit["baseline"])
        self.assertTrue(any("size_bytes" in error for error in errors))

    def test_source_inventory_expires_with_upstream_audit_window(self):
        manifest = delta.load_json(delta.MANIFEST_PATH)
        audit = delta.load_json(delta.ROOT / manifest["upstream_audit"])
        inventory = delta.load_json(delta.ROOT / manifest["snapshot_inventory"])
        errors = delta.validate_snapshot_inventory(
            inventory,
            audit["baseline"],
            today=date(2026, 10, 10),
            max_age_days=manifest["upstream_audit_max_age_days"],
        )
        self.assertTrue(any("snapshot inventory: stale" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
