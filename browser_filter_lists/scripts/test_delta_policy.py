from pathlib import Path
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
        self.assertTrue(canary_hosts)
        self.assertTrue(stable_hosts.isdisjoint(canary_hosts))


if __name__ == "__main__":
    unittest.main()
