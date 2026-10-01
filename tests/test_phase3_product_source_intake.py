from __future__ import annotations

import unittest

from phase3_security.product_source_intake import validate_registry


def base_product() -> dict:
    return {
        "product_id": "demo-product",
        "product_name": "Demo Product",
        "version": "1.0",
        "source_status": "MISSING",
        "immutable_source": None,
        "sha256": None,
        "size": None,
    }


class ProductSourceIntakeTests(unittest.TestCase):
    def test_missing_is_valid_but_not_ready(self) -> None:
        report = validate_registry({"schema_version": 1, "baseline": [base_product()]})
        self.assertFalse(report["summary"]["ready_for_complete_dependency_scan"])
        self.assertEqual(report["summary"]["vulnerability_posture"], "UNKNOWN")

    def test_missing_cannot_carry_fabricated_digest(self) -> None:
        product = base_product()
        product["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "must not carry invented evidence"):
            validate_registry({"schema_version": 1, "baseline": [product]})

    def test_verified_requires_complete_immutable_identity(self) -> None:
        product = base_product()
        product["source_status"] = "VERIFIED"
        with self.assertRaisesRegex(ValueError, "missing immutable_source"):
            validate_registry({"schema_version": 1, "baseline": [product]})

    def test_all_verified_is_ready_but_not_scanned(self) -> None:
        product = base_product()
        product.update(
            {
                "source_status": "VERIFIED",
                "immutable_source": "inputs/demo-source.zip",
                "sha256": "a" * 64,
                "size": 123,
            }
        )
        report = validate_registry({"schema_version": 1, "baseline": [product]})
        self.assertTrue(report["summary"]["ready_for_complete_dependency_scan"])
        self.assertEqual(report["summary"]["vulnerability_posture"], "NOT_RUN")

    def test_duplicate_product_id_rejected(self) -> None:
        product = base_product()
        with self.assertRaisesRegex(ValueError, "duplicate product_id"):
            validate_registry({"schema_version": 1, "baseline": [product, dict(product)]})

    def test_unsafe_source_reference_rejected(self) -> None:
        product = base_product()
        product.update(
            {
                "source_status": "VERIFIED",
                "immutable_source": "../escape.zip",
                "sha256": "a" * 64,
                "size": 123,
            }
        )
        with self.assertRaisesRegex(ValueError, "unsafe immutable source reference"):
            validate_registry({"schema_version": 1, "baseline": [product]})


if __name__ == "__main__":
    unittest.main()
