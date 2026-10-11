from datetime import date, timedelta
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import validate_candidate_promotion as promotion


class PromotionGateTests(unittest.TestCase):
    def validate_fixture(self, mutate):
        manifest = promotion.load_json(promotion.MANIFEST_PATH)
        queue = promotion.load_json(promotion.ROOT / manifest['candidate_queue'])
        mutate(queue)
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / 'manifest.json'
            manifest_path.write_text(json.dumps(manifest))
            queue_path = root / manifest['candidate_queue']
            queue_path.parent.mkdir(parents=True)
            queue_path.write_text(json.dumps(queue))
            with (patch.object(promotion, 'ROOT', root), patch.object(promotion, 'MANIFEST_PATH', manifest_path),
                  patch.object(promotion.evidence_validator, 'ROOT', root),
                  patch.object(promotion.evidence_validator, 'MANIFEST_PATH', manifest_path)):
                return promotion.validate(today=date.fromisoformat(queue['observed_at']))[0]

    def test_repository_promotion_state_is_valid(self):
        manifest = promotion.load_json(promotion.MANIFEST_PATH)
        queue = promotion.load_json(promotion.ROOT / manifest['candidate_queue'])
        errors, _warnings = promotion.validate(today=date.fromisoformat(queue['observed_at']))
        self.assertEqual(errors, [])

    def test_known_exception_cannot_be_candidate(self):
        def mutate(queue):
            queue['candidates'][0]['exception_review']['known_exception'] = True
        errors = self.validate_fixture(mutate)
        self.assertTrue(any('forbidden' in error for error in errors))

    def test_source_family_cannot_be_spoofed(self):
        def mutate(queue):
            queue['candidates'][0]['evidence'][1]['source_family'] = 'fake-independent-source'
        errors = self.validate_fixture(mutate)
        self.assertTrue(any('repository does not belong' in error for error in errors))

    def test_same_project_does_not_count_as_two_families(self):
        def mutate(queue):
            queue['candidates'][0]['evidence'][1] = dict(queue['candidates'][0]['evidence'][0])
        errors = self.validate_fixture(mutate)
        self.assertTrue(any('independent classification source families' in error for error in errors))

    def test_promotion_gate_also_rejects_expired_evidence(self):
        manifest = promotion.load_json(promotion.MANIFEST_PATH)
        queue = promotion.load_json(promotion.ROOT / manifest['candidate_queue'])
        observed = date.fromisoformat(queue['observed_at'])
        errors, _ = promotion.validate(today=observed + timedelta(days=manifest['candidate_evidence_max_age_days'] + 1))
        self.assertTrue(any('stale' in error for error in errors))

    def test_repository_cannot_be_registered_as_two_families(self):
        manifest = promotion.load_json(promotion.MANIFEST_PATH)
        manifest['source_family_repositories']['fake'] = ['EasyList/EasyList']
        with patch.object(promotion.evidence_validator, 'validate', return_value=([], [])), patch.object(promotion, 'load_json', return_value=manifest):
            errors, _ = promotion.validate()
        self.assertTrue(any('only one source family' in error for error in errors))

    def test_source_family_shape(self):
        for value in ["easylist", "adguard", "ublock", "source-2"]:
            with self.subTest(value=value):
                self.assertIsNotNone(promotion.SOURCE_FAMILY_RE.fullmatch(value))
        for value in ["EasyList", "bad family", "_bad", ""]:
            with self.subTest(value=value):
                self.assertIsNone(promotion.SOURCE_FAMILY_RE.fullmatch(value))


if __name__ == "__main__":
    unittest.main()
