from datetime import date
from copy import deepcopy
import unittest

import validate_candidate_evidence as ev


class EvidenceValidatorTests(unittest.TestCase):
    def test_repository_evidence_is_valid(self):
        errors, _warnings = ev.validate(today=date(2026, 10, 1))
        self.assertEqual(errors, [])

    def test_parse_iso_date(self):
        self.assertEqual(ev.parse_iso_date("2026-10-01"), date(2026, 10, 1))
        self.assertIsNone(ev.parse_iso_date("2026-1-1"))
        self.assertIsNone(ev.parse_iso_date("not-a-date"))
        self.assertIsNone(ev.parse_iso_date(None))

    def test_freshness_boundary(self):
        today = date(2026, 11, 15)
        self.assertFalse(ev.evidence_is_stale(date(2026, 10, 1), today, 45))
        self.assertTrue(ev.evidence_is_stale(date(2026, 9, 30), today, 45))

    def test_immutable_snapshot_shape(self):
        url = (
            "https://github.com/easylist/easylist/blob/"
            "de1806065e53df5732bd048688a9b2800fa69a73/"
            "easyprivacy/easyprivacy_trackingservers_general.txt"
        )
        match = ev.GITHUB_FILE_SNAPSHOT_RE.fullmatch(url)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(3), "de1806065e53df5732bd048688a9b2800fa69a73")

    def test_mutable_branch_url_is_not_snapshot(self):
        url = (
            "https://github.com/easylist/easylist/blob/master/"
            "easyprivacy/easyprivacy_trackingservers_general.txt"
        )
        self.assertIsNone(ev.GITHUB_FILE_SNAPSHOT_RE.fullmatch(url))

    def test_candidate_source_pins_match_inventory(self):
        queue = ev.load_json(ev.ROOT / "experimental/candidates.json")
        inventory = ev.load_json(ev.ROOT / "upstream/current-source-snapshot-inventory.json")
        self.assertEqual(ev.validate_inventory_pins(queue, inventory), [])

    def test_candidate_source_pin_drift_is_rejected(self):
        queue = deepcopy(ev.load_json(ev.ROOT / "experimental/candidates.json"))
        inventory = ev.load_json(ev.ROOT / "upstream/current-source-snapshot-inventory.json")
        queue["candidates"][0]["evidence"][0]["commit"] = "4f3f9cb97f86ee67db3c7cf33e8d786c822f5804"
        errors = ev.validate_inventory_pins(queue, inventory)
        self.assertTrue(any("commit does not match" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
