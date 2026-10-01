from datetime import date
import unittest

import validate_candidate_promotion as promotion


class PromotionGateTests(unittest.TestCase):
    def test_repository_promotion_state_is_valid(self):
        errors, _warnings = promotion.validate(today=date(2026, 10, 1))
        self.assertEqual(errors, [])

    def test_source_family_shape(self):
        for value in ["easylist", "adguard", "ublock", "source-2"]:
            with self.subTest(value=value):
                self.assertIsNotNone(promotion.SOURCE_FAMILY_RE.fullmatch(value))
        for value in ["EasyList", "bad family", "_bad", ""]:
            with self.subTest(value=value):
                self.assertIsNone(promotion.SOURCE_FAMILY_RE.fullmatch(value))


if __name__ == "__main__":
    unittest.main()
