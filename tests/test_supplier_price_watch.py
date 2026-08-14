from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from supplier_price_watch import (
    PriceWatchError,
    RiskLevel,
    SupplierQuote,
    compare_catalogs,
    compare_quote,
    load_quotes_csv,
)


class SupplierQuoteTests(unittest.TestCase):
    def test_from_mapping_normalizes_currency_and_money(self):
        quote = SupplierQuote.from_mapping(
            {
                "supplier": "  Arzu Bisiklet  ",
                "sku": " SKU-001 ",
                "unit_cost": "123.455",
                "currency": "try",
            }
        )

        self.assertEqual(quote.supplier, "Arzu Bisiklet")
        self.assertEqual(quote.sku, "SKU-001")
        self.assertEqual(quote.unit_cost, Decimal("123.46"))
        self.assertEqual(quote.currency, "TRY")

    def test_negative_cost_is_rejected(self):
        with self.assertRaisesRegex(PriceWatchError, "cannot be negative"):
            SupplierQuote.from_mapping(
                {"supplier": "S", "sku": "A", "unit_cost": "-1"}
            )

    def test_invalid_currency_is_rejected(self):
        with self.assertRaisesRegex(PriceWatchError, "3-letter code"):
            SupplierQuote.from_mapping(
                {
                    "supplier": "S",
                    "sku": "A",
                    "unit_cost": "10",
                    "currency": "TL",
                }
            )


class CsvLoaderTests(unittest.TestCase):
    def write_csv(self, content: str) -> Path:
        temp_dir = TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / "quotes.csv"
        path.write_text(content, encoding="utf-8")
        return path

    def test_loads_valid_rows_and_defaults_currency(self):
        path = self.write_csv(
            "supplier,sku,unit_cost,currency\n"
            "Arzu,SKU-1,100.125,try\n"
            "MSR,SKU-2,55.5,\n"
        )

        quotes = load_quotes_csv(path)

        self.assertEqual(len(quotes), 2)
        self.assertEqual(quotes[0].unit_cost, Decimal("100.13"))
        self.assertEqual(quotes[0].currency, "TRY")
        self.assertEqual(quotes[1].currency, "TRY")

    def test_supplier_specific_headers_can_be_mapped_explicitly(self):
        path = self.write_csv(
            "Tedarikci,Urun Kodu,Alis Fiyati,Para Birimi\n"
            "Arzu,8690001,123.45,try\n"
        )

        quotes = load_quotes_csv(
            path,
            column_map={
                "Tedarikci": "supplier",
                "Urun Kodu": "sku",
                "Alis Fiyati": "unit_cost",
                "Para Birimi": "currency",
            },
        )

        self.assertEqual(len(quotes), 1)
        self.assertEqual(quotes[0].supplier, "Arzu")
        self.assertEqual(quotes[0].sku, "8690001")
        self.assertEqual(quotes[0].unit_cost, Decimal("123.45"))
        self.assertEqual(quotes[0].currency, "TRY")

    def test_column_map_missing_source_is_rejected(self):
        path = self.write_csv("Tedarikci,Urun Kodu,Fiyat\nArzu,SKU-1,100\n")

        with self.assertRaisesRegex(PriceWatchError, "references missing columns: Doviz"):
            load_quotes_csv(
                path,
                column_map={
                    "Tedarikci": "supplier",
                    "Urun Kodu": "sku",
                    "Fiyat": "unit_cost",
                    "Doviz": "currency",
                },
            )

    def test_column_map_cannot_create_duplicate_canonical_columns(self):
        path = self.write_csv(
            "supplier,Tedarikci,sku,unit_cost\nArzu,Arzu,SKU-1,100\n"
        )

        with self.assertRaisesRegex(PriceWatchError, "duplicate canonical columns"):
            load_quotes_csv(path, column_map={"Tedarikci": "supplier"})

    def test_column_map_target_must_be_supported(self):
        path = self.write_csv("supplier,sku,unit_cost\nArzu,SKU-1,100\n")

        with self.assertRaisesRegex(PriceWatchError, "target is not supported"):
            load_quotes_csv(path, column_map={"supplier": "vendor"})

    def test_missing_required_column_is_rejected(self):
        path = self.write_csv("supplier,sku,currency\nArzu,SKU-1,TRY\n")

        with self.assertRaisesRegex(PriceWatchError, "unit_cost"):
            load_quotes_csv(path)

    def test_invalid_row_reports_line_number(self):
        path = self.write_csv(
            "supplier,sku,unit_cost,currency\nArzu,SKU-1,not-a-number,TRY\n"
        )

        with self.assertRaisesRegex(PriceWatchError, r"CSV row 2: unit_cost"):
            load_quotes_csv(path)

    def test_duplicate_identity_is_rejected(self):
        path = self.write_csv(
            "supplier,sku,unit_cost,currency\n"
            "Arzu,SKU-1,100,TRY\n"
            "Arzu,SKU-1,110,TRY\n"
        )

        with self.assertRaisesRegex(PriceWatchError, "duplicate supplier/SKU/currency"):
            load_quotes_csv(path)

    def test_extra_values_are_rejected(self):
        path = self.write_csv(
            "supplier,sku,unit_cost,currency\nArzu,SKU-1,100,TRY,unexpected\n"
        )

        with self.assertRaisesRegex(PriceWatchError, "more values than headers"):
            load_quotes_csv(path)


