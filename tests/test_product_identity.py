from decimal import Decimal
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from product_identity import (
    ProductIdentityAlias,
    ProductIdentityRegistry,
    load_identity_registry_json,
)
from supplier_price_watch import PriceWatchError, SupplierQuote


class ProductIdentityTests(unittest.TestCase):
    def test_resolves_supplier_alias_and_gtin(self) -> None:
        registry = ProductIdentityRegistry(
            [
                ProductIdentityAlias(
                    supplier="Supplier A",
                    source_sku="SUP-42",
                    canonical_sku="TYRE-42",
                    barcode="4006381333931",
                )
            ]
        )
        self.assertEqual(registry.resolve_supplier_sku("Supplier A", "SUP-42"), "TYRE-42")
        self.assertEqual(registry.resolve_barcode("4006381333931"), "TYRE-42")
        self.assertIsNone(registry.resolve_supplier_sku("Supplier B", "SUP-42"))

    def test_invalid_gtin_check_digit_is_rejected(self) -> None:
        with self.assertRaisesRegex(PriceWatchError, "check digit"):
            ProductIdentityAlias(
                supplier="Supplier A",
                source_sku="SUP-42",
                canonical_sku="TYRE-42",
                barcode="4006381333932",
            )

    def test_conflicting_barcode_mapping_is_rejected(self) -> None:
        registry = ProductIdentityRegistry(
            [
                ProductIdentityAlias(
                    "Supplier A", "A-1", "CANON-1", "4006381333931"
                )
            ]
        )
        with self.assertRaisesRegex(PriceWatchError, "multiple canonical SKUs"):
            registry.register(
                ProductIdentityAlias(
                    "Supplier B", "B-1", "CANON-2", "4006381333931"
                )
            )

    def test_canonicalize_quotes_preserves_financial_fields(self) -> None:
        registry = ProductIdentityRegistry(
            [ProductIdentityAlias("Supplier A", "SUP-42", "TYRE-42")]
        )
        quote = SupplierQuote("Supplier A", "SUP-42", Decimal("123.45"), "TRY")
        canonical = registry.canonicalize_quote(quote)
        self.assertEqual(canonical.sku, "TYRE-42")
        self.assertEqual(canonical.unit_cost, Decimal("123.45"))
        self.assertEqual(canonical.currency, "TRY")

    def test_alias_collision_after_canonicalization_fails_closed(self) -> None:
        registry = ProductIdentityRegistry(
            [ProductIdentityAlias("Supplier A", "SUP-42", "TYRE-42")]
        )
        quotes = [
            SupplierQuote("Supplier A", "SUP-42", Decimal("100.00"), "TRY"),
            SupplierQuote("Supplier A", "TYRE-42", Decimal("101.00"), "TRY"),
        ]
        with self.assertRaisesRegex(PriceWatchError, "duplicate supplier/SKU/currency"):
            registry.canonicalize_quotes(quotes)

    def test_json_loader_rejects_unknown_fields_and_duplicate_keys(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            unknown = root / "unknown.json"
            unknown.write_text(
                json.dumps(
                    [
                        {
                            "supplier": "Supplier A",
                            "source_sku": "SUP-42",
                            "canonical_sku": "TYRE-42",
                            "guess": True,
                        }
                    ]
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(PriceWatchError, "unknown fields"):
                load_identity_registry_json(unknown)

            duplicate = root / "duplicate.json"
            duplicate.write_text(
                '[{"supplier":"A","supplier":"B","source_sku":"S","canonical_sku":"C"}]',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(PriceWatchError, "duplicate JSON key"):
                load_identity_registry_json(duplicate)


if __name__ == "__main__":
    unittest.main()
