from __future__ import annotations

import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from sales_catalog import SalePrice, load_sales_catalog_csv, sale_price_mapping_for_quotes
from supplier_price_watch import PriceWatchError, SupplierQuote


class SalePriceTests(unittest.TestCase):
    def test_from_mapping_defaults_currency_and_rounds_money(self) -> None:
        price = SalePrice.from_mapping({"sku": " SKU-1 ", "sale_price": "149.995"})

        self.assertEqual(price.sku, "SKU-1")
        self.assertEqual(price.sale_price, Decimal("150.00"))
        self.assertEqual(price.currency, "TRY")

    def test_from_mapping_rejects_non_positive_sale_price(self) -> None:
        for value in ("0", "-1"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(PriceWatchError, "greater than zero"):
                    SalePrice.from_mapping({"sku": "SKU-1", "sale_price": value})

    def test_from_mapping_rejects_invalid_currency(self) -> None:
        with self.assertRaisesRegex(PriceWatchError, "3-letter code"):
            SalePrice.from_mapping(
                {"sku": "SKU-1", "sale_price": "100", "currency": "TL"}
            )


class SalesCatalogCsvTests(unittest.TestCase):
    def _write_csv(self, content: str) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / "sales.csv"
        path.write_text(content, encoding="utf-8")
        return path

    def test_loads_catalog_with_default_and_explicit_currency(self) -> None:
        path = self._write_csv(
            "sku,sale_price,currency\n"
            "SKU-1,150.00,\n"
            "SKU-2,20.50,USD\n"
        )

        prices = load_sales_catalog_csv(path)

        self.assertEqual(
            prices,
            [
                SalePrice("SKU-1", Decimal("150.00"), "TRY"),
                SalePrice("SKU-2", Decimal("20.50"), "USD"),
            ],
        )

    def test_rejects_duplicate_sku_currency_identity(self) -> None:
        path = self._write_csv(
            "sku,sale_price,currency\n"
            "SKU-1,150,TRY\n"
            "SKU-1,160,TRY\n"
        )

        with self.assertRaisesRegex(PriceWatchError, "duplicate SKU/currency"):
            load_sales_catalog_csv(path)

    def test_rejects_unsupported_columns(self) -> None:
        path = self._write_csv("sku,sale_price,discount\nSKU-1,150,10\n")

        with self.assertRaisesRegex(PriceWatchError, "unsupported columns: discount"):
            load_sales_catalog_csv(path)

    def test_rejects_missing_required_columns(self) -> None:
        path = self._write_csv("sku,currency\nSKU-1,TRY\n")

        with self.assertRaisesRegex(PriceWatchError, "missing required columns: sale_price"):
            load_sales_catalog_csv(path)


class SalePriceMappingTests(unittest.TestCase):
    @staticmethod
    def _quote(sku: str, *, currency: str = "TRY") -> SupplierQuote:
        return SupplierQuote.from_mapping(
            {
                "supplier": "Arzu",
                "sku": sku,
                "unit_cost": "100",
                "currency": currency,
            }
        )

    def test_builds_mapping_for_exact_currency_match(self) -> None:
        mapping = sale_price_mapping_for_quotes(
            [SalePrice("SKU-1", Decimal("150.00"), "TRY")],
            [self._quote("SKU-1")],
        )

        self.assertEqual(mapping, {"SKU-1": Decimal("150.00")})

    def test_missing_sale_price_is_allowed(self) -> None:
        mapping = sale_price_mapping_for_quotes([], [self._quote("SKU-1")])

        self.assertEqual(mapping, {})

    def test_rejects_currency_mismatch(self) -> None:
        with self.assertRaisesRegex(PriceWatchError, "currency mismatch"):
            sale_price_mapping_for_quotes(
                [SalePrice("SKU-1", Decimal("150.00"), "USD")],
                [self._quote("SKU-1", currency="TRY")],
            )

    def test_rejects_sale_price_for_multi_currency_supplier_sku(self) -> None:
        with self.assertRaisesRegex(PriceWatchError, "multi-currency supplier data"):
            sale_price_mapping_for_quotes(
                [SalePrice("SKU-1", Decimal("150.00"), "TRY")],
                [
                    self._quote("SKU-1", currency="TRY"),
                    self._quote("SKU-1", currency="USD"),
                ],
            )

    def test_ignores_multi_currency_sku_when_no_sale_price_is_configured(self) -> None:
        mapping = sale_price_mapping_for_quotes(
            [],
            [
                self._quote("SKU-1", currency="TRY"),
                self._quote("SKU-1", currency="USD"),
            ],
        )

        self.assertEqual(mapping, {})


if __name__ == "__main__":
    unittest.main()