class PriceComparisonTests(unittest.TestCase):
    def quote(self, cost: str, *, sku: str = "SKU-1", currency: str = "TRY"):
        return SupplierQuote.from_mapping(
            {
                "supplier": "Supplier A",
                "sku": sku,
                "unit_cost": cost,
                "currency": currency,
            }
        )

    def test_price_change_and_rounding_use_decimal_math(self):
        result = compare_quote(self.quote("100.00"), self.quote("112.345"))

        self.assertEqual(result.current_cost, Decimal("112.35"))
        self.assertEqual(result.absolute_change, Decimal("12.35"))
        self.assertEqual(result.percent_change, Decimal("12.35"))

    def test_zero_previous_cost_has_no_percent_change(self):
        result = compare_quote(self.quote("0"), self.quote("25"))

        self.assertIsNone(result.percent_change)
        self.assertEqual(result.absolute_change, Decimal("25.00"))

    def test_currency_mismatch_fails_closed(self):
        with self.assertRaisesRegex(PriceWatchError, "currency mismatch"):
            compare_quote(self.quote("100", currency="TRY"), self.quote("100", currency="USD"))

    def test_critical_margin_boundary_is_inclusive(self):
        result = compare_quote(
            self.quote("80"),
            self.quote("90"),
            sale_price="100",
            warning_margin_percent="20",
            critical_margin_percent="10",
        )

        self.assertEqual(result.gross_margin_percent, Decimal("10.00"))
        self.assertEqual(result.risk, RiskLevel.CRITICAL)

    def test_warning_margin_boundary_is_inclusive(self):
        result = compare_quote(
            self.quote("70"),
            self.quote("80"),
            sale_price="100",
            warning_margin_percent="20",
            critical_margin_percent="10",
        )

        self.assertEqual(result.gross_margin_percent, Decimal("20.00"))
        self.assertEqual(result.risk, RiskLevel.WARNING)

    def test_invalid_threshold_order_is_rejected(self):
        with self.assertRaisesRegex(PriceWatchError, "cannot exceed warning"):
            compare_quote(
                self.quote("70"),
                self.quote("80"),
                sale_price="100",
                warning_margin_percent="10",
                critical_margin_percent="20",
            )

    def test_zero_sale_price_is_rejected(self):
        with self.assertRaisesRegex(PriceWatchError, "greater than zero"):
            compare_quote(self.quote("70"), self.quote("80"), sale_price="0")


class CatalogComparisonTests(unittest.TestCase):
    def test_catalog_comparison_matches_exact_supplier_sku_currency_only(self):
        previous = [
            SupplierQuote.from_mapping(
                {"supplier": "A", "sku": "MATCH", "unit_cost": "100", "currency": "TRY"}
            ),
            SupplierQuote.from_mapping(
                {"supplier": "A", "sku": "OLD", "unit_cost": "50", "currency": "TRY"}
            ),
        ]
        current = [
            SupplierQuote.from_mapping(
                {"supplier": "A", "sku": "MATCH", "unit_cost": "110", "currency": "TRY"}
            ),
            SupplierQuote.from_mapping(
                {"supplier": "A", "sku": "NEW", "unit_cost": "55", "currency": "TRY"}
            ),
        ]

        results = compare_catalogs(previous, current, sale_prices={"MATCH": "150"})

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].sku, "MATCH")
        self.assertEqual(results[0].gross_margin_percent, Decimal("26.67"))
        self.assertEqual(results[0].risk, RiskLevel.OK)


if __name__ == "__main__":
    unittest.main()
